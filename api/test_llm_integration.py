#!/usr/bin/env python3
"""
Test script for LLM integration
Tests the SLM endpoint and extraction functionality
"""

import json
import sys
import os
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

from app.agents.llm_extractor import _call_llm_for_extraction, _get_llm_health
from app.config import get_settings

def test_llm_health():
    """Test if the LLM service is available"""
    print("Testing LLM health...")
    
    settings = get_settings()
    print(f"SLM enabled: {settings.slm_enabled}")
    print(f"SLM base URL: {settings.slm_base_url}")
    print(f"SLM model: {settings.slm_model_name}")
    
    if settings.slm_enabled:
        health = _get_llm_health()
        print(f"LLM health check: {'PASS' if health else 'FAIL'}")
        return health
    else:
        print("SLM is disabled in configuration")
        return False

def test_llm_extraction():
    """Test LLM extraction with sample data"""
    print("\nTesting LLM extraction...")
    
    # Sample email content
    sample_text = """
    Provider Roster Update
    
    Please add the following provider to our network:
    
    Provider Name: Dr. John Smith
    NPI: 1234567890
    Specialty: Internal Medicine
    Effective Date: 2024-01-15
    Organization: ABC Medical Group
    Address: 123 Main St, City, ST 12345
    Phone: (555) 123-4567
    License: MD12345
    TIN: 12-3456789
    
    Also, please terminate Dr. Jane Doe (NPI: 0987654321) effective 2024-02-01.
    Reason: Retirement
    """
    
    try:
        result = _call_llm_for_extraction(sample_text)
        print(f"Extraction successful! Found {len(result)} records")
        
        for i, record in enumerate(result):
            print(f"\nRecord {i+1}:")
            for key, value in record.items():
                if value is not None:
                    print(f"  {key}: {value}")
        
        return True
        
    except Exception as e:
        print(f"Extraction failed: {str(e)}")
        return False

def main():
    """Main test function"""
    print("=== LLM Integration Test ===")
    
    # Test health
    health_ok = test_llm_health()
    
    if health_ok:
        # Test extraction
        extraction_ok = test_llm_extraction()
        
        if extraction_ok:
            print("\n✅ All tests passed!")
            return 0
        else:
            print("\n❌ Extraction test failed!")
            return 1
    else:
        print("\n❌ Health check failed!")
        print("Make sure your SLM service is running on localhost:5000")
        return 1

if __name__ == "__main__":
    exit(main())
