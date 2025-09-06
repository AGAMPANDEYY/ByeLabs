"""
VLM Client Agent

This agent interfaces with the Vision Language Model:
- Send documents to VLM for processing
- Handle VLM responses and errors
- Fallback to rule-based extraction if VLM fails
"""

import time
import json
import requests
from typing import Dict, Any, List

from ..config import settings
from ..storage import storage_client
from ..metrics import track_agent_metrics, track_vlm_invocation, get_logger

logger = get_logger(__name__)
@track_agent_metrics("vlm_client")
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
        
        # Check if VLM is required based on classification or force toggle
        classification = state.get("classification", {})
        needs_vlm = classification.get("requires_vlm", False)
        force_vlm = state.get("force_vlm_toggle", False)
        
        if not needs_vlm and not force_vlm:
            logger.info("VLM not required, skipping VLM processing", job_id=state.get("job_id"))
            state.update({
                "vlm_processing": False,
                "vlm_reason": "VLM not required based on classification"
            })
            return state
        
        # Get VLM inputs from previous agents
        vlm_inputs = state.get("vlm_inputs", [])
        if not vlm_inputs:
            logger.warning("No VLM inputs found, skipping VLM processing")
            state.update({
                "vlm_processing": False,
                "vlm_reason": "No VLM inputs available"
            })
            return state
        
        # Define schema for roster data
        schema = [
            "NPI",
            "Provider Name", 
            "Specialty",
            "Phone",
            "Email",
            "Address"
        ]
        
        # Process each VLM input
        vlm_extracted_data = []
        vlm_metadata = {
            "total_inputs": len(vlm_inputs),
            "successful_extractions": 0,
            "failed_extractions": 0,
            "methods_used": [],
            "total_processing_time": 0
        }
        
        for vlm_input in vlm_inputs:
            try:
                result = _process_vlm_input(vlm_input, schema)
                if result:
                    vlm_extracted_data.extend(result["rows"])
                    vlm_metadata["successful_extractions"] += 1
                    vlm_metadata["methods_used"].append(result["method"])
                    vlm_metadata["total_processing_time"] += result["processing_time"]
                    
                    # Track VLM invocation
                    track_vlm_invocation(result.get("method", "unknown"), "success")
                else:
                    vlm_metadata["failed_extractions"] += 1
                    
            except Exception as e:
                logger.error("VLM input processing failed", 
                           input_type=vlm_input.get("type"),
                           error=str(e))
                vlm_metadata["failed_extractions"] += 1
        
        # Merge with existing extracted data (prefer higher coverage)
        existing_data = state.get("extracted_data", [])
        merged_data = _merge_extraction_results(existing_data, vlm_extracted_data)
        
        # Update state with VLM results
        state.update({
            "vlm_processing": True,
            "vlm_used": True,
            "extracted_data": merged_data,
            "vlm_data": {
                "extracted_data": vlm_extracted_data,
                "metadata": vlm_metadata
            },
            "extraction_stats": {
                "total_rows": len(merged_data),
                "vlm_rows": len(vlm_extracted_data),
                "rule_based_rows": len(existing_data),
                "vlm_success_rate": vlm_metadata["successful_extractions"] / vlm_metadata["total_inputs"] if vlm_metadata["total_inputs"] > 0 else 0
            },
            "processing_notes": state.get("processing_notes", []) + [
                f"VLM processing completed: {len(vlm_extracted_data)} rows extracted",
                f"VLM success rate: {vlm_metadata['successful_extractions']}/{vlm_metadata['total_inputs']}"
            ]
        })
        
        logger.info("VLM client agent completed", 
                   job_id=state.get("job_id"),
                   vlm_rows=len(vlm_extracted_data),
                   total_rows=len(merged_data))
        
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

def _process_vlm_input(vlm_input: Dict[str, Any], schema: List[str]) -> Dict[str, Any]:
    """Process a single VLM input (page image or PDF)."""
    try:
        vlm_start_time = time.time()
        
        # Get file content from MinIO
        uri = vlm_input.get("uri", "")
        if not uri:
            raise ValueError("No URI provided for VLM input")
        
        file_content = storage_client.get_bytes(uri.split('/', 1)[1])
        
        # Prepare request to VLM service
        files = {
            "file": ("input", file_content, "application/octet-stream")
        }
        data = {
            "schema": json.dumps(schema)
        }
        
        # Send request to VLM service with timeout and retries
        max_retries = 3
        timeout = settings.vlm_timeout_seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    f"{settings.vlm_url}/infer",
                    files=files,
                    data=data,
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    vlm_latency = time.time() - vlm_start_time
                    VLM_LATENCY_SECONDS.observe(vlm_latency)
                    VLM_REQUESTS_TOTAL.labels(status="success").inc()
                    
                    return {
                        "rows": result.get("rows", []),
                        "method": result.get("method", "unknown"),
                        "confidence": result.get("confidence", 0.0),
                        "processing_time": result.get("processing_time", vlm_latency)
                    }
                else:
                    logger.warning(f"VLM request failed with status {response.status_code}", 
                                 attempt=attempt + 1)
                    
            except requests.exceptions.Timeout:
                logger.warning(f"VLM request timeout", attempt=attempt + 1)
            except requests.exceptions.ConnectionError:
                logger.warning(f"VLM connection error", attempt=attempt + 1)
            except Exception as e:
                logger.warning(f"VLM request error: {e}", attempt=attempt + 1)
        
        # All retries failed
        VLM_REQUESTS_TOTAL.labels(status="failed").inc()
        logger.error("VLM processing failed after all retries")
        return None
        
    except Exception as e:
        logger.error(f"VLM input processing failed: {e}")
        VLM_REQUESTS_TOTAL.labels(status="error").inc()
        return None

def _merge_extraction_results(rule_based_data: List[Dict[str, Any]], vlm_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge rule-based and VLM extraction results, preferring higher coverage."""
    if not vlm_data:
        return rule_based_data
    
    if not rule_based_data:
        return vlm_data
    
    # Simple merging strategy: prefer VLM data if it has more rows
    # In a more sophisticated implementation, you might:
    # - Compare confidence scores
    # - Merge non-overlapping data
    # - Use VLM to fill gaps in rule-based extraction
    
    if len(vlm_data) > len(rule_based_data):
        logger.info("Preferring VLM data due to higher row count", 
                   vlm_rows=len(vlm_data), 
                   rule_rows=len(rule_based_data))
        return vlm_data
    else:
        logger.info("Preferring rule-based data due to higher row count",
                   rule_rows=len(rule_based_data),
                   vlm_rows=len(vlm_data))
        return rule_based_data
