"""
SQLAlchemy ORM models for HiLabs Roster Processing.

This module defines all database tables and their relationships
for the roster processing system.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from enum import Enum

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, ForeignKey,
    Index, UniqueConstraint, CheckConstraint, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, validates
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

Base = declarative_base()


class JobStatus(str, Enum):
    """Job processing status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"
    FAILED = "failed"
    CANCELLED = "cancelled"


class IssueLevel(str, Enum):
    """Issue severity level enumeration."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Email(Base):
    """
    Email table - stores raw email metadata and references.
    
    This table stores metadata about incoming emails and references
    to the raw email content stored in MinIO.
    """
    __tablename__ = "emails"
    
    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    from_addr = Column(String(255), nullable=False, index=True)
    to_addr = Column(String(255), nullable=False)
    subject = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    raw_uri = Column(String(500), nullable=False)  # MinIO object URI
    hash = Column(String(64), nullable=False, index=True)  # SHA-256 hash of raw content
    
    # Relationships
    jobs = relationship("Job", back_populates="email", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_emails_received_at', 'received_at'),
        Index('idx_emails_from_addr', 'from_addr'),
    )
    
    def __repr__(self):
        return f"<Email(id={self.id}, message_id='{self.message_id}', from_addr='{self.from_addr}')>"


class Job(Base):
    """
    Job table - represents a processing job for an email.
    
    Each email can have multiple jobs (for reprocessing), but typically
    there's one job per email. Jobs track the overall processing status.
    """
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), nullable=False, default=JobStatus.PENDING.value, index=True)
    current_version_id = Column(Integer, ForeignKey("versions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, default=func.now(), onupdate=func.now())
    
    # Relationships
    email = relationship("Email", back_populates="jobs")
    current_version = relationship("Version", foreign_keys=[current_version_id], post_update=True)
    versions = relationship("Version", back_populates="job", foreign_keys="Version.job_id", cascade="all, delete-orphan")
    exports = relationship("Export", back_populates="job", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="job", cascade="all, delete-orphan")
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_jobs_status', 'status'),
        Index('idx_jobs_created_at', 'created_at'),
        Index('idx_jobs_updated_at', 'updated_at'),
        CheckConstraint("status IN ('pending', 'processing', 'needs_review', 'ready', 'failed', 'cancelled')", name='ck_jobs_status'),
    )
    
    def __repr__(self):
        return f"<Job(id={self.id}, email_id={self.email_id}, status='{self.status}')>"


class Version(Base):
    """
    Version table - represents a snapshot of processed data.
    
    Versions are append-only snapshots of the processed roster data.
    Each version can have a parent version for rollback capabilities.
    """
    __tablename__ = "versions"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    parent_version_id = Column(Integer, ForeignKey("versions.id", ondelete="SET NULL"), nullable=True)
    author = Column(String(100), nullable=False, default="system")  # system, user, api
    reason = Column(String(255), nullable=True)  # Description of changes
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Relationships
    job = relationship("Job", back_populates="versions", foreign_keys=[job_id])
    parent_version = relationship("Version", remote_side=[id], backref="child_versions")
    records = relationship("Record", back_populates="version", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="version", cascade="all, delete-orphan")
    exports = relationship("Export", back_populates="version")
    
    # Indexes
    __table_args__ = (
        Index('idx_versions_job_id', 'job_id'),
        Index('idx_versions_created_at', 'created_at'),
        Index('idx_versions_author', 'author'),
    )
    
    def __repr__(self):
        return f"<Version(id={self.id}, job_id={self.job_id}, author='{self.author}')>"


class Record(Base):
    """
    Record table - stores individual roster records for each version.
    
    Each record represents one provider's data in a specific version.
    The payload_json contains the actual roster data.
    """
    __tablename__ = "records"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    version_id = Column(Integer, ForeignKey("versions.id", ondelete="CASCADE"), nullable=False)
    row_idx = Column(Integer, nullable=False)  # Row index in the original data
    payload_json = Column(JSON, nullable=False)  # The actual roster data
    
    # Relationships
    job = relationship("Job")
    version = relationship("Version", back_populates="records")
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_records_job_id', 'job_id'),
        Index('idx_records_version_id', 'version_id'),
        Index('idx_records_row_idx', 'row_idx'),
        UniqueConstraint('version_id', 'row_idx', name='uq_records_version_row'),
    )
    
    def __repr__(self):
        return f"<Record(id={self.id}, job_id={self.job_id}, version_id={self.version_id}, row_idx={self.row_idx})>"
    
    @validates('payload_json')
    def validate_payload_json(self, key, value):
        """Validate that payload_json is a valid JSON object."""
        if not isinstance(value, dict):
            raise ValueError("payload_json must be a dictionary")
        return value


class Issue(Base):
    """
    Issue table - stores validation issues and warnings.
    
    Issues are attached to specific versions and can reference
    specific rows and fields for precise error reporting.
    """
    __tablename__ = "issues"
    
    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("versions.id", ondelete="CASCADE"), nullable=False)
    row_idx = Column(Integer, nullable=True)  # Row index (null for global issues)
    field = Column(String(100), nullable=True)  # Field name (null for row-level issues)
    level = Column(String(20), nullable=False, index=True)  # error, warning, info
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Relationships
    version = relationship("Version", back_populates="issues")
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_issues_version_id', 'version_id'),
        Index('idx_issues_level', 'level'),
        Index('idx_issues_row_idx', 'row_idx'),
        Index('idx_issues_field', 'field'),
        CheckConstraint("level IN ('error', 'warning', 'info')", name='ck_issues_level'),
    )
    
    def __repr__(self):
        return f"<Issue(id={self.id}, version_id={self.version_id}, level='{self.level}', message='{self.message[:50]}...')>"


class Export(Base):
    """
    Export table - stores references to exported Excel files.
    
    Each export is tied to a specific version and contains
    metadata about the exported file stored in MinIO.
    """
    __tablename__ = "exports"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    version_id = Column(Integer, ForeignKey("versions.id", ondelete="CASCADE"), nullable=False)
    file_uri = Column(String(500), nullable=False)  # MinIO object URI
    checksum = Column(String(64), nullable=False, index=True)  # SHA-256 hash of file
    file_size = Column(Integer, nullable=True)  # File size in bytes
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Relationships
    job = relationship("Job", back_populates="exports")
    version = relationship("Version", back_populates="exports")
    
    # Indexes
    __table_args__ = (
        Index('idx_exports_job_id', 'job_id'),
        Index('idx_exports_version_id', 'version_id'),
        Index('idx_exports_created_at', 'created_at'),
        Index('idx_exports_checksum', 'checksum'),
    )
    
    def __repr__(self):
        return f"<Export(id={self.id}, job_id={self.job_id}, version_id={self.version_id}, checksum='{self.checksum}')>"


class AuditLog(Base):
    """
    AuditLog table - tracks all changes for compliance and debugging.
    
    This table provides a complete audit trail of all changes
    made to jobs, versions, and records.
    """
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    actor = Column(String(100), nullable=False)  # user, system, api
    action = Column(String(50), nullable=False)  # create, update, delete, export, rollback
    before_json = Column(JSON, nullable=True)  # State before change
    after_json = Column(JSON, nullable=True)  # State after change
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    
    # Relationships
    job = relationship("Job", back_populates="audit_logs")
    
    # Indexes
    __table_args__ = (
        Index('idx_audit_logs_job_id', 'job_id'),
        Index('idx_audit_logs_actor', 'actor'),
        Index('idx_audit_logs_action', 'action'),
        Index('idx_audit_logs_created_at', 'created_at'),
    )
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, job_id={self.job_id}, actor='{self.actor}', action='{self.action}')>"


# Utility functions for working with models

def create_audit_log(
    session,
    job_id: int,
    actor: str,
    action: str,
    before_data: Optional[Dict[str, Any]] = None,
    after_data: Optional[Dict[str, Any]] = None
) -> AuditLog:
    """
    Create an audit log entry.
    
    Args:
        session: Database session
        job_id: Job ID
        actor: Who performed the action
        action: What action was performed
        before_data: State before the change
        after_data: State after the change
    
    Returns:
        Created AuditLog instance
    """
    audit_log = AuditLog(
        job_id=job_id,
        actor=actor,
        action=action,
        before_json=before_data,
        after_json=after_data
    )
    session.add(audit_log)
    return audit_log


def get_job_with_relations(session, job_id: int) -> Optional[Job]:
    """
    Get a job with all related data loaded.
    
    Args:
        session: Database session
        job_id: Job ID
    
    Returns:
        Job instance with relations loaded, or None if not found
    """
    return session.query(Job).filter(Job.id == job_id).first()


def get_latest_version(session, job_id: int) -> Optional[Version]:
    """
    Get the latest version for a job.
    
    Args:
        session: Database session
        job_id: Job ID
    
    Returns:
        Latest Version instance, or None if no versions exist
    """
    return session.query(Version).filter(
        Version.job_id == job_id
    ).order_by(Version.created_at.desc()).first()


def get_version_with_relations(session, version_id: int) -> Optional[Version]:
    """
    Get a version with all related data loaded.
    
    Args:
        session: Database session
        version_id: Version ID
    
    Returns:
        Version instance with relations loaded, or None if not found
    """
    return session.query(Version).filter(Version.id == version_id).first()
