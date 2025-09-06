# HiLabs Roster Processing - Smoke Test Script (PowerShell)
# This script performs an end-to-end test of the system

param(
    [string]$ApiUrl = "http://localhost:8000",
    [string]$SampleFile = "samples/Sample-1.eml",
    [int]$MaxWaitTime = 300,  # 5 minutes
    [int]$PollInterval = 10   # 10 seconds
)

# Configuration
$ErrorActionPreference = "Stop"

# Helper functions
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

# Check if Docker Compose is running
function Test-DockerCompose {
    Write-Info "Checking if Docker Compose services are running..."
    
    $services = docker compose ps
    if ($services -notmatch "Up") {
        Write-Warning "Docker Compose services not running. Starting services..."
        docker compose up -d
        
        Write-Info "Waiting for services to be ready..."
        Start-Sleep -Seconds 30
    } else {
        Write-Success "Docker Compose services are running"
    }
}

# Wait for API to be ready
function Wait-ForApi {
    param([string]$Url)
    
    Write-Info "Waiting for API to be ready..."
    
    $attempts = 0
    $maxAttempts = 30
    
    while ($attempts -lt $maxAttempts) {
        try {
            $response = Invoke-WebRequest -Uri "$Url/health" -UseBasicParsing -TimeoutSec 5
            if ($response.StatusCode -eq 200) {
                Write-Success "API is ready"
                return $true
            }
        } catch {
            # API not ready yet
        }
        
        Write-Info "API not ready yet, waiting... (attempt $($attempts + 1)/$maxAttempts)"
        Start-Sleep -Seconds 10
        $attempts++
    }
    
    Write-Error "API failed to become ready after $($maxAttempts * 10) seconds"
    return $false
}

# Check if sample file exists
function Test-SampleFile {
    param([string]$FilePath)
    
    if (-not (Test-Path $FilePath)) {
        Write-Error "Sample file not found: $FilePath"
        Write-Info "Creating a sample EML file..."
        
        $samplesDir = Split-Path $FilePath -Parent
        if (-not (Test-Path $samplesDir)) {
            New-Item -ItemType Directory -Path $samplesDir -Force | Out-Null
        }
        
        $sampleContent = @"
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
"@
        
        $sampleContent | Out-File -FilePath $FilePath -Encoding UTF8
        Write-Success "Sample EML file created: $FilePath"
    } else {
        Write-Success "Sample file found: $FilePath"
    }
}

# Ingest sample file
function Invoke-SampleIngest {
    param([string]$Url, [string]$FilePath)
    
    Write-Info "Ingesting sample file..."
    
    try {
        $form = @{
            file = Get-Item $FilePath
        }
        
        $response = Invoke-RestMethod -Uri "$Url/ingest" -Method Post -Form $form
        
        if ($response.job_id) {
            Write-Success "Sample file ingested successfully. Job ID: $($response.job_id)"
            return $response.job_id
        } else {
            Write-Error "Failed to extract job ID from response: $($response | ConvertTo-Json)"
            return $null
        }
    } catch {
        Write-Error "Failed to ingest sample file: $($_.Exception.Message)"
        return $null
    }
}

# Poll job status
function Wait-JobCompletion {
    param([string]$Url, [int]$JobId, [int]$MaxWait, [int]$PollInterval)
    
    Write-Info "Polling job status for job ID: $JobId"
    
    $startTime = Get-Date
    $maxWaitTime = $startTime.AddSeconds($MaxWait)
    
    while ((Get-Date) -lt $maxWaitTime) {
        try {
            $response = Invoke-RestMethod -Uri "$Url/jobs/$JobId"
            $status = $response.status
            
            $elapsed = [int]((Get-Date) - $startTime).TotalSeconds
            Write-Info "Job status: $status (elapsed: ${elapsed}s)"
            
            switch ($status) {
                "completed" { 
                    Write-Success "Job completed with status: $status"
                    return $true
                }
                "needs_review" { 
                    Write-Success "Job completed with status: $status"
                    return $true
                }
                "failed" { 
                    Write-Error "Job failed with status: $status"
                    return $false
                }
                "error" { 
                    Write-Error "Job failed with status: $status"
                    return $false
                }
                default { 
                    Write-Info "Job still processing, waiting $PollInterval seconds..."
                    Start-Sleep -Seconds $PollInterval
                }
            }
        } catch {
            Write-Error "Failed to get job status: $($_.Exception.Message)"
            return $false
        }
    }
    
    Write-Error "Job processing timed out after $MaxWait seconds"
    return $false
}

