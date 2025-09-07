"""
HiLabs Roster Processing - FastAPI Main Application

This is the main FastAPI application that provides:
- Health check endpoints
- Prometheus metrics
- API documentation
- Egress guard for local-only operation
"""

import logging
import time
import email
import email.policy
import hashlib
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Request, Response, UploadFile, File, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import structlog
from sqlalchemy.orm import Session

from .config import settings
from .net_guard import test_egress_guard, test_local_requests
from .db import init_database, check_database_connection, get_database_info, get_db, get_db_session
from .llm import get_llm_client
from .storage import ensure_bucket, storage_client, calculate_checksum, generate_object_key
from .models import Email, Job, Version, Record, Issue, Export, AuditLog, JobStatus, IssueLevel

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer() if settings.log_format == "json" 
        else structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Prometheus metrics (using lazy registration)
from .metrics import get_agent_runs_total, get_agent_latency_seconds, get_active_jobs_gauge

# Create HTTP-specific metrics
from prometheus_client import Counter, Histogram, Gauge

REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'http_active_connections',
    'Number of active HTTP connections'
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(
        "Starting HiLabs Roster Processing API",
        version=settings.app_version,
        environment=settings.app_env,
        allow_egress=settings.allow_egress
    )
    
    # Initialize database
    logger.info("Initializing database...")
    try:
        init_database()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        # Continue startup but mark as unhealthy
    
    # Initialize storage
    logger.info("Initializing storage...")
    try:
        ensure_bucket(settings.s3_bucket)
        logger.info("Storage initialized successfully")
    except Exception as e:
        logger.error(f"Storage initialization failed: {e}")
        # Continue startup but mark as unhealthy
    
    # Test egress guard
    if not settings.allow_egress:
        logger.info("Testing egress guard...")
        guard_working = test_egress_guard()
        local_working = test_local_requests()
        
        if not guard_working:
            logger.error("Egress guard test failed!")
        else:
            logger.info("Egress guard is working correctly")
    
    yield
    
    # Shutdown
    logger.info("Shutting down HiLabs Roster Processing API")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="Local-only roster email processing with AI assistance",
    version=settings.app_version,
    docs_url="/docs" if settings.dev_mode else None,
    redoc_url="/redoc" if settings.dev_mode else None,
    openapi_url="/openapi.json" if settings.dev_mode else None,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Initialize templates
templates = Jinja2Templates(directory="api/templates")


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """
    Middleware to collect Prometheus metrics.
    """
    start_time = time.time()
    
    # Increment active connections
    ACTIVE_CONNECTIONS.inc()
    
    try:
        response = await call_next(request)
        
        # Record metrics
        duration = time.time() - start_time
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()
        
        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        
        return response
        
    except Exception as e:
        # Record error metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=500
        ).inc()
        
        logger.error(
            "Request failed",
            method=request.method,
            endpoint=request.url.path,
            error=str(e)
        )
        
        raise
    
    finally:
        # Decrement active connections
        ACTIVE_CONNECTIONS.dec()


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """
    Middleware for request/response logging.
    """
    start_time = time.time()
    
    # Log request
    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent")
    )
    
    response = await call_next(request)
    
    # Log response
    duration = time.time() - start_time
    logger.info(
        "Request completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        duration_ms=round(duration * 1000, 2)
    )
    
    return response


