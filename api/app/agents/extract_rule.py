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
from prometheus_client import Counter, Histogram
import structlog
import pandas as pd
from bs4 import BeautifulSoup

from ..storage import storage_client

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
        AGENT_RUNS_TOTAL.labels(agent=agent_name).inc()
        
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
        AGENT_LATENCY_SECONDS.labels(agent=agent_name).observe(duration)

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
        
        # Convert to rows
        rows = []
        for idx, row in best_table.iterrows():
            row_data = {}
            for col in best_table.columns:
                value = row[col]
                if pd.notna(value):
                    row_data[str(col)] = str(value)
            
            if row_data:  # Only add non-empty rows
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
            logger.warning("No header line found in plain text")
            return []
        
        # Parse header
        headers = _parse_text_line(header_line)
        if len(headers) < 2:
            logger.warning("Insufficient headers in plain text")
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
                        "extraction_method": "plain_text",
                        "source": artifact.get("type", "unknown")
                    })
        
        logger.info("Plain text extraction completed", 
                   artifact_type=artifact.get("type"),
                   rows_extracted=len(rows))
        
        return rows
        
    except Exception as e:
        logger.error("Plain text extraction failed", error=str(e))
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
        
        # Bonus for common roster headers
        headers = [str(col).lower() for col in table.columns]
        roster_headers = ['npi', 'name', 'provider', 'specialty', 'phone', 'email', 'address']
        header_matches = sum(1 for header in roster_headers if any(h in header for h in headers))
        score += header_matches * 10
        
        if score > best_score:
            best_score = score
            best_table = table
    
    return best_table