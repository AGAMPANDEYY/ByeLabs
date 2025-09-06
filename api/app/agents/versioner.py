"""
Versioner Agent

This agent manages data versions:
- Create new versions with validated data
- Handle version rollbacks
- Maintain version history and audit trail
"""

import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from ..db import get_db_session
from ..models import Job, Version, Record, Issue, AuditLog, JobStatus, IssueLevel
from ..metrics import track_agent_metrics, get_logger

logger = get_logger(__name__)

@track_agent_metrics("versioner")
def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create new version with validated data.
    
    Args:
        state: Current processing state with validated data
    
    Returns:
        Updated state with version information
    """
    logger.info("Starting versioner agent", job_id=state.get("job_id"))
    
    try:
        
        job_id = state.get("job_id")
        if not job_id:
            raise ValueError("Job ID is required for versioning")
        
        # Get validated data
        rows = state.get("rows", [])
        validation_issues = state.get("validation_issues", [])
        validation_stats = state.get("validation_stats", {})
        
        # Create version in database
        version_id = _create_version(
            job_id=job_id,
            author=state.get("author", "system"),
            reason=state.get("reason", "auto extract"),
            parent_version_id=state.get("parent_version_id")
        )
        
        # Store records
        records_created = _store_records(version_id, job_id, rows)
        
        # Store issues
        issues_created = _store_issues(version_id, validation_issues)
        
        # Update job current version
        _update_job_version(job_id, version_id, validation_stats)
        
        # Create audit log
        _create_audit_log(job_id, version_id, "version_created", {
            "version_id": version_id,
            "author": state.get("author", "system"),
            "reason": state.get("reason", "auto extract"),
            "record_count": records_created,
            "issue_count": issues_created
        })
        
        # Update state with version information
        state.update({
            "version_id": version_id,
            "version_created": True,
            "records_created": records_created,
            "issues_created": issues_created,
            "processing_notes": state.get("processing_notes", []) + [
                f"Version {version_id} created with {records_created} records and {issues_created} issues"
            ]
        })
        
        logger.info("Versioner agent completed", 
                   job_id=job_id,
                   version_id=version_id,
                   records=records_created,
                   issues=issues_created)
        
        return state
        
    except Exception as e:
        logger.error("Versioner agent failed", job_id=state.get("job_id"), error=str(e))
        state.update({
            "error": str(e),
            "failed_agent": "versioner"
        })
        return state

def _create_version(job_id: int, author: str, reason: str, parent_version_id: Optional[int] = None) -> int:
    """Create a new version record in the database."""
    with get_db_session() as db:
        version = Version(
            job_id=job_id,
            parent_version_id=parent_version_id,
            author=author,
            reason=reason,
            created_at=datetime.now(timezone.utc)
        )
        db.add(version)
        db.commit()
        db.refresh(version)
        return version.id

def _store_records(version_id: int, job_id: int, rows: List[Dict[str, Any]]) -> int:
    """Store validated rows as records in the database."""
    records_created = 0
    
    with get_db_session() as db:
        for row in rows:
            record = Record(
                job_id=job_id,
                version_id=version_id,
                row_idx=row.get("row_idx", 0),
                payload_json=row.get("data", {})
            )
            db.add(record)
            records_created += 1
        
        db.commit()
    
    return records_created

def _store_issues(version_id: int, validation_issues: List[Dict[str, Any]]) -> int:
    """Store validation issues in the database."""
    issues_created = 0
    
    with get_db_session() as db:
        for issue in validation_issues:
            issue_record = Issue(
                version_id=version_id,
                row_idx=issue.get("row_idx", 0),
                field=issue.get("field", ""),
                level=IssueLevel(issue.get("level", "warning")),
                message=issue.get("message", ""),
                created_at=datetime.now(timezone.utc)
            )
            db.add(issue_record)
            issues_created += 1
        
        db.commit()
    
    return issues_created

def _update_job_version(job_id: int, version_id: int, validation_stats: Dict[str, Any]):
    """Update job's current version and status."""
    with get_db_session() as db:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.current_version_id = version_id
            job.updated_at = datetime.now(timezone.utc)
            
            # Update job status based on validation results
            error_count = validation_stats.get("error_count", 0)
            if error_count > 0:
                job.status = JobStatus.NEEDS_REVIEW
            else:
                job.status = JobStatus.COMPLETED
            
            db.commit()

def _create_audit_log(job_id: int, version_id: int, action: str, details: Dict[str, Any]):
    """Create audit log entry."""
    with get_db_session() as db:
        audit_log = AuditLog(
            job_id=job_id,
            actor="system",
            action=action,
            before_json=None,
            after_json=details,
            created_at=datetime.now(timezone.utc)
        )
        db.add(audit_log)
        db.commit()
