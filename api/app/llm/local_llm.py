"""
Local LLM Client

This module provides a simple wrapper around small local language models for:
- Classification disambiguation
- Header mapping and column alignment
- Natural language explanations
- Issue descriptions

Uses CPU-only inference with strict token limits and graceful fallbacks.
"""

import os
import gc
import time
from typing import Dict, Any, List, Optional, Union
import structlog

from ..metrics import get_vlm_invocations_total
import structlog

logger = structlog.get_logger(__name__)

class LocalLLMClient:
    """
    Local LLM client for text processing tasks.
    
    Supports small models like Qwen2.5-1.5B-Instruct or phi-3-mini
    with CPU-only inference and strict resource limits.
    """
    
    def __init__(self, model_name: str = None, max_tokens: int = 256):
        """
        Initialize the local LLM client.
        
        Args:
            model_name: Hugging Face model name (None to disable LLM)
            max_tokens: Maximum tokens for generation
        """
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.model = None
        self.tokenizer = None
        self.device = "cpu"
        self.is_loaded = False
        self.is_enabled = model_name is not None
        
        if self.is_enabled:
            logger.info("LocalLLMClient initialized", model=model_name, max_tokens=max_tokens)
        else:
            logger.info("LocalLLMClient disabled - no model specified")
    
    def _load_model(self) -> bool:
        """Load the model and tokenizer. Returns True if successful."""
        if not self.is_enabled:
            logger.info("LLM disabled - skipping model load")
            return False
            
        if self.is_loaded:
            return True
        
        try:
            logger.info("Loading local LLM model", model=self.model_name)
            
            # Import transformers only when needed
            from transformers import AutoTokenizer, AutoModelForCausalLM
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_name,
                trust_remote_code=True,
                use_fast=True
            )
            
            # Add padding token if not present
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model with CPU-only inference
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                trust_remote_code=True,
                torch_dtype="auto",
                device_map="cpu",
                low_cpu_mem_usage=True
            )
            
            self.is_loaded = True
            logger.info("Local LLM model loaded successfully", model=self.model_name)
            
            # Track model loading
            get_vlm_invocations_total().labels(model="local_llm", status="model_loaded").inc()
            
            return True
            
        except Exception as e:
            logger.error("Failed to load local LLM model", 
                        model=self.model_name, 
                        error=str(e),
                        error_type=type(e).__name__)
            
            # Clean up on failure
            self.model = None
            self.tokenizer = None
            self.is_loaded = False
            
            # Track model loading failure
            get_vlm_invocations_total().labels(model="local_llm", status="model_load_failed").inc()
            
            return False
    
    def _cleanup(self):
        """Clean up model resources."""
        if self.model is not None:
            del self.model
            self.model = None
        
        if self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
        
        self.is_loaded = False
        
        # Force garbage collection
        gc.collect()
        
        logger.debug("Local LLM resources cleaned up")
    
    def classify_document_type(self, content: str, headers: List[str]) -> Dict[str, Any]:
        """
        Classify document type and suggest processing approach.
        
        Args:
            content: Document content (first 1000 chars)
            headers: List of column headers found
        
        Returns:
            Classification result with confidence and suggestions
        """
        if not self._load_model():
            return self._fallback_classification(content, headers)
        
        try:
            # Create classification prompt
            prompt = self._create_classification_prompt(content, headers)
            
            # Generate response
            response = self._generate_response(prompt, max_new_tokens=100)
            
            # Parse response
            result = self._parse_classification_response(response)
            
            # Track successful classification
            get_vlm_invocations_total().labels(model="local_llm", status="classification_success").inc()
            
            return result
            
        except Exception as e:
            logger.error("Classification failed", error=str(e))
            get_vlm_invocations_total().labels(model="local_llm", status="classification_failed").inc()
            return self._fallback_classification(content, headers)
    
    def suggest_header_mapping(self, extracted_headers: List[str], target_schema: List[str]) -> Dict[str, Any]:
        """
        Suggest mapping between extracted headers and target schema.
        
        Args:
            extracted_headers: Headers found in document
            target_schema: Target Excel schema headers
        
        Returns:
            Mapping suggestions with confidence scores
        """
        if not self._load_model():
            return self._fallback_header_mapping(extracted_headers, target_schema)
        
        try:
            # Create mapping prompt
            prompt = self._create_mapping_prompt(extracted_headers, target_schema)
            
            # Generate response
            response = self._generate_response(prompt, max_new_tokens=200)
            
            # Parse response
            result = self._parse_mapping_response(response, extracted_headers, target_schema)
            
            # Track successful mapping
            get_vlm_invocations_total().labels(model="local_llm", status="mapping_success").inc()
            
            return result
            
        except Exception as e:
            logger.error("Header mapping failed", error=str(e))
            get_vlm_invocations_total().labels(model="local_llm", status="mapping_failed").inc()
            return self._fallback_header_mapping(extracted_headers, target_schema)
    
    def explain_validation_issue(self, issue: Dict[str, Any]) -> str:
        """
        Generate natural language explanation for validation issues.
        
        Args:
            issue: Validation issue dictionary
        
        Returns:
            Human-readable explanation
        """
        if not self._load_model():
            return self._fallback_issue_explanation(issue)
        
        try:
            # Create explanation prompt
            prompt = self._create_explanation_prompt(issue)
            
            # Generate response
            response = self._generate_response(prompt, max_new_tokens=150)
            
            # Clean up response
            explanation = self._clean_response(response)
            
            # Track successful explanation
            get_vlm_invocations_total().labels(model="local_llm", status="explanation_success").inc()
            
            return explanation
            
        except Exception as e:
            logger.error("Issue explanation failed", error=str(e))
            get_vlm_invocations_total().labels(model="local_llm", status="explanation_failed").inc()
            return self._fallback_issue_explanation(issue)
    
    def _generate_response(self, prompt: str, max_new_tokens: int = 100) -> str:
        """Generate response from the model."""
        try:
            # Tokenize input
            inputs = self.tokenizer.encode(prompt, return_tensors="pt", truncation=True, max_length=1024)
            
            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    inputs,
                    max_new_tokens=max_new_tokens,
                    do_sample=True,
                    temperature=0.7,
                    top_p=0.9,
                    pad_token_id=self.tokenizer.eos_token_id,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            
            # Decode response
            response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Remove input prompt from response
            if prompt in response:
                response = response.replace(prompt, "").strip()
            
            return response
            
        except Exception as e:
            logger.error("Text generation failed", error=str(e))
            raise
    
    def _create_classification_prompt(self, content: str, headers: List[str]) -> str:
        """Create prompt for document classification."""
        return f"""Analyze this document and classify its type:

Content preview: {content[:500]}...
Headers found: {', '.join(headers)}

Classify as one of: HTML_TABLE, XLSX, CSV, PDF_NATIVE, PDF_SCANNED, PLAIN_TEXT
Provide confidence (0-1) and reasoning.

Response format:
Type: [CLASSIFICATION]
Confidence: [0.0-1.0]
Reasoning: [brief explanation]"""
    
    def _create_mapping_prompt(self, extracted_headers: List[str], target_schema: List[str]) -> str:
        """Create prompt for header mapping."""
        return f"""Map these extracted headers to the target schema:

Extracted: {', '.join(extracted_headers)}
Target: {', '.join(target_schema)}

Provide mapping suggestions with confidence scores.
Format as JSON with "mappings" array containing "source", "target", "confidence" fields."""
    
    def _create_explanation_prompt(self, issue: Dict[str, Any]) -> str:
        """Create prompt for issue explanation."""
        return f"""Explain this data validation issue in simple terms:

Field: {issue.get('field', 'Unknown')}
Level: {issue.get('level', 'Unknown')}
Message: {issue.get('message', 'Unknown')}

Provide a clear, helpful explanation for a user."""
    
    def _parse_classification_response(self, response: str) -> Dict[str, Any]:
        """Parse classification response."""
        try:
            lines = response.strip().split('\n')
            result = {
                "type": "UNKNOWN",
                "confidence": 0.5,
                "reasoning": "Unable to parse response"
            }
            
            for line in lines:
                if line.startswith("Type:"):
                    result["type"] = line.split(":", 1)[1].strip()
                elif line.startswith("Confidence:"):
                    try:
                        result["confidence"] = float(line.split(":", 1)[1].strip())
                    except ValueError:
                        pass
                elif line.startswith("Reasoning:"):
                    result["reasoning"] = line.split(":", 1)[1].strip()
            
            return result
            
        except Exception as e:
            logger.error("Failed to parse classification response", error=str(e))
            return {"type": "UNKNOWN", "confidence": 0.5, "reasoning": "Parse error"}
    
    def _parse_mapping_response(self, response: str, extracted_headers: List[str], target_schema: List[str]) -> Dict[str, Any]:
        """Parse mapping response."""
        try:
            # Try to extract JSON from response
            import json
            import re
            
            # Find JSON-like structure
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                data = json.loads(json_str)
                return {"mappings": data.get("mappings", [])}
            
            # Fallback to simple parsing
            mappings = []
            for extracted in extracted_headers:
                for target in target_schema:
                    if extracted.lower() in target.lower() or target.lower() in extracted.lower():
                        mappings.append({
                            "source": extracted,
                            "target": target,
                            "confidence": 0.8
                        })
            
            return {"mappings": mappings}
            
        except Exception as e:
            logger.error("Failed to parse mapping response", error=str(e))
            return {"mappings": []}
    
    def _clean_response(self, response: str) -> str:
        """Clean up generated response."""
        # Remove common artifacts
        response = response.strip()
        response = response.replace("Response:", "").strip()
        response = response.replace("Explanation:", "").strip()
        
        # Limit length
        if len(response) > 200:
            response = response[:200] + "..."
        
        return response
    
    def _fallback_classification(self, content: str, headers: List[str]) -> Dict[str, Any]:
        """Fallback classification without LLM."""
        # Simple rule-based classification
        content_lower = content.lower()
        headers_lower = [h.lower() for h in headers]
        
        if any(tag in content_lower for tag in ['<table>', '<tr>', '<td>']):
            return {"type": "HTML_TABLE", "confidence": 0.8, "reasoning": "HTML table detected"}
        elif any(ext in headers_lower for ext in ['.xlsx', '.xls']):
            return {"type": "XLSX", "confidence": 0.8, "reasoning": "Excel file detected"}
        elif any(ext in headers_lower for ext in ['.csv']):
            return {"type": "CSV", "confidence": 0.8, "reasoning": "CSV file detected"}
        elif any(ext in headers_lower for ext in ['.pdf']):
            return {"type": "PDF_UNKNOWN", "confidence": 0.6, "reasoning": "PDF file detected"}
        else:
            return {"type": "PLAIN_TEXT", "confidence": 0.5, "reasoning": "Plain text fallback"}
    
    def _fallback_header_mapping(self, extracted_headers: List[str], target_schema: List[str]) -> Dict[str, Any]:
        """Fallback header mapping without LLM."""
        mappings = []
        
        for extracted in extracted_headers:
            best_match = None
            best_score = 0
            
            for target in target_schema:
                # Simple string similarity
                extracted_lower = extracted.lower()
                target_lower = target.lower()
                
                if extracted_lower in target_lower or target_lower in extracted_lower:
                    score = min(len(extracted_lower), len(target_lower)) / max(len(extracted_lower), len(target_lower))
                    if score > best_score:
                        best_score = score
                        best_match = target
            
            if best_match and best_score > 0.3:
                mappings.append({
                    "source": extracted,
                    "target": best_match,
                    "confidence": best_score
                })
        
        return {"mappings": mappings}
    
    def _fallback_issue_explanation(self, issue: Dict[str, Any]) -> str:
        """Fallback issue explanation without LLM."""
        field = issue.get('field', 'Unknown field')
        level = issue.get('level', 'error')
        message = issue.get('message', 'Unknown issue')
        
        if level == 'error':
            return f"There's a problem with the {field} field: {message}"
        else:
            return f"Warning for {field}: {message}"

