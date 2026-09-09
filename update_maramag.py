import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from database import SessionLocal
from models import AidProgram, Household, User
from engine import MCDAEngine

def update_to_maramag():
    db = SessionLocal()
    try:
        print("[1/3] Updating Aid Program to Municipality of Maramag, Bukidnon...")
        program = db.query(AidProgram).first()
        if program:
            program.program_name = "Municipality of Maramag Disaster Relief & Social Assistance Program 2026"
            program.description = "Official targeted emergency relief assistance and basic subsistence food pack distribution for vulnerable and calamity-affected families across the 20 barangays of Maramag, Province of Bukidnon."
            db.commit()
            print(f"      Updated Program Name: {program.program_name}")

        print("[2/3] Updating applicant households to authentic Maramag, Bukidnon Barangays...")
        maramag_locations = [
            ("APP-2026-00101", "Base Camp", "Purok 4", "Sitio Riverside, Base Camp, Maramag"),
            ("APP-2026-00102", "Dologon", "Purok 5", "Purok Bayanihan near CMU, Dologon, Maramag"),
            ("APP-2026-00103", "North Poblacion", "Purok 1", "Market Site, North Poblacion, Maramag"),
            ("APP-2026-00104", "Dagumbaan", "Purok 3", "Pulangi Riverbank, Dagumbaan, Maramag"),
            ("APP-2026-00105", "South Poblacion", "Purok Masagana", "Sayre Highway, South Poblacion, Maramag"),
            ("APP-2026-00106", "Musuan", "Purok 2", "Musuan Peak Foothills, Musuan, Maramag"),
            ("APP-2026-00107", "Kuya", "Purok 5", "Sitio Dike, Kuya, Maramag"),
            ("APP-2026-00108", "Panadtalan", "Purok 1", "Panadtalan Agro Lot 14, Maramag"),
            ("APP-2026-00109", "Colambugon", "Purok 2", "Colambugon Proper, Maramag"),
            ("APP-2026-00110", "Camp 1", "Purok 3", "Camp 1 Riverside, Maramag"),
            ("APP-2026-00111", "Bayabason", "Purok 4", "Bayabason Crossing, Maramag"),
            ("APP-2026-00112", "Anahawon", "Purok 2", "Anahawon Valley, Maramag"),
            ("APP-2026-00113", "San Miguel", "Purok 6", "San Miguel Agricultural Area, Maramag"),
            ("APP-2026-00114", "San Roque", "Purok 2", "Sitio Maligaya, San Roque, Maramag"),
            ("APP-2026-00115", "Tubigon", "Purok 5", "Tubigon Plains, Maramag"),
            ("APP-2026-00116", "La Asuncion", "Purok 4", "Sayre Highway Corridor, La Asuncion, Maramag"),
            ("APP-2026-00117", "Dibulang", "Purok 1", "Commercial Row, Dibulang, Maramag"),
            ("APP-2026-00118", "Kisanayan", "Purok 4", "Kisanayan Center, Maramag"),
            ("APP-2026-00119", "Danggawan", "Purok 1", "Villa Teresa, Danggawan, Maramag"),
            ("APP-2026-00120", "Panalsalan", "Purok 3", "Panalsalan Heights, Maramag"),
        ]

        for ref, brgy, zone, addr in maramag_locations:
            hh = db.query(Household).filter(Household.reference_number == ref).first()
            if hh:
                hh.barangay = brgy
                hh.purok_zone = zone
                hh.street_address = addr

        # Update staff agent station
        agent = db.query(User).filter(User.username == "agent1").first()
        if agent:
            agent.assigned_barangay = "North Poblacion, Maramag"

        worker = db.query(User).filter(User.username == "worker1").first()
        if worker:
            worker.assigned_barangay = "Dologon, Maramag"

        db.commit()
        print("      Updated all households and staff stations to Maramag, Bukidnon.")

        print("[3/3] Re-evaluating allocations with updated Maramag parameters...")
        if program:
            engine = MCDAEngine(db)
            res = engine.evaluate_program(program.id)
            print(f"      Re-evaluation successful: {res['approved']} Approved, {res['waitlisted']} Waitlisted, {res['disqualified']} Disqualified.")

        print("\n=== SUCCESS: System localized for Municipality of Maramag, Province of Bukidnon! ===")
    finally:
        db.close()

if __name__ == "__main__":
    update_to_maramag()
