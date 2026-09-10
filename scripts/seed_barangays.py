import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from database import SessionLocal
from models import User
from auth import get_password_hash

BARANGAYS = [
    ('North Poblacion', 'brgy_northpob'),
    ('South Poblacion', 'brgy_southpob'),
    ('Base Camp', 'brgy_basecamp'),
    ('Dologon', 'brgy_dologon'),
    ('Musuan', 'brgy_musuan'),
    ('Camp 1', 'brgy_camp1'),
    ('Panadtalan', 'brgy_panadtalan'),
    ('Dagumbaan', 'brgy_dagumbaan'),
    ('Kuya', 'brgy_kuya'),
    ('San Miguel', 'brgy_sanmiguel'),
    ('San Roque', 'brgy_sanroque'),
    ('Colambugon', 'brgy_colambugon'),
    ('Anahawon', 'brgy_anahawon'),
    ('Bayabason', 'brgy_bayabason'),
    ('Tubigon', 'brgy_tubigon'),
    ('La Asuncion', 'brgy_laasuncion'),
    ('Dibulang', 'brgy_dibulang'),
    ('Kisanayan', 'brgy_kisanayan'),
    ('Danggawan', 'brgy_danggawan'),
    ('Panalsalan', 'brgy_panalsalan'),
]

def seed_barangays():
    db = SessionLocal()
    try:
        created_count = 0
        updated_count = 0
        hashed_pwd = get_password_hash('barangay123')

        for b_name, username in BARANGAYS:
            existing = db.query(User).filter(User.username == username).first()
            if not existing:
                user = User(
                    full_name=f'Brgy. {b_name} Staff Officer',
                    username=username,
                    hashed_password=hashed_pwd,
                    role='barangay_staff',
                    assigned_barangay=b_name,
                    is_active=True
                )
                db.add(user)
                created_count += 1
            else:
                existing.role = 'barangay_staff'
                existing.assigned_barangay = b_name
                updated_count += 1

        db.commit()
        print(f'Successfully seeded Barangay Accounts: {created_count} created, {updated_count} updated.')
    finally:
        db.close()

if __name__ == '__main__':
    seed_barangays()