# Global LLM client instance
_llm_client: Optional[LocalLLMClient] = None

def get_llm_client() -> Optional[LocalLLMClient]:
    """Get the global LLM client instance."""
    global _llm_client
    
    if _llm_client is None:
        # Check if LLM is enabled
        enabled = os.getenv("LOCAL_LLM_ENABLED", "false").lower() == "true"
        if not enabled:
            logger.info("Local LLM disabled via LOCAL_LLM_ENABLED=false")
            return None
        
        # Get model name from environment - use a smaller, faster model
        model_name = os.getenv("LOCAL_LLM_MODEL", "microsoft/DialoGPT-small")
        max_tokens = int(os.getenv("LOCAL_LLM_MAX_TOKENS", "256"))
        
        # If no model specified, return None (graceful fallback)
        if not model_name or model_name.lower() in ["none", "null", ""]:
            logger.info("No LLM model specified - using rule-based fallbacks")
            return None
        
        try:
            _llm_client = LocalLLMClient(model_name=model_name, max_tokens=max_tokens)
            logger.info("Local LLM client created", model=model_name)
        except Exception as e:
            logger.error("Failed to create LLM client", error=str(e))
            logger.info("Falling back to rule-based processing")
            _llm_client = None
    
    return _llm_client

def cleanup_llm_client():
    """Clean up the global LLM client."""
    global _llm_client
    
    if _llm_client is not None:
        _llm_client._cleanup()
        _llm_client = None
        logger.info("Local LLM client cleaned up")
