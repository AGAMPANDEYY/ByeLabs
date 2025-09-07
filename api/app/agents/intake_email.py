"""
Intake Email Agent

This agent handles the initial email processing:
- Parse email headers and content using stdlib email
- Extract attachments and store in MinIO
- Identify document types
- Prepare data for downstream processing
"""

import time
import email
import email.policy
import mimetypes
import uuid
from typing import Dict, Any, List
from io import BytesIO
from ..metrics import get_agent_runs_total, get_agent_latency_seconds
import structlog

from ..db import get_db_session
from ..models import Email, Job
from ..storage import storage_client, calculate_checksum, generate_object_key

logger = structlog.get_logger(__name__)

# Metrics are now imported from metrics module

def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process email intake and prepare for classification.
    
    Args:
        state: Current processing state containing job_id, email data, etc.
    
    Returns:
        Updated state with parsed email information
    """
    start_time = time.time()
    agent_name = "intake_email"
    
    logger.info("Starting intake email agent", job_id=state.get("job_id"))
    
    try:
        # Increment run counter
        get_agent_runs_total().labels(agent=agent_name, status="started").inc()
        
        job_id = state.get("job_id")
        if not job_id:
            raise ValueError("job_id is required")
        
        # Get email record from database
        with get_db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            email_record = job.email
            if not email_record:
                raise ValueError(f"Email record not found for job {job_id}")
            
            # Get all needed data while still in session
            raw_uri = email_record.raw_uri
            message_id = email_record.message_id
            from_addr = email_record.from_addr
            to_addr = email_record.to_addr
            subject = email_record.subject
            received_at = email_record.received_at
        
        # Get raw email content from MinIO
        try:
            raw_content = storage_client.get_bytes(raw_uri.split('/', 1)[1])
        except Exception as e:
            raise Exception(f"Failed to retrieve raw email: {e}")
        
        # Parse email with stdlib email module
        try:
            email_message = email.message_from_bytes(raw_content, policy=email.policy.default)
        except Exception as e:
            raise Exception(f"Failed to parse email: {e}")
        
        # Extract email body content
        body_content = _extract_email_body(email_message)
        
        # Extract attachments
        attachments = []
        for part in email_message.walk():
            if part.get_content_disposition() == 'attachment':
                attachment_data = _process_attachment(part, job_id)
                if attachment_data:
                    attachments.append(attachment_data)
        
        # Create artifacts manifest
        artifacts = {
            "email_body": {
                "text": body_content.get("text", ""),
                "html": body_content.get("html", ""),
                "content_type": "text/plain" if body_content.get("text") else "text/html"
            },
            "attachments": attachments,
            "email_metadata": {
                "message_id": message_id,
                "from_addr": from_addr,
                "to_addr": to_addr,
                "subject": subject,
                "received_at": received_at.isoformat() if received_at else None
            }
        }
        
        # Update state with parsed information
        state.update({
            "email_parsed": True,
            "artifacts": artifacts,
            "processing_notes": state.get("processing_notes", []) + [
                f"Email parsed successfully",
                f"Found {len(attachments)} attachments",
                f"Body content: {len(body_content.get('text', ''))} chars text, {len(body_content.get('html', ''))} chars HTML"
            ]
        })
        
        logger.info("Intake email agent completed", 
                   job_id=job_id, 
                   attachments_count=len(attachments),
                   body_text_len=len(body_content.get("text", "")),
                   body_html_len=len(body_content.get("html", "")))
        
        return state
        
    except Exception as e:
        logger.error("Intake email agent failed", job_id=state.get("job_id"), error=str(e))
        state.update({
            "error": str(e),
            "failed_agent": agent_name
        })
        return state
        
    finally:
        # Record latency
        duration = time.time() - start_time
        get_agent_latency_seconds().labels(agent=agent_name).observe(duration)

def _extract_email_body(email_message) -> Dict[str, str]:
    """Extract text and HTML body from email message."""
    text_content = ""
    html_content = ""
    
    for part in email_message.walk():
        content_type = part.get_content_type()
        
        if content_type == "text/plain" and not text_content:
            try:
                text_content = part.get_content()
            except Exception:
                pass
        elif content_type == "text/html" and not html_content:
            try:
                html_content = part.get_content()
            except Exception:
                pass
    
    # If no explicit text/plain, try to get text from multipart/alternative
    if not text_content and not html_content:
        payload = email_message.get_payload()
        if isinstance(payload, str):
            text_content = payload
        elif isinstance(payload, list):
            for part in payload:
                if part.get_content_type() == "text/plain":
                    text_content = part.get_content()
                    break
                elif part.get_content_type() == "text/html":
                    html_content = part.get_content()
                    break
    
    return {
        "text": text_content,
        "html": html_content
    }

def _process_attachment(part, job_id: int) -> Dict[str, Any]:
    """Process an email attachment and store it in MinIO."""
    try:
        # Get attachment metadata
        filename = part.get_filename()
        if not filename:
            filename = f"attachment_{uuid.uuid4().hex[:8]}"
        
        content_type = part.get_content_type()
        content_disposition = part.get_content_disposition()
        
        # Get attachment content
        attachment_data = part.get_payload(decode=True)
        if not attachment_data:
            logger.warning("Empty attachment", filename=filename)
            return None
        
        # Generate storage key
        storage_key = generate_object_key("attachments", f"{job_id}/{filename}")
        
        # Store in MinIO
        try:
            uri = storage_client.put_bytes(
                key=storage_key,
                data=attachment_data,
                content_type=content_type
            )
        except Exception as e:
            logger.error("Failed to store attachment", filename=filename, error=str(e))
            return None
        
        # Calculate checksum
        checksum = calculate_checksum(attachment_data)
        
        return {
            "filename": filename,
            "content_type": content_type,
            "size": len(attachment_data),
            "uri": uri,
            "checksum": checksum,
            "storage_key": storage_key
        }
        
    except Exception as e:
        logger.error("Failed to process attachment", filename=filename, error=str(e))
        return None
