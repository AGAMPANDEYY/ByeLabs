"""
Classifier Agent

This agent classifies documents and determines processing strategy:
- Identify document types (HTML_TABLE, XLSX, CSV, PDF_NATIVE, PDF_SCANNED, PLAIN_TEXT)
- Determine extraction method (rule-based vs VLM)
- Set processing parameters
"""

import time
import re
from typing import Dict, Any, List
from prometheus_client import Counter, Histogram
import structlog

logger = structlog.get_logger(__name__)

# Prometheus metrics
AGENT_RUNS_TOTAL = Counter(
    "agent_runs_total", "Total agent runs", ["agent"]
)
AGENT_LATENCY_SECONDS = Histogram(
    "agent_latency_seconds", "Agent execution latency", ["agent"]
)

def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Classify documents and determine processing strategy.
    
    Args:
        state: Current processing state
    
    Returns:
        Updated state with classification results
    """
    start_time = time.time()
    agent_name = "classifier"
    
    logger.info("Starting classifier agent", job_id=state.get("job_id"))
    
    try:
        # Increment run counter
        AGENT_RUNS_TOTAL.labels(agent=agent_name).inc()
        
        artifacts = state.get("artifacts", {})
        if not artifacts:
            raise ValueError("No artifacts found in state")
        
        # Classify each artifact
        classified_artifacts = []
        
        # Classify email body
        email_body = artifacts.get("email_body", {})
        if email_body:
            body_classification = _classify_email_body(email_body)
            if body_classification:
                classified_artifacts.append(body_classification)
        
        # Classify attachments
        attachments = artifacts.get("attachments", [])
        for attachment in attachments:
            attachment_classification = _classify_attachment(attachment)
            if attachment_classification:
                classified_artifacts.append(attachment_classification)
        
        # Determine overall processing strategy
        processing_strategy = _determine_processing_strategy(classified_artifacts)
        
        # Update state with classification results
        state.update({
            "classification": {
                "artifacts": classified_artifacts,
                "strategy": processing_strategy,
                "requires_vlm": processing_strategy.get("requires_vlm", False),
                "extraction_method": processing_strategy.get("extraction_method", "rule_based"),
                "confidence": processing_strategy.get("confidence", 0.8),
                "processing_params": processing_strategy.get("processing_params", {})
            },
            "processing_notes": state.get("processing_notes", []) + [
                f"Classified {len(classified_artifacts)} artifacts",
                f"Strategy: {processing_strategy.get('extraction_method', 'unknown')}",
                f"VLM required: {processing_strategy.get('requires_vlm', False)}"
            ]
        })
        
        logger.info("Classifier agent completed", 
                   job_id=state.get("job_id"),
                   artifacts_count=len(classified_artifacts),
                   requires_vlm=processing_strategy.get("requires_vlm", False))
        
        return state
        
    except Exception as e:
        logger.error("Classifier agent failed", job_id=state.get("job_id"), error=str(e))
        state.update({
            "error": str(e),
            "failed_agent": agent_name
        })
        return state
        
    finally:
        # Record latency
        duration = time.time() - start_time
        AGENT_LATENCY_SECONDS.labels(agent=agent_name).observe(duration)

def _classify_email_body(email_body: Dict[str, Any]) -> Dict[str, Any]:
    """Classify email body content."""
    html_content = email_body.get("html", "")
    text_content = email_body.get("text", "")
    
    # Check for HTML table
    if html_content and "<table" in html_content.lower():
        return {
            "type": "email_body",
            "document_type": "HTML_TABLE",
            "content": html_content,
            "confidence": 0.9,
            "extraction_method": "rule_based",
            "metadata": {
                "has_html": True,
                "has_text": bool(text_content),
                "table_count": html_content.lower().count("<table")
            }
        }
    
    # Check for plain text with potential table structure
    if text_content:
        # Look for tabular patterns (multiple spaces, tabs, or pipe separators)
        lines = text_content.split('\n')
        tabular_lines = 0
        for line in lines:
            if re.search(r'\s{2,}|\t|\|', line.strip()):
                tabular_lines += 1
        
        if tabular_lines > 2:  # At least 3 lines with tabular structure
            return {
                "type": "email_body",
                "document_type": "PLAIN_TEXT",
                "content": text_content,
                "confidence": 0.7,
                "extraction_method": "rule_based",
                "metadata": {
                    "has_html": bool(html_content),
                    "has_text": True,
                    "tabular_lines": tabular_lines,
                    "total_lines": len(lines)
                }
            }
    
    # Default to plain text
    return {
        "type": "email_body",
        "document_type": "PLAIN_TEXT",
        "content": text_content or html_content,
        "confidence": 0.5,
        "extraction_method": "rule_based",
        "metadata": {
            "has_html": bool(html_content),
            "has_text": bool(text_content)
        }
    }

def _classify_attachment(attachment: Dict[str, Any]) -> Dict[str, Any]:
    """Classify an attachment based on filename and content type."""
    filename = attachment.get("filename", "").lower()
    content_type = attachment.get("content_type", "").lower()
    size = attachment.get("size", 0)
    
    # Classify by file extension and MIME type
    if filename.endswith(('.xlsx', '.xls')) or 'spreadsheet' in content_type:
        return {
            "type": "attachment",
            "document_type": "XLSX",
            "filename": attachment.get("filename"),
            "content_type": content_type,
            "size": size,
            "uri": attachment.get("uri"),
            "confidence": 0.95,
            "extraction_method": "rule_based",
            "metadata": {
                "file_extension": filename.split('.')[-1] if '.' in filename else None
            }
        }
    
    elif filename.endswith('.csv') or 'csv' in content_type:
        return {
            "type": "attachment",
            "document_type": "CSV",
            "filename": attachment.get("filename"),
            "content_type": content_type,
            "size": size,
            "uri": attachment.get("uri"),
            "confidence": 0.95,
            "extraction_method": "rule_based",
            "metadata": {
                "file_extension": "csv"
            }
        }
    
    elif filename.endswith('.pdf') or 'pdf' in content_type:
        # For PDFs, we need to determine if they're native or scanned
        # This will be done in the extract_pdf agent
        return {
            "type": "attachment",
            "document_type": "PDF_UNKNOWN",  # Will be refined in extract_pdf
            "filename": attachment.get("filename"),
            "content_type": content_type,
            "size": size,
            "uri": attachment.get("uri"),
            "confidence": 0.9,
            "extraction_method": "rule_based",  # Will be refined
            "metadata": {
                "file_extension": "pdf",
                "needs_pdf_analysis": True
            }
        }
    
    elif filename.endswith(('.html', '.htm')) or 'html' in content_type:
        return {
            "type": "attachment",
            "document_type": "HTML_TABLE",
            "filename": attachment.get("filename"),
            "content_type": content_type,
            "size": size,
            "uri": attachment.get("uri"),
            "confidence": 0.9,
            "extraction_method": "rule_based",
            "metadata": {
                "file_extension": filename.split('.')[-1] if '.' in filename else None
            }
        }
    
    elif filename.endswith(('.txt', '.text')) or 'text/plain' in content_type:
        return {
            "type": "attachment",
            "document_type": "PLAIN_TEXT",
            "filename": attachment.get("filename"),
            "content_type": content_type,
            "size": size,
            "uri": attachment.get("uri"),
            "confidence": 0.8,
            "extraction_method": "rule_based",
            "metadata": {
                "file_extension": "txt"
            }
        }
    
    else:
        # Unknown file type - might need VLM
        return {
            "type": "attachment",
            "document_type": "UNKNOWN",
            "filename": attachment.get("filename"),
            "content_type": content_type,
            "size": size,
            "uri": attachment.get("uri"),
            "confidence": 0.3,
            "extraction_method": "vlm_assisted",
            "metadata": {
                "file_extension": filename.split('.')[-1] if '.' in filename else None,
                "unknown_type": True
            }
        }

def _determine_processing_strategy(classified_artifacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Determine overall processing strategy based on classified artifacts."""
    if not classified_artifacts:
        return {
            "extraction_method": "rule_based",
            "requires_vlm": False,
            "confidence": 0.0,
            "processing_params": {}
        }
    
    # Count document types
    doc_types = [artifact.get("document_type") for artifact in classified_artifacts]
    requires_vlm = any(artifact.get("extraction_method") == "vlm_assisted" for artifact in classified_artifacts)
    
    # Check for PDFs that need analysis
    has_pdf_unknown = any(dt == "PDF_UNKNOWN" for dt in doc_types)
    
    # Determine extraction method
    if requires_vlm or has_pdf_unknown:
        extraction_method = "vlm_assisted"
        confidence = 0.7
    else:
        extraction_method = "rule_based"
        confidence = 0.9
    
    # Set processing parameters
    processing_params = {
        "max_pages": 10,
        "confidence_threshold": 0.7,
        "document_types": doc_types,
        "artifact_count": len(classified_artifacts)
    }
    
    return {
        "extraction_method": extraction_method,
        "requires_vlm": requires_vlm or has_pdf_unknown,
        "confidence": confidence,
        "processing_params": processing_params
    }