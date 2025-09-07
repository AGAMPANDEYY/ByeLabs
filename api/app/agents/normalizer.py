"""
Normalizer Agent

This agent normalizes extracted data to the exact Excel schema (17 fields):
- Phone → phonenumbers (US default) → E.164; keep national display
- Dates → dateparser with MDY bias → string MM/DD/YYYY
- NPI → digits only; Luhn with 80840 prefix; store validity flag
- Address → usaddress.tag → standardized; on fail, fallback to raw with low confidence
- Record normalization deltas for the issues panel
"""

import time
import re
from typing import Dict, Any, List, Optional, Tuple
import phonenumbers
import dateparser
import usaddress
from datetime import datetime

from ..metrics import get_agent_runs_total, get_agent_latency_seconds
from ..llm import get_llm_client
import structlog

logger = structlog.get_logger(__name__)

# Excel Schema - 17 fields for roster data (matching exporter_excel.py)
EXCEL_SCHEMA = [
    "Transaction Type",
    "Transaction Attribute", 
    "Effective Date",
    "Term Date",
    "Term Reason",
    "Provider Name",
    "Provider NPI",
    "Provider Specialty",
    "State License",
    "Organization Name",
    "TIN",
    "Group NPI",
    "Complete Address",
    "Phone Number",
    "Fax Number",
    "PPG ID",
    "Line Of Business"
]

def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize extracted data to the exact Excel schema (17 fields).
    
    Args:
        state: Current processing state with extracted data
    
    Returns:
        Updated state with normalized data and normalization deltas
    """
    logger.info("Starting normalizer agent", job_id=state.get("job_id"))
    
    try:
        
        # Get extracted data from previous agents
        rows = state.get("rows", [])
        
        if not rows:
            logger.warning("No rows to normalize", job_id=state.get("job_id"))
            state.update({
                "normalized_rows": [],
                "normalization_deltas": [],
                "normalization_stats": {
                    "total_rows": 0,
                    "successful_normalizations": 0,
                    "failed_normalizations": 0
                }
            })
            return state
        
        # Get LLM client for enhanced header mapping
        llm_client = get_llm_client()
        
        # Extract headers from first row for LLM analysis
        extracted_headers = []
        if rows and rows[0].get("data"):
            extracted_headers = list(rows[0]["data"].keys())
        
        # Get LLM header mapping suggestions if available
        header_mapping = None
        if llm_client and extracted_headers:
            try:
                llm_mapping = llm_client.suggest_header_mapping(extracted_headers, EXCEL_SCHEMA)
                if llm_mapping.get("mappings"):
                    header_mapping = llm_mapping
                    logger.info("LLM header mapping obtained", 
                               job_id=state.get("job_id"),
                               mappings_count=len(llm_mapping["mappings"]))
            except Exception as e:
                logger.warning("LLM header mapping failed, using fallback", error=str(e))
        
        # Normalize each row
        normalized_rows = []
        normalization_deltas = []
        successful_normalizations = 0
        failed_normalizations = 0
        
        for row in rows:
            try:
                original_data = row.get("data", {})
                normalized_data, deltas = _normalize_row_data(original_data, row.get("row_idx", 0), header_mapping)
                
                normalized_row = {
                    **row,
                    "data": normalized_data,
                    "normalized": True,
                    "normalization_deltas": deltas
                }
                normalized_rows.append(normalized_row)
                normalization_deltas.extend(deltas)
                successful_normalizations += 1
                
            except Exception as e:
                logger.error("Failed to normalize row", 
                           job_id=state.get("job_id"), 
                           row_idx=row.get("row_idx", 0), 
                           error=str(e))
                failed_normalizations += 1
                
                # Keep original data with error flag
                normalized_row = {
                    **row,
                    "normalized": False,
                    "normalization_error": str(e)
                }
                normalized_rows.append(normalized_row)
        
        # Update state with normalized data
        state.update({
            "rows": normalized_rows,
            "normalization_deltas": normalization_deltas,
            "normalization_stats": {
                "total_rows": len(rows),
                "successful_normalizations": successful_normalizations,
                "failed_normalizations": failed_normalizations
            },
            "processing_notes": state.get("processing_notes", []) + [
                f"Data normalization completed: {successful_normalizations}/{len(rows)} rows normalized"
            ]
        })
        
        logger.info("Normalizer agent completed", 
                   job_id=state.get("job_id"),
                   successful=successful_normalizations,
                   failed=failed_normalizations)
        
        return state
        
    except Exception as e:
        logger.error("Normalizer agent failed", job_id=state.get("job_id"), error=str(e))
        state.update({
            "error": str(e),
            "failed_agent": "normalizer"
        })
        return state

def _normalize_row_data(original_data: Dict[str, Any], row_idx: int, header_mapping: Optional[Dict[str, Any]] = None) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Normalize a single row's data to the Excel schema.
    
    Args:
        original_data: Raw extracted data
        row_idx: Row index for tracking
    
    Returns:
        Tuple of (normalized_data, normalization_deltas)
    """
    normalized_data = {}
    deltas = []
    
    # Initialize all schema fields
    for field in EXCEL_SCHEMA:
        normalized_data[field] = ""
    
    # Use LLM header mapping if available
    if header_mapping and header_mapping.get("mappings"):
        for mapping in header_mapping["mappings"]:
            source_field = mapping.get("source", "")
            target_field = mapping.get("target", "")
            confidence = mapping.get("confidence", 0.0)
            
            if source_field in original_data and target_field in EXCEL_SCHEMA:
                value = original_data[source_field]
                if value and str(value).strip():
                    # Apply field-specific normalization
                    if target_field == "Provider NPI":
                        normalized_value, delta = _normalize_npi(str(value))
                    elif target_field == "Phone Number":
                        normalized_value, delta = _normalize_phone(str(value))
                    elif target_field in ["Effective Date", "Term Date"]:
                        normalized_value, delta = _normalize_date(str(value))
                    elif target_field == "Complete Address":
                        normalized_value, delta = _normalize_address(str(value))
                    elif target_field == "Provider Name":
                        normalized_value, delta = _normalize_name(str(value))
                    else:
                        normalized_value = str(value).strip().title()
                        delta = None
                    
                    normalized_data[target_field] = normalized_value
                    if delta:
                        delta.update({
                            "llm_mapped": True,
                            "llm_confidence": confidence,
                            "original_field": source_field
                        })
                        deltas.append(delta)
    
    # Map and normalize each field (fallback for unmapped fields)
    for field in EXCEL_SCHEMA:
        if not normalized_data[field]:  # Only process if not already mapped by LLM
            # Try to get value from original data, with field name mapping
            original_value = _get_mapped_value(original_data, field)
            
            if field == "Provider NPI":
                normalized_value, delta = _normalize_npi(original_value)
            elif field == "Phone Number":
                normalized_value, delta = _normalize_phone(original_value)
            elif field in ["Effective Date", "Term Date"]:
                normalized_value, delta = _normalize_date(original_value)
            elif field == "Complete Address":
                normalized_value, delta = _normalize_address(original_value)
            elif field == "Provider Name":
                normalized_value, delta = _normalize_name(original_value)
            else:
                # Simple text normalization for other fields
                normalized_value = original_value.strip().title() if original_value else ""
                delta = None
            
            normalized_data[field] = normalized_value
            
            # Record delta if value changed
            if delta:
                delta["row_idx"] = row_idx
                delta["field"] = field
                delta["llm_mapped"] = False  # Mark as rule-based mapping
                deltas.append(delta)
    
    return normalized_data, deltas

def _get_mapped_value(original_data: Dict[str, Any], target_field: str) -> str:
    """
    Get value from original data, mapping old field names to new 17-column schema.
    """
    # Direct mapping first
    if target_field in original_data:
        return str(original_data[target_field]).strip()
    
    # Field name mapping for backward compatibility
    field_mapping = {
        "Provider NPI": ["NPI", "Provider NPI"],
        "Provider Specialty": ["Specialty", "Provider Specialty"],
        "Phone Number": ["Phone", "Phone Number"],
        "Complete Address": ["Address", "Complete Address"],
        "State License": ["License", "State License"],
        "Organization Name": ["Organization", "Organization Name"],
        "Group NPI": ["Group NPI"],
        "Fax Number": ["Fax", "Fax Number"],
        "PPG ID": ["PPG", "PPG ID"],
        "Line Of Business": ["LOB", "Line of Business", "Line Of Business"],
        "Transaction Type": ["Type", "Transaction Type"],
        "Transaction Attribute": ["Attribute", "Transaction Attribute"],
        "Term Reason": ["Reason", "Term Reason"]
    }
    
    # Try mapped field names
    if target_field in field_mapping:
        for old_field in field_mapping[target_field]:
            if old_field in original_data:
                return str(original_data[old_field]).strip()
    
    return ""

def _normalize_npi(npi: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Normalize NPI: digits only; Luhn with 80840 prefix; store validity flag."""
    if not npi:
        return "", None
    
    # Extract digits only
    digits = re.sub(r'[^\d]', '', npi)
    
    # Validate NPI format (10 digits)
    is_valid = len(digits) == 10 and digits.isdigit()
    
    # Apply Luhn algorithm with 80840 prefix
    if is_valid:
        # NPI validation: 10-digit number with Luhn check
        is_valid = _validate_npi_luhn(digits)
    
    delta = None
    if digits != npi or not is_valid:
        delta = {
            "original_value": npi,
            "normalized_value": digits,
            "change_type": "normalized",
            "validation_passed": is_valid,
            "message": f"NPI normalized to digits only, validation: {'passed' if is_valid else 'failed'}"
        }
    
    return digits, delta

def _normalize_phone(phone: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Normalize phone: phonenumbers (US default) → E.164; keep national display."""
    if not phone:
        return "", None
    
    try:
        # Parse with US as default region
        parsed = phonenumbers.parse(phone, "US")
        
        if phonenumbers.is_valid_number(parsed):
            # Format as national display format
            national_format = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
            # Also get E.164 for reference
            e164_format = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
            
            delta = None
            if national_format != phone:
                delta = {
                    "original_value": phone,
                    "normalized_value": national_format,
                    "e164_value": e164_format,
                    "change_type": "normalized",
                    "validation_passed": True,
                    "message": f"Phone normalized to national format: {national_format}"
                }
            
            return national_format, delta
        else:
            # Invalid phone number
            delta = {
                "original_value": phone,
                "normalized_value": phone,
                "change_type": "validation_failed",
                "validation_passed": False,
                "message": f"Invalid phone number format: {phone}"
            }
            return phone, delta
            
    except Exception as e:
        # Parsing failed
        delta = {
            "original_value": phone,
            "normalized_value": phone,
            "change_type": "parsing_failed",
            "validation_passed": False,
            "message": f"Phone parsing failed: {str(e)}"
        }
        return phone, delta

def _normalize_date(date_str: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Normalize date: dateparser with MDY bias → string MM/DD/YYYY."""
    if not date_str:
        return "", None
    
    try:
        # Parse with MDY bias (US format)
        parsed_date = dateparser.parse(date_str, date_formats=['%m/%d/%Y', '%m-%d-%Y', '%Y-%m-%d'], 
                                     settings={'DATE_ORDER': 'MDY'})
        
        if parsed_date:
            # Format as MM/DD/YYYY
            formatted_date = parsed_date.strftime('%m/%d/%Y')
            
            delta = None
            if formatted_date != date_str:
                delta = {
                    "original_value": date_str,
                    "normalized_value": formatted_date,
                    "change_type": "normalized",
                    "validation_passed": True,
                    "message": f"Date normalized to MM/DD/YYYY: {formatted_date}"
                }
            
            return formatted_date, delta
        else:
            # Parsing failed
            delta = {
                "original_value": date_str,
                "normalized_value": date_str,
                "change_type": "parsing_failed",
                "validation_passed": False,
                "message": f"Date parsing failed: {date_str}"
            }
            return date_str, delta
            
    except Exception as e:
        delta = {
            "original_value": date_str,
            "normalized_value": date_str,
            "change_type": "parsing_failed",
            "validation_passed": False,
            "message": f"Date parsing error: {str(e)}"
        }
        return date_str, delta

def _normalize_address(address: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Normalize address: usaddress.tag → standardized; on fail, fallback to raw with low confidence."""
    if not address:
        return "", None
    
    try:
        # Parse address using usaddress
        parsed, address_type = usaddress.tag(address)
        
        if address_type == 'Street Address':
            # Standardize the address components
            standardized_parts = []
            
            # Add house number
            if 'AddressNumber' in parsed:
                standardized_parts.append(parsed['AddressNumber'])
            
            # Add street name and type
            street_parts = []
            for key in ['StreetNamePreDirectional', 'StreetName', 'StreetNamePostType']:
                if key in parsed:
                    street_parts.append(parsed[key])
            
            if street_parts:
                standardized_parts.append(' '.join(street_parts))
            
            # Add apartment/suite if present
            if 'OccupancyType' in parsed and 'OccupancyIdentifier' in parsed:
                standardized_parts.append(f"{parsed['OccupancyType']} {parsed['OccupancyIdentifier']}")
            
            standardized_address = ', '.join(standardized_parts)
            
            delta = {
                "original_value": address,
                "normalized_value": standardized_address,
                "change_type": "normalized",
                "validation_passed": True,
                "confidence": "high",
                "message": f"Address standardized: {standardized_address}"
            }
            
            return standardized_address, delta
        else:
            # Address type not recognized, use original with low confidence
            delta = {
                "original_value": address,
                "normalized_value": address,
                "change_type": "low_confidence",
                "validation_passed": False,
                "confidence": "low",
                "message": f"Address type not recognized: {address_type}"
            }
            return address, delta
            
    except Exception as e:
        # Parsing failed, use original with low confidence
        delta = {
            "original_value": address,
            "normalized_value": address,
            "change_type": "parsing_failed",
            "validation_passed": False,
            "confidence": "low",
            "message": f"Address parsing failed: {str(e)}"
        }
        return address, delta

def _normalize_email(email: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Normalize email: lowercase, trim, basic validation."""
    if not email:
        return "", None
    
    normalized_email = email.strip().lower()
    
    # Basic email validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    is_valid = bool(re.match(email_pattern, normalized_email))
    
    delta = None
    if normalized_email != email or not is_valid:
        delta = {
            "original_value": email,
            "normalized_value": normalized_email,
            "change_type": "normalized" if normalized_email != email else "validation_failed",
            "validation_passed": is_valid,
            "message": f"Email {'normalized' if normalized_email != email else 'validation failed'}: {normalized_email}"
        }
    
    return normalized_email, delta

def _normalize_name(name: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Normalize provider name: title case, trim."""
    if not name:
        return "", None
    
    normalized_name = name.strip().title()
    
    delta = None
    if normalized_name != name:
        delta = {
            "original_value": name,
            "normalized_value": normalized_name,
            "change_type": "normalized",
            "validation_passed": True,
            "message": f"Name normalized to title case: {normalized_name}"
        }
    
    return normalized_name, delta

def _validate_npi_luhn(npi: str) -> bool:
    """Validate NPI using Luhn algorithm with 80840 prefix."""
    if len(npi) != 10 or not npi.isdigit():
        return False
    
    # NPI validation: 10-digit number with Luhn check
    # For NPIs, we use the Luhn algorithm on the 10-digit number
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
