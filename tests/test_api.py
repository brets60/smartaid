import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from main import app

def run_api_tests():
    client = TestClient(app)
    print("\n=== RUNNING FASTAPI ENDPOINT INTEGRATION TESTS ===")

    # 1. HTML View Endpoints
    print("\n[API 1] Testing Web Views...")
    r = client.get("/")
    assert r.status_code == 200, f"GET / failed: {r.status_code}"
    assert "SmartAid" in r.text
    print("  ✓ GET / (200 OK)")

    r = client.get("/login")
    assert r.status_code == 200, f"GET /login failed: {r.status_code}"
    assert "Unified Portal" in r.text
    print("  ✓ GET /login (200 OK)")

    r = client.get("/apply")
    assert r.status_code == 200, f"GET /apply failed: {r.status_code}"
    assert "Beneficiary Intake" in r.text
    print("  ✓ GET /apply (200 OK)")

    r = client.get("/track")
    assert r.status_code == 200, f"GET /track failed: {r.status_code}"
    print("  ✓ GET /track (200 OK)")

    # 2. Staff Authentication
    print("\n[API 2] Testing Staff Authentication (/api/v1/auth/token)...")
    login_res = client.post(
        "/api/v1/auth/token",
        data={"username": "admin", "password": "admin123"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["role"] == "admin"
    admin_token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}
    print(f"  ✓ POST /api/v1/auth/token -> 200 OK (Role: {token_data['role']})")

    # Current user
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "admin"
    print("  ✓ GET /api/v1/auth/me -> 200 OK")

    # 3. Programs & Allocations
    print("\n[API 3] Testing Programs & Allocations API...")
    progs_res = client.get("/api/v1/programs")
    assert progs_res.status_code == 200
    progs = progs_res.json()
    assert len(progs) > 0
    program_id = progs[0]["id"]
    print(f"  ✓ GET /api/v1/programs -> 200 OK ({len(progs)} program found)")

    allocs_res = client.get(f"/api/v1/programs/{program_id}/allocations", headers=headers)
    assert allocs_res.status_code == 200
    allocs = allocs_res.json()
    if len(allocs) == 0:
        # Submit test intake first if database has no allocations
        pre_app = {
            "head_name": "Initial Test Beneficiary",
            "contact_number": "09171112233",
            "barangay": "North Poblacion",
            "purok_zone": "Purok 1",
            "street_address": "Main Street",
            "monthly_income": 4000.0,
            "is_informal_settler": True,
            "has_calamity_damage": False,
            "members": []
        }
        client.post("/api/v1/apply", json=pre_app)
        client.post(f"/api/v1/programs/{program_id}/evaluate", headers=headers)
        allocs_res = client.get(f"/api/v1/programs/{program_id}/allocations", headers=headers)
        allocs = allocs_res.json()
    assert len(allocs) > 0
    print(f"  ✓ GET /api/v1/programs/{program_id}/allocations -> 200 OK ({len(allocs)} allocations)")

    # 4. Public Intake Submission
    print("\n[API 4] Testing Public Intake Submission (/api/v1/apply)...")
    new_applicant = {
        "head_name": "Test Beneficiary Santos",
        "contact_number": "09998887766",
        "barangay": "San Jose",
        "purok_zone": "Zone 5",
        "street_address": "Block 3 Lot 9",
        "monthly_income": 3200.0,
        "is_informal_settler": True,
        "has_calamity_damage": True,
        "members": [
            {
                "first_name": "Junior",
                "last_name": "Santos",
                "relationship_to_head": "Son",
                "is_pwd": True,
                "is_senior": False
            }
        ]
    }
    apply_res = client.post("/api/v1/apply", json=new_applicant)
    assert apply_res.status_code == 200, f"Intake submission failed: {apply_res.text}"
    app_data = apply_res.json()
    ref_num = app_data["reference_number"]
    assert ref_num.startswith("APP-")
    print(f"  ✓ POST /api/v1/apply -> 200 OK (Generated Ref: {ref_num})")

    # 5. Beneficiary Tracking Endpoint
    print("\n[API 5] Testing Beneficiary Tracking (/api/v1/beneficiary/track/{ref})...")
    track_res = client.get(f"/api/v1/beneficiary/track/{ref_num}")
    assert track_res.status_code == 200
    track_data = track_res.json()
    assert track_data["reference_number"] == ref_num
    print(f"  ✓ GET /api/v1/beneficiary/track/{ref_num} -> 200 OK (Status: {track_data['status']})")

    # 6. QR Code Image Streaming
    print("\n[API 6] Testing Dynamic QR Generator (/api/v1/qr/{hash})...")
    # Find an approved allocation with a claim hash
    approved_alloc = next((a for a in allocs if a["status"] == "Approved" and a["claim_qr_hash"]), None)
    assert approved_alloc is not None, "Need at least 1 approved allocation with claim_qr_hash"
    qr_hash = approved_alloc["claim_qr_hash"]

    qr_res = client.get(f"/api/v1/qr/{qr_hash}")
    assert qr_res.status_code == 200
    assert qr_res.headers["content-type"] == "image/png"
    assert len(qr_res.content) > 100
    print(f"  ✓ GET /api/v1/qr/{qr_hash[:16]}... -> 200 OK (Streaming PNG Image: {len(qr_res.content)} bytes)")

    # 7. Field Verification & Double-Claim Prevention
    print("\n[API 7] Testing Field QR Verification & Double-Claim Prevention (/api/v1/disburse/verify-scan)...")
    # First: find an undisbursed approved allocation
    undisbursed = next((a for a in allocs if a["status"] == "Approved" and not a["is_disbursed"]), None)
    if undisbursed:
        # Scan and verify first time
        scan1_res = client.post(
            "/api/v1/disburse/verify-scan",
            json={"claim_qr_hash": undisbursed["claim_qr_hash"], "notes": "Automated integration scan test"},
            headers=headers
        )
        if scan1_res.status_code != 200:
            print(f"  [DEBUG] scan1 failed with status {scan1_res.status_code}: {scan1_res.text}")
        assert scan1_res.status_code == 200, f"Scan1 failed: {scan1_res.text}"
        scan1_data = scan1_res.json()
        assert scan1_data["status"] == "SUCCESS"
        assert scan1_data["valid"] is True
        print(f"  ✓ First Scan -> 200 SUCCESS (Disbursement recorded for {scan1_data['head_name']})")

        # Scan second time -> must detect ALREADY_CLAIMED (409 Conflict)
        scan2_res = client.post(
            "/api/v1/disburse/verify-scan",
            json={"claim_qr_hash": undisbursed["claim_qr_hash"]},
            headers=headers
        )
        assert scan2_res.status_code == 409
        scan2_data = scan2_res.json()
        assert scan2_data["status"] == "ALREADY_CLAIMED"
        assert scan2_data["valid"] is False
        print(f"  ✓ Second Scan -> 409 ALREADY_CLAIMED! (Double-claim prevented successfully: '{scan2_data['message']}')")

    print("\n=======================================================")
    print("  ALL API & TEMPLATE INTEGRATION TESTS PASSED 100%!")
    print("=======================================================\n")

if __name__ == "__main__":
    run_api_tests()
