import sys
from fastapi.testclient import TestClient

# Ensure local directory is in path
from main import app
import db

# Initialize the database for unit testing
db.init_db()

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_diagnose_and_retry_plan():
    # 1. Test method error scenario (Weather POST -> GET)
    payload = {
        "method": "POST",
        "url": "/weather",
        "status": 405,
        "response": "Method Not Allowed"
    }
    resp = client.post("/diagnose", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "id" in data
    assert data["category"] == "METHOD_ERROR"
    assert data["retry"] is True
    assert "GET" in data["fix"]
    
    diag_id = data["id"]
    
    # 2. Test retry plan retrieval
    retry_resp = client.post("/retry-plan", json={"diagnosis_id": diag_id})
    assert retry_resp.status_code == 200
    retry_data = retry_resp.json()
    assert "next_request" in retry_data
    assert retry_data["next_request"]["method"] == "GET"
    assert "city" in retry_data["next_request"]["url"]

def test_explain():
    payload = {
        "status": 429,
        "body": "Rate limit exceeded"
    }
    resp = client.post("/explain", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "meaning" in data
    assert data["wait_seconds"] == 60
    assert data["retry"] is True

def test_workflow_recovery():
    payload = {
        "goal": "Buy ticket",
        "history": ["checkout initialized", "payment failed"]
    }
    resp = client.post("/workflow-recovery", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "next_step" in data
    assert "Reserve seat" in data["next_step"]
    assert data["retry"] is False

def test_recover():
    payload = {
        "status": 404,
        "body": "Not Found"
    }
    resp = client.post("/recover", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "plan" in data
    assert len(data["plan"]) > 0
    assert data["severity"] == "HIGH"
    assert data["recoverable"] is True

def test_skill_endpoint():
    resp = client.get("/skill.md")
    assert resp.status_code == 200
    assert "Agent Recovery Protocol" in resp.text

if __name__ == "__main__":
    print("Running RecoveryAI API Unit Tests...")
    
    tests = [
        test_health,
        test_diagnose_and_retry_plan,
        test_explain,
        test_workflow_recovery,
        test_recover,
        test_skill_endpoint
    ]
    
    passed = 0
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__} - Assertion failed")
        except Exception as e:
            print(f"ERROR: {test.__name__} - {e}")
            
    print(f"\nTest Summary: {passed}/{len(tests)} passed.")
    if passed < len(tests):
        sys.exit(1)
    else:
        sys.exit(0)
