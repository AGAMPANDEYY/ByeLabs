"""
Normalizer Agent

This agent normalizes extracted data:
- Standardize formats (phone numbers, addresses, dates)
- Clean and validate data
- Apply business rules for data consistency
"""

import time
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
    Normalize extracted data to standard formats.
    
    Args:
        state: Current processing state
    
    Returns:
        Updated state with normalized data
    """
    start_time = time.time()
    agent_name = "normalizer"
    
    logger.info("Starting normalizer agent", job_id=state.get("job_id"))
    
    try:
        # Increment run counter
        AGENT_RUNS_TOTAL.labels(agent=agent_name).inc()
        
        # Get extracted data from previous agents
        extracted_data = state.get("extracted_data", [])
        vlm_data = state.get("vlm_data", {})
        
        # Combine data from different sources
        all_data = extracted_data + vlm_data.get("extracted_data", [])
        
        # Placeholder implementation
        # In a real implementation, this would:
        # 1. Normalize phone numbers to standard format
        # 2. Standardize addresses using usaddress
        # 3. Clean and validate email addresses
        # 4. Normalize names and titles
        # 5. Apply business rules for data consistency
        
        # Simulate processing time
        time.sleep(0.3)
        
        # Normalize the data
        normalized_data = []
        for row in all_data:
            normalized_row = {
                "row_idx": row["row_idx"],
                "data": {
                    "NPI": row["data"].get("NPI", "").strip(),
                    "Provider Name": row["data"].get("Provider Name", "").strip().title(),
                    "Specialty": row["data"].get("Specialty", "").strip(),
                    "Phone": _normalize_phone(row["data"].get("Phone", "")),
                    "Email": row["data"].get("Email", "").strip().lower(),
                    "Address": _normalize_address(row["data"].get("Address", ""))
                },
                "confidence": row.get("confidence", 0.0),
                "extraction_method": row.get("extraction_method", "unknown"),
                "normalized": True
            }
            normalized_data.append(normalized_row)
        
        # Update state with normalized data
        state.update({
            "normalized_data": normalized_data,
            "normalization_stats": {
                "total_rows": len(normalized_data),
                "successful_normalizations": len(normalized_data),
                "failed_normalizations": 0
            },
            "processing_notes": state.get("processing_notes", []) + ["Data normalization completed"]
        })
        
        logger.info("Normalizer agent completed", job_id=state.get("job_id"))
        
        return state
        
    except Exception as e:
        logger.error("Normalizer agent failed", job_id=state.get("job_id"), error=str(e))
        state.update({
            "error": str(e),
            "failed_agent": agent_name
        })
        return state
        
    finally:
        # Record latency
        duration = time.time() - start_time
        AGENT_LATENCY_SECONDS.labels(agent=agent_name).observe(duration)

def _normalize_phone(phone: str) -> str:
    """Normalize phone number to standard format."""
    if not phone:
        return ""
    
    # Remove all non-digit characters
    digits = ''.join(filter(str.isdigit, phone))
    
    # Format as (XXX) XXX-XXXX if 10 digits
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    elif len(digits) == 11 and digits[0] == '1':
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    
    return phone  # Return original if can't normalize

def _normalize_address(address: str) -> str:
    """Normalize address to standard format."""
    if not address:
        return ""
    
    # Basic address normalization
    # In a real implementation, use usaddress library
    return address.strip().title()