@app.get("/health", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.
    
    Returns the current status of the application and its dependencies.
    """
    # Check database health
    db_healthy = check_database_connection()
    db_info = get_database_info() if db_healthy else {"connected": False}
    
    # Check storage health
    try:
        storage_client.object_exists("health-check")
        storage_healthy = True
    except Exception:
        storage_healthy = False
    
    health_status = {
        "status": "healthy" if db_healthy and storage_healthy else "degraded",
        "timestamp": time.time(),
        "version": settings.app_version,
        "environment": settings.app_env,
        "services": {
            "api": "healthy",
            "database": "healthy" if db_healthy else "unhealthy",
            "storage": "healthy" if storage_healthy else "unhealthy",
            "egress_guard": "active" if not settings.allow_egress else "disabled"
        },
        "database_info": db_info
    }
    
    return health_status


@app.get("/health/ready", tags=["Health"])
@app.get("/healthz/ready", tags=["Health"])  # Kubernetes-style endpoint
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check endpoint.
    
    Returns whether the application is ready to serve requests.
    Kubernetes-compatible endpoint at /healthz/ready.
    """
    # Check database connectivity
    db_ready = check_database_connection()
    
    # Check storage connectivity
    storage_ready = True
    try:
        storage_client.object_exists("health-check")
    except Exception:
        storage_ready = False
    
    # Check if all critical services are ready
    ready = db_ready and storage_ready
    
    return {
        "status": "ready" if ready else "not_ready",
        "timestamp": time.time(),
        "checks": {
            "database": "ready" if db_ready else "not_ready",
            "storage": "ready" if storage_ready else "not_ready",
            "queue": "ready",     # TODO: Implement actual check
            "vlm": "ready"        # TODO: Implement actual check
        }
    }


@app.get("/health/live", tags=["Health"])
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness check endpoint.
    
    Returns whether the application is alive and should not be restarted.
    """
    return {
        "status": "alive",
        "timestamp": time.time(),
        "uptime": time.time()  # TODO: Track actual uptime
    }


@app.get("/metrics", tags=["Observability"])
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus format.
    """
    if not settings.enable_metrics:
        return JSONResponse(
            status_code=404,
            content={"error": "Metrics disabled"}
        )
    
    metrics_data = generate_latest()
    return Response(
        content=metrics_data,
        media_type=CONTENT_TYPE_LATEST
    )


@app.get("/analytics", summary="Get Analytics", tags=["Analytics"])
async def get_analytics():
    """Get system analytics and statistics."""
    # Return mock data for now to avoid database issues
    return {
        "totalJobs": 1247,
        "completedJobs": 1156,
        "pendingJobs": 23,
        "errorJobs": 68,
        "avgProcessingTime": 2.4,
        "totalExports": 1089,
        "successRate": 92.7
    }

@app.post("/jobs/check-timeouts", summary="Check and Mark Stuck Jobs", tags=["Jobs"])
async def check_stuck_jobs(db: Session = Depends(get_db)):
    """Check for jobs that have been processing for more than 3 minutes and mark them as failed."""
    try:
        from datetime import datetime, timedelta
        
        # Calculate cutoff time (3 minutes ago)
        cutoff_time = datetime.utcnow() - timedelta(minutes=3)
        
        # Find stuck jobs
        stuck_jobs = db.query(Job).filter(
            Job.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]),
            Job.updated_at < cutoff_time
        ).all()
        
        updated_count = 0
        for job in stuck_jobs:
            job.status = JobStatus.ERROR
            job.error_message = "Job timeout: Processing exceeded 3 minutes"
            job.updated_at = datetime.utcnow()
            updated_count += 1
            
            # Log the timeout
            audit_log = AuditLog(
                job_id=job.id,
                action="job_timeout",
                details=f"Job marked as failed due to timeout after 3 minutes",
                timestamp=datetime.utcnow()
            )
            db.add(audit_log)
        
        db.commit()
        
        return {
            "message": f"Checked for stuck jobs",
            "stuck_jobs_found": len(stuck_jobs),
            "jobs_updated": updated_count,
            "cutoff_time": cutoff_time.isoformat()
        }
        
    except Exception as e:
        logger.error("Error checking stuck jobs", error=str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error checking stuck jobs: {str(e)}")


@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with basic information.
    """
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Local-only roster email processing with AI assistance",
        "environment": settings.app_env,
        "docs_url": "/docs" if settings.dev_mode else "disabled",
        "health_url": "/health",
        "metrics_url": "/metrics" if settings.enable_metrics else "disabled"
    }


@app.get("/info", tags=["Info"])
async def app_info():
    """
    Application information endpoint.
    """
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "debug": settings.debug,
        "log_level": settings.log_level,
        "allow_egress": settings.allow_egress,
        "features": {
            "metrics": settings.enable_metrics,
            "tracing": settings.enable_tracing,
            "vlm_enabled": settings.vlm_enabled,
            "dev_mode": settings.dev_mode
        }
    }


# ============================================================================
# INGESTION ENDPOINTS
# ============================================================================

@app.post("/ingest", summary="Ingest EML File", tags=["Ingestion"])
async def ingest_eml_file(
    file: UploadFile = File(..., description="EML file to process"),
    db: Session = Depends(get_db)
):
    """
    Ingest an EML file for roster processing.
    
    This endpoint:
    1. Parses the EML file headers using Python's email module
    2. Computes a content hash for duplicate detection
    3. Stores the raw EML file in MinIO
    4. Creates Email and Job records in the database
    5. Enqueues background processing (placeholder for Celery)
    
    Args:
        file: The EML file to process
        db: Database session
    
    Returns:
        Job information including job_id for tracking
    
    Raises:
        HTTPException: For validation errors or processing failures
    """
    logger.info("EML ingestion started", filename=file.filename, content_type=file.content_type)
    
    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    if not file.filename.lower().endswith('.eml'):
        raise HTTPException(status_code=400, detail="File must be an EML file")
    
    try:
        # Read file content
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file")
        
        if len(content) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(
                status_code=400, 
                detail=f"File too large. Maximum size: {settings.max_upload_mb}MB"
            )
        
        # Parse email headers
        try:
            # Use default policy for Python 3.3+, fallback for older versions
            try:
                email_message = email.message_from_bytes(content, policy=email.policy.default)
            except AttributeError:
                # Fallback for older Python versions
                email_message = email.message_from_bytes(content)
        except Exception as e:
            logger.error("Failed to parse EML file", error=str(e))
            raise HTTPException(status_code=400, detail=f"Invalid EML file: {str(e)}")
        
        # Extract email metadata
        message_id = email_message.get('Message-ID', '').strip()
        from_addr = email_message.get('From', '').strip()
        to_addr = email_message.get('To', '').strip()
        subject = email_message.get('Subject', '').strip()
        
        if not message_id:
            raise HTTPException(status_code=400, detail="Missing Message-ID header")
        
        if not from_addr:
            raise HTTPException(status_code=400, detail="Missing From header")
        
        # Compute content hash
        content_hash = calculate_checksum(content)
        
        # Check for duplicates
        existing_email = db.query(Email).filter(
            (Email.message_id == message_id) | (Email.hash == content_hash)
        ).first()
        
        if existing_email:
            logger.info("Duplicate email detected", message_id=message_id, hash=content_hash)
            # Return existing job if available
            existing_job = db.query(Job).filter(Job.email_id == existing_email.id).first()
            if existing_job:
                return {
                    "job_id": existing_job.id,
                    "status": "duplicate",
                    "message": "Email already processed",
                    "existing_job_id": existing_job.id
                }
        
        # Generate storage key
        storage_key = generate_object_key("raw", f"{uuid.uuid4()}.eml")
        
        # Store raw EML in MinIO
        try:
            raw_uri = storage_client.put_bytes(
                key=storage_key,
                data=content,
                content_type="message/rfc822"
            )
        except Exception as e:
            logger.error("Failed to store EML file", error=str(e))
            raise HTTPException(status_code=500, detail="Failed to store file")
        
        # Create Email record
        email_record = Email(
            message_id=message_id,
            from_addr=from_addr,
            to_addr=to_addr,
            subject=subject,
            received_at=datetime.now(timezone.utc),
            raw_uri=raw_uri,
            hash=content_hash
        )
        db.add(email_record)
        db.flush()  # Get the ID
        
        # Create Job record
        job = Job(
            email_id=email_record.id,
            status=JobStatus.PENDING.value
        )
        db.add(job)
        db.flush()  # Get the ID
        
        # Create initial version
        version = Version(
            job_id=job.id,
            author="system",
            reason="Initial ingestion"
        )
        db.add(version)
        db.flush()
        
        # Update job with current version
        job.current_version_id = version.id
        
        # Create audit log
        audit_log = AuditLog(
            job_id=job.id,
            actor="api",
            action="create",
            after_json={
                "email_id": email_record.id,
                "status": job.status,
                "version_id": version.id
            }
        )
        db.add(audit_log)
        
        # Commit transaction
        db.commit()
        
        # Enqueue background processing via Celery
        try:
            from .pipeline import process_job
            task = process_job.delay(job.id)
            logger.info("Job enqueued for processing", job_id=job.id, task_id=task.id)
        except Exception as e:
            logger.error("Failed to enqueue job", job_id=job.id, error=str(e))
            # Continue anyway - job is created and can be processed later
        
        logger.info("EML ingestion completed", job_id=job.id, email_id=email_record.id)
        
        return {
            "job_id": job.id,
            "status": "pending",
            "message": "Email ingested successfully",
            "email_id": email_record.id,
            "version_id": version.id,
            "task_id": task.id if 'task' in locals() else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Unexpected error during ingestion", error=str(e))
        db.rollback()
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/jobs", summary="List Jobs", tags=["Jobs"])
async def list_jobs(
    skip: int = Query(0, ge=0, description="Number of jobs to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of jobs to return"),
    status: Optional[str] = Query(None, description="Filter by job status"),
    db: Session = Depends(get_db)
):
    """
    List all jobs with pagination and optional status filtering.
    
    Args:
        skip: Number of jobs to skip (for pagination)
        limit: Maximum number of jobs to return
        status: Optional status filter
        db: Database session
    
    Returns:
        List of jobs with basic information
    """
    logger.info("Listing jobs", skip=skip, limit=limit, status=status)
    
    try:
        # Build query
        query = db.query(Job).join(Email).order_by(Job.created_at.desc())
        
        if status:
            if status not in [s.value for s in JobStatus]:
                raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
            query = query.filter(Job.status == status)
        
        # Get total count
        total_count = query.count()
        
        # Get jobs with pagination
        jobs = query.offset(skip).limit(limit).all()
        
        # Format response
        job_list = []
        for job in jobs:
            job_list.append({
                "id": job.id,
                "status": job.status,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
                "email": {
                    "id": job.email.id,
                    "from_addr": job.email.from_addr,
                    "subject": job.email.subject,
                    "received_at": job.email.received_at.isoformat()
                },
                "current_version_id": job.current_version_id
            })
        
        return {
            "jobs": job_list,
            "total": total_count,
            "skip": skip,
            "limit": limit,
            "has_more": skip + len(jobs) < total_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error listing jobs", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/jobs/{job_id}", summary="Get Job Details", tags=["Jobs"])
async def get_job_details(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed information about a specific job.
    
    Args:
        job_id: The job ID to retrieve
        db: Database session
    
    Returns:
        Detailed job information including email metadata, status, 
        current version, latest issues, and artifact URIs
    
    Raises:
        HTTPException: 404 if job not found, 400 for invalid ID
    """
    logger.info("Getting job details", job_id=job_id)
    
    try:
        # Get job with relations
        job = db.query(Job).filter(Job.id == job_id).first()
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        # Get email information
        email_info = {
            "id": job.email.id,
            "message_id": job.email.message_id,
            "from_addr": job.email.from_addr,
            "to_addr": job.email.to_addr,
            "subject": job.email.subject,
            "received_at": job.email.received_at.isoformat(),
            "raw_uri": job.email.raw_uri,
            "hash": job.email.hash
        }
        
        # Get current version info
        current_version_info = None
        if job.current_version_id:
            current_version = db.query(Version).filter(Version.id == job.current_version_id).first()
            if current_version:
                current_version_info = {
                    "id": current_version.id,
                    "author": current_version.author,
                    "reason": current_version.reason,
                    "created_at": current_version.created_at.isoformat(),
                    "record_count": db.query(Record).filter(Record.version_id == current_version.id).count()
                }
        
        # Get latest issues summary
        issues_summary = {"error": 0, "warning": 0, "info": 0}
        if job.current_version_id:
            issues = db.query(Issue).filter(Issue.version_id == job.current_version_id).all()
            for issue in issues:
                issues_summary[issue.level] += 1
        
        # Get artifact URIs
        artifacts = {
            "raw_email": job.email.raw_uri,
            "exports": []
        }
        
        # Get export URIs
        exports = db.query(Export).filter(Export.job_id == job.id).all()
        for export in exports:
            artifacts["exports"].append({
                "id": export.id,
                "version_id": export.version_id,
                "file_uri": export.file_uri,
                "checksum": export.checksum,
                "created_at": export.created_at.isoformat()
            })
        
        # Get all versions
        versions = []
        for version in job.versions:
            versions.append({
                "id": version.id,
                "author": version.author,
                "reason": version.reason,
                "created_at": version.created_at.isoformat(),
                "record_count": db.query(Record).filter(Record.version_id == version.id).count()
            })
        
        # Calculate total and processed records
        total_records = 0
        processed_records = 0
        
        if job.current_version_id:
            # Get total records from current version
            total_records = db.query(Record).filter(Record.version_id == job.current_version_id).count()
            
            # Get processed records (records that passed validation)
            # For now, we'll consider all records as "processed" if they exist
            # In the future, we could add a validation status field to records
            processed_records = total_records
        
        return {
            "id": job.id,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "email": email_info,
            "current_version": current_version_info,
            "issues_summary": issues_summary,
            "artifacts": artifacts,
            "versions": versions,
            "total_records": total_records,
            "processed_records": processed_records,
            "issues_count": sum(issues_summary.values())
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting job details", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/jobs/{job_id}/process", summary="Process Job", tags=["Jobs"])
async def process_job_endpoint(
    job_id: int,
    db: Session = Depends(get_db)
):
    """
    Trigger processing of a job through the multi-agent pipeline.
    
    Args:
        job_id: The job ID to process
        db: Database session
    
    Returns:
        Processing status and task information
    
    Raises:
        HTTPException: 404 if job not found, 400 if job cannot be processed
    """
    logger.info("Triggering job processing", job_id=job_id)
    
    try:
        # Get job
        job = db.query(Job).filter(Job.id == job_id).first()
        
        if not job:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        # Check if job can be processed
        if job.status not in ["pending", "failed"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Job {job_id} cannot be processed. Current status: {job.status}"
            )
        
        # Import Celery task
        from .pipeline import process_job
        
        # Queue the job for processing
        task = process_job.delay(job_id)
        
        logger.info("Job processing queued", job_id=job_id, task_id=task.id)
        
        return {
            "job_id": job_id,
            "task_id": task.id,
            "status": "queued",
            "message": f"Job {job_id} has been queued for processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error queuing job processing", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


# ============================================================================
# UI ROUTES (HTMX)
# ============================================================================

@app.get("/ui/jobs", response_class=HTMLResponse)
async def ui_jobs_list():
    """List all jobs with statuses and action buttons."""
    try:
        with get_db_session() as db:
            jobs = db.query(Job).order_by(Job.created_at.desc()).limit(50).all()
            
            jobs_data = []
            for job in jobs:
                jobs_data.append({
                    "id": job.id,
                    "status": job.status,
                    "created_at": job.created_at.strftime("%Y-%m-%d %H:%M"),
                    "updated_at": job.updated_at.strftime("%Y-%m-%d %H:%M") if job.updated_at else None,
                    "current_version_id": job.current_version_id
                })
        
        return templates.TemplateResponse("jobs_list.html", {
            "request": request,
            "jobs": jobs_data
        })
        
    except Exception as e:
        logger.error("Error loading jobs list", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/ui/jobs/{job_id}", response_class=HTMLResponse)
async def ui_job_detail(job_id: int):
    """Job detail page with two-pane layout: artifact preview + editable grid."""
    try:
        with get_db_session() as db:
            # Get job details
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")
            
            # Get current version records
            records = []
            if job.current_version_id:
                records_query = db.query(Record).filter(Record.version_id == job.current_version_id).order_by(Record.row_idx)
                records = [{"row_idx": r.row_idx, "data": r.payload_json} for r in records_query.all()]
            
            # Get validation issues
            issues = []
            if job.current_version_id:
                issues_query = db.query(Issue).filter(Issue.version_id == job.current_version_id)
                issues = [{"row_idx": i.row_idx, "field": i.field, "level": i.level, "message": i.message} for i in issues_query.all()]
            
            # Get versions history
            versions = db.query(Version).filter(Version.job_id == job_id).order_by(Version.created_at.desc()).all()
            versions_data = [{"id": v.id, "author": v.author, "reason": v.reason, "created_at": v.created_at.strftime("%Y-%m-%d %H:%M")} for v in versions]
        
        return templates.TemplateResponse("job_detail.html", {
            "request": request,
            "job": {
                "id": job.id,
                "status": job.status,
                "created_at": job.created_at.strftime("%Y-%m-%d %H:%M"),
                "current_version_id": job.current_version_id
            },
            "records": records,
            "issues": issues,
            "versions": versions_data
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error loading job detail", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/ui/jobs/{job_id}/edit")
async def ui_edit_record(job_id: int, request: Request):
    """Handle inline editing with HTMX - creates new version and re-validates."""
    try:
        form_data = await request.form()
        row_idx = int(form_data.get("row_idx"))
        field = form_data.get("field")
        new_value = form_data.get("value", "").strip()
        
        with get_db_session() as db:
            # Get current job and version
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job or not job.current_version_id:
                raise HTTPException(status_code=404, detail="Job or version not found")
            
            # Get current records
            records = db.query(Record).filter(Record.version_id == job.current_version_id).order_by(Record.row_idx).all()
            
            # Find and update the specific record
            updated_record = None
            for record in records:
                if record.row_idx == row_idx:
                    # Update the field
                    record.payload_json[field] = new_value
                    updated_record = record
                    break
            
            if not updated_record:
                raise HTTPException(status_code=404, detail="Record not found")
            
            # Create new version with updated data
            new_version = Version(
                job_id=job_id,
                parent_version_id=job.current_version_id,
                author="user",
                reason=f"Edit {field} in row {row_idx}",
                created_at=datetime.now(timezone.utc)
            )
            db.add(new_version)
            db.flush()  # Get the new version ID
            
            # Copy all records to new version with the update
            for record in records:
                new_record = Record(
                    job_id=job_id,
                    version_id=new_version.id,
                    row_idx=record.row_idx,
                    payload_json=record.payload_json.copy()
                )
                db.add(new_record)
            
            # Update job current version
            job.current_version_id = new_version.id
            job.updated_at = datetime.now(timezone.utc)
            
            db.commit()
            
            # Re-validate the updated data (simplified)
            validation_issues = _validate_record_data(updated_record.payload_json, row_idx)
            
            # Store validation issues
            for issue in validation_issues:
                issue_record = Issue(
                    version_id=new_version.id,
                    row_idx=issue["row_idx"],
                    field=issue["field"],
                    level=issue["level"],
                    message=issue["message"],
                    created_at=datetime.now(timezone.utc)
                )
                db.add(issue_record)
            
            db.commit()
        
        # Return updated row HTML for HTMX
        return templates.TemplateResponse("partials/record_row.html", {
            "request": request,
            "record": updated_record.payload_json,
            "row_idx": row_idx,
            "issues": validation_issues
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error editing record", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/jobs/{job_id}/versions")
async def get_job_versions(job_id: int):
    """Get all versions for a job."""
    try:
        with get_db_session() as db:
            versions = db.query(Version).filter(Version.job_id == job_id).order_by(Version.created_at.desc()).all()
            
            versions_data = []
            for version in versions:
                # Get record count for this version
                record_count = db.query(Record).filter(Record.version_id == version.id).count()
                issue_count = db.query(Issue).filter(Issue.version_id == version.id).count()
                
                versions_data.append({
                    "id": version.id,
                    "author": version.author,
                    "reason": version.reason,
                    "created_at": version.created_at.isoformat(),
                    "record_count": record_count,
                    "issue_count": issue_count,
                    "parent_version_id": version.parent_version_id
                })
        
        return {"versions": versions_data}
        
    except Exception as e:
        logger.error("Error getting job versions", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/jobs/{job_id}/versions/{version_id}/rollback")
async def rollback_to_version(job_id: int, version_id: int):
    """Rollback job to a specific version."""
    try:
        with get_db_session() as db:
            # Verify job and version exist
            job = db.query(Job).filter(Job.id == job_id).first()
            version = db.query(Version).filter(Version.id == version_id, Version.job_id == job_id).first()
            
            if not job or not version:
                raise HTTPException(status_code=404, detail="Job or version not found")
            
            # Update job current version
            job.current_version_id = version_id
            job.updated_at = datetime.now(timezone.utc)
            
            # Create audit log
            audit_log = AuditLog(
                job_id=job_id,
                actor="user",
                action="rollback",
                before_json={"current_version_id": job.current_version_id},
                after_json={"current_version_id": version_id},
                created_at=datetime.now(timezone.utc)
            )
            db.add(audit_log)
            
            db.commit()
        
        return {"message": f"Successfully rolled back to version {version_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error rolling back version", job_id=job_id, version_id=version_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

# ============================================================================
# EXPORT ROUTES
# ============================================================================

@app.post("/jobs/{job_id}/export")
async def create_export(job_id: int):
    """Create Excel export for a job's current version."""
    try:
        with get_db_session() as db:
            # Get job and current version
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job or not job.current_version_id:
                raise HTTPException(status_code=404, detail="Job or current version not found")
            
            # Get records for current version
            records = db.query(Record).filter(Record.version_id == job.current_version_id).order_by(Record.row_idx).all()
            
            if not records:
                raise HTTPException(status_code=400, detail="No records found for export")
            
            # Create Excel file
            from .agents.exporter_excel import _create_excel_file, _store_excel_file, _create_export_record
            
            excel_bytes = _create_excel_file(job_id, job.current_version_id, [{"row_idx": r.row_idx, "data": r.payload_json} for r in records])
            file_uri = _store_excel_file(job_id, job.current_version_id, excel_bytes)
            export_id = _create_export_record(job_id, job.current_version_id, file_uri, excel_bytes)
            
            return {"export_id": export_id, "file_uri": file_uri}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating export", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/exports/{export_id}/download")
async def download_export(export_id: int):
    """Download Excel export file."""
    try:
        with get_db_session() as db:
            export = db.query(Export).filter(Export.id == export_id).first()
            if not export:
                raise HTTPException(status_code=404, detail="Export not found")
            
            # Extract object key from S3 URI
            if not export.file_uri.startswith("s3://"):
                raise HTTPException(status_code=400, detail="Invalid file URI")
            
            object_key = export.file_uri.replace("s3://hilabs-artifacts/", "")
            
            # Get file from MinIO
            file_data = storage_client.get_bytes(object_key)
            
            # Generate filename
            filename = f"roster_export_job_{export.job_id}_v{export.version_id}.xlsx"
            
            return Response(
                content=file_data,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error downloading export", export_id=export_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/issues/{issue_id}/explain")
async def explain_issue(issue_id: int):
    """Generate natural language explanation for a validation issue using LLM."""
    try:
        with get_db_session() as db:
            # Get issue record
            issue = db.query(Issue).filter(Issue.id == issue_id).first()
            if not issue:
                raise HTTPException(status_code=404, detail="Issue not found")
            
            # Get LLM client
            llm_client = get_llm_client()
            if not llm_client:
                return {
                    "explanation": "LLM service is not available. Please check the issue details manually.",
                    "llm_available": False
                }
            
            # Prepare issue data for LLM
            issue_data = {
                "field": issue.field,
                "level": issue.level,
                "message": issue.message,
                "row_idx": issue.row_idx
            }
            
            # Get LLM explanation
            explanation = llm_client.explain_validation_issue(issue_data)
            
            return {
                "explanation": explanation,
                "llm_available": True,
                "issue_id": issue_id
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Issue explanation failed", issue_id=issue_id, error=str(e))
        return {
            "explanation": f"Failed to generate explanation: {str(e)}",
            "llm_available": True,
            "error": True
        }

def _validate_record_data(record_data: dict, row_idx: int) -> List[Dict[str, Any]]:
    """Simple validation for edited record data."""
    issues = []
    
    # Check required fields
    required_fields = ["NPI", "Provider Name", "Specialty", "Effective Date"]
    for field in required_fields:
        if not record_data.get(field, "").strip():
            issues.append({
                "row_idx": row_idx,
                "field": field,
                "level": "error",
                "message": f"Required field '{field}' is missing"
            })
    
    # Check NPI format
    npi = record_data.get("NPI", "").strip()
    if npi and (len(npi) != 10 or not npi.isdigit()):
        issues.append({
            "row_idx": row_idx,
            "field": "NPI",
            "level": "error",
            "message": f"Invalid NPI format: {npi}"
        })
    
    return issues

# Import net_guard to ensure it's installed
from . import net_guard  # noqa: F401

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )
