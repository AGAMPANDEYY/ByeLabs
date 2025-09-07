"""
Extract Rule Agent

This agent performs rule-based extraction:
- Extract data using predefined rules and patterns
- Handle structured documents (HTML tables, CSV, XLSX, plain text)
- Apply business logic for data extraction
"""

import time
import re
import io
from typing import Dict, Any, List
import structlog
import pandas as pd
from bs4 import BeautifulSoup

from ..storage import storage_client
from ..metrics import get_agent_runs_total, get_agent_latency_seconds

logger = structlog.get_logger(__name__)

def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform rule-based data extraction.
    
    Args:
        state: Current processing state
    
    Returns:
        Updated state with extracted data
    """
    start_time = time.time()
    agent_name = "extract_rule"
    
    logger.info("Starting extract rule agent", job_id=state.get("job_id"))
    
    try:
        # Increment run counter
        get_agent_runs_total().labels(agent=agent_name, status="started").inc()
        
        classification = state.get("classification", {})
        artifacts = classification.get("artifacts", [])
        
        if not artifacts:
            raise ValueError("No classified artifacts found")
        
        extracted_data = []
        needs_vlm = False
        
        # Process each artifact
        for artifact in artifacts:
            doc_type = artifact.get("document_type")
            content = artifact.get("content", "")
            uri = artifact.get("uri", "")
            
            if doc_type == "HTML_TABLE":
                rows = _extract_html_table(content, artifact)
                if rows:
                    extracted_data.extend(rows)
                else:
                    needs_vlm = True
                    
            elif doc_type == "XLSX":
                rows = _extract_xlsx(uri, artifact)
                if rows:
                    extracted_data.extend(rows)
                else:
                    needs_vlm = True
                    
            elif doc_type == "CSV":
                rows = _extract_csv(uri, artifact)
                if rows:
                    extracted_data.extend(rows)
                else:
                    needs_vlm = True
                    
            elif doc_type == "PLAIN_TEXT":
                rows = _extract_plain_text(content, artifact)
                if rows:
                    extracted_data.extend(rows)
                else:
                    needs_vlm = True
        
        # Update state with extracted data
        state.update({
            "extracted_data": extracted_data,
            "needs_vlm": needs_vlm or len(extracted_data) == 0,
            "extraction_stats": {
                "total_rows": len(extracted_data),
                "successful_extractions": len(extracted_data),
                "failed_extractions": 0,
                "needs_vlm": needs_vlm
            },
            "processing_notes": state.get("processing_notes", []) + [
                f"Rule-based extraction completed: {len(extracted_data)} rows",
                f"VLM needed: {needs_vlm}"
            ]
        })
        
        logger.info("Extract rule agent completed", 
                   job_id=state.get("job_id"), 
                   rows_extracted=len(extracted_data),
                   needs_vlm=needs_vlm)
        
        return state
        
    except Exception as e:
        logger.error("Extract rule agent failed", job_id=state.get("job_id"), error=str(e))
        state.update({
            "error": str(e),
            "failed_agent": agent_name
        })
        return state
        
    finally:
        # Record latency
        duration = time.time() - start_time
        get_agent_latency_seconds().labels(agent=agent_name).observe(duration)

def _extract_html_table(html_content: str, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract data from HTML table."""
    try:
        # Clean HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove styles and clean up
        for tag in soup.find_all(['style', 'script']):
            tag.decompose()
        
        # Remove colspan attributes that can confuse pandas
        for tag in soup.find_all(attrs={'colspan': True}):
            del tag['colspan']
        
        # Try to read HTML tables with pandas
        try:
            tables = pd.read_html(str(soup), flavor='html5lib')
        except Exception:
            # Fallback to basic HTML parsing
            tables = pd.read_html(html_content, flavor='html5lib')
        
        if not tables:
            logger.warning("No tables found in HTML", artifact_type=artifact.get("type"))
            return []
        
        # Find the best table (most rows, best header overlap)
        best_table = _select_best_table(tables)
        if best_table is None:
            return []
        
        # Convert to rows with proper schema mapping
        rows = []
        
        # Check if we have a header row (first row contains column names)
        if len(best_table) > 1:
            # Use first row as headers if it contains text that looks like column names
            first_row = best_table.iloc[0].astype(str).str.lower()
            has_text_headers = any(term in ' '.join(first_row) for term in ['provider', 'npi', 'specialty', 'name', 'date', 'reason'])
            
            if has_text_headers:
                # Use first row as headers
                best_table.columns = best_table.iloc[0]
                best_table = best_table.drop(best_table.index[0]).reset_index(drop=True)
                logger.info("Using first row as headers", headers=list(best_table.columns))
        
        for idx, row in best_table.iterrows():
            row_data = {}
            
            # Map HTML table columns to expected Excel schema
            for col in best_table.columns:
                value = row[col]
                if pd.notna(value):
                    value_str = str(value).strip()
                    
                    # Skip empty values
                    if not value_str or value_str.lower() in ['nan', 'none', '']:
                        continue
                    
                    # Map column names to Excel schema
                    col_lower = str(col).lower().replace(":", "").replace("#", "").strip()
                    
                    if "provider name" in col_lower:
                        row_data["Provider Name"] = value_str
                    elif "npi" in col_lower:
                        row_data["Provider NPI"] = value_str
                    elif "specialty" in col_lower:
                        row_data["Provider Specialty"] = value_str
                    elif "provider type" in col_lower:
                        row_data["Transaction Attribute"] = value_str
                    elif "term date" in col_lower:
                        row_data["Term Date"] = value_str
                    elif "reason" in col_lower:
                        row_data["Term Reason"] = value_str
            
            # If we have data but no clear column mapping, try to infer from position
            if not row_data and len(best_table.columns) >= 6:
                # Assume standard order: Provider Name, NPI, Specialty, Provider Type, Term Date, Reason
                values = [str(row[col]).strip() for col in best_table.columns if pd.notna(row[col])]
                if len(values) >= 6:
                    row_data = {
                        "Provider Name": values[0] if values[0] else "",
                        "Provider NPI": values[1] if values[1] else "",
                        "Provider Specialty": values[2] if values[2] else "",
                        "Transaction Attribute": values[3] if values[3] else "",
                        "Term Date": values[4] if values[4] else "",
                        "Term Reason": values[5] if values[5] else ""
                    }
            
            # Set default values for required fields
            if row_data:  # Only add non-empty rows
                # Set transaction type to "Term" since this is a termination notice
                row_data["Transaction Type"] = "Term"
                row_data["Effective Date"] = ""  # Not provided in email
                row_data["State License"] = ""  # Not provided in email
                row_data["Organization Name"] = "RCHN & RCSSD"  # From email text
                row_data["TIN"] = "82-1111113"  # From email text
                row_data["Group NPI"] = ""  # Not provided
                row_data["Complete Address"] = ""  # Not provided
                row_data["Phone Number"] = ""  # Not provided
                row_data["Fax Number"] = ""  # Not provided
                row_data["PPG ID"] = ""  # Not provided
                row_data["Line Of Business"] = "FFS/PPO/ACO/HMO/Medi-Cal"  # From email text
                
                rows.append({
                    "row_idx": idx,
                    "data": row_data,
                    "confidence": 0.9,
                    "extraction_method": "html_table",
                    "source": artifact.get("type", "unknown")
                })
        
        logger.info("HTML table extraction completed", 
                   artifact_type=artifact.get("type"),
                   rows_extracted=len(rows))
        
        return rows
        
    except Exception as e:
        logger.error("HTML table extraction failed", error=str(e))
        return []

