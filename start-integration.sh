#!/bin/bash

echo "🚀 Starting HiLabs Roster Automation - Full Stack Integration"
echo "=============================================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo "✅ Docker is running"

# Start backend services
echo "📦 Starting backend services..."
cd api
docker-compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are healthy
echo "🔍 Checking service health..."
if curl -f http://localhost:8000/health > /dev/null 2>&1; then
    echo "✅ Backend API is ready"
else
    echo "❌ Backend API is not responding. Check Docker logs."
    exit 1
fi

# Start frontend
echo "🌐 Starting frontend..."
cd ../web

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

# Create .env.local if it doesn't exist
if [ ! -f ".env.local" ]; then
    echo "📝 Creating environment configuration..."
    echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
    echo "NODE_ENV=development" >> .env.local
fi

echo "🚀 Starting Next.js development server..."
npm run dev &

# Wait a moment for the server to start
sleep 5

echo ""
echo "🎉 Integration is ready!"
echo "=============================================================="
echo "📊 Backend API: http://localhost:8000"
echo "🌐 Frontend: http://localhost:3000"
echo "📧 Mailpit: http://localhost:8025"
echo "🗄️  MinIO: http://localhost:9001"
echo ""
echo "📋 Available endpoints:"
echo "  • POST /jobs/upload - Upload .eml file"
echo "  • GET /jobs - List all jobs"
echo "  • GET /jobs/{id} - Get job details"
echo "  • POST /jobs/{id}/resume - Resume job processing"
echo "  • POST /jobs/{id}/export - Create Excel export"
echo "  • GET /exports/{key}/download - Download export"
echo "  • GET /analytics - Get analytics data"
echo "  • GET /health - Health check"
echo ""
echo "🔄 To test the complete flow:"
echo "  1. Go to http://localhost:3000"
echo "  2. Upload a .eml file"
echo "  3. Monitor processing in the inbox"
echo "  4. Download the Excel export when complete"
echo ""
echo "Press Ctrl+C to stop all services"
