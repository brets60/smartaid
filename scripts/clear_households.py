import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from database import SessionLocal
from models import Household, HouseholdMember, Allocation, Disbursement

def clear_all_households():
    db = SessionLocal()
    try:
        print("[1/4] Deleting existing disbursements...")
        disb_count = db.query(Disbursement).delete()
        
        print("[2/4] Deleting existing allocations...")
        alloc_count = db.query(Allocation).delete()

        print("[3/4] Deleting existing household members...")
        mem_count = db.query(HouseholdMember).delete()

        print("[4/4] Deleting existing household records...")
        hh_count = db.query(Household).delete()

        db.commit()
        print(f"\n=== SUCCESS: Cleared {hh_count} households, {mem_count} members, {alloc_count} allocations, and {disb_count} disbursements! ===")
        print("Staff user accounts, program rules, and Maramag configuration are preserved.")
        print("You can now enter your own real household data fresh at http://127.0.0.1:8000/apply !")
    except Exception as e:
        db.rollback()
        print(f"Error clearing households: {e}", file=sys.stderr)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    clear_all_households()
