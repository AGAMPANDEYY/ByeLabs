"""
Observability and Metrics Module

This module provides comprehensive metrics collection for the HiLabs roster processing system:
- Per-agent metrics (runs, latency, errors)
- Pipeline-level metrics (VLM invocations, fallbacks, job processing)
- Structured logging with data masking
- Health check endpoints
"""

import time
import uuid
import re
from typing import Dict, Any, Optional, Callable
from functools import wraps
from prometheus_client import Counter, Histogram, Gauge, Info
import structlog

# ============================================================================
# PROMETHEUS METRICS
# ============================================================================

# Per-agent metrics
AGENT_RUNS_TOTAL = Counter(
    "agent_runs_total", 
    "Total agent runs", 
    ["agent", "status"]
)

AGENT_LATENCY_SECONDS = Histogram(
    "agent_latency_seconds", 
    "Agent execution latency in seconds", 
    ["agent"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0]
)

AGENT_ERRORS_TOTAL = Counter(
    "agent_errors_total",
    "Total agent errors",
    ["agent", "error_type"]
)

# Pipeline-level metrics
VLM_INVOCATIONS_TOTAL = Counter(
    "vlm_invocations_total",
    "Total VLM service invocations",
    ["model", "status"]
)

EXTRACT_FALLBACK_TOTAL = Counter(
    "extract_fallback_total",
    "Total extraction fallbacks",
    ["extractor", "fallback_type"]
)

PIPELINE_JOBS_PROCESSED_TOTAL = Counter(
    "pipeline_jobs_processed_total",
    "Total jobs processed by pipeline",
    ["status"]
)

PIPELINE_E2E_DURATION_SECONDS = Histogram(
    "pipeline_e2e_duration_seconds",
    "End-to-end pipeline processing duration",
    ["status"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1200.0]
)

# System metrics
ACTIVE_JOBS_GAUGE = Gauge(
    "active_jobs_total",
    "Number of currently active jobs"
)

SYSTEM_INFO = Info(
    "system_info",
    "System information"
)

# ============================================================================
# STRUCTURED LOGGING SETUP
# ============================================================================

def setup_structured_logging():
    """Configure structlog for JSON logging with data masking."""
    
    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        mask_sensitive_data,
        structlog.processors.JSONRenderer()
    ]
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

