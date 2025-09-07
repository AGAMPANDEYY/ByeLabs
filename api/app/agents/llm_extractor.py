#!/usr/bin/env python3
"""
LLM Extractor Agent - Uses trained SLM for data extraction
Primary extraction method with fallback to rule-based extraction
"""

import json
import time
import structlog
from typing import Dict, Any, List, Optional
from openai import OpenAI
from ..config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Excel schema for consistent output
EXCEL_SCHEMA = [
    "Transaction Type", "Transaction Attribute", "Effective Date", "Term Date", "Term Reason",
    "Provider Name", "Provider NPI", "Provider Specialty", "State License", "Organization Name",
    "TIN", "Group NPI", "Complete Address", "Phone Number", "Fax Number", "PPG ID", "Line Of Business"
]

# System prompt for the LLM
SYSTEM_PROMPT = """You are a healthcare data extraction specialist. Your task is to extract provider roster information from email content and convert it into a structured JSON format.

IMPORTANT INSTRUCTIONS:
1. Extract ALL provider information from the email content
2. Each provider should be a separate record in the JSON array
3. Use the exact field names from the schema provided
4. If a field is not available, use null or appropriate default values
5. Ensure data accuracy and completeness
6. Follow healthcare data standards for formatting

SCHEMA FIELDS:
- Transaction Type: "Add", "Term", "Change", "Update", etc.
- Transaction Attribute: "Provider", "Location", "Specialty", "Network", etc.
- Effective Date: YYYY-MM-DD format
- Term Date: YYYY-MM-DD format (if applicable)
- Term Reason: Reason for termination (if applicable)
- Provider Name: Full name of the provider
- Provider NPI: 10-digit NPI number
- Provider Specialty: Medical specialty
- State License: State license number
- Organization Name: Name of the healthcare organization
- TIN: Tax Identification Number
- Group NPI: Group NPI number
- Complete Address: Full address including city, state, zip
- Phone Number: Phone number in standard format
- Fax Number: Fax number in standard format
- PPG ID: Provider Practice Group ID
- Line Of Business: Type of business line

OUTPUT FORMAT:
Return a JSON array where each object represents a provider record with the above fields.

EXAMPLE:
[
  {
    "Transaction Type": "Add",
    "Transaction Attribute": "Provider",
    "Effective Date": "2024-01-15",
    "Term Date": null,
    "Term Reason": null,
    "Provider Name": "Dr. John Smith",
    "Provider NPI": "1234567890",
    "Provider Specialty": "Internal Medicine",
    "State License": "MD12345",
    "Organization Name": "ABC Medical Group",
    "TIN": "12-3456789",
    "Group NPI": "0987654321",
    "Complete Address": "123 Main St, City, ST 12345",
    "Phone Number": "(555) 123-4567",
    "Fax Number": "(555) 123-4568",
    "PPG ID": "PPG001",
    "Line Of Business": "Commercial"
  }
]

Extract the data accurately and return only the JSON array."""

