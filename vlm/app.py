"""
Local VLM Service

This service provides Vision Language Model capabilities for document processing:
- MiniCPM-V for complex document understanding
- Fallback to pdfplumber table extraction
- OCR fallback for scanned documents
- Always runs locally, no external HTTP calls
"""

import os
import time
import json
import logging
from typing import List, Dict, Any, Optional
from io import BytesIO

import torch
import pdfplumber
import pytesseract
from PIL import Image
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import structlog

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Local VLM Service",
    description="Vision Language Model for document extraction (MiniCPM-V or CPU fallback)",
    version="0.1.0",
)

# Global variables for model state
vlm_model = None
vlm_processor = None
model_loaded = False
fallback_enabled = True

class InferRequest(BaseModel):
    schema: List[str]

class InferResponse(BaseModel):
    rows: List[Dict[str, str]]
    method: str
    confidence: float
    processing_time: float

def load_vlm_model():
    """Load the VLM model (MiniCPM-V or similar)."""
    global vlm_model, vlm_processor, model_loaded
    
    try:
        logger.info("Attempting to load VLM model...")
        
        # Check available resources
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        
        if device == "cpu":
            logger.warning("CUDA not available, using CPU fallback")
            model_loaded = False
            return
        
        # Try to load MiniCPM-V or similar VLM
        # Note: This is a placeholder - actual model loading would depend on specific VLM implementation
        try:
            from transformers import AutoModel, AutoProcessor
            
            # Example model loading (replace with actual MiniCPM-V model)
            model_name = "openbmb/MiniCPM-V"  # or similar VLM model
            
            logger.info(f"Loading model: {model_name}")
            vlm_processor = AutoProcessor.from_pretrained(model_name)
            vlm_model = AutoModel.from_pretrained(
                model_name,
                torch_dtype=torch.float16 if device == "cuda" else torch.float32,
                device_map="auto" if device == "cuda" else None
            )
            
            if device == "cuda":
                vlm_model = vlm_model.cuda()
            
            model_loaded = True
            logger.info("VLM model loaded successfully")
            
        except Exception as e:
            logger.warning(f"Failed to load VLM model: {e}")
            logger.info("Falling back to rule-based extraction")
            model_loaded = False
            
    except Exception as e:
        logger.error(f"Error during model loading: {e}")
        model_loaded = False