def mask_sensitive_data(logger, method_name, event_dict):
    """Mask sensitive data in log entries."""
    if isinstance(event_dict, dict):
        # Mask NPI numbers (10 digits)
        for key, value in event_dict.items():
            if isinstance(value, str):
                # Mask NPI patterns
                event_dict[key] = re.sub(r'\b\d{10}\b', 'NPI_****', value)
                # Mask phone numbers
                event_dict[key] = re.sub(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', 'PHONE_****', value)
                # Mask email addresses (keep domain)
                event_dict[key] = re.sub(r'\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b', r'***@\1', value)
    
    return event_dict

# ============================================================================
# METRICS DECORATORS AND UTILITIES
# ============================================================================

def track_agent_metrics(agent_name: str):
    """Decorator to track agent metrics (runs, latency, errors)."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            logger = structlog.get_logger(agent_name)
            
            # Extract job context for logging
            job_id = None
            version_id = None
            trace_id = None
            
            if args and isinstance(args[0], dict):
                state = args[0]
                job_id = state.get("job_id")
                version_id = state.get("version_id")
                trace_id = state.get("trace_id")
            
            # Start logging
            logger.info(
                "Agent started",
                agent=agent_name,
                job_id=job_id,
                version_id=version_id,
                trace_id=trace_id
            )
            
            try:
                # Increment run counter
                AGENT_RUNS_TOTAL.labels(agent=agent_name, status="started").inc()
                
                # Execute the function
                result = func(*args, **kwargs)
                
                # Record success
                AGENT_RUNS_TOTAL.labels(agent=agent_name, status="success").inc()
                
                # Log success
                logger.info(
                    "Agent completed successfully",
                    agent=agent_name,
                    job_id=job_id,
                    version_id=version_id,
                    trace_id=trace_id
                )
                
                return result
                
            except Exception as e:
                # Record error
                AGENT_RUNS_TOTAL.labels(agent=agent_name, status="error").inc()
                AGENT_ERRORS_TOTAL.labels(agent=agent_name, error_type=type(e).__name__).inc()
                
                # Log error
                logger.error(
                    "Agent failed",
                    agent=agent_name,
                    job_id=job_id,
                    version_id=version_id,
                    trace_id=trace_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                
                raise
                
            finally:
                # Record latency
                duration = time.time() - start_time
                AGENT_LATENCY_SECONDS.labels(agent=agent_name).observe(duration)
                
                # Log completion
                logger.info(
                    "Agent completed",
                    agent=agent_name,
                    job_id=job_id,
                    version_id=version_id,
                    trace_id=trace_id,
                    duration_seconds=duration
                )
        
        return wrapper
    return decorator

def track_pipeline_metrics():
    """Decorator to track pipeline-level metrics."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            logger = structlog.get_logger("pipeline")
            
            # Extract job context
            job_id = None
            if args and isinstance(args[0], dict):
                job_id = args[0].get("job_id")
            
            # Generate trace ID if not present
            trace_id = str(uuid.uuid4())
            if args and isinstance(args[0], dict):
                args[0]["trace_id"] = trace_id
            
            logger.info(
                "Pipeline started",
                job_id=job_id,
                trace_id=trace_id
            )
            
            try:
                # Execute the function
                result = func(*args, **kwargs)
                
                # Record success
                PIPELINE_JOBS_PROCESSED_TOTAL.labels(status="success").inc()
                
                logger.info(
                    "Pipeline completed successfully",
                    job_id=job_id,
                    trace_id=trace_id
                )
                
                return result
                
            except Exception as e:
                # Record error
                PIPELINE_JOBS_PROCESSED_TOTAL.labels(status="error").inc()
                
                logger.error(
                    "Pipeline failed",
                    job_id=job_id,
                    trace_id=trace_id,
                    error=str(e),
                    error_type=type(e).__name__
                )
                
                raise
                
            finally:
                # Record E2E duration
                duration = time.time() - start_time
                status = "success" if "result" in locals() else "error"
                PIPELINE_E2E_DURATION_SECONDS.labels(status=status).observe(duration)
                
                logger.info(
                    "Pipeline completed",
                    job_id=job_id,
                    trace_id=trace_id,
                    duration_seconds=duration,
                    status=status
                )
        
        return wrapper
    return decorator

# ============================================================================
# VLM METRICS
# ============================================================================

def track_vlm_invocation(model: str, status: str = "success"):
    """Track VLM service invocation."""
    VLM_INVOCATIONS_TOTAL.labels(model=model, status=status).inc()
    
    logger = structlog.get_logger("vlm")
    logger.info(
        "VLM invocation tracked",
        model=model,
        status=status
    )

def track_extract_fallback(extractor: str, fallback_type: str):
    """Track extraction fallback usage."""
    EXTRACT_FALLBACK_TOTAL.labels(extractor=extractor, fallback_type=fallback_type).inc()
    
    logger = structlog.get_logger("extractor")
    logger.info(
        "Extraction fallback tracked",
        extractor=extractor,
        fallback_type=fallback_type
    )

# ============================================================================
# SYSTEM METRICS
# ============================================================================

def update_active_jobs_count(count: int):
    """Update the active jobs gauge."""
    ACTIVE_JOBS_GAUGE.set(count)

def set_system_info(version: str, build_date: str, git_commit: str = "unknown"):
    """Set system information."""
    SYSTEM_INFO.info({
        "version": version,
        "build_date": build_date,
        "git_commit": git_commit,
        "component": "hilabs-roster-processing"
    })

# ============================================================================
# LOGGING UTILITIES
# ============================================================================

def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger with proper configuration."""
    return structlog.get_logger(name)

def log_job_event(event: str, job_id: int, **kwargs):
    """Log a job-related event with proper context."""
    logger = structlog.get_logger("job")
    logger.info(event, job_id=job_id, **kwargs)

def log_version_event(event: str, job_id: int, version_id: int, **kwargs):
    """Log a version-related event with proper context."""
    logger = structlog.get_logger("version")
    logger.info(event, job_id=job_id, version_id=version_id, **kwargs)

# Initialize structured logging
setup_structured_logging()
