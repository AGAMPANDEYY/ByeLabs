#!/bin/bash

# HiLabs Roster Processing - Smoke Test Script
# This script performs an end-to-end test of the system

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="http://localhost:8000"
SAMPLE_FILE="samples/Sample-1.eml"
MAX_WAIT_TIME=300  # 5 minutes
POLL_INTERVAL=10   # 10 seconds

# Helper functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker Compose is running
check_docker_compose() {
    log_info "Checking if Docker Compose services are running..."
    
    if ! docker compose ps | grep -q "Up"; then
        log_warning "Docker Compose services not running. Starting services..."
        docker compose up -d
        
        log_info "Waiting for services to be ready..."
        sleep 30
    else
        log_success "Docker Compose services are running"
    fi
}

# Wait for API to be ready
wait_for_api() {
    log_info "Waiting for API to be ready..."
    
    local attempts=0
    local max_attempts=30
    
    while [ $attempts -lt $max_attempts ]; do
        if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
            log_success "API is ready"
            return 0
        fi
        
        log_info "API not ready yet, waiting... (attempt $((attempts + 1))/$max_attempts)"
        sleep 10
        attempts=$((attempts + 1))
    done
    
    log_error "API failed to become ready after $((max_attempts * 10)) seconds"
    return 1
}

# Check if sample file exists
check_sample_file() {
    if [ ! -f "$SAMPLE_FILE" ]; then
        log_error "Sample file not found: $SAMPLE_FILE"
        log_info "Creating a sample EML file..."
        
        mkdir -p samples
        
        cat > "$SAMPLE_FILE" << 'EOF'
From: sender@example.com
To: recipient@example.com
Subject: Provider Roster Update
Date: Mon, 01 Jan 2024 12:00:00 +0000
MIME-Version: 1.0
Content-Type: text/html; charset=UTF-8

<html>
<body>
<h2>Provider Roster Update</h2>
<table border="1">
<tr>
<th>NPI</th>
<th>Provider Name</th>
<th>Specialty</th>
<th>Phone</th>
<th>Email</th>
<th>Effective Date</th>
</tr>
<tr>
<td>1234567893</td>
<td>Dr. John Smith</td>
<td>Internal Medicine</td>
<td>(555) 123-4567</td>
<td>john.smith@example.com</td>
<td>01/01/2024</td>
</tr>
<tr>
<td>9876543210</td>
<td>Dr. Jane Doe</td>
<td>Cardiology</td>
<td>(555) 987-6543</td>
<td>jane.doe@example.com</td>
<td>01/01/2024</td>
</tr>
</table>
</body>
</html>
EOF
        
        log_success "Sample EML file created: $SAMPLE_FILE"
    else
        log_success "Sample file found: $SAMPLE_FILE"
    fi
}

# Ingest sample file
ingest_sample() {
    log_info "Ingesting sample file..."
    
    local response
    response=$(curl -s -X POST \
        -F "file=@$SAMPLE_FILE" \
        "$API_URL/ingest")
    
    if [ $? -ne 0 ]; then
        log_error "Failed to ingest sample file"
        return 1
    fi
    
    # Extract job ID from response
    local job_id
    job_id=$(echo "$response" | grep -o '"job_id":[0-9]*' | cut -d':' -f2)
    
    if [ -z "$job_id" ]; then
        log_error "Failed to extract job ID from response: $response"
        return 1
    fi
    
    log_success "Sample file ingested successfully. Job ID: $job_id"
    echo "$job_id"
}

# Poll job status
poll_job_status() {
    local job_id=$1
    local start_time=$(date +%s)
    
    log_info "Polling job status for job ID: $job_id"
    
    while true; do
        local current_time=$(date +%s)
        local elapsed=$((current_time - start_time))
        
        if [ $elapsed -gt $MAX_WAIT_TIME ]; then
            log_error "Job processing timed out after $MAX_WAIT_TIME seconds"
            return 1
        fi
        
        local response
        response=$(curl -s "$API_URL/jobs/$job_id")
        
        if [ $? -ne 0 ]; then
            log_error "Failed to get job status"
            return 1
        fi
        
        local status
        status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
        
        log_info "Job status: $status (elapsed: ${elapsed}s)"
        
        case "$status" in
            "completed"|"needs_review")
                log_success "Job completed with status: $status"
                return 0
                ;;
            "failed"|"error")
                log_error "Job failed with status: $status"
                return 1
                ;;
            "pending"|"processing")
                log_info "Job still processing, waiting $POLL_INTERVAL seconds..."
                sleep $POLL_INTERVAL
                ;;
            *)
                log_warning "Unknown job status: $status"
                sleep $POLL_INTERVAL
                ;;
        esac
    done
}

# Trigger export
trigger_export() {
    local job_id=$1
    
    log_info "Triggering export for job ID: $job_id"
    
    local response
    response=$(curl -s -X POST "$API_URL/jobs/$job_id/export")
    
    if [ $? -ne 0 ]; then
        log_error "Failed to trigger export"
        return 1
    fi
    
    # Extract export ID from response
    local export_id
    export_id=$(echo "$response" | grep -o '"export_id":[0-9]*' | cut -d':' -f2)
    
    if [ -z "$export_id" ]; then
        log_error "Failed to extract export ID from response: $response"
        return 1
    fi
    
    log_success "Export triggered successfully. Export ID: $export_id"
    echo "$export_id"
}

# Get export download URL
get_export_url() {
    local export_id=$1
    local download_url="$API_URL/exports/$export_id/download"
    
    log_success "Export ready for download:"
    echo "   URL: $download_url"
    echo "   Command: curl -O '$download_url'"
    
    # Test download URL
    if curl -s -I "$download_url" | grep -q "200 OK"; then
        log_success "Export download URL is accessible"
    else
        log_warning "Export download URL may not be accessible yet"
    fi
}

# Main smoke test function
main() {
    log_info "Starting HiLabs Roster Processing Smoke Test"
    echo "=========================================="
    
    # Step 1: Check Docker Compose
    check_docker_compose
    
    # Step 2: Wait for API
    wait_for_api
    
    # Step 3: Check sample file
    check_sample_file
    
    # Step 4: Ingest sample
    local job_id
    job_id=$(ingest_sample)
    
    # Step 5: Poll job status
    poll_job_status "$job_id"
    
    # Step 6: Trigger export
    local export_id
    export_id=$(trigger_export "$job_id")
    
    # Step 7: Get export URL
    get_export_url "$export_id"
    
    echo ""
    log_success "🎉 Smoke test completed successfully!"
    echo ""
    echo "Summary:"
    echo "  - Job ID: $job_id"
    echo "  - Export ID: $export_id"
    echo "  - Download URL: $API_URL/exports/$export_id/download"
    echo ""
    echo "You can now:"
    echo "  1. View the job details: $API_URL/ui/jobs/$job_id"
    echo "  2. Download the Excel file: curl -O '$API_URL/exports/$export_id/download'"
    echo "  3. Check the API documentation: $API_URL/docs"
    
    exit 0
}

# Run main function
main "$@"