# Trigger export
function Invoke-Export {
    param([string]$Url, [int]$JobId)
    
    Write-Info "Triggering export for job ID: $JobId"
    
    try {
        $response = Invoke-RestMethod -Uri "$Url/jobs/$JobId/export" -Method Post
        
        if ($response.export_id) {
            Write-Success "Export triggered successfully. Export ID: $($response.export_id)"
            return $response.export_id
        } else {
            Write-Error "Failed to extract export ID from response: $($response | ConvertTo-Json)"
            return $null
        }
    } catch {
        Write-Error "Failed to trigger export: $($_.Exception.Message)"
        return $null
    }
}

# Get export download URL
function Get-ExportUrl {
    param([string]$Url, [int]$ExportId)
    
    $downloadUrl = "$Url/exports/$ExportId/download"
    
    Write-Success "Export ready for download:"
    Write-Host "   URL: $downloadUrl" -ForegroundColor Cyan
    Write-Host "   Command: Invoke-WebRequest -Uri '$downloadUrl' -OutFile 'roster_export.xlsx'" -ForegroundColor Cyan
    
    # Test download URL
    try {
        $response = Invoke-WebRequest -Uri $downloadUrl -Method Head -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Success "Export download URL is accessible"
        }
    } catch {
        Write-Warning "Export download URL may not be accessible yet"
    }
}

# Main smoke test function
function Start-SmokeTest {
    Write-Info "Starting HiLabs Roster Processing Smoke Test"
    Write-Host "=========================================="
    
    # Step 1: Check Docker Compose
    Test-DockerCompose
    
    # Step 2: Wait for API
    if (-not (Wait-ForApi -Url $ApiUrl)) {
        exit 1
    }
    
    # Step 3: Check sample file
    Test-SampleFile -FilePath $SampleFile
    
    # Step 4: Ingest sample
    $jobId = Invoke-SampleIngest -Url $ApiUrl -FilePath $SampleFile
    if (-not $jobId) {
        exit 1
    }
    
    # Step 5: Poll job status
    if (-not (Wait-JobCompletion -Url $ApiUrl -JobId $jobId -MaxWait $MaxWaitTime -PollInterval $PollInterval)) {
        exit 1
    }
    
    # Step 6: Trigger export
    $exportId = Invoke-Export -Url $ApiUrl -JobId $jobId
    if (-not $exportId) {
        exit 1
    }
    
    # Step 7: Get export URL
    Get-ExportUrl -Url $ApiUrl -ExportId $exportId
    
    Write-Host ""
    Write-Success "🎉 Smoke test completed successfully!"
    Write-Host ""
    Write-Host "Summary:" -ForegroundColor Cyan
    Write-Host "  - Job ID: $jobId" -ForegroundColor White
    Write-Host "  - Export ID: $exportId" -ForegroundColor White
    Write-Host "  - Download URL: $ApiUrl/exports/$exportId/download" -ForegroundColor White
    Write-Host ""
    Write-Host "You can now:" -ForegroundColor Cyan
    Write-Host "  1. View the job details: $ApiUrl/ui/jobs/$jobId" -ForegroundColor White
    Write-Host "  2. Download the Excel file: Invoke-WebRequest -Uri '$ApiUrl/exports/$exportId/download' -OutFile 'roster_export.xlsx'" -ForegroundColor White
    Write-Host "  3. Check the API documentation: $ApiUrl/docs" -ForegroundColor White
    
    exit 0
}

# Run main function
Start-SmokeTest