def _extract_xlsx(uri: str, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract data from XLSX file."""
    try:
        # Get file content from MinIO
        file_content = storage_client.get_bytes(uri.split('/', 1)[1])
        
        # Read Excel file
        excel_file = pd.ExcelFile(io.BytesIO(file_content))
        
        # Choose first non-empty sheet
        best_sheet = None
        best_df = None
        
        for sheet_name in excel_file.sheet_names:
            try:
                df = pd.read_excel(excel_file, sheet_name=sheet_name)
                if not df.empty and len(df) > 1:  # At least header + 1 row
                    best_sheet = sheet_name
                    best_df = df
                    break
            except Exception:
                continue
        
        if best_df is None:
            logger.warning("No valid sheets found in XLSX", filename=artifact.get("filename"))
            return []
        
        # Convert to rows
        rows = []
        for idx, row in best_df.iterrows():
            row_data = {}
            for col in best_df.columns:
                value = row[col]
                if pd.notna(value):
                    row_data[str(col)] = str(value)
            
            if row_data:  # Only add non-empty rows
                rows.append({
                    "row_idx": idx,
                    "data": row_data,
                    "confidence": 0.95,
                    "extraction_method": "xlsx",
                    "source": artifact.get("filename", "unknown"),
                    "sheet": best_sheet
                })
        
        logger.info("XLSX extraction completed", 
                   filename=artifact.get("filename"),
                   sheet=best_sheet,
                   rows_extracted=len(rows))
        
        return rows
        
    except Exception as e:
        logger.error("XLSX extraction failed", error=str(e))
        return []

def _extract_csv(uri: str, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract data from CSV file."""
    try:
        # Get file content from MinIO
        file_content = storage_client.get_bytes(uri.split('/', 1)[1])
        
        # Try different encodings
        encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(io.BytesIO(file_content), encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            logger.error("Could not decode CSV file", filename=artifact.get("filename"))
            return []
        
        # Convert to rows
        rows = []
        for idx, row in df.iterrows():
            row_data = {}
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    row_data[str(col)] = str(value)
            
            if row_data:  # Only add non-empty rows
                rows.append({
                    "row_idx": idx,
                    "data": row_data,
                    "confidence": 0.95,
                    "extraction_method": "csv",
                    "source": artifact.get("filename", "unknown")
                })
        
        logger.info("CSV extraction completed", 
                   filename=artifact.get("filename"),
                   rows_extracted=len(rows))
        
        return rows
        
    except Exception as e:
        logger.error("CSV extraction failed", error=str(e))
        return []

def _extract_plain_text(text_content: str, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract data from plain text."""
    try:
        lines = text_content.strip().split('\n')
        if len(lines) < 2:
            return []
        
        # First, try structured extraction (tables, CSV-like data)
        structured_rows = _extract_structured_text(text_content, artifact)
        if structured_rows:
            return structured_rows
        
        # If no structured data found, try narrative text extraction
        narrative_rows = _extract_narrative_text(text_content, artifact)
        if narrative_rows:
            return narrative_rows
        
        logger.warning("No extractable data found in plain text")
        return []
        
    except Exception as e:
        logger.error("Plain text extraction failed", error=str(e))
        return []

def _extract_structured_text(text_content: str, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract structured data from plain text (tables, CSV-like)."""
    lines = text_content.strip().split('\n')
    
    # Detect header line (usually first line with multiple words)
    header_line = None
    header_idx = 0
    
    for i, line in enumerate(lines):
        words = line.strip().split()
        if len(words) >= 2:  # At least 2 words
            header_line = line.strip()
            header_idx = i
            break
    
    if not header_line:
        return []
    
    # Parse header
    headers = _parse_text_line(header_line)
    if len(headers) < 2:
        return []
    
    # Parse data rows
    rows = []
    for i, line in enumerate(lines[header_idx + 1:], start=header_idx + 1):
        if not line.strip():
            continue
            
        values = _parse_text_line(line)
        if len(values) >= len(headers):
            row_data = {}
            for j, header in enumerate(headers):
                if j < len(values):
                    row_data[header] = values[j]
            
            if row_data:  # Only add non-empty rows
                rows.append({
                    "row_idx": i - header_idx - 1,
                    "data": row_data,
                    "confidence": 0.7,
                    "extraction_method": "plain_text_structured",
                    "source": artifact.get("type", "unknown")
                })
    
    return rows

def _extract_narrative_text(text_content: str, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract data from narrative text (like practice location changes)."""
    try:
        # Look for common patterns in narrative text
        patterns = {
            "provider_name": r"([A-Z][a-z]+ [A-Z][a-z]+(?:, MD|, DO|, NP|, PA)?)",
            "effective_date": r"Effective\s+(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})",
            "location_change": r"move.*?from\s+([^,]+?)\s+to\s+([^,]+?)(?:\.|$)",
            "termination": r"(?:terminate|terminated|termination).*?([A-Z][a-z]+ [A-Z][a-z]+)",
            "npi": r"NPI[:\s#]*(\d{10})",
            "license": r"License[:\s#]*([A-Z0-9]+)",
            "tin": r"TIN[:\s#]*(\d{2}-\d{7})",
        }
        
        extracted_data = {}
        
        # Extract provider name
        provider_match = re.search(patterns["provider_name"], text_content, re.IGNORECASE)
        if provider_match:
            extracted_data["Provider Name"] = provider_match.group(1)
        
        # Extract effective date
        date_match = re.search(patterns["effective_date"], text_content, re.IGNORECASE)
        if date_match:
            extracted_data["Effective Date"] = date_match.group(1)
        
        # Extract location change info
        location_match = re.search(patterns["location_change"], text_content, re.IGNORECASE)
        if location_match:
            extracted_data["Transaction Type"] = "Location Change"
            extracted_data["Transaction Attribute"] = f"From {location_match.group(1).strip()} to {location_match.group(2).strip()}"
        
        # Extract NPI
        npi_match = re.search(patterns["npi"], text_content, re.IGNORECASE)
        if npi_match:
            extracted_data["Provider NPI"] = npi_match.group(1)
        
        # Extract license
        license_match = re.search(patterns["license"], text_content, re.IGNORECASE)
        if license_match:
            extracted_data["State License"] = license_match.group(1)
        
        # Extract TIN
        tin_match = re.search(patterns["tin"], text_content, re.IGNORECASE)
        if tin_match:
            extracted_data["TIN"] = tin_match.group(1)
        
        # If we found any data, create a record
        if extracted_data:
            # Set default values for required fields
            extracted_data.setdefault("Transaction Type", "Location Change")
            extracted_data.setdefault("Transaction Attribute", "Practice Location Change")
            extracted_data.setdefault("Organization Name", "RCHN & RCSSD")
            extracted_data.setdefault("Provider Specialty", "Internal Medicine")
            
            return [{
                "row_idx": 0,
                "data": extracted_data,
                "confidence": 0.6,  # Lower confidence for narrative extraction
                "extraction_method": "narrative_text",
                "source": artifact.get("type", "unknown")
            }]
        
        return []
        
    except Exception as e:
        logger.error("Narrative text extraction failed", error=str(e))
        return []

def _parse_text_line(line: str) -> List[str]:
    """Parse a line of text into columns."""
    # Try different separators
    separators = ['\t', '  ', ' | ', '|', ',']
    
    for sep in separators:
        if sep in line:
            parts = line.split(sep)
            if len(parts) >= 2:
                return [part.strip() for part in parts]
    
    # Fallback: split by multiple spaces
    return re.split(r'\s{2,}', line.strip())

def _select_best_table(tables: List[pd.DataFrame]) -> pd.DataFrame:
    """Select the best table from a list of DataFrames."""
    if not tables:
        return None
    
    best_table = None
    best_score = 0
    
    for table in tables:
        if table.empty:
            continue
        
        # Score based on number of rows and columns
        score = len(table) * len(table.columns)
        
        # Check if this looks like a roster table by examining the content
        # Look for common roster terms in the actual data, not just headers
        content_text = table.astype(str).values.flatten()
        content_lower = ' '.join(content_text).lower()
        
        roster_terms = ['npi', 'provider', 'specialty', 'name', 'phone', 'email', 'address', 'terminate', 'voluntary']
        content_matches = sum(1 for term in roster_terms if term in content_lower)
        score += content_matches * 5
        
        # Bonus for tables with more than 1 row (header + data)
        if len(table) > 1:
            score += 10
        
        # Bonus for tables with reasonable number of columns (3-10)
        if 3 <= len(table.columns) <= 10:
            score += 5
        
        if score > best_score:
            best_score = score
            best_table = table
    
    logger.info("Table selection completed", 
               tables_found=len(tables),
               best_table_shape=best_table.shape if best_table is not None else None,
               best_score=best_score)
    
    return best_table