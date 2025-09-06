"""
HiLabs Roster Processing - VLM Service

Minimal VLM service for local-only operation.
Provides a placeholder /infer endpoint for document processing.
"""

from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
import json

app = FastAPI(
    title="HiLabs VLM Service",
    description="Local VLM service for document processing",
    version="1.0.0"
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "vlm"}


@app.post("/infer")
async def infer(
    file: UploadFile = File(...),
    schema: str = Form(...)
):
    """
    VLM inference endpoint.
    
    This is a placeholder implementation that will be replaced
    with actual VLM processing in later phases.
    """
    try:
        # Parse schema
        schema_data = json.loads(schema)
        
        # For now, return empty results
        # TODO: Implement actual VLM processing
        result = {
            "rows": [],
            "confidence": 0.0,
            "message": "VLM service placeholder - no actual processing yet"
        }
        
        return JSONResponse(content=result)
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"VLM processing failed: {str(e)}"}
        )


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "HiLabs VLM Service",
        "version": "1.0.0",
        "status": "running"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
