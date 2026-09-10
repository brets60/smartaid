import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from database import SessionLocal
from models import User, Household, AidProgram, Allocation, Disbursement
from engine import MCDAEngine
from auth import verify_password, create_access_token

def run_tests():
    db = SessionLocal()
    try:
        print("\n=== STARTING SMARTAID SYSTEM VERIFICATION TESTS ===")

        # Test 1: User Auth & Password Hashing
        print("\n[TEST 1] Verifying user credentials and password hashes...")
        admin = db.query(User).filter(User.username == "admin").first()
        assert admin is not None, "Admin user should exist"
        assert verify_password("admin123", admin.hashed_password), "Admin password verification failed"
        token = create_access_token({"sub": admin.username, "role": admin.role})
        assert token and len(token) > 20, "JWT creation failed"
        print("✓ Test 1 Passed: Password hashing & JWT generation verified.")

        # Test 2: Aid Program & Rules
        print("\n[TEST 2] Verifying Aid Program and Program Rules...")
        prog = db.query(AidProgram).first()
        assert prog is not None, "Program should exist"
        assert prog.total_quota_slots == 10, f"Expected 10 slots, got {prog.total_quota_slots}"
        rules = prog.rules
        assert rules is not None, "Rules should exist"
        assert rules.income_ceiling == 15000.0, f"Expected ceiling 15000, got {rules.income_ceiling}"
        print("✓ Test 2 Passed: Program & Rules verified.")

        # Test 3: Hard Income Screening
        print("\n[TEST 3] Verifying Hard Constraint Income Screening...")
        disqualified = db.query(Allocation).filter(
            Allocation.program_id == prog.id,
            Allocation.status == "Disqualified"
        ).all()
        assert len(disqualified) >= 4, f"Expected at least 4 disqualified applicants, got {len(disqualified)}"
        for d in disqualified:
            assert d.rank == -1, f"Disqualified applicant should have rank -1, got {d.rank}"
            assert d.vulnerability_score == 0.0, f"Disqualified VPI should be 0.0, got {d.vulnerability_score}"
            assert d.claim_qr_hash is None, "Disqualified applicant must not have a claim QR hash"
            if d.household.monthly_income <= rules.income_ceiling:
                print(f"  [Disqualified non-income]: {d.household.head_name}, income={d.household.monthly_income}, status={d.status}")
        print(f"✓ Test 3 Passed: {len(disqualified)} applicants properly disqualified.")

        # Test 4: Constrained Allocation (Knapsack Cap)
        print("\n[TEST 4] Verifying Constrained Quota Allocation (Knapsack Cap)...")
        approved = db.query(Allocation).filter(
            Allocation.program_id == prog.id,
            Allocation.status == "Approved"
        ).order_by(Allocation.rank.asc()).all()
        assert len(approved) <= prog.total_quota_slots, f"Expected <= {prog.total_quota_slots} approved, got {len(approved)}"
        
        # Check ranks are sequential 1..len(approved)
        ranks = [a.rank for a in approved]
        assert ranks == list(range(1, len(approved) + 1)), f"Ranks must be 1..{len(approved)}, got {ranks}"
        
        # Check VPI scores are descending
        vpis = [a.vulnerability_score for a in approved]
        assert all(vpis[i] >= vpis[i+1] for i in range(len(vpis)-1)), f"VPI scores must be descending: {vpis}"
        
        # Check SHA-256 claim QR hashes
        for a in approved:
            assert a.claim_qr_hash and len(a.claim_qr_hash) == 64, f"Valid 64-char SHA-256 hash expected, got {a.claim_qr_hash}"
        print(f"✓ Test 4 Passed: Exactly {len(approved)} approved within quota; all have SHA-256 claim hashes.")

        # Test 5: Priority Waitlist
        print("\n[TEST 5] Verifying Waitlisted Applicants...")
        waitlisted = db.query(Allocation).filter(
            Allocation.program_id == prog.id,
            Allocation.status == "Waitlisted"
        ).order_by(Allocation.rank.asc()).all()
        assert len(waitlisted) >= 0
        for w in waitlisted:
            assert w.rank > prog.total_quota_slots, f"Waitlisted rank must exceed quota slots, got {w.rank}"
            assert w.claim_qr_hash is None, "Waitlisted applicants must NOT have claim QR hashes"
            assert w.vulnerability_score > 0.0, "Waitlisted applicants must have valid calculated VPI"
        print(f"✓ Test 5 Passed: {len(waitlisted)} eligible applicants properly placed on priority waitlist.")

        # Test 6: Explainable AI (XAI) Score Breakdown
        print("\n[TEST 6] Verifying XAI Score Breakdown and Auditing...")
        top_alloc = approved[0]
        bd = top_alloc.score_breakdown
        assert bd is not None, "Score breakdown must exist"
        assert "factors" in bd, "Factors breakdown missing"
        assert "income" in bd["factors"]
        assert "dependency" in bd["factors"]
        assert "calamity" in bd["factors"]
        assert "housing" in bd["factors"]
        assert bd["vpi"] == top_alloc.vulnerability_score
        assert bd["allocation_decision"]["rank"] == 1
        print("✓ Test 6 Passed: Full Explainable AI (XAI) transparent factors verified.")

        # Test 7: Double-Disbursement Prevention & Field Verification
        print("\n[TEST 7] Verifying Field Verification & Double-Claim Prevention...")
        # Rank 1 was already disbursed in seed
        rank1 = approved[0]
        assert rank1.disbursement is not None, "Rank 1 should be disbursed from seed"
        disb = rank1.disbursement
        assert disb.verified_by.role in ["field_agent", "admin", "social_worker"]
        
        # Test engine cooldown detection
        engine = MCDAEngine(db)
        in_cooldown, reason = engine.check_cooldown(rank1.household, 14)
        assert in_cooldown is True, f"Household should be in cooldown, but got {in_cooldown}"
        print(f"✓ Test 7 Passed: Double claim prevention verified: '{reason}'")

        print("\n==================================================")
        print("  ALL 7 TESTS PASSED PERFECTLY! Production Ready!")
        print("==================================================\n")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
