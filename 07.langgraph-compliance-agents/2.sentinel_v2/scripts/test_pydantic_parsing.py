"""
Test Pydantic model parsing of applicant_data
"""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sentinel.api.models import InvestigationRequest

# Test 1: Direct dict
print("\n=== TEST 1: Direct dict ===")
request_data = {
    "query": "Test investigation with applicant data",
    "date_from": "2026-01-01",
    "date_to": "2026-12-31",
    "applicant_data": {
        "applicant_id": "TEST_001",
        "applicant_name": "Test User",
        "race": "African American",
        "age": 35,
        "income": 45000,
        "credit_score": 620,
        "denied": True,
        "denial_reason": "credit_score_too_low",
    }
}

try:
    req = InvestigationRequest(**request_data)
    print(f"[OK] Pydantic parsing succeeded")
    print(f"[DEBUG] req.applicant_data: {req.applicant_data}")
    print(f"[DEBUG] type: {type(req.applicant_data)}")
    print(f"[DEBUG] is dict: {isinstance(req.applicant_data, dict)}")
    if isinstance(req.applicant_data, dict):
        print(f"[DEBUG] keys: {list(req.applicant_data.keys())}")
        print(f"[DEBUG] len: {len(req.applicant_data)}")
        print(f"[DEBUG] bool check: {bool(req.applicant_data)}")
        # Test JSON serialization
        json_str = json.dumps(req.applicant_data)
        print(f"[DEBUG] JSON serialized: {json_str[:100]}")
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()

# Test 2: From JSON string
print("\n=== TEST 2: From JSON string (httpx-style) ===")
request_json_str = json.dumps(request_data)
print(f"[DEBUG] JSON string: {request_json_str[:100]}")

try:
    req2 = InvestigationRequest(**json.loads(request_json_str))
    print(f"[OK] Pydantic parsing from JSON string succeeded")
    print(f"[DEBUG] req.applicant_data: {req2.applicant_data}")
    print(f"[DEBUG] type: {type(req2.applicant_data)}")
except Exception as e:
    print(f"[ERROR] {e}")
    import traceback
    traceback.print_exc()
