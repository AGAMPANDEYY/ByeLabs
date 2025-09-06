"""
VLM Client Agent

This agent interfaces with the Vision Language Model:
- Send documents to VLM for processing
- Handle VLM responses and errors
- Fallback to rule-based extraction if VLM fails
"""

import time
import requests
from typing import Dict, Any, List
from prometheus_client import Counter, Histogram
import structlog

from ..config import settings

logger = structlog.get_logger(__name__)

# Prometheus metrics
AGENT_RUNS_TOTAL = Counter(
    "agent_runs_total", "Total agent runs", ["agent"]
)
AGENT_LATENCY_SECONDS = Histogram(
    "agent_latency_seconds", "Agent execution latency", ["agent"]
)
VLM_REQUESTS_TOTAL = Counter(
    "vlm_requests_total", "Total VLM requests", ["status"]
)
VLM_LATENCY_SECONDS = Histogram(
    "vlm_latency_seconds", "VLM request latency"
)

def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process documents using Vision Language Model.
    
    Args:
        state: Current processing state
    
    Returns:
        Updated state with VLM processing results
    """
    start_time = time.time()
    agent_name = "vlm_client"
    
    logger.info("Starting VLM client agent", job_id=state.get("job_id"))
    
    try:
        # Increment run counter
        AGENT_RUNS_TOTAL.labels(agent=agent_name).inc()
        
        # Check if VLM is enabled and required
        if not settings.vlm_enabled:
            logger.info("VLM disabled, skipping VLM processing", job_id=state.get("job_id"))
            state.update({
                "vlm_processing": False,
                "vlm_reason": "VLM disabled in configuration"
            })
            return state
        
        # Check if VLM is required based on classification
        classification = state.get("classification", {})
        if not classification.get("requires_vlm", False):
            logger.info("VLM not required, skipping VLM processing", job_id=state.get("job_id"))
            state.update({
                "vlm_processing": False,
                "vlm_reason": "VLM not required based on classification"
            })
            return state
        
        # Placeholder implementation
        # In a real implementation, this would:
        # 1. Prepare document data for VLM
        # 2. Send request to VLM service
        # 3. Handle VLM response and errors
        # 4. Process VLM output into structured data
        
        # Simulate VLM processing time
        time.sleep(1.0)
        
        # Generate placeholder VLM results
        vlm_data = {
            "extracted_data": [
                {
                    "row_idx": 0,
                    "data": {
                        "NPI": "1234567890",
                        "Provider Name": "John Doe, MD",
                        "Specialty": "Internal Medicine",
                        "Phone": "(555) 123-4567",
                        "Email": "john.doe@example.com",
                        "Address": "123 Main St, Anytown, ST 12345"
                    },
                    "confidence": 0.92,
                    "extraction_method": "vlm"
                }
            ],
            "vlm_metadata": {
                "model_used": "MiniCPM-V",
                "processing_time": 1.0,
                "confidence_threshold": 0.7
            }
        }
        
        # Update state with VLM results
        state.update({
            "vlm_processing": True,
            "vlm_data": vlm_data,
            "extraction_stats": {
                "vlm_rows_extracted": len(vlm_data["extracted_data"]),
                "vlm_confidence": vlm_data["extracted_data"][0]["confidence"] if vlm_data["extracted_data"] else 0
            },
            "processing_notes": state.get("processing_notes", []) + ["VLM processing completed"]
        })
        
        logger.info("VLM client agent completed", job_id=state.get("job_id"))
        
        return state
        
    except Exception as e:
        logger.error("VLM client agent failed", job_id=state.get("job_id"), error=str(e))
        state.update({
            "error": str(e),
            "failed_agent": agent_name,
            "vlm_processing": False,
            "vlm_fallback": True
        })
        return state
        
    finally:
        # Record latency
        duration = time.time() - start_time
        AGENT_LATENCY_SECONDS.labels(agent=agent_name).observe(duration)
