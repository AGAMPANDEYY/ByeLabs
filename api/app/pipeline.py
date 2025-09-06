"""
Processing Pipeline

This module contains the main Celery task for processing jobs through the
multi-agent pipeline: Intake → Classifier → Extractor → Normalizer → Validator → Versioner → Exporter
"""

import time
from typing import Dict, Any
from sqlalchemy.orm import Session
from prometheus_client import Counter, Histogram
import structlog

from .celery_app import celery_app
from .db import get_db_session
from .models import Job, Version, Record, Issue, Export, JobStatus, IssueLevel
from .storage import storage_client, calculate_checksum, generate_object_key
from .orchestrator import run_graph, resume_graph

logger = structlog.get_logger(__name__)

# Prometheus metrics
PIPELINE_RUNS_TOTAL = Counter(
    "pipeline_runs_total", "Total pipeline runs", ["status"]
)
PIPELINE_LATENCY_SECONDS = Histogram(
    "pipeline_latency_seconds", "Pipeline execution latency"
)

@celery_app.task(bind=True, name="app.pipeline.process_job")
def process_job(self, job_id: int):
    """
    Process a job through the multi-agent pipeline.
    
    This is the main Celery task that orchestrates the entire processing pipeline:
    1. Intake Email - Parse and prepare email data
    2. Classifier - Determine processing strategy
    3. Extract Rule - Rule-based data extraction
    4. Extract PDF - PDF-specific extraction
    5. VLM Client - Vision Language Model processing (if needed)
    6. Normalizer - Data normalization
    7. Validator - Data validation
    8. Versioner - Create new version
    9. Exporter Excel - Generate Excel export
    
    Args:
        job_id: The job ID to process
    
    Returns:
        Processing result with status and metadata
    """
    start_time = time.time()
    task_id = self.request.id
    
    logger.info("Starting job processing pipeline", job_id=job_id, task_id=task_id)
    
    try:
        # Increment pipeline run counter
        PIPELINE_RUNS_TOTAL.labels(status="started").inc()
        
        # Initialize processing state
        state = {
            "job_id": job_id,
            "task_id": task_id,
            "start_time": start_time,
            "processing_notes": []
        }
        
        # Update job status to processing
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            job.status = JobStatus.PROCESSING
            db.commit()
        
        # Run the LangGraph orchestrator
        result = run_graph(job_id)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        result["processing_time"] = processing_time
        
        logger.info("Job processing pipeline completed", job_id=job_id, **result)
        
        # Increment success counter
        PIPELINE_RUNS_TOTAL.labels(status="completed").inc()
        
        return result
        
    except Exception as e:
        # Update job status to failed
        try:
            with get_db_session() as db:
                job = db.query(Job).filter(Job.id == job_id).first()
                if job:
                    job.status = JobStatus.FAILED
                    db.commit()
        except Exception as db_error:
            logger.error("Failed to update job status", job_id=job_id, error=str(db_error))
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        logger.error("Job processing pipeline failed", job_id=job_id, error=str(e), processing_time=processing_time)
        
        # Increment failure counter
        PIPELINE_RUNS_TOTAL.labels(status="failed").inc()
        
        raise Exception(f"Job processing failed: {str(e)}")
        
    finally:
        # Record pipeline latency
        duration = time.time() - start_time
        PIPELINE_LATENCY_SECONDS.observe(duration)

@celery_app.task(name="app.pipeline.cleanup_old_jobs")
def cleanup_old_jobs():
    """
    Cleanup old completed jobs and their associated data.
    
    This is a periodic task that removes old job data to prevent
    database bloat in long-running systems.
    """
    logger.info("Starting cleanup of old jobs")
    
    try:
        with get_db_session() as db:
            # Find old completed jobs (older than 30 days)
            from datetime import datetime, timezone, timedelta
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            
            old_jobs = db.query(Job).filter(
                Job.status.in_([JobStatus.READY, JobStatus.FAILED]),
                Job.updated_at < cutoff_date
            ).all()
            
            cleanup_count = 0
            for job in old_jobs:
                # Delete associated records, issues, exports
                db.query(Record).filter(Record.job_id == job.id).delete()
                db.query(Issue).filter(Issue.version_id.in_(
                    db.query(Version.id).filter(Version.job_id == job.id)
                )).delete()
                db.query(Export).filter(Export.job_id == job.id).delete()
                db.query(Version).filter(Version.job_id == job.id).delete()
                
                # Delete the job
                db.delete(job)
                cleanup_count += 1
            
            db.commit()
            
            logger.info("Cleanup completed", jobs_cleaned=cleanup_count)
            return {"jobs_cleaned": cleanup_count}
            
    except Exception as e:
        logger.error("Cleanup failed", error=str(e))
        raise

@celery_app.task(bind=True, name="app.pipeline.resume_job")
def resume_job(self, job_id: int, version_id: int):
    """
    Resume processing a job from a specific version.
    
    Args:
        job_id: The job ID to resume
        version_id: The version ID to resume from
    
    Returns:
        Processing result with status and metadata
    """
    start_time = time.time()
    task_id = self.request.id
    
    logger.info("Resuming job processing", job_id=job_id, version_id=version_id, task_id=task_id)
    
    try:
        # Update job status to processing
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            job.status = JobStatus.PROCESSING
            db.commit()
        
        # Resume the LangGraph orchestrator
        result = resume_graph(job_id, version_id)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        result["processing_time"] = processing_time
        
        logger.info("Job resume completed", job_id=job_id, **result)
        
        # Increment success counter
        PIPELINE_RUNS_TOTAL.labels(status="resumed").inc()
        
        return result
        
    except Exception as e:
        # Update job status to failed
        try:
            with get_db_session() as db:
                job = db.query(Job).filter(Job.id == job_id).first()
                if job:
                    job.status = JobStatus.FAILED
                    db.commit()
        except Exception as db_error:
            logger.error("Failed to update job status", job_id=job_id, error=str(db_error))
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        logger.error("Job resume failed", job_id=job_id, error=str(e), processing_time=processing_time)
        
        # Increment failure counter
        PIPELINE_RUNS_TOTAL.labels(status="failed").inc()
        
        raise Exception(f"Job resume failed: {str(e)}")

@celery_app.task(name="app.pipeline.get_pipeline_status")
def get_pipeline_status():
    """
    Get current pipeline status and statistics.
    
    Returns:
        Dictionary with pipeline status information
    """
    try:
        with get_db_session() as db:
            # Get job statistics
            total_jobs = db.query(Job).count()
            pending_jobs = db.query(Job).filter(Job.status == JobStatus.PENDING).count()
            processing_jobs = db.query(Job).filter(Job.status == JobStatus.PROCESSING).count()
            ready_jobs = db.query(Job).filter(Job.status == JobStatus.READY).count()
            failed_jobs = db.query(Job).filter(Job.status == JobStatus.FAILED).count()
            
            return {
                "total_jobs": total_jobs,
                "pending_jobs": pending_jobs,
                "processing_jobs": processing_jobs,
                "ready_jobs": ready_jobs,
                "failed_jobs": failed_jobs,
                "pipeline_healthy": True
            }
            
    except Exception as e:
        logger.error("Failed to get pipeline status", error=str(e))
        return {"error": str(e), "pipeline_healthy": False}
