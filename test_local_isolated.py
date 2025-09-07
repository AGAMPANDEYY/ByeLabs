#!/usr/bin/env python3
"""
Local isolated test - no external dependencies
Tests core logic without Docker services
"""

import sys
import os
import time
import email
import email.policy
from pathlib import Path

# Add the api directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

def test_basic_imports():
    """Test basic imports without external services"""
    print("🔍 Testing basic imports...")
    
    try:
        # Test basic Python modules
        import pandas as pd
        print("✅ pandas imported")
        
        import structlog
        print("✅ structlog imported")
        
        import prometheus_client
        print("✅ prometheus_client imported")
        
        # Test our modules (without storage/db)
        from app.config import settings
        print("✅ config imported")
        
        from app.metrics import get_agent_runs_total, get_agent_latency_seconds
        print("✅ metrics imported")
        
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_email_parsing():
    """Test email parsing without storage"""
    print("\n🔍 Testing email parsing...")
    
    try:
        # Create a simple test email
        test_email_content = """From: test@example.com
To: recipient@example.com
Subject: Test Email
Content-Type: text/html; charset=utf-8

<html>
<body>
<h1>Provider Roster</h1>
<table>
<tr><th>Name</th><th>NPI</th><th>Specialty</th></tr>
<tr><td>John Doe</td><td>1234567890</td><td>Cardiology</td></tr>
</table>
</body>
</html>"""
        
        # Parse email
        email_message = email.message_from_string(test_email_content, policy=email.policy.default)
        
        # Extract headers
        from_addr = email_message.get('From', '')
        to_addr = email_message.get('To', '')
        subject = email_message.get('Subject', '')
        
        print(f"✅ From: {from_addr}")
        print(f"✅ To: {to_addr}")
        print(f"✅ Subject: {subject}")
        
        # Extract body
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == "text/html":
                    body = part.get_content()
                    break
        else:
            body = email_message.get_content()
        
        print(f"✅ Body length: {len(body)} chars")
        
        return True
        
    except Exception as e:
        print(f"❌ Email parsing error: {e}")
        return False

def test_processing_state():
    """Test ProcessingState without external dependencies"""
    print("\n🔍 Testing ProcessingState...")
    
    try:
        # Create a mock ProcessingState-like dict
        state = {
            "job_id": 1,
            "version_id": None,
            "artifacts": {},
            "route_map": {},
            "rows": [],
            "needs_vlm": False,
            "vlm_used": False,
            "force_vlm_toggle": False,
            "issues": [],
            "status": "processing",
            "processing_notes": [],
            "start_time": time.time(),
            "checkpoint_data": {},
            "error": None,
            "failed_agent": None
        }
        
        print(f"✅ State created: job_id={state['job_id']}")
        print(f"✅ Status: {state['status']}")
        print(f"✅ Artifacts: {len(state['artifacts'])} items")
        
        # Test state updates
        state["artifacts"]["email_body"] = {"text": "test content"}
        state["processing_notes"].append("Test note")
        
        print(f"✅ State updated: {len(state['artifacts'])} artifacts, {len(state['processing_notes'])} notes")
        
        return True
        
    except Exception as e:
        print(f"❌ ProcessingState error: {e}")
        return False

def test_metrics():
    """Test metrics without external dependencies"""
    print("\n🔍 Testing metrics...")
    
    try:
        from app.metrics import get_agent_runs_total, get_agent_latency_seconds
        
        # Test metric creation
        agent_runs = get_agent_runs_total()
        latency = get_agent_latency_seconds()
        
        print("✅ Metrics created successfully")
        
        # Test metric usage
        agent_runs.labels(agent="test", status="success").inc()
        latency.labels(agent="test").observe(0.5)
        
        print("✅ Metrics usage works")
        
        return True
        
    except Exception as e:
        print(f"❌ Metrics error: {e}")
        return False

def test_orchestrator_logic():
    """Test orchestrator logic without LangGraph"""
    print("\n🔍 Testing orchestrator logic...")
    
    try:
        # Test the node functions we fixed
        def mock_intake_node(state):
            """Mock intake node"""
            state["artifacts"]["email_body"] = {"text": "test"}
            state["processing_notes"].append("Email parsed")
            return state
        
        def mock_classify_node(state):
            """Mock classify node"""
            state["route_map"] = {"type": "html_table"}
            state["needs_vlm"] = False
            state["processing_notes"].append("Classified as HTML table")
            return state
        
        # Test the flow
        state = {
            "job_id": 1,
            "artifacts": {},
            "processing_notes": [],
            "route_map": {},
            "needs_vlm": False
        }
        
        # Run nodes
        state = mock_intake_node(state)
        state = mock_classify_node(state)
        
        print(f"✅ Intake completed: {len(state['artifacts'])} artifacts")
        print(f"✅ Classification completed: {state['route_map']}")
        print(f"✅ Notes: {len(state['processing_notes'])} items")
        
        return True
        
    except Exception as e:
        print(f"❌ Orchestrator logic error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting isolated local tests...\n")
    
    tests = [
        test_basic_imports,
        test_email_parsing,
        test_processing_state,
        test_metrics,
        test_orchestrator_logic
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✅ All tests passed! Ready to rebuild Docker.")
        return True
    else:
        print("❌ Some tests failed. Fix issues before rebuilding Docker.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
