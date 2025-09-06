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
import hashlib
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, Request, Response, UploadFile, File, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import structlog
from sqlalchemy.orm import Session

from .config import settings
from .net_guard import test_egress_guard, test_local_requests
from .db import init_database, check_database_connection, get_database_info, get_db
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

# Prometheus metrics
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

ACTIVE_CONNECTIONS = Counter(
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
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check endpoint.
    
    Returns whether the application is ready to serve requests.
    """
    # TODO: Check database connectivity
    # TODO: Check MinIO connectivity
    # TODO: Check RabbitMQ connectivity
    # TODO: Check VLM service connectivity
    
    return {
        "status": "ready",
        "timestamp": time.time(),
        "checks": {
            "database": "ready",  # TODO: Implement actual check
            "storage": "ready",   # TODO: Implement actual check
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
            email_message = email.message_from_bytes(content, policy=email.policy.default)
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
            status=JobStatus.PENDING
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
        
        return {
            "id": job.id,
            "status": job.status,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "email": email_info,
            "current_version": current_version_info,
            "issues_summary": issues_summary,
            "artifacts": artifacts,
            "versions": versions
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting job details", job_id=job_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


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
