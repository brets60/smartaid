import os
import sys
sys.path.insert(0, os.path.abspath("."))
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

# Login as admin
login_res = client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"})
assert login_res.status_code == 200
token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Test Report Export
export_res = client.get("/api/v1/reports/allocations/export", headers=headers)
print("Export CSV status:", export_res.status_code)
print("Export Content-Type:", export_res.headers.get("content-type"))
assert export_res.status_code == 200
assert "text/csv" in export_res.headers.get("content-type")
print("First 2 lines of exported CSV:")
for line in export_res.text.splitlines()[:3]:
    print(" ", line)

# Test Audit Logs
audit_res = client.get("/api/v1/audit-logs", headers=headers)
assert audit_res.status_code == 200
logs = audit_res.json()
print(f"\nAudit Logs count: {len(logs)}")
for l in logs[:5]:
    print(f"  [{l['created_at'][:19]}] {l['username']}: {l['action']} ({l['target_entity']})")

print("\nAll new feature endpoints verified successfully!")
