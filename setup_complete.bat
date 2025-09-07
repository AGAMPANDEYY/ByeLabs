@echo off
REM HiLabs Roster Processing - Complete Setup Script (Windows Batch)
REM This script sets up the entire system including model download, Docker build, and frontend

setlocal enabledelayedexpansion

echo [INFO] Starting HiLabs Roster Processing Setup...
echo ==================================================

REM Check prerequisites
echo [INFO] Checking prerequisites...

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not installed. Please install Docker Desktop first.
    exit /b 1
)

REM Check if Docker Compose is installed
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker Compose is not installed. Please install Docker Compose first.
    exit /b 1
)

REM Check if Node.js is installed
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js is not installed. Please install Node.js first.
    exit /b 1
)

REM Check if npm is installed
npm --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm is not installed. Please install npm first.
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed. Please install Python first.
    exit /b 1
)

echo [SUCCESS] All prerequisites are installed!

REM Step 1: Install HuggingFace CLI
echo [INFO] Installing HuggingFace CLI...
huggingface-cli --version >nul 2>&1
if errorlevel 1 (
    pip install huggingface_hub[cli]
    if errorlevel 1 (
        echo [ERROR] Failed to install HuggingFace CLI
        exit /b 1
    )
    echo [SUCCESS] HuggingFace CLI installed!
) else (
    echo [SUCCESS] HuggingFace CLI already installed!
)

REM Step 2: Create models directory and download model
echo [INFO] Setting up model directory...

if not exist "models" (
    mkdir models
    echo [SUCCESS] Created models directory
) else (
    echo [SUCCESS] Models directory already exists
)

REM Check if model already exists
if exist "models\adapter.gguf" (
    echo [WARNING] Model already exists, skipping download
) else (
    echo [INFO] Downloading trained model from HuggingFace...
    echo [INFO] This may take several minutes depending on your internet connection...
    
    REM Download the model
    huggingface-cli download P3g4su5/ByeLabs-LoRA adapter.gguf --local-dir ./models
    
    if exist "models\adapter.gguf" (
        echo [SUCCESS] Model downloaded successfully!
    ) else (
        echo [ERROR] Model download failed!
        exit /b 1
    )
)

REM Step 3: Build Docker containers
echo [INFO] Building Docker containers...

REM Stop any existing containers
echo [INFO] Stopping any existing containers...
docker-compose down -v >nul 2>&1

REM Build the containers
echo [INFO] Building Docker images (this may take several minutes)...
docker-compose build --no-cache
if errorlevel 1 (
    echo [ERROR] Docker build failed!
    exit /b 1
)
echo [SUCCESS] Docker containers built successfully!

REM Step 4: Start backend services
echo [INFO] Starting backend services...

REM Start database first
echo [INFO] Starting PostgreSQL database...
docker-compose up -d db

REM Wait for database to be ready
echo [INFO] Waiting for database to initialize...
timeout /t 10 /nobreak >nul

REM Start all other services
echo [INFO] Starting all backend services...
docker-compose up -d

REM Wait for services to be ready
echo [INFO] Waiting for backend services to be ready...
timeout /t 15 /nobreak >nul

echo [SUCCESS] Backend services are running!

REM Step 5: Install frontend dependencies
echo [INFO] Installing frontend dependencies...

cd web

if not exist "node_modules" (
    echo [INFO] Installing npm packages (this may take a few minutes)...
    npm install
    if errorlevel 1 (
        echo [ERROR] Frontend dependency installation failed!
        exit /b 1
    )
    echo [SUCCESS] Frontend dependencies installed!
) else (
    echo [SUCCESS] Frontend dependencies already installed!
)

REM Step 6: Start frontend development server
echo [INFO] Starting frontend development server...

REM Start frontend in background
start /b npm run dev

REM Wait for frontend to be ready
echo [INFO] Waiting for frontend server to start...
timeout /t 10 /nobreak >nul

echo [SUCCESS] Frontend server is running!

REM Go back to root directory
cd ..

REM Step 7: Display final information
echo.
echo ==================================================
echo [SUCCESS] HiLabs Roster Processing Setup Complete!
echo ==================================================
echo.
echo [INFO] Services are now running:
echo   🌐 Frontend:        http://localhost:3000
echo   🔧 API Server:      http://localhost:8000
echo   📊 API Docs:        http://localhost:8000/docs
echo   📧 Mailpit:         http://localhost:8025
echo   💾 MinIO Console:   http://localhost:9001
echo   📈 Flower (Celery): http://localhost:5555
echo.
echo [INFO] Model Information:
echo   🤖 Model Location:  ./models/adapter.gguf
echo   🔗 Model Source:    P3g4su5/ByeLabs-LoRA
echo.
echo [INFO] To test the system:
echo   1. Open http://localhost:3000 in your browser
echo   2. Upload a .eml file to test the pipeline
echo   3. Check the roster table for processed results
echo.
echo [INFO] To stop all services:
echo   docker-compose down
echo   taskkill /f /im node.exe  # Stop frontend server
echo.
echo [INFO] To view logs:
echo   docker-compose logs -f api    # API logs
echo   docker-compose logs -f worker # Worker logs
echo   docker-compose logs -f db     # Database logs
echo.
echo [INFO] Press any key to stop all services and exit...
pause >nul

REM Cleanup
echo [INFO] Stopping services...
docker-compose down
taskkill /f /im node.exe >nul 2>&1
echo [SUCCESS] All services stopped!

endlocal