def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM Extractor Agent - Primary extraction method using trained SLM
    """
    logger.info("Starting LLM extraction", job_id=state.get("job_id"))
    
    try:
        # Get email content from state - use the same structure as extract_rule
        classification = state.get("classification", {})
        artifacts = classification.get("artifacts", [])
        
        if not artifacts:
            raise ValueError("No classified artifacts found in state")
        
        # Find email body artifact
        email_body = None
        for artifact in artifacts:
            if artifact.get("document_type") == "PLAIN_TEXT" and "email_body" in artifact.get("content", ""):
                email_body = artifact
                break
        
        if not email_body:
            raise ValueError("No email body artifact found in classified artifacts")
        
        # Extract text content from email
        text_content = _extract_text_from_email_state(state)
        if not text_content:
            raise ValueError("No text content found in email")
        
        # Call LLM for extraction
        extracted_data = _call_llm_for_extraction(text_content)
        
        # Validate and clean the extracted data
        validated_data = _validate_llm_output(extracted_data)
        
        # Update state with extracted data in the correct format
        # Convert to the expected structure with row_idx, data, confidence, etc.
        formatted_data = []
        for idx, record in enumerate(validated_data):
            formatted_data.append({
                "row_idx": idx,
                "data": record,
                "confidence": 0.9,  # High confidence for LLM extraction
                "extraction_method": "llm",
                "source": "llm_extraction"
            })
        
        state["extracted_data"] = formatted_data
        state["extraction_method"] = "llm"
        state["llm_used"] = True
        
        logger.info("LLM extraction completed successfully", 
                   job_id=state.get("job_id"),
                   records_extracted=len(validated_data))
        
        return state
        
    except Exception as e:
        error_msg = f"LLM extraction failed: {str(e)}"
        logger.error(error_msg, job_id=state.get("job_id"), error=str(e))
        
        # Mark as failed but don't raise - let pipeline fallback to rule-based
        state["llm_error"] = error_msg
        state["llm_used"] = False
        state["extraction_method"] = "llm_failed"
        
        return state

def _extract_text_from_email_state(state: Dict[str, Any]) -> str:
    """
    Extract text content from email for LLM processing
    """
    text_parts = []
    
    # Get classified artifacts from state
    classification = state.get("classification", {})
    artifacts = classification.get("artifacts", [])

    # Extract from email body artifact
    for artifact in artifacts:
        if artifact.get("document_type") == "PLAIN_TEXT":
            content = artifact.get("content", "")
            if content:
                text_parts.append(f"Email Content: {content}")
        
        elif artifact.get("document_type") == "HTML_TABLE":
            content = artifact.get("content", "")
            if content:
                # Clean HTML for better LLM processing
                import re
                html_text = re.sub(r'<[^>]+>', ' ', content)
                html_text = re.sub(r'\s+', ' ', html_text).strip()
                if html_text:
                    text_parts.append(f"HTML Table Content: {html_text}")

    # Also check original artifacts for additional context
    original_artifacts = state.get("artifacts", {})
    email_body = original_artifacts.get("email_body", {})
    
    # HTML content
    if "html" in email_body and email_body["html"]:
        import re
        html_text = re.sub(r'<[^>]+>', ' ', email_body["html"])
        html_text = re.sub(r'\s+', ' ', html_text).strip()
        if html_text:
            text_parts.append(f"HTML Content: {html_text}")

    # Plain text content
    if "text" in email_body and email_body["text"]:
        text_parts.append(f"Plain Text: {email_body['text']}")

    # Extract from attachments if any
    attachments = original_artifacts.get("attachments", [])
    for attachment in attachments:
        if attachment.get("content_type") == "text/plain":
            # Note: We don't have attachment content in state, just metadata
            text_parts.append(f"Attachment: {attachment.get('filename', 'Unknown')}")
    
    return "\n\n".join(text_parts)

def _call_llm_for_extraction(text_content: str) -> List[Dict[str, Any]]:
    """
    Call the trained SLM for data extraction
    """
    try:
        # Check if SLM is enabled
        if not settings.slm_enabled:
            raise Exception("SLM is disabled in configuration")
        
        # Initialize OpenAI client with local endpoint
        client = OpenAI(
            base_url=settings.slm_base_url,
            api_key=settings.slm_api_key
        )
        
        # Prepare the prompt
        user_prompt = f"""Please extract provider roster information from the following email content:

{text_content}

Return the data in the exact JSON format specified in the system prompt."""
        
        # Call the LLM
        logger.info("Calling SLM for extraction", 
                   content_length=len(text_content),
                   model=settings.slm_model_name,
                   base_url=settings.slm_base_url)
        
        response = client.chat.completions.create(
            model=settings.slm_model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=settings.slm_temperature,
            max_tokens=settings.slm_max_tokens,
            timeout=settings.slm_timeout
        )
        
        # Extract the response
        llm_response = response.choices[0].message.content.strip()
        logger.info("LLM response received", response_length=len(llm_response))
        
        # Parse JSON response
        try:
            # Clean the response - remove any markdown formatting
            if llm_response.startswith("```json"):
                llm_response = llm_response[7:]
            if llm_response.endswith("```"):
                llm_response = llm_response[:-3]
            
            extracted_data = json.loads(llm_response.strip())
            
            # Ensure it's a list
            if not isinstance(extracted_data, list):
                extracted_data = [extracted_data]
            
            return extracted_data
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM JSON response", error=str(e), response=llm_response)
            raise ValueError(f"Invalid JSON response from LLM: {str(e)}")
        
    except Exception as e:
        logger.error("LLM API call failed", error=str(e))
        raise Exception(f"LLM extraction failed: {str(e)}")

def _validate_llm_output(extracted_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate and clean the LLM output
    """
    validated_data = []
    
    for record in extracted_data:
        if not isinstance(record, dict):
            continue
        
        # Create a clean record with all required fields
        clean_record = {}
        
        for field in EXCEL_SCHEMA:
            value = record.get(field)
            
            # Clean and validate the value
            if value is None or value == "":
                clean_record[field] = None
            else:
                # Basic cleaning
                if isinstance(value, str):
                    value = value.strip()
                    if value.lower() in ["null", "none", "n/a", "na"]:
                        value = None
                
                clean_record[field] = value
        
        # Only add records that have at least some meaningful data
        if any(v for v in clean_record.values() if v is not None):
            validated_data.append(clean_record)
    
    return validated_data

def _get_llm_health() -> bool:
    """
    Check if LLM service is available
    """
    try:
        if not settings.slm_enabled:
            return False
            
        client = OpenAI(
            base_url=settings.slm_base_url,
            api_key=settings.slm_api_key
        )
        
        # Simple health check
        response = client.chat.completions.create(
            model=settings.slm_model_name,
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10,
            timeout=5
        )
        
        return True
        
    except Exception as e:
        logger.warning("SLM health check failed", error=str(e))
        return False