def extract_with_vlm(image: Image.Image, schema: List[str]) -> List[Dict[str, str]]:
    """Extract data using VLM model."""
    global vlm_model, vlm_processor
    
    try:
        if not model_loaded or vlm_model is None or vlm_processor is None:
            raise Exception("VLM model not loaded")
        
        # Prepare prompt for VLM
        schema_str = ", ".join(schema)
        prompt = f"Extract the following information from this document: {schema_str}. Return the data in JSON format with the exact column names provided."
        
        # Process image and text
        inputs = vlm_processor(images=image, text=prompt, return_tensors="pt")
        
        # Move to device
        device = next(vlm_model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        
        # Generate response
        with torch.no_grad():
            outputs = vlm_model.generate(**inputs, max_length=512, do_sample=False)
        
        # Decode response
        response = vlm_processor.decode(outputs[0], skip_special_tokens=True)
        
        # Parse JSON response
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = response[json_start:json_end]
                data = json.loads(json_str)
                
                # Convert to expected format
                rows = []
                if isinstance(data, dict):
                    rows.append({str(k): str(v) for k, v in data.items()})
                elif isinstance(data, list):
                    rows = [{str(k): str(v) for k, v in item.items()} for item in data]
                
                return rows
            else:
                raise Exception("No valid JSON found in response")
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse VLM JSON response: {e}")
            return []
            
    except Exception as e:
        logger.error(f"VLM extraction failed: {e}")
        raise

def extract_with_pdfplumber(pdf_bytes: bytes, schema: List[str]) -> List[Dict[str, str]]:
    """Extract data using pdfplumber as fallback."""
    try:
        rows = []
        
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                # Try to extract tables
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        if len(table) >= 2:  # At least header + 1 row
                            # Use first row as headers
                            headers = [str(cell).strip() if cell else f"col_{i}" for i, cell in enumerate(table[0])]
                            
                            # Map headers to schema
                            header_mapping = {}
                            for schema_col in schema:
                                for i, header in enumerate(headers):
                                    if schema_col.lower() in header.lower() or header.lower() in schema_col.lower():
                                        header_mapping[schema_col] = i
                                        break
                            
                            # Extract data rows
                            for row in table[1:]:
                                row_data = {}
                                for schema_col, col_idx in header_mapping.items():
                                    if col_idx < len(row) and row[col_idx]:
                                        row_data[schema_col] = str(row[col_idx]).strip()
                                
                                if row_data:
                                    rows.append(row_data)
        
        return rows
        
    except Exception as e:
        logger.error(f"PDFplumber extraction failed: {e}")
        return []

def extract_with_ocr(image: Image.Image, schema: List[str]) -> List[Dict[str, str]]:
    """Extract data using OCR as final fallback."""
    try:
        # Perform OCR
        text = pytesseract.image_to_string(image, config='--psm 6')
        
        # Simple text parsing - look for tabular patterns
        lines = text.strip().split('\n')
        if len(lines) < 2:
            return []
        
        # Try to find header line
        header_line = None
        for line in lines:
            words = line.strip().split()
            if len(words) >= 2:
                header_line = line
                break
        
        if not header_line:
            return []
        
        # Parse headers
        headers = [h.strip() for h in header_line.split() if h.strip()]
        
        # Map headers to schema
        header_mapping = {}
        for schema_col in schema:
            for i, header in enumerate(headers):
                if schema_col.lower() in header.lower() or header.lower() in schema_col.lower():
                    header_mapping[schema_col] = i
                    break
        
        # Parse data rows
        rows = []
        for line in lines[1:]:
            if not line.strip():
                continue
                
            values = [v.strip() for v in line.split() if v.strip()]
            if len(values) >= len(header_mapping):
                row_data = {}
                for schema_col, col_idx in header_mapping.items():
                    if col_idx < len(values):
                        row_data[schema_col] = values[col_idx]
                
                if row_data:
                    rows.append(row_data)
        
        return rows
        
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        return []

@app.on_event("startup")
async def startup_event():
    """Initialize the VLM service on startup."""
    logger.info("Starting VLM service...")
    
    # Load VLM model
    load_vlm_model()
    
    logger.info("VLM service startup complete", model_loaded=model_loaded)

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("VLM service shutdown")

@app.get("/health", summary="Health Check", tags=["Monitoring"])
async def health_check():
    """
    Performs a health check on the VLM service.
    Returns 200 OK if the service is running.
    """
    return {
        "status": "ok",
        "model_loaded": model_loaded,
        "fallback_enabled": fallback_enabled,
        "device": "cuda" if torch.cuda.is_available() else "cpu"
    }

@app.post("/infer", response_model=InferResponse, summary="Infer Roster Data", tags=["VLM"])
async def infer_data(
    file: UploadFile = File(..., description="PDF page or image file"),
    schema: str = Form(..., description="JSON array of column names, e.g., '[\"NPI\", \"Name\"]'")
):
    """
    Processes a document (PDF page or image) to extract roster data
    based on a provided schema.
    
    Args:
        file: PDF page or image file
        schema: JSON array of column names
    
    Returns:
        Extracted data in the specified schema format
    """
    start_time = time.time()
    
    try:
        # Parse schema
        try:
            schema_list = json.loads(schema)
            if not isinstance(schema_list, list):
                raise ValueError("Schema must be a list")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON schema")
        
        # Read file content
        file_content = await file.read()
        if not file_content:
            raise HTTPException(status_code=400, detail="Empty file")
        
        # Determine file type and process accordingly
        content_type = file.content_type or ""
        filename = file.filename or ""
        
        rows = []
        method = "unknown"
        confidence = 0.0
        
        if content_type.startswith("image/") or filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            # Process as image
            try:
                image = Image.open(BytesIO(file_content))
                
                # Try VLM first if available
                if model_loaded:
                    try:
                        rows = extract_with_vlm(image, schema_list)
                        method = "vlm"
                        confidence = 0.9
                    except Exception as e:
                        logger.warning(f"VLM failed, falling back to OCR: {e}")
                        rows = extract_with_ocr(image, schema_list)
                        method = "ocr"
                        confidence = 0.6
                else:
                    rows = extract_with_ocr(image, schema_list)
                    method = "ocr"
                    confidence = 0.6
                    
            except Exception as e:
                logger.error(f"Image processing failed: {e}")
                raise HTTPException(status_code=500, detail=f"Image processing failed: {e}")
        
        elif content_type == "application/pdf" or filename.lower().endswith('.pdf'):
            # Process as PDF
            try:
                # Try VLM first if available
                if model_loaded:
                    try:
                        # Convert PDF to image for VLM
                        with pdfplumber.open(BytesIO(file_content)) as pdf:
                            if pdf.pages:
                                page = pdf.pages[0]
                                # Convert page to image
                                image = page.to_image(resolution=200).original
                                rows = extract_with_vlm(image, schema_list)
                                method = "vlm"
                                confidence = 0.9
                    except Exception as e:
                        logger.warning(f"VLM failed, falling back to pdfplumber: {e}")
                        rows = extract_with_pdfplumber(file_content, schema_list)
                        method = "pdfplumber"
                        confidence = 0.7
                else:
                    rows = extract_with_pdfplumber(file_content, schema_list)
                    method = "pdfplumber"
                    confidence = 0.7
                    
            except Exception as e:
                logger.error(f"PDF processing failed: {e}")
                raise HTTPException(status_code=500, detail=f"PDF processing failed: {e}")
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        processing_time = time.time() - start_time
        
        logger.info("VLM inference completed", 
                   method=method, 
                   rows_count=len(rows), 
                   processing_time=processing_time)
        
        return InferResponse(
            rows=rows,
            method=method,
            confidence=confidence,
            processing_time=processing_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"VLM inference failed: {e}")
        raise HTTPException(status_code=500, detail=f"Inference failed: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)