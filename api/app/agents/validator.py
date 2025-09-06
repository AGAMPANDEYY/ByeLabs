"""
Validator Agent

This agent validates normalized data:
- Check data quality and completeness
- Validate business rules
- Generate validation issues and warnings
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
    Validate normalized data and generate issues.
    
    Args:
        state: Current processing state
    
    Returns:
        Updated state with validation results
    """
    start_time = time.time()
    agent_name = "validator"
    
    logger.info("Starting validator agent", job_id=state.get("job_id"))
    
    try:
        # Increment run counter
        AGENT_RUNS_TOTAL.labels(agent=agent_name).inc()
        
        # Get normalized data
        normalized_data = state.get("normalized_data", [])
        
        # Placeholder implementation
        # In a real implementation, this would:
        # 1. Validate NPI numbers
        # 2. Check email format and validity
        # 3. Validate phone numbers
        # 4. Check required fields
        # 5. Apply business rules validation
        
        # Simulate processing time
        time.sleep(0.2)
        
        # Validate each row
        validation_issues = []
        validated_data = []
        
        for row in normalized_data:
            row_issues = []
            data = row["data"]
            
            # Validate NPI
            if not data.get("NPI"):
                row_issues.append({
                    "field": "NPI",
                    "level": "error",
                    "message": "NPI is required"
                })
            elif not _is_valid_npi(data["NPI"]):
                row_issues.append({
                    "field": "NPI",
                    "level": "error",
                    "message": f"Invalid NPI format: {data['NPI']}"
                })
            
            # Validate Provider Name
            if not data.get("Provider Name"):
                row_issues.append({
                    "field": "Provider Name",
                    "level": "error",
                    "message": "Provider Name is required"
                })
            
            # Validate Email
            if data.get("Email") and not _is_valid_email(data["Email"]):
                row_issues.append({
                    "field": "Email",
                    "level": "warning",
                    "message": f"Invalid email format: {data['Email']}"
                })
            
            # Validate Phone
            if data.get("Phone") and not _is_valid_phone(data["Phone"]):
                row_issues.append({
                    "field": "Phone",
                    "level": "warning",
                    "message": f"Invalid phone format: {data['Phone']}"
                })
            
            # Add row issues to validation issues
            for issue in row_issues:
                validation_issues.append({
                    "row_idx": row["row_idx"],
                    "field": issue["field"],
                    "level": issue["level"],
                    "message": issue["message"]
                })
            
            # Add validated row
            validated_data.append({
                **row,
                "validation_issues": row_issues,
                "is_valid": len(row_issues) == 0
            })
        
        # Update state with validation results
        state.update({
            "validated_data": validated_data,
            "validation_issues": validation_issues,
            "validation_stats": {
                "total_rows": len(validated_data),
                "valid_rows": sum(1 for row in validated_data if row["is_valid"]),
                "invalid_rows": sum(1 for row in validated_data if not row["is_valid"]),
                "total_issues": len(validation_issues),
                "error_count": sum(1 for issue in validation_issues if issue["level"] == "error"),
                "warning_count": sum(1 for issue in validation_issues if issue["level"] == "warning")
            },
            "processing_notes": state.get("processing_notes", []) + ["Data validation completed"]
        })
        
        logger.info("Validator agent completed", job_id=state.get("job_id"))
        
        return state
        
    except Exception as e:
        logger.error("Validator agent failed", job_id=state.get("job_id"), error=str(e))
        state.update({
            "error": str(e),
            "failed_agent": agent_name
        })
        return state
        
    finally:
        # Record latency
        duration = time.time() - start_time
        AGENT_LATENCY_SECONDS.labels(agent=agent_name).observe(duration)

def _is_valid_npi(npi: str) -> bool:
    """Validate NPI number format."""
    if not npi:
        return False
    
    # NPI should be 10 digits
    if len(npi) != 10 or not npi.isdigit():
        return False
    
    # Basic NPI validation (Luhn algorithm)
    # In a real implementation, use proper NPI validation
    return True

def _is_valid_email(email: str) -> bool:
    """Validate email format."""
    if not email:
        return False
    
    # Basic email validation
    return "@" in email and "." in email.split("@")[-1]

def _is_valid_phone(phone: str) -> bool:
    """Validate phone number format."""
    if not phone:
        return False
    
    # Check if phone matches (XXX) XXX-XXXX format
    import re
    pattern = r'^\(\d{3}\) \d{3}-\d{4}$'
    return bool(re.match(pattern, phone))
