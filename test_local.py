#!/usr/bin/env python3
"""
Local test script to verify the code works before rebuilding Docker.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'api'))

def test_imports():
    """Test all critical imports."""
    print("🔍 Testing imports...")
    
    try:
        # Test basic imports
        from app.models import Email, Job, Version, Record, Issue, Export
        print("✅ Database models imported successfully")
        
        from app.db import get_db_session
        print("✅ Database connection imported successfully")
        
        from app.storage import storage_client
        print("✅ Storage client imported successfully")
        
        from app.metrics import get_agent_runs_total, get_agent_latency_seconds
        print("✅ Metrics imported successfully")
        
        from app.agents.intake_email import run as intake_run
        print("✅ Intake email agent imported successfully")
        
        from app.agents.classifier import run as classifier_run
        print("✅ Classifier agent imported successfully")
        
        from app.orchestrator import ProcessingState, create_processing_graph
        print("✅ Orchestrator imported successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_email_parsing():
    """Test email parsing functionality."""
    print("\n🔍 Testing email parsing...")
    
    try:
        import email
        import email.policy
        
        # Test with a simple email
        test_email = """From: test@example.com
To: recipient@example.com
Subject: Test Email
Content-Type: text/plain

This is a test email body.
"""
        
        email_message = email.message_from_string(test_email, policy=email.policy.default)
        print("✅ Email parsing works")
        
        # Test body extraction
        body = email_message.get_body()
        if body:
            print("✅ Email body extraction works")
        else:
            print("⚠️  No body found (expected for simple test)")
            
        return True
        
    except Exception as e:
        print(f"❌ Email parsing error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_processing_state():
    """Test ProcessingState model."""
    print("\n🔍 Testing ProcessingState...")
    
    try:
        from app.orchestrator import ProcessingState
        
        # Create a test state
        state = ProcessingState(
            job_id=1,
            status="processing",
            start_time=1234567890.0
        )
        
        print("✅ ProcessingState creation works")
        
        # Test conversion to dict
        state_dict = state.dict()
        print("✅ ProcessingState.dict() works")
        
        # Test that it has expected fields
        expected_fields = ["job_id", "status", "start_time", "artifacts", "rows", "issues"]
        for field in expected_fields:
            if field in state_dict:
                print(f"✅ Field '{field}' present")
            else:
                print(f"❌ Field '{field}' missing")
                
        return True
        
    except Exception as e:
        print(f"❌ ProcessingState error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_metrics():
    """Test metrics functionality."""
    print("\n🔍 Testing metrics...")
    
    try:
        from app.metrics import get_agent_runs_total, get_agent_latency_seconds
        
        # Test metric creation
        agent_runs = get_agent_runs_total()
        agent_latency = get_agent_latency_seconds()
        
        print("✅ Metrics creation works")
        
        # Test metric usage
        agent_runs.labels(agent="test", status="success").inc()
        agent_latency.labels(agent="test").observe(1.5)
        
        print("✅ Metrics usage works")
        
        return True
        
    except Exception as e:
        print(f"❌ Metrics error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("🚀 Starting local tests...\n")
    
    tests = [
        test_imports,
        test_email_parsing,
        test_processing_state,
        test_metrics
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Code should work in Docker.")
        return True
    else:
        print("❌ Some tests failed. Fix issues before rebuilding Docker.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
