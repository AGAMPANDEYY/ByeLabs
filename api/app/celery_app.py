"""
Celery application configuration and setup.

This module provides the Celery instance for background task processing
in the HiLabs Roster Processing system.
"""

import os
from celery import Celery
from kombu import Queue
import structlog

from .config import settings

logger = structlog.get_logger(__name__)

# Create Celery instance
celery_app = Celery(
    "hilabs_roster",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.pipeline",
        "app.agents.intake_email",
        "app.agents.classifier", 
        "app.agents.extract_rule",
        "app.agents.extract_pdf",
        "app.agents.vlm_client",
        "app.agents.normalizer",
        "app.agents.validator",
        "app.agents.versioner",
        "app.agents.exporter_excel"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task routing and queues
    task_default_queue="default",
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("processing", routing_key="processing"),
        Queue("vlm", routing_key="vlm"),
        Queue("export", routing_key="export"),
    ),
    task_routes={
        "app.pipeline.process_job": {"queue": "processing"},
        "app.agents.vlm_client.*": {"queue": "vlm"},
        "app.agents.exporter_excel.*": {"queue": "export"},
    },
    
    # Task execution
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
    
    # Time limits
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3000,  # 50 minutes
    
    # Result backend
    result_expires=3600,  # 1 hour
    result_persistent=True,
    
    # Worker configuration
    worker_concurrency=2,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Error handling
    task_annotations={
        "*": {
            "rate_limit": "10/s",
            "time_limit": 3600,
            "soft_time_limit": 3000,
        }
    },
    
    # Beat schedule (for periodic tasks if needed)
    beat_schedule={
        # Example: cleanup old jobs every hour
        # "cleanup-old-jobs": {
        #     "task": "app.pipeline.cleanup_old_jobs",
        #     "schedule": 3600.0,  # 1 hour
        # },
    },
)

# Task base class with common functionality
class BaseTask(celery_app.Task):
    """Base task class with common functionality for all tasks."""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Called on task success."""
        logger.info(
            "Task completed successfully",
            task_id=task_id,
            task_name=self.name,
            args=args,
            kwargs=kwargs
        )
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called on task failure."""
        logger.error(
            "Task failed",
            task_id=task_id,
            task_name=self.name,
            args=args,
            kwargs=kwargs,
            error=str(exc),
            traceback=str(einfo)
        )
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Called on task retry."""
        logger.warning(
            "Task retrying",
            task_id=task_id,
            task_name=self.name,
            args=args,
            kwargs=kwargs,
            error=str(exc),
            retry_count=self.request.retries
        )

# Set the base task class
celery_app.Task = BaseTask

# Health check task
@celery_app.task(bind=True, name="app.pipeline.health_check")
def health_check(self):
    """Health check task to verify Celery is working."""
    logger.info("Celery health check task executed")
    return {
        "status": "healthy",
        "task_id": self.request.id,
        "worker": self.request.hostname,
        "timestamp": self.request.eta
    }

# Task to get worker status
@celery_app.task(name="app.pipeline.get_worker_status")
def get_worker_status():
    """Get current worker status and statistics."""
    try:
        # Get active workers
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        registered_tasks = inspect.registered()
        stats = inspect.stats()
        
        return {
            "active_workers": active_workers or {},
            "registered_tasks": registered_tasks or {},
            "worker_stats": stats or {},
            "total_workers": len(active_workers) if active_workers else 0
        }
    except Exception as e:
        logger.error("Failed to get worker status", error=str(e))
        return {"error": str(e)}

# Task to get queue lengths
@celery_app.task(name="app.pipeline.get_queue_lengths")
def get_queue_lengths():
    """Get current queue lengths."""
    try:
        inspect = celery_app.control.inspect()
        active_queues = inspect.active_queues()
        
        queue_lengths = {}
        if active_queues:
            for worker, queues in active_queues.items():
                for queue in queues:
                    queue_name = queue["name"]
                    if queue_name not in queue_lengths:
                        queue_lengths[queue_name] = 0
                    # Note: This is a simplified approach
                    # In production, you might want to use Redis or RabbitMQ management API
                    # to get actual queue lengths
        
        return {
            "queue_lengths": queue_lengths,
            "active_queues": active_queues or {}
        }
    except Exception as e:
        logger.error("Failed to get queue lengths", error=str(e))
        return {"error": str(e)}

# Initialize Celery
def init_celery():
    """Initialize Celery application."""
    logger.info("Initializing Celery application")
    
    # Test broker connection
    try:
        celery_app.control.inspect().ping()
        logger.info("Celery broker connection successful")
    except Exception as e:
        logger.error("Celery broker connection failed", error=str(e))
        raise
    
    logger.info("Celery application initialized successfully")

# Auto-initialize if not in testing mode
if not settings.app_env == "test":
    try:
        init_celery()
    except Exception as e:
        logger.warning(f"Celery initialization failed: {e}")
        logger.warning("Application will continue but background tasks may not work")
