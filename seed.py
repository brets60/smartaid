import sys
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from database import engine, SessionLocal, Base
from models import User, Household, HouseholdMember, AidProgram, ProgramRule, Allocation, Disbursement
from auth import get_password_hash
from engine import MCDAEngine

def seed_database():
    print("[1/5] Initializing database tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        print("[2/5] Seeding staff user accounts...")
        existing_users = db.query(User).count()
        if existing_users == 0:
            users_to_seed = [
                User(
                    full_name="Administrator Maria Santos",
                    username="admin",
                    hashed_password=get_password_hash("admin123"),
                    role="admin",
                    assigned_barangay=None,
                    is_active=True
                ),
                User(
                    full_name="Social Worker Juan Dela Cruz",
                    username="worker1",
                    hashed_password=get_password_hash("worker123"),
                    role="social_worker",
                    assigned_barangay="San Jose",
                    is_active=True
                ),
                User(
                    full_name="Field Agent Ana Reyes",
                    username="agent1",
                    hashed_password=get_password_hash("agent123"),
                    role="field_agent",
                    assigned_barangay="San Jose",
                    is_active=True
                ),
            ]
            db.add_all(users_to_seed)
            db.commit()
            print("      Created admin, worker1, and agent1 accounts.")
        else:
            print("      Users already present. Skipping user creation.")

        print("[3/5] Seeding relief aid program and MCDA criteria rules...")
        program = db.query(AidProgram).first()
        if not program:
            program = AidProgram(
                program_name="Municipality of Maramag Disaster Relief & Social Assistance Program 2026",
                description="Official targeted emergency relief assistance and basic subsistence food pack distribution for vulnerable and calamity-affected families across the 20 barangays of Maramag, Province of Bukidnon.",
                target_barangay=None,  # Open to all 20 Maramag barangays
                total_quota_slots=10,
                budget_per_slot=5000.0,
                status="Active"
            )
            db.add(program)
            db.commit()
            db.refresh(program)

            rules = ProgramRule(
                program_id=program.id,
                income_ceiling=15000.0,
                weight_income=0.35,
                weight_dependency=0.25,
                weight_calamity=0.20,
                weight_housing=0.20,
                cooldown_days=14
            )
            db.add(rules)
            db.commit()
            print(f"      Created program '{program.program_name}' with 10 quota slots (PHP 5,000/slot).")
        else:
            print(f"      Program '{program.program_name}' already exists.")

        print("[4/5] Seeding 20 realistic applicant households with demographic variance...")
        existing_hh = db.query(Household).count()
        if existing_hh == 0:
            sample_households = [
                # 1. Extreme vulnerability: single mother, informal settler, flood loss, PWD + senior
                {
                    "ref": "APP-2026-00101",
                    "head": "Elena Ramos",
                    "phone": "09171112233",
                    "brgy": "San Jose",
                    "zone": "Purok 4",
                    "addr": "Sitio Riverside Lot 12",
                    "income": 1200.0,
                    "informal": True,
                    "calamity": True,
                    "members": [
                        ("Elena", "Ramos", "Head", False, False),
                        ("Danilo", "Ramos", "Son", True, False),
                        ("Lourdes", "Ramos", "Mother", False, True),
                        ("Kyle", "Ramos", "Grandson", False, False),
                        ("Angel", "Ramos", "Granddaughter", False, False)
                    ]
                },
                # 2. Extreme vulnerability: large family, 2 PWDs, 1 senior, informal settler, storm damaged
                {
                    "ref": "APP-2026-00102",
                    "head": "Rodrigo Bautista",
                    "phone": "09182223344",
                    "brgy": "Bagong Silang",
                    "zone": "Block 12",
                    "addr": "Purok Bayanihan Alley 3",
                    "income": 2500.0,
                    "informal": True,
                    "calamity": True,
                    "members": [
                        ("Rodrigo", "Bautista", "Head", False, False),
                        ("Marites", "Bautista", "Spouse", False, False),
                        ("Joshua", "Bautista", "Son", True, False),
                        ("Clarisse", "Bautista", "Daughter", True, False),
                        ("Ester", "Bautista", "Mother", False, True),
                        ("Mark", "Bautista", "Son", False, False)
                    ]
                },
                # 3. Elderly couple with severe calamity damage
                {
                    "ref": "APP-2026-00103",
                    "head": "Corazon Dizon",
                    "phone": "09193334455",
                    "brgy": "San Jose",
                    "zone": "Purok 1",
                    "addr": "14 Mabini St",
                    "income": 3000.0,
                    "informal": True,
                    "calamity": True,
                    "members": [
                        ("Corazon", "Dizon", "Head", False, True),
                        ("Vicente", "Dizon", "Spouse", False, True),
                        ("Grace", "Dizon", "Daughter", False, False),
                        ("Alden", "Dizon", "Grandson", False, False)
                    ]
                },
                # 4. Large household, informal settler, calamity damaged
                {
                    "ref": "APP-2026-00104",
                    "head": "Danilo Macaraeg",
                    "phone": "09204445566",
                    "brgy": "Santa Cruz",
                    "zone": "Zone 3",
                    "addr": "Riverside Alleyway 7",
                    "income": 4200.0,
                    "informal": True,
                    "calamity": True,
                    "members": [
                        ("Danilo", "Macaraeg", "Head", False, False),
                        ("Norma", "Macaraeg", "Spouse", False, False),
                        ("Ben", "Macaraeg", "Son", True, False),
                        ("Carlo", "Macaraeg", "Son", False, False),
                        ("Diane", "Macaraeg", "Daughter", False, False),
                        ("Edgar", "Macaraeg", "Son", False, False),
                        ("Faith", "Macaraeg", "Daughter", False, False)
                    ]
                },
                # 5. Low income with PWD & Senior, formal housing but storm damage
                {
                    "ref": "APP-2026-00105",
                    "head": "Teresa Morales",
                    "phone": "09215556677",
                    "brgy": "Poblacion",
                    "zone": "Purok Masagana",
                    "addr": "22 Public Market Road",
                    "income": 4800.0,
                    "informal": False,
                    "calamity": True,
                    "members": [
                        ("Teresa", "Morales", "Head", False, False),
                        ("Alfonso", "Morales", "Father", False, True),
                        ("Bianca", "Morales", "Sister", True, False),
                        ("Cedric", "Morales", "Nephew", False, False),
                        ("Daisy", "Morales", "Niece", False, False)
                    ]
                },
                # 6. Coastal informal settler with calamity damage
                {
                    "ref": "APP-2026-00106",
                    "head": "Mateo Alcantara",
                    "phone": "09226667788",
                    "brgy": "Bagong Silang",
                    "zone": "Zone 2",
                    "addr": "Coastal Road Lot 4B",
                    "income": 5000.0,
                    "informal": True,
                    "calamity": True,
                    "members": [
                        ("Mateo", "Alcantara", "Head", False, False),
                        ("Leila", "Alcantara", "Spouse", False, False),
                        ("Gregorio", "Alcantara", "Father", False, True),
                        ("Mia", "Alcantara", "Daughter", False, False)
                    ]
                },
                # 7. Low income informal settler, no calamity damage
                {
                    "ref": "APP-2026-00107",
                    "head": "Leticia Villanueva",
                    "phone": "09237778899",
                    "brgy": "San Jose",
                    "zone": "Purok 5",
                    "addr": "Sitio Dike Extension",
                    "income": 5500.0,
                    "informal": True,
                    "calamity": False,
                    "members": [
                        ("Leticia", "Villanueva", "Head", False, False),
                        ("Oscar", "Villanueva", "Spouse", True, False),
                        ("Paul", "Villanueva", "Son", False, False),
                        ("Queen", "Villanueva", "Daughter", False, False),
                        ("Ron", "Villanueva", "Son", False, False),
                        ("Sara", "Villanueva", "Daughter", False, False)
                    ]
                },
                # 8. Modest income with calamity damage & 1 senior
                {
                    "ref": "APP-2026-00108",
                    "head": "Renato Soriano",
                    "phone": "09248889900",
                    "brgy": "Santa Cruz",
                    "zone": "Zone 1",
                    "addr": "88 Ilang-Ilang St",
                    "income": 6200.0,
                    "informal": False,
                    "calamity": True,
                    "members": [
                        ("Renato", "Soriano", "Head", False, False),
                        ("Bella", "Soriano", "Spouse", False, False),
                        ("Gloria", "Soriano", "Mother", False, True),
                        ("Leo", "Soriano", "Son", False, False)
                    ]
                },
                # 9. Informal settler, 1 senior, no calamity damage
                {
                    "ref": "APP-2026-00109",
                    "head": "Rosalie Fernandez",
                    "phone": "09259990011",
                    "brgy": "Poblacion",
                    "zone": "Purok 2",
                    "addr": "105 Rizal Ave Backlot",
                    "income": 7000.0,
                    "informal": True,
                    "calamity": False,
                    "members": [
                        ("Rosalie", "Fernandez", "Head", False, False),
                        ("Enrique", "Fernandez", "Spouse", False, False),
                        ("Pilar", "Fernandez", "Mother-in-law", False, True),
                        ("Tina", "Fernandez", "Daughter", False, False),
                        ("Ulysses", "Fernandez", "Son", False, False)
                    ]
                },
                # 10. Borderline Quota household: 1 PWD, storm damage
                {
                    "ref": "APP-2026-00110",
                    "head": "Arnel Castillo",
                    "phone": "09260001122",
                    "brgy": "San Jose",
                    "zone": "Purok 3",
                    "addr": "74 Bonifacio St",
                    "income": 7500.0,
                    "informal": False,
                    "calamity": True,
                    "members": [
                        ("Arnel", "Castillo", "Head", False, False),
                        ("Rowena", "Castillo", "Spouse", False, False),
                        ("Joel", "Castillo", "Son", True, False),
                        ("Vicky", "Castillo", "Daughter", False, False)
                    ]
                },
                # 11. Waitlisted Rank 11: Informal settler, calamity damage, higher income
                {
                    "ref": "APP-2026-00111",
                    "head": "Gloria Manalo",
                    "phone": "09271113344",
                    "brgy": "Bagong Silang",
                    "zone": "Zone 4",
                    "addr": "Block 8 Lot 19",
                    "income": 8200.0,
                    "informal": True,
                    "calamity": True,
                    "members": [
                        ("Gloria", "Manalo", "Head", False, False),
                        ("Wilfredo", "Manalo", "Spouse", False, False),
                        ("Xavier", "Manalo", "Son", False, False),
                        ("Yvonne", "Manalo", "Daughter", False, False)
                    ]
                },
                # 12. Waitlisted: 1 senior, calamity damage, moderate income
                {
                    "ref": "APP-2026-00112",
                    "head": "Felipe Ocampo",
                    "phone": "09282224455",
                    "brgy": "Santa Cruz",
                    "zone": "Zone 2",
                    "addr": "45 Sampaguita St",
                    "income": 9000.0,
                    "informal": False,
                    "calamity": True,
                    "members": [
                        ("Felipe", "Ocampo", "Head", False, False),
                        ("Esperanza", "Ocampo", "Spouse", False, True),
                        ("Zack", "Ocampo", "Son", False, False)
                    ]
                },
                # 13. Waitlisted: Calamity damage only
                {
                    "ref": "APP-2026-00113",
                    "head": "Carmencita Cruz",
                    "phone": "09293335566",
                    "brgy": "Poblacion",
                    "zone": "Purok 6",
                    "addr": "18 Del Pilar St",
                    "income": 9800.0,
                    "informal": False,
                    "calamity": True,
                    "members": [
                        ("Carmencita", "Cruz", "Head", False, False),
                        ("Arturo", "Cruz", "Spouse", False, False),
                        ("Brenda", "Cruz", "Daughter", False, False),
                        ("Cesar", "Cruz", "Son", False, False),
                        ("Donna", "Cruz", "Daughter", False, False)
                    ]
                },
                # 14. Waitlisted: 1 PWD, no calamity, near ₱11,000
                {
                    "ref": "APP-2026-00114",
                    "head": "Bernardo Pascual",
                    "phone": "09304446677",
                    "brgy": "San Jose",
                    "zone": "Purok 2",
                    "addr": "Sitio Maligaya Compound",
                    "income": 11000.0,
                    "informal": False,
                    "calamity": False,
                    "members": [
                        ("Bernardo", "Pascual", "Head", False, False),
                        ("Erlinda", "Pascual", "Spouse", False, False),
                        ("Francis", "Pascual", "Son", True, False),
                        ("Gemma", "Pascual", "Daughter", False, False)
                    ]
                },
                # 15. Waitlisted: ₱12,500 income, 1 senior
                {
                    "ref": "APP-2026-00115",
                    "head": "Mercedes Tolentino",
                    "phone": "09315557788",
                    "brgy": "Bagong Silang",
                    "zone": "Zone 5",
                    "addr": "Block 15 Lot 3",
                    "income": 12500.0,
                    "informal": False,
                    "calamity": False,
                    "members": [
                        ("Mercedes", "Tolentino", "Head", False, False),
                        ("Hector", "Tolentino", "Father", False, True),
                        ("Iris", "Tolentino", "Daughter", False, False)
                    ]
                },
                # 16. Waitlisted: ₱14,200 (near ₱15,000 ceiling), calamity damaged
                {
                    "ref": "APP-2026-00116",
                    "head": "Gabriel Mendoza",
                    "phone": "09326668899",
                    "brgy": "Santa Cruz",
                    "zone": "Zone 4",
                    "addr": "12 MacArthur Highway",
                    "income": 14200.0,
                    "informal": False,
                    "calamity": True,
                    "members": [
                        ("Gabriel", "Mendoza", "Head", False, False),
                        ("Janet", "Mendoza", "Spouse", False, False)
                    ]
                },
                # 17. DISQUALIFIED: Income ₱18,500 exceeds ₱15,000 ceiling
                {
                    "ref": "APP-2026-00117",
                    "head": "Victoriano Reyes",
                    "phone": "09337779900",
                    "brgy": "Poblacion",
                    "zone": "Purok 1",
                    "addr": "50 Commercial Row",
                    "income": 18500.0,
                    "informal": False,
                    "calamity": True,
                    "members": [
                        ("Victoriano", "Reyes", "Head", False, False),
                        ("Karen", "Reyes", "Spouse", False, False),
                        ("Luke", "Reyes", "Son", False, False)
                    ]
                },
                # 18. DISQUALIFIED: Income ₱24,000 exceeds ceiling
                {
                    "ref": "APP-2026-00118",
                    "head": "Imelda Navarro",
                    "phone": "09348880011",
                    "brgy": "San Jose",
                    "zone": "Purok 4",
                    "addr": "120 Narra St",
                    "income": 24000.0,
                    "informal": False,
                    "calamity": False,
                    "members": [
                        ("Imelda", "Navarro", "Head", False, False),
                        ("Manuel", "Navarro", "Spouse", False, False),
                        ("Nina", "Navarro", "Daughter", False, False),
                        ("Ofelia", "Navarro", "Mother", False, True)
                    ]
                },
                # 19. DISQUALIFIED: Income ₱35,000 exceeds ceiling
                {
                    "ref": "APP-2026-00119",
                    "head": "Eduardo Gutierrez",
                    "phone": "09359991122",
                    "brgy": "Bagong Silang",
                    "zone": "Zone 1",
                    "addr": "Villa Teresa Subd Lot 8",
                    "income": 35000.0,
                    "informal": False,
                    "calamity": False,
                    "members": [
                        ("Eduardo", "Gutierrez", "Head", False, False),
                        ("Paula", "Gutierrez", "Spouse", False, False),
                        ("Quentin", "Gutierrez", "Son", False, False),
                        ("Ria", "Gutierrez", "Daughter", False, False)
                    ]
                },
                # 20. DISQUALIFIED: Income ₱21,000 exceeds ceiling
                {
                    "ref": "APP-2026-00120",
                    "head": "Patricia Salazar",
                    "phone": "09360002233",
                    "brgy": "Santa Cruz",
                    "zone": "Zone 3",
                    "addr": "77 Orchid Ave",
                    "income": 21000.0,
                    "informal": False,
                    "calamity": False,
                    "members": [
                        ("Patricia", "Salazar", "Head", False, False),
                        ("Simon", "Salazar", "Spouse", False, False),
                        ("Thea", "Salazar", "Daughter", True, False),
                        ("Una", "Salazar", "Daughter", False, False),
                        ("Vance", "Salazar", "Son", False, False)
                    ]
                }
            ]

            for d in sample_households:
                # Count pwd and elderly
                pwd_c = sum(1 for m in d["members"] if m[3])
                eld_c = sum(1 for m in d["members"] if m[4])
                mem_c = len(d["members"])

                hh = Household(
                    reference_number=d["ref"],
                    head_name=d["head"],
                    contact_number=d["phone"],
                    barangay=d["brgy"],
                    purok_zone=d["zone"],
                    street_address=d["addr"],
                    monthly_income=d["income"],
                    member_count=mem_c,
                    pwd_count=pwd_c,
                    elderly_count=eld_c,
                    is_informal_settler=d["informal"],
                    has_calamity_damage=d["calamity"],
                    created_at=datetime.now(timezone.utc)
                )
                db.add(hh)
                db.flush()

                for m in d["members"]:
                    mem = HouseholdMember(
                        household_id=hh.id,
                        first_name=m[0],
                        last_name=m[1],
                        relationship_to_head=m[2],
                        is_pwd=m[3],
                        is_senior=m[4]
                    )
                    db.add(mem)

            db.commit()
            print(f"      Seeded {len(sample_households)} diverse applicant households.")
        else:
            print(f"      {existing_hh} households already exist. Skipping household creation.")

        print("[5/5] Executing initial MCDA Evaluation & Allocation Engine...")
        engine_instance = MCDAEngine(db)
        eval_result = engine_instance.evaluate_program(program.id)
        print(f"      Evaluation Complete:")
        print(f"      - Total Evaluated: {eval_result['total_evaluated']}")
        print(f"      - Approved:        {eval_result['approved']} (Quota: {eval_result['quota_slots']})")
        print(f"      - Waitlisted:      {eval_result['waitlisted']}")
        print(f"      - Disqualified:    {eval_result['disqualified']}")

        # Seed 1 initial test disbursement on Rank 1 to showcase claimed state
        top_approved = (
            db.query(Allocation)
            .filter(Allocation.program_id == program.id, Allocation.status == "Approved")
            .order_by(Allocation.rank.asc())
            .first()
        )
        if top_approved and not top_approved.disbursement:
            agent = db.query(User).filter(User.username == "agent1").first()
            if agent:
                disb = Disbursement(
                    allocation_id=top_approved.id,
                    verified_by_user_id=agent.id,
                    notes="Relief food pack and emergency financial grant disbursed at Barangay San Jose distribution post.",
                    disbursed_at=datetime.now(timezone.utc)
                )
                db.add(disb)
                db.commit()
                print(f"      Pre-disbursed Rank 1 ({top_approved.household.head_name}) to showcase claimed verification state.")

        print("\n=== SUCCESS: SmartAid Database Successfully Seeded & Ready! ===")
        print("Staff Credentials:")
        print("  - Admin:         admin / admin123")
        print("  - Social Worker: worker1 / worker123")
        print("  - Field Agent:   agent1 / agent123")
        print("===============================================================\n")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}", file=sys.stderr)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
