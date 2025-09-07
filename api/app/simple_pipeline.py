#!/usr/bin/env python3
"""
Simple Pipeline - No LangGraph, just sequential agent execution
This is much more reliable and easier to debug
"""

import time
import structlog
from typing import Dict, Any, List
from .agents.intake_email import run as intake_email_run
from .agents.classifier import run as classifier_run
from .agents.extract_rule import run as extract_rule_run
from .agents.extract_pdf import run as extract_pdf_run
from .agents.normalizer import run as normalizer_run
from .agents.validator import run as validator_run
from .agents.versioner import run as versioner_run
from .agents.exporter_excel import run as exporter_excel_run
# from .agents.vlm_client import run as vlm_client_run  # Not needed for basic processing

logger = structlog.get_logger(__name__)

def process_job_simple(job_id: int) -> Dict[str, Any]:
    """
    Simple sequential pipeline - no LangGraph complexity
    Just run agents one after another with proper error handling
    """
    logger.info("Starting simple job processing pipeline", job_id=job_id)
    start_time = time.time()
    
    # Initialize state as a simple dictionary
    state = {
        "job_id": job_id,
        "version_id": None,
        "artifacts": {},
        "route_map": {},
        "rows": [],
        "needs_vlm": False,
        "vlm_used": False,
        "force_vlm_toggle": False,
        "issues": [],
        "status": "processing",
        "processing_notes": [],
        "start_time": start_time,
        "checkpoint_data": {},
        "error": None,
        "failed_agent": None
    }
    
    try:
        # Step 1: Intake Email
        logger.info("Step 1: Intake Email", job_id=job_id)
        state = intake_email_run(state)
        if state.get("error"):
            raise Exception(f"Intake failed: {state['error']}")
        
        # Step 2: Classify Document
        logger.info("Step 2: Classify Document", job_id=job_id)
        state = classifier_run(state)
        if state.get("error"):
            raise Exception(f"Classification failed: {state['error']}")
        
        # Step 3: Extract Data (Rule-based)
        logger.info("Step 3: Extract Data (Rule-based)", job_id=job_id)
        state = extract_rule_run(state)
        if state.get("error"):
            raise Exception(f"Rule extraction failed: {state['error']}")
        
        # Copy extracted_data to rows for versioner
        if "extracted_data" in state:
            state["rows"] = state["extracted_data"]
        
        # Step 4: Extract PDF (if needed)
        if state.get("route_map", {}).get("type") in ["PDF_NATIVE", "PDF_SCANNED"]:
            logger.info("Step 4: Extract PDF", job_id=job_id)
            state = extract_pdf_run(state)
            if state.get("error"):
                logger.warning("PDF extraction failed, continuing with rule-based data", 
                             job_id=job_id, error=state["error"])
                # Don't fail the pipeline, just continue with what we have
            else:
                # Copy PDF extracted_data to rows for versioner
                if "extracted_data" in state:
                    state["rows"] = state["extracted_data"]
        
        # Step 5: VLM Assist (skip entirely for now - not needed for basic email processing)
        logger.info("Step 5: Skipping VLM Assist (not needed for basic processing)", job_id=job_id)
        
        # Step 6: Normalize Data
        logger.info("Step 6: Normalize Data", job_id=job_id)
        state = normalizer_run(state)
        if state.get("error"):
            raise Exception(f"Normalization failed: {state['error']}")
        
        # Step 7: Validate Data
        logger.info("Step 7: Validate Data", job_id=job_id)
        state = validator_run(state)
        if state.get("error"):
            raise Exception(f"Validation failed: {state['error']}")
        
        # Step 8: Create Version
        logger.info("Step 8: Create Version", job_id=job_id)
        state = versioner_run(state)
        if state.get("error"):
            raise Exception(f"Versioning failed: {state['error']}")
        
        # Step 9: Export Excel
        logger.info("Step 9: Export Excel", job_id=job_id)
        state = exporter_excel_run(state)
        if state.get("error"):
            raise Exception(f"Export failed: {state['error']}")
        
        # Success!
        state["status"] = "ready"
        processing_time = time.time() - start_time
        
        logger.info("Simple pipeline completed successfully", 
                   job_id=job_id, 
                   processing_time=processing_time,
                   rows_count=len(state.get("rows", [])),
                   issues_count=len(state.get("issues", [])),
                   version_id=state.get("version_id"))
        
        return {
            "job_id": job_id,
            "status": "ready",
            "version_id": state.get("version_id"),
            "rows_processed": len(state.get("rows", [])),
            "issues_found": len(state.get("issues", [])),
            "vlm_used": state.get("vlm_used", False),
            "processing_notes": state.get("processing_notes", []),
            "processing_time": processing_time
        }
        
    except Exception as e:
        processing_time = time.time() - start_time
        error_msg = str(e)
        
        logger.error("Simple pipeline failed", 
                    job_id=job_id, 
                    error=error_msg,
                    failed_agent=state.get("failed_agent"),
                    processing_time=processing_time)
        
        return {
            "job_id": job_id,
            "status": "failed",
            "error": error_msg,
            "failed_agent": state.get("failed_agent"),
            "processing_time": processing_time
        }

def resume_job_simple(job_id: int, from_step: str = "validate") -> Dict[str, Any]:
    """
    Resume job from a specific step - much simpler than LangGraph
    """
    logger.info("Resuming simple job processing", job_id=job_id, from_step=from_step)
    
    # For now, just run the full pipeline
    # In a more sophisticated version, we could load the state from database
    # and resume from the specific step
    return process_job_simple(job_id)
