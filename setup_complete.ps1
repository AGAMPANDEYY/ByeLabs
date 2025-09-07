# HiLabs Roster Processing - Complete Setup Script (PowerShell)
# This script sets up the entire system including model download, Docker build, and frontend

param(
    [switch]$SkipModelDownload,
    [switch]$SkipDockerBuild,
    [switch]$SkipFrontend
)

# Function to print colored output
function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Blue
}

function Write-Success {
    param([string]$Message)
    Write-Host "[SUCCESS] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARNING] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Function to check if command exists
function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

# Function to check if port is in use
function Test-Port {
    param([int]$Port)
    try {
        $connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        return $connection -ne $null
    }
    catch {
        return $false
    }
}

# Function to wait for service to be ready
function Wait-ForService {
    param(
        [string]$Url,
        [string]$ServiceName,
        [int]$MaxAttempts = 30
    )
    
    Write-Status "Waiting for $ServiceName to be ready..."
    
    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            $response = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -ErrorAction SilentlyContinue
            if ($response.StatusCode -eq 200) {
                Write-Success "$ServiceName is ready!"
                return $true
            }
        }
        catch {
            # Service not ready yet
        }
        
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }
    
    Write-Error "$ServiceName failed to start within expected time"
    return $false
}

# Main setup function
function Main {
    Write-Status "Starting HiLabs Roster Processing Setup..."
    Write-Host "=================================================="
    
    # Check prerequisites
    Write-Status "Checking prerequisites..."
    
    # Check if Docker is installed
    if (-not (Test-Command "docker")) {
        Write-Error "Docker is not installed. Please install Docker Desktop first."
        exit 1
    }
    
    # Check if Docker Compose is installed
    if (-not (Test-Command "docker-compose")) {
        Write-Error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    }
    
    # Check if Node.js is installed
    if (-not (Test-Command "node")) {
        Write-Error "Node.js is not installed. Please install Node.js first."
        exit 1
    }
    
    # Check if npm is installed
    if (-not (Test-Command "npm")) {
        Write-Error "npm is not installed. Please install npm first."
        exit 1
    }
    
    # Check if Python is installed
    if (-not (Test-Command "python")) {
        Write-Error "Python is not installed. Please install Python first."
        exit 1
    }
    
    Write-Success "All prerequisites are installed!"
    
    # Step 1: Install HuggingFace CLI (if not in Docker)
    Write-Status "Installing HuggingFace CLI..."
    if (-not (Test-Command "huggingface-cli")) {
        pip install huggingface_hub[cli]
        Write-Success "HuggingFace CLI installed!"
    } else {
        Write-Success "HuggingFace CLI already installed!"
    }
    
    # Step 2: Create models directory and download model
    if (-not $SkipModelDownload) {
        Write-Status "Setting up model directory..."
        
        if (-not (Test-Path "models")) {
            New-Item -ItemType Directory -Path "models" -Force | Out-Null
            Write-Success "Created models directory"
        } else {
            Write-Success "Models directory already exists"
        }
        
        # Check if model already exists
        if (Test-Path "models\adapter.gguf") {
            Write-Warning "Model already exists, skipping download"
        } else {
            Write-Status "Downloading trained model from HuggingFace..."
            Write-Status "This may take several minutes depending on your internet connection..."
            
            # Download the model
            huggingface-cli download P3g4su5/ByeLabs-LoRA adapter.gguf --local-dir ./models
            
            if (Test-Path "models\adapter.gguf") {
                Write-Success "Model downloaded successfully!"
            } else {
                Write-Error "Model download failed!"
                exit 1
            }
        }
    }
    
    # Step 3: Check if ports are available
    Write-Status "Checking if required ports are available..."
    
    $ports = @(8000, 3000, 5432, 9000, 5672, 1025, 9090, 5555)
    foreach ($port in $ports) {
        if (Test-Port $port) {
            Write-Warning "Port $port is already in use. You may need to stop the service using this port."
        }
    }
    
    # Step 4: Build Docker containers
    if (-not $SkipDockerBuild) {
        Write-Status "Building Docker containers..."
        
        # Stop any existing containers
        Write-Status "Stopping any existing containers..."
        docker-compose down -v 2>$null
        
        # Build the containers
        Write-Status "Building Docker images (this may take several minutes)..."
        docker-compose build --no-cache
        
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Docker containers built successfully!"
        } else {
            Write-Error "Docker build failed!"
            exit 1
        }
    }
    
    # Step 5: Start backend services
    Write-Status "Starting backend services..."
    
    # Start database first
    Write-Status "Starting PostgreSQL database..."
    docker-compose up -d db
    
    # Wait for database to be ready
    Start-Sleep -Seconds 10
    
    # Start all other services
    Write-Status "Starting all backend services..."
    docker-compose up -d
    
    # Wait for services to be ready
    Write-Status "Waiting for backend services to be ready..."
    
    # Wait for API to be ready
    Wait-ForService "http://localhost:8000/health" "API Server"
    
    # Wait for MinIO to be ready
    Wait-ForService "http://localhost:9001" "MinIO"
    
    # Wait for Mailpit to be ready
    Wait-ForService "http://localhost:8025" "Mailpit"
    
    Write-Success "Backend services are running!"
    
    # Step 6: Install frontend dependencies
    if (-not $SkipFrontend) {
        Write-Status "Installing frontend dependencies..."
        
        Set-Location web
        
        if (-not (Test-Path "node_modules")) {
            Write-Status "Installing npm packages (this may take a few minutes)..."
            npm install
            
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Frontend dependencies installed!"
            } else {
                Write-Error "Frontend dependency installation failed!"
                exit 1
            }
        } else {
            Write-Success "Frontend dependencies already installed!"
        }
        
        # Step 7: Start frontend development server
        Write-Status "Starting frontend development server..."
        
        # Start frontend in background
        $frontendJob = Start-Job -ScriptBlock {
            Set-Location $using:PWD
            npm run dev
        }
        
        # Wait for frontend to be ready
        Wait-ForService "http://localhost:3000" "Frontend Server"
        
        Write-Success "Frontend server is running!"
        
        # Go back to root directory
        Set-Location ..
    }
    
    # Step 8: Display final information
    Write-Host ""
    Write-Host "=================================================="
    Write-Success "HiLabs Roster Processing Setup Complete!"
    Write-Host "=================================================="
    Write-Host ""
    Write-Status "Services are now running:"
    Write-Host "  🌐 Frontend:        http://localhost:3000"
    Write-Host "  🔧 API Server:      http://localhost:8000"
    Write-Host "  📊 API Docs:        http://localhost:8000/docs"
    Write-Host "  📧 Mailpit:         http://localhost:8025"
    Write-Host "  💾 MinIO Console:   http://localhost:9001"
    Write-Host "  📈 Flower (Celery): http://localhost:5555"
    Write-Host ""
    Write-Status "Model Information:"
    Write-Host "  🤖 Model Location:  ./models/adapter.gguf"
    Write-Host "  🔗 Model Source:    P3g4su5/ByeLabs-LoRA"
    Write-Host ""
    Write-Status "To test the system:"
    Write-Host "  1. Open http://localhost:3000 in your browser"
    Write-Host "  2. Upload a .eml file to test the pipeline"
    Write-Host "  3. Check the roster table for processed results"
    Write-Host ""
    Write-Status "To stop all services:"
    Write-Host "  docker-compose down"
    if (-not $SkipFrontend) {
        Write-Host "  Stop-Job $($frontendJob.Id)  # Stop frontend server"
    }
    Write-Host ""
    Write-Status "To view logs:"
    Write-Host "  docker-compose logs -f api    # API logs"
    Write-Host "  docker-compose logs -f worker # Worker logs"
    Write-Host "  docker-compose logs -f db     # Database logs"
    Write-Host ""
    
    # Keep script running to maintain services
    Write-Status "Press Ctrl+C to stop all services and exit..."
    
    # Function to cleanup on exit
    function Cleanup {
        Write-Status "Stopping services..."
        if (-not $SkipFrontend) {
            Stop-Job $frontendJob -ErrorAction SilentlyContinue
            Remove-Job $frontendJob -ErrorAction SilentlyContinue
        }
        docker-compose down
        Write-Success "All services stopped!"
        exit 0
    }
    
    # Set trap to cleanup on script exit
    $null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Cleanup }
    
    # Wait for user to stop
    try {
        while ($true) {
            Start-Sleep -Seconds 1
        }
    }
    catch {
        Cleanup
    }
}

# Run main function
Main
