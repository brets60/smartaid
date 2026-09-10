# SmartAid: Automated Multi-Criteria Decision Support System
### For Localized Social Welfare and Constrained Relief Resource Allocation

SmartAid resolves the challenge of allocating limited social aid (food packs, emergency financial grants, disaster relief) when applicant demand far exceeds available inventory. It eliminates political bias, nepotism, and human subjectivity through a transparent, mathematically rigorous decision pipeline.

---

## Key Features & Architecture

1. **Hard Eligibility Screening**:
   - **Income Ceiling Gate**: Automatically disqualifies applicant households whose declared monthly income exceeds the program's threshold ($monthly\_income > income\_ceiling$), setting $VPI = 0.0000$ and $Rank = -1$.
   - **Cooldown & Deduplication Filter**: Prevents duplicate claims by checking if a household or registered mobile number received assistance within $cooldown\_days$ (default 14 days).

2. **Deterministic Multi-Criteria Decision Analysis (MCDA)**:
   - Evaluates multidimensional vulnerability using normalized vectors $\in [0.0, 1.0]$:
     - **Income Vulnerability ($S_{income}$)**:
       $$S_{\text{income}} = 1.0 - \left(\frac{\min(\text{monthly\_income}, \text{income\_ceiling})}{\text{income\_ceiling}}\right)$$
     - **Demographic Dependency Ratio ($S_{dependency}$)**:
       $$S_{\text{dependency}} = \min\left(\frac{\text{pwd\_count} \times 1.5 + \text{elderly\_count}}{\max(\text{member\_count}, 1)}, 1.0\right)$$
     - **Housing Vulnerability ($S_{housing}$)**: $1.0$ if informal settler, else $0.0$.
     - **Calamity Impact ($S_{calamity}$)**: $1.0$ if disaster/storm damage sustained, else $0.0$.
   - **Composite Vulnerability Priority Index (VPI)**:
     $$\text{VPI} = (S_{\text{income}} \times W_{\text{income}}) + (S_{\text{dependency}} \times W_{\text{dependency}}) + (S_{\text{housing}} \times W_{\text{housing}}) + (S_{\text{calamity}} \times W_{\text{calamity}})$$

3. **Constrained Resource Matching (Knapsack-Style Allocation)**:
   - Vector-sorted using Pandas and NumPy: Sorted by `VPI` (Descending), broken deterministically by `monthly_income` (Ascending) and `created_at` (Ascending).
   - Ranks $1 \dots \text{total\_quota\_slots}$ receive `Approved` status and a unique SHA-256 `claim_qr_hash`.
   - Ranks $> \text{total\_quota\_slots}$ are assigned to the `Waitlisted` priority queue.

4. **Explainable AI (XAI) Transparent Auditing**:
   - Every allocation record includes an exact JSON score breakdown detailing raw metrics, normalized scores, weighted contributions, and plain-language decision rationales.

5. **Field Verification & Disbursement via Cryptographic QR Codes**:
   - Approved beneficiaries receive a digital claim voucher and printable QR stub.
   - Field officers scan the QR voucher using an in-browser camera viewfinder (`html5-qrcode`).
   - Instant double-claim prevention: First scan approves disbursement; subsequent scans immediately alert the officer with previous claiming timestamp and agent ID.

---

## Tech Stack

- **Backend**: Python 3.11+ / 3.13 with **FastAPI**
- **ORM & Database**: **SQLAlchemy 2.0** targeting PostgreSQL (automatic SQLite fallback for development)
- **Data Math**: **Pandas** and **NumPy**
- **Security & Auth**: **OAuth2 Password Bearer**, **PyJWT (HS256)**, and **Bcrypt**
- **QR Generation**: Python `qrcode[pil]` with on-the-fly streaming PNG generation
- **Frontend**: Responsive Single-Page UI with **Tailwind CSS**, **Lucide Icons**, and **HTML5-QRCode**

---

## Project Structure & Architecture

