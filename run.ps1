# HiLabs Roster Processing - Windows Startup Script
# This script starts the entire system using Docker Compose

param(
    [switch]$Build = $false,
    [switch]$Detached = $true
)

# Colors for output
$ErrorActionPreference = "Continue"

function Write-Info {
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

# Docker path
$DockerPath = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"

# Check if Docker is available
if (-not (Test-Path $DockerPath)) {
    Write-Error "Docker not found at $DockerPath"
    Write-Info "Please install Docker Desktop and try again"
    exit 1
}

Write-Info "Starting HiLabs Roster Processing System..."

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Info "Creating .env file from .env.example..."
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Success ".env file created"
    } else {
        Write-Warning ".env.example not found, using default settings"
    }
}

# Create necessary directories
Write-Info "Creating directory structure..."
$directories = @("api", "vlm", "samples", "logs", "scripts")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Info "Created directory: $dir"
    }
}

# Check Docker Compose
Write-Info "Checking Docker Compose..."
try {
    & $DockerPath compose version | Out-Null
    Write-Success "Docker Compose is available"
} catch {
    Write-Error "Docker Compose not available. Please update Docker Desktop."
    exit 1
}

# Pull images
Write-Info "Pulling Docker images..."
try {
    & $DockerPath compose pull
    Write-Success "Images pulled successfully"
} catch {
    Write-Warning "Failed to pull some images, will build locally"
}

# Start services
Write-Info "Starting services..."
try {
    if ($Build) {
        & $DockerPath compose up --build -d
    } else {
        & $DockerPath compose up -d
    }
    Write-Success "Services started successfully"
} catch {
    Write-Error "Failed to start services: $($_.Exception.Message)"
    exit 1
}

# Wait for services to be ready
Write-Info "Waiting for services to be ready..."
Start-Sleep -Seconds 30

# Check service status
Write-Info "Checking service status..."
try {
    $services = & $DockerPath compose ps
    Write-Host $services
} catch {
    Write-Warning "Could not get service status"
}

Write-Success "🎉 HiLabs Roster Processing System is starting!"
Write-Host ""
Write-Host "Service URLs:" -ForegroundColor Cyan
Write-Host "  • API Documentation: http://localhost:8000/docs" -ForegroundColor White
Write-Host "  • Review UI: http://localhost:8000/ui/jobs" -ForegroundColor White
Write-Host "  • Health Check: http://localhost:8000/health" -ForegroundColor White
Write-Host "  • Metrics: http://localhost:8000/metrics" -ForegroundColor White
Write-Host "  • Mailpit: http://localhost:8025" -ForegroundColor White
Write-Host "  • MinIO Console: http://localhost:9001" -ForegroundColor White
Write-Host "  • RabbitMQ: http://localhost:15672" -ForegroundColor White
Write-Host ""
Write-Host "To run the smoke test:" -ForegroundColor Cyan
Write-Host "  .\scripts\smoke.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To stop the system:" -ForegroundColor Cyan
Write-Host "  & `"$DockerPath`" compose down" -ForegroundColor White
