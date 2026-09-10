import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient
from main import app
from database import get_db
from models import Household, Allocation, AidProgram, ProgramRule
from ai_engine import (
    SmartAidAICopilot,
    generate_xai_narrative,
    evaluate_intake_risk,
    simulate_policy_scenario,
    SCENARIOS
)

def run_all_ai_tests():
    client = TestClient(app)
    db = next(get_db())

    print("\n=== RUNNING SMARTAID AI & DECISION INTELLIGENCE TESTS ===")

    # ----------------------------------------------------
    # 1. TEST AI COPILOT CHAT ENDPOINT & ENGINE
    # ----------------------------------------------------
    print("\n[AI 1] Testing SmartAid AI Copilot...")
    
    # 1a. English General Query
    res_en = client.post("/api/v1/ai/chat", json={"message": "What is the poverty income ceiling in Maramag?", "language": "en"})
    assert res_en.status_code == 200, f"Chat failed: {res_en.text}"
    data_en = res_en.json()
    assert "15,000" in data_en["reply"]
    print("  ✓ English FAQ reply verified (Income ceiling: ₱15,000)")

    # 1b. Bisaya Query
    res_ceb = client.post("/api/v1/ai/chat", json={"message": "Pila ang limit sa kita aron makakuha og ayuda?", "language": "ceb"})
    assert res_ceb.status_code == 200
    data_ceb = res_ceb.json()
    assert "15,000" in data_ceb["reply"] or "limitasyon" in data_ceb["reply"].lower()
    print("  ✓ Bisaya contextual response verified")

    # 1c. Criteria Breakdown Query
    res_crit = client.post("/api/v1/ai/chat", json={"message": "How does the MCDA criteria scoring work?"})
    assert res_crit.status_code == 200
    crit_reply = res_crit.json()["reply"]
    assert "35%" in crit_reply or "VPI" in crit_reply
    print("  ✓ MCDA vector scoring explanation verified")

    # 1d. Live Reference Lookup via Copilot
    existing_hh = db.query(Household).first()
    if existing_hh:
        res_ref = client.post("/api/v1/ai/chat", json={"message": f"Please check my status: {existing_hh.reference_number}"})
        assert res_ref.status_code == 200
        ref_data = res_ref.json()
        assert existing_hh.reference_number in ref_data["reply"]
        assert ref_data["household"] is not None
        assert ref_data["household"]["reference_number"] == existing_hh.reference_number
        print(f"  ✓ Live Database Grounded Reference Lookup verified for {existing_hh.reference_number}")

    # ----------------------------------------------------
    # 2. TEST GENERATIVE XAI NARRATIVE GENERATION
    # ----------------------------------------------------
    print("\n[AI 2] Testing Generative XAI Natural Language Explanations...")
    if existing_hh:
        alloc = db.query(Allocation).filter(Allocation.household_id == existing_hh.id).first()
        if alloc:
            rules = alloc.program.rules if alloc.program else None
            narr_en = generate_xai_narrative(alloc, existing_hh, rules, lang="en")
            narr_ceb = generate_xai_narrative(alloc, existing_hh, rules, lang="ceb")

            assert "en" in narr_en and len(narr_en["en"]) > 20
            assert "ceb" in narr_ceb and len(narr_ceb["ceb"]) > 20
            print("  ✓ Generative XAI English Narrative:")
            print(f"    \"{narr_en['en'][:110]}...\"")
            print("  ✓ Generative XAI Bisaya Narrative:")
            print(f"    \"{narr_ceb['ceb'][:110]}...\"")

        # Check /api/v1/beneficiary/track/{ref} returns AI narrative
        track_res = client.get(f"/api/v1/beneficiary/track/{existing_hh.reference_number}")
        assert track_res.status_code == 200
        track_data = track_res.json()
        assert "ai_narrative" in track_data
        assert track_data["ai_narrative"] is not None
        assert "en" in track_data["ai_narrative"]
        assert "ceb" in track_data["ai_narrative"]
        print("  ✓ GET /api/v1/beneficiary/track returns live dual-language XAI justifications")

    # ----------------------------------------------------
    # 3. TEST INTAKE ANOMALY & FRAUD DETECTION ENGINE
    # ----------------------------------------------------
    print("\n[AI 3] Testing AI Intake Anomaly & Fraud Detection Engine...")

    # 3a. Admin Login
    login_res = client.post("/api/v1/auth/token", data={"username": "admin", "password": "admin123"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {token}"}

    # 3b. Registry Risk Screening Endpoint
    risk_res = client.get("/api/v1/ai/risk-analysis", headers=admin_headers)
    assert risk_res.status_code == 200, f"Risk screening failed: {risk_res.text}"
    risk_data = risk_res.json()
    assert "summary" in risk_data
    assert "total" in risk_data["summary"]
    assert "LOW" in risk_data["summary"]
    print(f"  ✓ Screened {risk_data['summary']['total']} registered applicants across Maramag:")
    print(f"    LOW Risk: {risk_data['summary']['LOW']} | MEDIUM Risk: {risk_data['summary']['MEDIUM']} | HIGH Risk: {risk_data['summary']['HIGH']}")

    # 3c. Unit evaluation of synthetic anomalous households
    clean_hh = Household(
        reference_number="APP-TEST-CLEAN",
        head_name="Maria Santos",
        barangay="North Poblacion",
        purok_zone="Purok 1",
        street_address="Sayre Highway",
        contact_number="0917-000-1111",
        monthly_income=6500.0,
        member_count=4,
        pwd_count=1,
        elderly_count=0,
        is_informal_settler=False,
        has_calamity_damage=True
    )
    clean_risk = evaluate_intake_risk(db, clean_hh)
    assert clean_risk["risk_level"] == "LOW"
    print("  ✓ Clean applicant correctly assigned LOW risk (0-10 pts)")

    fraud_hh = Household(
        reference_number="APP-TEST-FRAUD",
        head_name="Juan Tamad",
        barangay="North Poblacion",
        purok_zone="Purok 1",
        street_address="Sayre Highway",
        contact_number="0917-000-1111",  # Same phone as Maria
        monthly_income=0.0,              # Suspicious ₱0 with 7 members without calamity
        member_count=7,
        pwd_count=0,
        elderly_count=0,
        is_informal_settler=False,
        has_calamity_damage=False
    )
    # Temporary add clean_hh to check duplicate contact
    db.add(clean_hh)
    db.commit()
    try:
        fraud_risk = evaluate_intake_risk(db, fraud_hh)
        assert fraud_risk["risk_score"] >= 40
        assert fraud_risk["risk_level"] in ("MEDIUM", "HIGH")
        assert len(fraud_risk["risk_flags"]) >= 1
        print(f"  ✓ Anomaly Engine flagged suspicious applicant: Level={fraud_risk['risk_level']} (Score: {fraud_risk['risk_score']})")
        for flag in fraud_risk["risk_flags"]:
            print(f"    - Flag: {flag}")
    finally:
        db.delete(clean_hh)
        db.commit()

    # ----------------------------------------------------
    # 4. TEST AI POLICY SIMULATOR & SCENARIO LAB
    # ----------------------------------------------------
    print("\n[AI 4] Testing AI Policy Simulator & Scenario Lab...")
    prog = db.query(AidProgram).filter(AidProgram.status == "Active").first() or db.query(AidProgram).first()
    assert prog is not None, "No aid program found for simulation testing."

    # 4a. Simulate Typhoon Emergency Shock
    sim_res = client.post(
        f"/api/v1/ai/simulate?program_id={prog.id}",
        json={"scenario": "typhoon_flood"},
        headers=admin_headers
    )
    assert sim_res.status_code == 200, f"Simulation failed: {sim_res.text}"
    sim_data = sim_res.json()
    assert sim_data["applied_weights"]["calamity"] == 0.45
    assert "total_approved" in sim_data
    assert "barangay_distribution" in sim_data
    print(f"  ✓ Simulated 'Typhoon & Flash Flood Emergency Shock' (Calamity Weight: 45%):")
    print(f"    Evaluated: {sim_data['total_evaluated']} | Approved: {sim_data['total_approved']} | Waitlisted: {sim_data['total_waitlisted']}")
    print(f"    Barangay Capture: {sim_data['barangay_distribution']}")

    # 4b. Simulate Senior / PWD Caregiver Focus
    sim_pwd_res = client.post(
        f"/api/v1/ai/simulate?program_id={prog.id}",
        json={"scenario": "vulnerable_sectors"},
        headers=admin_headers
    )
    assert sim_pwd_res.status_code == 200
    pwd_data = sim_pwd_res.json()
    assert pwd_data["applied_weights"]["dependency"] == 0.45
    print("  ✓ Simulated 'Senior & PWD Caregiver Focus' (Dependency Weight: 45%)")

    # 4c. Apply Simulated Policy Weights to Active Program
    apply_res = client.post(
        f"/api/v1/ai/apply-simulated-weights?program_id={prog.id}",
        json={"scenario": "typhoon_flood"},
        headers=admin_headers
    )
    assert apply_res.status_code == 200, f"Apply weights failed: {apply_res.text}"
    apply_data = apply_res.json()
    assert apply_data["status"] == "SUCCESS"
    assert apply_data["weights"]["calamity"] == 0.45
    print("  ✓ Committed simulated policy weights to program rules & triggered MCDA re-evaluation")

    # 4d. Verify Audit Event Logged
    audit_res = client.get("/api/v1/audit-logs?limit=5", headers=admin_headers)
    assert audit_res.status_code == 200
    latest_log = audit_res.json()[0]
    assert latest_log["action"] == "AI_POLICY_WEIGHTS_APPLIED"
    print(f"  ✓ Governance audit log recorded: {latest_log['action']} by {latest_log['username']}")

    # 4e. Restore default balanced equilibrium
    client.post(
        f"/api/v1/ai/apply-simulated-weights?program_id={prog.id}",
        json={"scenario": "balanced_equilibrium"},
        headers=admin_headers
    )
    print("  ✓ Restored default Balanced MCDA equilibrium weights.")

    print("\n=======================================================")
    print("ALL 4 AI CAPABILITIES PASSED VERIFICATION WITH 100% SUCCESS!")
    print("=======================================================\n")

if __name__ == "__main__":
    run_all_ai_tests()