```text
📁 smartaid/
├── 📁 templates/                 # HTML Web Views (Jinja2 Templates)
│   ├── base.html                 # Master layout & high-contrast navigation bar
│   ├── login.html                # Unified Staff & Beneficiary Portal
│   ├── apply.html                # Public Beneficiary Intake Application
│   ├── track.html                # Status Tracker & Holographic Voucher Pass
│   ├── scanner.html              # Field Agent Optical QR Camera Scanner
│   └── admin.html                # Operations Command & 20 Barangay Workstations
├── 📁 static/                    # Frontend Assets & Logic
│   ├── 📁 css/
│   │   └── style.css             # Design system, animations & glassmorphism
│   ├── 📁 js/
│   │   ├── admin.js              # Operations dashboard & XAI audit controller
│   │   ├── apply.js              # Dynamic multi-step intake controller
│   │   └── scanner.js            # Barcode video scanner & claim verification
│   └── 📁 img/                   # Civic landmarks & graphics
├── 📁 tests/                     # Automated Test Suites
│   ├── test_api.py               # Complete REST API & view integration tests
│   └── test_smartaid.py          # Deterministic MCDA mathematical unit tests
├── 📁 scripts/                   # Database Utilities & Migration Scripts
│   ├── seed_barangays.py         # 20 Barangay staff account generator
│   ├── clear_households.py       # Applicant reset & purge utility
│   └── update_maramag.py         # Address & demographic normalizer
├── 📁 .vscode/                   # Visual Studio Code Explorer Configuration
│   └── settings.json             # File nesting rules & cache exclusion
├── 📄 main.py                    # FastAPI Web Application & API Route Definitions
├── 📄 engine.py                  # Mathematical MCDA Engine (VPI, Knapsack, XAI)
├── 📄 models.py                  # Relational Database Schema (SQLAlchemy Models)
├── 📄 schemas.py                 # Data Validation & Serialization (Pydantic v2)
├── 📄 database.py                # Database Engine & Connection Session
├── 📄 auth.py                    # Security, Password Hashing & JWT Authentication
├── 📄 seed.py                    # Master Database Seeder (20 Barangays & Demo Data)
├── 📄 requirements.txt           # Python Project Dependencies
├── 📄 README.md                  # Project Documentation
└── 📄 .env.example               # Environment Variables Template
```

---

## Getting Started

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Populate Database & Run Initial MCDA Ranking
```bash
python seed.py
```
This initializes the database, creates staff accounts, loads an active emergency program with criteria rules, registers 20 realistic households with demographic variance, and executes the MCDA allocation engine.

### 3. Launch Application Server
```bash
python -m uvicorn main:app --reload --port 8000
```
Or simply:
```bash
python main.py
```
Navigate to: **`http://127.0.0.1:8000`**

---

## Default Staff Credentials

| Role | Username | Password | Full Name | Primary Station |
| :--- | :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | Maria Santos | Operations Command |
| **Social Worker** | `worker1` | `worker123` | Juan Dela Cruz | Case Evaluation |
| **Field Agent** | `agent1` | `agent123` | Ana Reyes | Barangay San Jose Post |

---

## Core Application Views

- `/`: Public Overview and Civic Portal landing page.
- `/login`: Unified Portal with dual tabs:
  - Tab 1: Staff Authentication (Admin, Social Worker, Field Agent)
  - Tab 2: Public Beneficiary Status Tracker
- `/admin`: Operations Dashboard:
  - Real-time KPI cards (Quota Slots, Approved, Disbursed, Budget)
  - Interactive Criteria Weight Slider modal (Income, Dependency, Calamity, Housing)
  - Master Allocation table with search, status filters (Approved, Waitlisted, Disqualified)
  - "Audit XAI" Slide-Over Drawer with visual contribution breakdown
- `/apply`: Public mobile-friendly intake registration with dynamic dependent rows and reference generator.
- `/track`: Beneficiary tracker with official digital QR claim pass and printable stub.
- `/scanner`: Field agent QR camera scanner with instant validation cards and double-claim prevention.

---

## Verification & Testing

To run the automated mathematical and logic verification suite:
```bash
python test_smartaid.py
```
Validates:
- Password hashing & JWT generation
- Hard income ceiling constraint enforcement
- Knapsack quota capacity limit ($K = 10$)
- Descending VPI vector order & tie-breakers
- Cryptographic SHA-256 voucher tokens
- Cooldown & double-claim prevention
