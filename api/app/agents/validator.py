"""
Validator Agent

This agent validates normalized data:
- Required columns; missing values → issue
- NPI length+checksum; duplicate NPIs; Effective≤Term; DOB not future; low address confidence → warn
- Set needs_review=True if any error-level issues
"""

import time
import re
from typing import Dict, Any, List, Set, Optional
from datetime import datetime, date
from dateutil.parser import parse as parse_date

from ..metrics import get_agent_runs_total, get_agent_latency_seconds
import structlog

logger = structlog.get_logger(__name__)

# Required fields for validation
REQUIRED_FIELDS = ["NPI", "Provider Name", "Specialty", "Effective Date"]

# Fields that should not be empty if present
OPTIONAL_BUT_VALIDATED_FIELDS = ["Phone", "Email", "Address", "DOB", "Term Date"]
def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate normalized data and generate comprehensive issues.
    
    Args:
        state: Current processing state with normalized data
    
    Returns:
        Updated state with validation results and needs_review flag
    """
    logger.info("Starting validator agent", job_id=state.get("job_id"))
    
    try:
        
        # Get normalized data
        rows = state.get("rows", [])
        
        if not rows:
            logger.warning("No rows to validate", job_id=state.get("job_id"))
            state.update({
                "validation_issues": [],
                "validation_stats": {
                    "total_rows": 0,
                    "valid_rows": 0,
                    "invalid_rows": 0,
                    "total_issues": 0,
                    "error_count": 0,
                    "warning_count": 0
                },
                "needs_review": False
            })
            return state
        
        # Validate each row and collect all issues
        all_issues = []
        validated_rows = []
        npi_set: Set[str] = set()  # Track NPIs for duplicate detection
        
        for row in rows:
            row_data = row.get("data", {})
            row_idx = row.get("row_idx", 0)
            
            # Validate this row
            row_issues = _validate_row(row_data, row_idx, npi_set)
            all_issues.extend(row_issues)
            
            # Add validated row
            validated_row = {
                **row,
                "validation_issues": row_issues,
                "is_valid": len([i for i in row_issues if i["level"] == "error"]) == 0
            }
            validated_rows.append(validated_row)
            
            # Add NPI to set for duplicate detection
            npi = row_data.get("NPI", "").strip()
            if npi:
                npi_set.add(npi)
        
        # Calculate validation statistics
        total_rows = len(validated_rows)
        valid_rows = sum(1 for row in validated_rows if row["is_valid"])
        invalid_rows = total_rows - valid_rows
        total_issues = len(all_issues)
        error_count = sum(1 for issue in all_issues if issue["level"] == "error")
        warning_count = sum(1 for issue in all_issues if issue["level"] == "warning")
        
        # Set needs_review flag if there are any error-level issues
        needs_review = error_count > 0
        
        # Update state with validation results
        state.update({
            "rows": validated_rows,
            "validation_issues": all_issues,
            "validation_stats": {
                "total_rows": total_rows,
                "valid_rows": valid_rows,
                "invalid_rows": invalid_rows,
                "total_issues": total_issues,
                "error_count": error_count,
                "warning_count": warning_count
            },
            "needs_review": needs_review,
            "processing_notes": state.get("processing_notes", []) + [
                f"Data validation completed: {valid_rows}/{total_rows} rows valid, {error_count} errors, {warning_count} warnings"
            ]
        })
        
        logger.info("Validator agent completed", 
                   job_id=state.get("job_id"),
                   valid_rows=valid_rows,
                   total_rows=total_rows,
                   errors=error_count,
                   warnings=warning_count,
                   needs_review=needs_review)
        
        return state
        
    except Exception as e:
        logger.error("Validator agent failed", job_id=state.get("job_id"), error=str(e))
        state.update({
            "error": str(e),
            "failed_agent": "validator",
            "needs_review": True  # Set to True on validation failure
        })
        return state

def _validate_row(row_data: Dict[str, Any], row_idx: int, npi_set: Set[str]) -> List[Dict[str, Any]]:
    """
    Validate a single row and return list of issues.
    
    Args:
        row_data: The row's data dictionary
        row_idx: Row index for tracking
        npi_set: Set of NPIs seen so far (for duplicate detection)
    
    Returns:
        List of validation issues
    """
    issues = []
    
    # 1. Required fields validation
    for field in REQUIRED_FIELDS:
        value = row_data.get(field, "").strip()
        if not value:
            issues.append({
                "row_idx": row_idx,
                "field": field,
                "level": "error",
                "message": f"Required field '{field}' is missing or empty"
            })
    
    # 2. NPI validation (length + checksum + duplicates)
    npi = row_data.get("NPI", "").strip()
    if npi:
        if not _is_valid_npi_format(npi):
            issues.append({
                "row_idx": row_idx,
                "field": "NPI",
                "level": "error",
                "message": f"Invalid NPI format: {npi} (must be 10 digits)"
            })
        elif not _is_valid_npi_checksum(npi):
            issues.append({
                "row_idx": row_idx,
                "field": "NPI",
                "level": "warning",
                "message": f"NPI checksum validation failed: {npi}"
            })
        elif npi in npi_set:
            issues.append({
                "row_idx": row_idx,
                "field": "NPI",
                "level": "warning",
                "message": f"Duplicate NPI found: {npi}"
            })
    
    # 3. Date validations
    dob = row_data.get("DOB", "").strip()
    if dob:
        dob_issue = _validate_dob(dob, row_idx)
        if dob_issue:
            issues.append(dob_issue)
    
    effective_date = row_data.get("Effective Date", "").strip()
    term_date = row_data.get("Term Date", "").strip()
    
    if effective_date and term_date:
        date_issue = _validate_date_range(effective_date, term_date, row_idx)
        if date_issue:
            issues.append(date_issue)
    
    # 4. Email validation
    email = row_data.get("Email", "").strip()
    if email and not _is_valid_email(email):
        issues.append({
            "row_idx": row_idx,
            "field": "Email",
            "level": "warning",
            "message": f"Invalid email format: {email}"
        })
    
    # 5. Phone validation
    phone = row_data.get("Phone", "").strip()
    if phone and not _is_valid_phone(phone):
        issues.append({
            "row_idx": row_idx,
            "field": "Phone",
            "level": "warning",
            "message": f"Invalid phone format: {phone}"
        })
    
    # 6. Address confidence validation
    address = row_data.get("Address", "").strip()
    if address:
        # Check if address has low confidence indicators
        if _has_low_address_confidence(address):
            issues.append({
                "row_idx": row_idx,
                "field": "Address",
                "level": "warning",
                "message": f"Address may have low confidence: {address}"
            })
    
    return issues

def _is_valid_npi_format(npi: str) -> bool:
    """Validate NPI format: 10 digits only."""
    if not npi:
        return False
    return len(npi) == 10 and npi.isdigit()

def _is_valid_npi_checksum(npi: str) -> bool:
    """Validate NPI using Luhn algorithm."""
    if not _is_valid_npi_format(npi):
        return False
    
    # Luhn algorithm for NPI validation
    def luhn_checksum(card_num):
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_num)
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum(digits_of(d*2))
        return checksum % 10
    
    return luhn_checksum(npi) == 0

def _validate_dob(dob: str, row_idx: int) -> Optional[Dict[str, Any]]:
    """Validate DOB: not future date."""
    try:
        # Parse the date
        dob_date = parse_date(dob)
        
        # Check if DOB is in the future
        if dob_date.date() > date.today():
            return {
                "row_idx": row_idx,
                "field": "DOB",
                "level": "error",
                "message": f"Date of birth cannot be in the future: {dob}"
            }
        
        # Check if DOB is reasonable (not more than 120 years ago)
        if dob_date.date() < date.today().replace(year=date.today().year - 120):
            return {
                "row_idx": row_idx,
                "field": "DOB",
                "level": "warning",
                "message": f"Date of birth seems unusually old: {dob}"
            }
        
        return None
        
    except Exception as e:
        return {
            "row_idx": row_idx,
            "field": "DOB",
            "level": "error",
            "message": f"Invalid date format: {dob} - {str(e)}"
        }

def _validate_date_range(effective_date: str, term_date: str, row_idx: int) -> Optional[Dict[str, Any]]:
    """Validate that Effective Date <= Term Date."""
    try:
        eff_date = parse_date(effective_date)
        term_date_parsed = parse_date(term_date)
        
        if eff_date > term_date_parsed:
            return {
                "row_idx": row_idx,
                "field": "Term Date",
                "level": "error",
                "message": f"Term date ({term_date}) must be after or equal to effective date ({effective_date})"
            }
        
        return None
        
    except Exception as e:
        return {
            "row_idx": row_idx,
            "field": "Term Date",
            "level": "warning",
            "message": f"Could not validate date range: {str(e)}"
        }

def _is_valid_email(email: str) -> bool:
    """Validate email format using regex."""
    if not email:
        return False
    
    # Comprehensive email validation regex
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(email_pattern, email))

def _is_valid_phone(phone: str) -> bool:
    """Validate phone number format."""
    if not phone:
        return False
    
    # Check various phone formats
    patterns = [
        r'^\(\d{3}\) \d{3}-\d{4}$',  # (XXX) XXX-XXXX
        r'^\d{3}-\d{3}-\d{4}$',      # XXX-XXX-XXXX
        r'^\d{3}\.\d{3}\.\d{4}$',    # XXX.XXX.XXXX
        r'^\d{10}$',                  # XXXXXXXXXX
        r'^\+1\d{10}$'                # +1XXXXXXXXXX
    ]
    
    return any(re.match(pattern, phone) for pattern in patterns)

def _has_low_address_confidence(address: str) -> bool:
    """Check if address has indicators of low confidence."""
    if not address:
        return True
    
    # Indicators of low confidence
    low_confidence_indicators = [
        len(address) < 10,  # Too short
        address.count(',') < 1,  # Missing comma separators
        not any(char.isdigit() for char in address),  # No numbers
        'unknown' in address.lower(),
        'n/a' in address.lower(),
        'tbd' in address.lower()
    ]
    
    return any(low_confidence_indicators)
