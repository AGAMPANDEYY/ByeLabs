"""
Extract PDF Agent

This agent handles PDF-specific extraction:
- Extract text and tables from PDFs
- Handle different PDF formats and layouts
- Determine if PDF is native or scanned
- Prepare data for rule-based or VLM processing
"""

import time
import io
from typing import Dict, Any, List
from ..metrics import get_agent_runs_total, get_agent_latency_seconds
import structlog
import pdfplumber
import camelot
import fitz  # PyMuPDF
from PIL import Image

from ..storage import storage_client, generate_object_key, calculate_checksum

logger = structlog.get_logger(__name__)

# Metrics are now imported from metrics module

def run(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Perform PDF-specific data extraction.
    
    Args:
        state: Current processing state
    
    Returns:
        Updated state with PDF extraction results
    """
    start_time = time.time()
    agent_name = "extract_pdf"
    
    logger.info("Starting extract PDF agent", job_id=state.get("job_id"))
    
    try:
        # Increment run counter
        get_agent_runs_total().labels(agent=agent_name, status="started").inc()
        
        classification = state.get("classification", {})
        artifacts = classification.get("artifacts", [])
        
        # Find PDF artifacts
        pdf_artifacts = [a for a in artifacts if a.get("document_type") == "PDF_UNKNOWN"]
        
        if not pdf_artifacts:
            logger.info("No PDF artifacts found")
            return state
        
        extracted_data = []
        vlm_inputs = []
        needs_vlm = False
        
        # Process each PDF artifact
        for artifact in pdf_artifacts:
            uri = artifact.get("uri", "")
            filename = artifact.get("filename", "")
            
            # Get PDF content from MinIO
            try:
                pdf_content = storage_client.get_bytes(uri.split('/', 1)[1])
            except Exception as e:
                logger.error("Failed to retrieve PDF", filename=filename, error=str(e))
                continue
            
            # Determine if PDF is native or scanned
            pdf_type = _classify_pdf_type(pdf_content)
            
            if pdf_type == "PDF_NATIVE":
                # Try rule-based extraction
                rows = _extract_native_pdf(pdf_content, artifact)
                if rows:
                    extracted_data.extend(rows)
                else:
                    needs_vlm = True
                    
            elif pdf_type == "PDF_SCANNED":
                # Prepare for VLM processing
                page_images = _prepare_scanned_pdf(pdf_content, artifact)
                if page_images:
                    vlm_inputs.extend(page_images)
                    needs_vlm = True
                else:
                    logger.warning("Failed to prepare scanned PDF for VLM", filename=filename)
        
        # Update state with PDF extraction results
        state.update({
            "pdf_extracted_data": extracted_data,
            "vlm_inputs": vlm_inputs,
            "needs_vlm": needs_vlm or len(extracted_data) == 0,
            "pdf_stats": {
                "pdfs_processed": len(pdf_artifacts),
                "native_pdfs": len([a for a in pdf_artifacts if _classify_pdf_type(storage_client.get_bytes(a.get("uri", "").split('/', 1)[1])) == "PDF_NATIVE"]),
                "scanned_pdfs": len([a for a in pdf_artifacts if _classify_pdf_type(storage_client.get_bytes(a.get("uri", "").split('/', 1)[1])) == "PDF_SCANNED"]),
                "rows_extracted": len(extracted_data),
                "vlm_pages": len(vlm_inputs)
            },
            "processing_notes": state.get("processing_notes", []) + [
                f"PDF extraction completed: {len(extracted_data)} rows, {len(vlm_inputs)} VLM pages",
                f"VLM needed: {needs_vlm}"
            ]
        })
        
        logger.info("Extract PDF agent completed", 
                   job_id=state.get("job_id"),
                   pdfs_processed=len(pdf_artifacts),
                   rows_extracted=len(extracted_data),
                   vlm_pages=len(vlm_inputs))
        
        return state
        
    except Exception as e:
        logger.error("Extract PDF agent failed", job_id=state.get("job_id"), error=str(e))
        state.update({
            "error": str(e),
            "failed_agent": agent_name
        })
        return state
        
    finally:
        # Record latency
        duration = time.time() - start_time
        get_agent_latency_seconds().labels(agent=agent_name).observe(duration)

def _classify_pdf_type(pdf_content: bytes) -> str:
    """Determine if PDF is native (text-based) or scanned (image-based)."""
    try:
        # Try to extract text with pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            total_text = ""
            for page in pdf.pages[:3]:  # Check first 3 pages
                text = page.extract_text()
                if text:
                    total_text += text
            
            # If we got substantial text, it's likely native
            if len(total_text.strip()) > 100:
                return "PDF_NATIVE"
            else:
                return "PDF_SCANNED"
                
    except Exception as e:
        logger.warning("Failed to classify PDF type", error=str(e))
        return "PDF_SCANNED"  # Default to scanned if we can't determine

def _extract_native_pdf(pdf_content: bytes, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract data from native PDF using pdfplumber and camelot."""
    try:
        extracted_rows = []
        
        with pdfplumber.open(io.BytesIO(pdf_content)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Try pdfplumber tables first
                tables = page.extract_tables()
                if tables:
                    for table_idx, table in enumerate(tables):
                        rows = _process_pdfplumber_table(table, page_num, table_idx, artifact)
                        extracted_rows.extend(rows)
                
                # If no tables found with pdfplumber, try camelot
                if not tables:
                    try:
                        camelot_tables = camelot.read_pdf(io.BytesIO(pdf_content), pages=str(page_num + 1))
                        for table_idx, table in enumerate(camelot_tables):
                            rows = _process_camelot_table(table, page_num, table_idx, artifact)
                            extracted_rows.extend(rows)
                    except Exception as e:
                        logger.warning("Camelot extraction failed", page=page_num, error=str(e))
        
        logger.info("Native PDF extraction completed", 
                   filename=artifact.get("filename"),
                   rows_extracted=len(extracted_rows))
        
        return extracted_rows
        
    except Exception as e:
        logger.error("Native PDF extraction failed", error=str(e))
        return []

def _process_pdfplumber_table(table: List[List[str]], page_num: int, table_idx: int, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process a table extracted by pdfplumber."""
    if not table or len(table) < 2:
        return []
    
    # Use first row as headers
    headers = [str(cell).strip() if cell else f"col_{i}" for i, cell in enumerate(table[0])]
    
    rows = []
    for row_idx, row in enumerate(table[1:], start=1):
        row_data = {}
        for col_idx, cell in enumerate(row):
            if col_idx < len(headers) and cell:
                row_data[headers[col_idx]] = str(cell).strip()
        
        if row_data:  # Only add non-empty rows
            rows.append({
                "row_idx": f"{page_num}_{table_idx}_{row_idx}",
                "data": row_data,
                "confidence": 0.8,
                "extraction_method": "pdfplumber",
                "source": artifact.get("filename", "unknown"),
                "page": page_num + 1,
                "table": table_idx + 1
            })
    
    return rows

def _process_camelot_table(table, page_num: int, table_idx: int, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Process a table extracted by camelot."""
    try:
        df = table.df
        if df.empty or len(df) < 2:
            return []
        
        # Use first row as headers
        headers = [str(col).strip() for col in df.iloc[0]]
        df_data = df.iloc[1:]  # Skip header row
        
        rows = []
        for idx, row in df_data.iterrows():
            row_data = {}
            for col_idx, value in enumerate(row):
                if col_idx < len(headers) and pd.notna(value):
                    row_data[headers[col_idx]] = str(value).strip()
            
            if row_data:  # Only add non-empty rows
                rows.append({
                    "row_idx": f"{page_num}_{table_idx}_{idx}",
                    "data": row_data,
                    "confidence": 0.85,
                    "extraction_method": "camelot",
                    "source": artifact.get("filename", "unknown"),
                    "page": page_num + 1,
                    "table": table_idx + 1
                })
        
        return rows
        
    except Exception as e:
        logger.error("Failed to process camelot table", error=str(e))
        return []

def _prepare_scanned_pdf(pdf_content: bytes, artifact: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Prepare scanned PDF pages as images for VLM processing."""
    try:
        vlm_inputs = []
        
        # Open PDF with PyMuPDF
        doc = fitz.open(stream=pdf_content, filetype="pdf")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Render page to image
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            
            # Store image in MinIO
            storage_key = generate_object_key("vlm_inputs", f"{artifact.get('filename', 'unknown')}_page_{page_num + 1}.png")
            
            try:
                uri = storage_client.put_bytes(
                    key=storage_key,
                    data=img_data,
                    content_type="image/png"
                )
                
                vlm_inputs.append({
                    "type": "page_image",
                    "uri": uri,
                    "page_number": page_num + 1,
                    "filename": artifact.get("filename", "unknown"),
                    "size": len(img_data),
                    "checksum": calculate_checksum(img_data)
                })
                
            except Exception as e:
                logger.error("Failed to store page image", page=page_num, error=str(e))
        
        doc.close()
        
        logger.info("Scanned PDF preparation completed", 
                   filename=artifact.get("filename"),
                   pages_prepared=len(vlm_inputs))
        
        return vlm_inputs
        
    except Exception as e:
        logger.error("Scanned PDF preparation failed", error=str(e))
        return []