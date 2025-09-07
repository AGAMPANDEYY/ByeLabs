#!/bin/bash

# HiLabs Roster Processing - Complete Setup Script
# This script sets up the entire system including model download, Docker build, and frontend

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if port is in use
port_in_use() {
    lsof -i :$1 >/dev/null 2>&1
}

# Function to wait for service to be ready
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    print_status "Waiting for $service_name to be ready..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" >/dev/null 2>&1; then
            print_success "$service_name is ready!"
            return 0
        fi
        
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    
    print_error "$service_name failed to start within expected time"
    return 1
}

# Main setup function
main() {
    print_status "Starting HiLabs Roster Processing Setup..."
    echo "=================================================="
    
    # Check prerequisites
    print_status "Checking prerequisites..."
    
    # Check if Docker is installed
    if ! command_exists docker; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command_exists docker-compose; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if Node.js is installed
    if ! command_exists node; then
        print_error "Node.js is not installed. Please install Node.js first."
        exit 1
    fi
    
    # Check if npm is installed
    if ! command_exists npm; then
        print_error "npm is not installed. Please install npm first."
        exit 1
    fi
    
    # Check if Python is installed
    if ! command_exists python3; then
        print_error "Python 3 is not installed. Please install Python 3 first."
        exit 1
    fi
    
    print_success "All prerequisites are installed!"
    
    # Step 1: Install HuggingFace CLI
    print_status "Installing HuggingFace CLI..."
    if ! command_exists huggingface-cli; then
        pip install huggingface_hub[cli]
        print_success "HuggingFace CLI installed!"
    else
        print_success "HuggingFace CLI already installed!"
    fi
    
    # Step 2: Create models directory and download model
    print_status "Setting up model directory..."
    
    if [ ! -d "models" ]; then
        mkdir -p models
        print_success "Created models directory"
    else
        print_success "Models directory already exists"
    fi
    
    # Check if model already exists
    if [ -f "models/adapter.gguf" ]; then
        print_warning "Model already exists, skipping download"
    else
        print_status "Downloading trained model from HuggingFace..."
        print_status "This may take several minutes depending on your internet connection..."
        
        # Download the model
        huggingface-cli download P3g4su5/ByeLabs-LoRA adapter.gguf --local-dir ./models
        
        if [ -f "models/adapter.gguf" ]; then
            print_success "Model downloaded successfully!"
        else
            print_error "Model download failed!"
            exit 1
        fi
    fi
    
    # Step 3: Check if ports are available
    print_status "Checking if required ports are available..."
    
    ports=(8000 3000 5432 9000 5672 1025 9090 5555)
    for port in "${ports[@]}"; do
        if port_in_use $port; then
            print_warning "Port $port is already in use. You may need to stop the service using this port."
        fi
    done
    
    # Step 4: Build Docker containers
    print_status "Building Docker containers..."
    
    # Stop any existing containers
    print_status "Stopping any existing containers..."
    docker-compose down -v 2>/dev/null || true
    
    # Build the containers
    print_status "Building Docker images (this may take several minutes)..."
    docker-compose build --no-cache
    
    if [ $? -eq 0 ]; then
        print_success "Docker containers built successfully!"
    else
        print_error "Docker build failed!"
        exit 1
    fi
    
    # Step 5: Start backend services
    print_status "Starting backend services..."
    
    # Start database first
    print_status "Starting PostgreSQL database..."
    docker-compose up -d db
    
    # Wait for database to be ready
    sleep 10
    
    # Start all other services
    print_status "Starting all backend services..."
    docker-compose up -d
    
    # Wait for services to be ready
    print_status "Waiting for backend services to be ready..."
    
    # Wait for API to be ready
    wait_for_service "http://localhost:8000/health" "API Server"
    
    # Wait for MinIO to be ready
    wait_for_service "http://localhost:9001" "MinIO"
    
    # Wait for Mailpit to be ready
    wait_for_service "http://localhost:8025" "Mailpit"
    
    print_success "Backend services are running!"
    
    # Step 6: Install frontend dependencies
    print_status "Installing frontend dependencies..."
    
    cd web
    
    if [ ! -d "node_modules" ]; then
        print_status "Installing npm packages (this may take a few minutes)..."
        npm install
        
        if [ $? -eq 0 ]; then
            print_success "Frontend dependencies installed!"
        else
            print_error "Frontend dependency installation failed!"
            exit 1
        fi
    else
        print_success "Frontend dependencies already installed!"
    fi
    
    # Step 7: Start frontend development server
    print_status "Starting frontend development server..."
    
    # Start frontend in background
    npm run dev &
    FRONTEND_PID=$!
    
    # Wait for frontend to be ready
    wait_for_service "http://localhost:3000" "Frontend Server"
    
    print_success "Frontend server is running!"
    
    # Step 8: Display final information
    echo ""
    echo "=================================================="
    print_success "HiLabs Roster Processing Setup Complete!"
    echo "=================================================="
    echo ""
    print_status "Services are now running:"
    echo "  🌐 Frontend:        http://localhost:3000"
    echo "  🔧 API Server:      http://localhost:8000"
    echo "  📊 API Docs:        http://localhost:8000/docs"
    echo "  📧 Mailpit:         http://localhost:8025"
    echo "  💾 MinIO Console:   http://localhost:9001"
    echo "  📈 Flower (Celery): http://localhost:5555"
    echo ""
    print_status "Model Information:"
    echo "  🤖 Model Location:  ./models/adapter.gguf"
    echo "  🔗 Model Source:    P3g4su5/ByeLabs-LoRA"
    echo ""
    print_status "To test the system:"
    echo "  1. Open http://localhost:3000 in your browser"
    echo "  2. Upload a .eml file to test the pipeline"
    echo "  3. Check the roster table for processed results"
    echo ""
    print_status "To stop all services:"
    echo "  docker-compose down"
    echo "  kill $FRONTEND_PID  # Stop frontend server"
    echo ""
    print_status "To view logs:"
    echo "  docker-compose logs -f api    # API logs"
    echo "  docker-compose logs -f worker # Worker logs"
    echo "  docker-compose logs -f db     # Database logs"
    echo ""
    
    # Keep script running to maintain services
    print_status "Press Ctrl+C to stop all services and exit..."
    
    # Function to cleanup on exit
    cleanup() {
        print_status "Stopping services..."
        kill $FRONTEND_PID 2>/dev/null || true
        docker-compose down
        print_success "All services stopped!"
        exit 0
    }
    
    # Set trap to cleanup on script exit
    trap cleanup SIGINT SIGTERM
    
    # Wait for user to stop
    wait
}

# Run main function
main "$@"
