#!/usr/bin/env bash
set -euo pipefail

# HiLabs Roster Processing - Setup Script
# This script sets up the development environment on any machine

echo "🚀 Setting up HiLabs Roster Processing development environment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Check Python version
print_status "Checking Python version..."
python_version=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
required_version="3.11"

if [[ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]]; then
    print_error "Python 3.11+ is required. Found: $python_version"
    exit 1
fi

print_success "Python version check passed: $python_version"

# Check if virtual environment exists
if [ -d "venv" ]; then
    print_warning "Virtual environment already exists. Removing..."
    rm -rf venv
fi

# Create virtual environment
print_status "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
print_status "Upgrading pip..."
pip install --upgrade pip

# Install root dependencies
print_status "Installing root dependencies..."
pip install -r requirements.txt

# Setup API service
print_status "Setting up API service..."
cd api
if [ -d "venv" ]; then
    rm -rf venv
fi
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cd ..

# Setup VLM service
print_status "Setting up VLM service..."
cd vlm
if [ -d "venv" ]; then
    rm -rf venv
fi
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cd ..

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    print_status "Creating .env file..."
    cp .env.example .env
fi

print_success "🎉 Setup complete!"
echo ""
echo "📋 Next steps:"
echo "  1. Activate the root environment: source venv/bin/activate"
echo "  2. Start services: ./run.sh"
echo "  3. Or test API locally: cd api && source venv/bin/activate && python -m app.main"
echo ""
echo "🔧 Service-specific environments:"
echo "  • API: cd api && source venv/bin/activate"
echo "  • VLM: cd vlm && source venv/bin/activate"
