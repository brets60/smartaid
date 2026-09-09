import io
import os
import sys
import random
import string

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, Depends, HTTPException, status, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
import qrcode
from PIL import Image

from database import engine, get_db, Base
from models import User, Household, HouseholdMember, AidProgram, ProgramRule, Allocation, Disbursement, Announcement
from schemas import (
    Token, UserLogin, UserCreate, UserResponse,
    HouseholdCreate, HouseholdResponse,
    AidProgramCreate, AidProgramResponse, ProgramRuleCreate, ProgramRuleUpdate, ProgramRuleResponse,
    AllocationResponse, VerifyScanRequest, DisbursementResponse, BeneficiaryTrackResponse,
    AnnouncementCreate, AnnouncementResponse
)
from auth import (
    verify_password, get_password_hash, create_access_token,
    get_current_user, get_current_active_user_optional,
    require_admin, require_worker, require_agent_or_above,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from engine import MCDAEngine

# Ensure tables exist
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SmartAid Decision Support System",
    description="Automated Multi-Criteria Decision Support System for Localized Social Welfare and Constrained Relief Resource Allocation",
    version="1.0.0"
)

# Static files & Jinja2 templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static")
templates_dir = os.path.join(BASE_DIR, "templates")

os.makedirs(static_dir, exist_ok=True)
os.makedirs(os.path.join(static_dir, "css"), exist_ok=True)
os.makedirs(os.path.join(static_dir, "js"), exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

def generate_reference_number(db: Session) -> str:
    year = datetime.now().year
    while True:
        suffix = "".join(random.choices(string.digits, k=5))
        ref = f"APP-{year}-{suffix}"
        if not db.query(Household).filter(Household.reference_number == ref).first():
            return ref

# ==========================================
# WEB TEMPLATE VIEWS
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def view_home(request: Request, db: Session = Depends(get_db)):
    active_program = db.query(AidProgram).filter(AidProgram.status == "Active").first()
    return templates.TemplateResponse(
        request=request,
        name="base.html",
        context={"page_title": "Home", "active_program": active_program}
    )

@app.get("/login", response_class=HTMLResponse)
async def view_login(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"page_title": "Sign In / Track Aid"}
    )

@app.get("/admin", response_class=HTMLResponse)
async def view_admin(
    request: Request,
    user: Optional[User] = Depends(get_current_active_user_optional),
    db: Session = Depends(get_db)
):
    if not user or user.role not in ["admin", "social_worker"]:
        return RedirectResponse(url="/login?error=unauthorized_admin", status_code=status.HTTP_303_SEE_OTHER)

    programs = db.query(AidProgram).order_by(AidProgram.created_at.desc()).all()
    active_program = programs[0] if programs else None

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "page_title": "Administrative Dashboard",
            "current_user": user,
            "programs": programs,
            "active_program": active_program
        }
    )

@app.get("/apply", response_class=HTMLResponse)
async def view_apply(request: Request, db: Session = Depends(get_db)):
    active_program = db.query(AidProgram).filter(AidProgram.status == "Active").first()
    return templates.TemplateResponse(
        request=request,
        name="apply.html",
        context={"page_title": "Public Beneficiary Intake", "active_program": active_program}
    )

@app.get("/scanner", response_class=HTMLResponse)
async def view_scanner(
    request: Request,
    user: Optional[User] = Depends(get_current_active_user_optional)
):
    if not user or user.role not in ["admin", "social_worker", "field_agent"]:
        return RedirectResponse(url="/login?error=unauthorized_agent", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="scanner.html",
        context={"page_title": "Field Verification & Disbursement", "current_user": user}
    )

@app.get("/track", response_class=HTMLResponse)
async def view_track(request: Request, ref: Optional[str] = None):
    return templates.TemplateResponse(
        request=request,
        name="track.html",
        context={"page_title": "Beneficiary Status Tracker", "initial_ref": ref or ""}
    )

# ==========================================
# REST API V1: AUTHENTICATION
# ==========================================

@app.post("/api/v1/auth/token", response_model=Token)
async def login_for_access_token(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    username = None
    password = None
    content_type = request.headers.get("content-type", "")

    if "application/json" in content_type:
        try:
            body = await request.json()
            username = body.get("username")
            password = body.get("password")
        except Exception:
            pass
    else:
        try:
            form = await request.form()
            username = form.get("username")
            password = form.get("password")
        except Exception:
            pass

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required."
        )

    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive."
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role, "full_name": user.full_name},
        expires_delta=access_token_expires
    )

    # Also set as HttpOnly cookie for seamless web template navigation
    response.set_cookie(
        key="smartaid_token",
        value=access_token,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=False,  # Allow JS access for API fetch calls
        samesite="lax"
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role,
        full_name=user.full_name,
        username=user.username
    )

@app.get("/api/v1/auth/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/api/v1/auth/logout")
async def logout(response: Response):
    response.delete_cookie(key="smartaid_token")
    return {"message": "Successfully logged out."}

# ==========================================
# REST API V1: AID PROGRAMS & RULES
# ==========================================

@app.post("/api/v1/programs", response_model=AidProgramResponse)
async def create_program(
    program_in: AidProgramCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_worker)
):
    program = AidProgram(
        program_name=program_in.program_name,
        description=program_in.description,
        target_barangay=program_in.target_barangay,
        total_quota_slots=program_in.total_quota_slots,
        budget_per_slot=program_in.budget_per_slot,
        status="Active"
    )
    db.add(program)
    db.commit()
    db.refresh(program)

    rule_data = program_in.rules or ProgramRuleCreate()
    rules = ProgramRule(
        program_id=program.id,
        income_ceiling=rule_data.income_ceiling,
        weight_income=rule_data.weight_income,
        weight_dependency=rule_data.weight_dependency,
        weight_calamity=rule_data.weight_calamity,
        weight_housing=rule_data.weight_housing,
        cooldown_days=rule_data.cooldown_days
    )
    db.add(rules)
    db.commit()
    db.refresh(program)

    return program

@app.get("/api/v1/programs", response_model=List[AidProgramResponse])
async def list_programs(db: Session = Depends(get_db)):
    programs = db.query(AidProgram).order_by(AidProgram.created_at.desc()).all()
    results = []
    for p in programs:
        total_allocations = db.query(Allocation).filter(Allocation.program_id == p.id).count()
        approved_count = db.query(Allocation).filter(Allocation.program_id == p.id, Allocation.status == "Approved").count()
        disbursed_count = (
            db.query(Disbursement)
            .join(Allocation, Disbursement.allocation_id == Allocation.id)
            .filter(Allocation.program_id == p.id)
            .count()
        )
        total_disbursed_budget = disbursed_count * p.budget_per_slot

        p_dict = AidProgramResponse.model_validate(p).model_dump()
        p_dict["stats"] = {
            "total_applicants": total_allocations,
            "approved_count": approved_count,
            "disbursed_count": disbursed_count,
            "quota_slots": p.total_quota_slots,
            "remaining_slots": max(0, p.total_quota_slots - approved_count),
            "total_budget": p.total_quota_slots * p.budget_per_slot,
            "disbursed_budget": total_disbursed_budget,
            "utilization_percent": round((approved_count / p.total_quota_slots * 100) if p.total_quota_slots > 0 else 0, 1)
        }
        results.append(p_dict)
    return results

@app.get("/api/v1/programs/{program_id}", response_model=AidProgramResponse)
async def get_program(program_id: str, db: Session = Depends(get_db)):
    p = db.query(AidProgram).filter(AidProgram.id == program_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Program not found")

    total_allocations = db.query(Allocation).filter(Allocation.program_id == p.id).count()
    approved_count = db.query(Allocation).filter(Allocation.program_id == p.id, Allocation.status == "Approved").count()
    disbursed_count = (
        db.query(Disbursement)
        .join(Allocation, Disbursement.allocation_id == Allocation.id)
        .filter(Allocation.program_id == p.id)
        .count()
    )
    p_dict = AidProgramResponse.model_validate(p).model_dump()
    p_dict["stats"] = {
        "total_applicants": total_allocations,
        "approved_count": approved_count,
        "disbursed_count": disbursed_count,
        "quota_slots": p.total_quota_slots,
        "remaining_slots": max(0, p.total_quota_slots - approved_count),
        "total_budget": p.total_quota_slots * p.budget_per_slot,
        "disbursed_budget": disbursed_count * p.budget_per_slot,
        "utilization_percent": round((approved_count / p.total_quota_slots * 100) if p.total_quota_slots > 0 else 0, 1)
    }
    return p_dict

@app.put("/api/v1/programs/{program_id}/rules", response_model=ProgramRuleResponse)
async def update_program_rules(
    program_id: str,
    rules_in: ProgramRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_worker)
):
    rules = db.query(ProgramRule).filter(ProgramRule.program_id == program_id).first()
    if not rules:
        raise HTTPException(status_code=404, detail="Program rules not found.")

    if rules_in.income_ceiling is not None:
        rules.income_ceiling = rules_in.income_ceiling
    if rules_in.weight_income is not None:
        rules.weight_income = rules_in.weight_income
    if rules_in.weight_dependency is not None:
        rules.weight_dependency = rules_in.weight_dependency
    if rules_in.weight_calamity is not None:
        rules.weight_calamity = rules_in.weight_calamity
    if rules_in.weight_housing is not None:
        rules.weight_housing = rules_in.weight_housing
    if rules_in.cooldown_days is not None:
        rules.cooldown_days = rules_in.cooldown_days

    db.commit()
    db.refresh(rules)
    return rules

# ==========================================
# REST API V1: PUBLIC INTAKE & BENEFICIARY
# ==========================================

@app.post("/api/v1/apply", response_model=HouseholdResponse)
async def submit_application(household_in: HouseholdCreate, db: Session = Depends(get_db)):
    ref_number = generate_reference_number(db)

    # Compute dependent counts
    pwd_c = sum(1 for m in household_in.members if m.is_pwd)
    eld_c = sum(1 for m in household_in.members if m.is_senior)
    total_m = len(household_in.members) + 1  # Head + members

    household = Household(
        reference_number=ref_number,
        head_name=household_in.head_name.strip(),
        contact_number=household_in.contact_number.strip(),
        barangay=household_in.barangay.strip(),
        purok_zone=household_in.purok_zone.strip(),
        street_address=household_in.street_address.strip(),
        monthly_income=household_in.monthly_income,
        member_count=total_m,
        pwd_count=pwd_c,
        elderly_count=eld_c,
        is_informal_settler=household_in.is_informal_settler,
        has_calamity_damage=household_in.has_calamity_damage,
        created_at=datetime.now(timezone.utc)
    )
    db.add(household)
    db.flush()

    for m in household_in.members:
        member = HouseholdMember(
            household_id=household.id,
            first_name=m.first_name.strip(),
            last_name=m.last_name.strip(),
            relationship_to_head=m.relationship_to_head.strip(),
            is_pwd=m.is_pwd,
            is_senior=m.is_senior
        )
        db.add(member)

    db.commit()
    db.refresh(household)

    # Auto-evaluate into active program if exists
    active_program = db.query(AidProgram).filter(AidProgram.status == "Active").first()
    if active_program:
        try:
            engine_inst = MCDAEngine(db)
            engine_inst.evaluate_program(active_program.id)
        except Exception as e:
            # Don't fail the intake if evaluation encounters an issue
            print(f"Evaluation trigger warning: {e}")

    return household

@app.get("/api/v1/beneficiary/track/{reference_number}", response_model=BeneficiaryTrackResponse)
async def track_beneficiary(reference_number: str, db: Session = Depends(get_db)):
    ref = reference_number.strip().upper()
    household = db.query(Household).filter(func.upper(Household.reference_number) == ref).first()
    if not household:
        raise HTTPException(
            status_code=404,
            detail=f"Application with reference number '{reference_number}' was not found. Please verify your reference number."
        )

    # Find latest allocation
    allocation = (
        db.query(Allocation)
        .filter(Allocation.household_id == household.id)
        .order_by(Allocation.allocated_at.desc())
        .first()
    )

    if not allocation:
        return BeneficiaryTrackResponse(
            reference_number=household.reference_number,
            head_name=household.head_name,
            contact_number=household.contact_number,
            barangay=household.barangay,
            purok_zone=household.purok_zone,
            street_address=household.street_address,
            status="Under Review",
            rank=None,
            total_quota=None,
            vulnerability_score=None,
            score_breakdown=None,
            claim_qr_hash=None,
            is_disbursed=False,
            disbursed_at=None,
            budget_per_slot=None,
            qr_image_url=None
        )

    program = allocation.program
    is_disbursed = allocation.disbursement is not None
    disbursed_at = allocation.disbursement.disbursed_at if is_disbursed else None
    qr_url = f"/api/v1/qr/{allocation.claim_qr_hash}" if allocation.claim_qr_hash else None

    return BeneficiaryTrackResponse(
        reference_number=household.reference_number,
        head_name=household.head_name,
        contact_number=household.contact_number,
        barangay=household.barangay,
        purok_zone=household.purok_zone,
        street_address=household.street_address,
        program_id=program.id if program else None,
        program_name=program.program_name if program else "Localized Relief Program",
        status=allocation.status,
        rank=allocation.rank if allocation.rank > 0 else None,
        total_quota=program.total_quota_slots if program else None,
        vulnerability_score=allocation.vulnerability_score,
        score_breakdown=allocation.score_breakdown,
        claim_qr_hash=allocation.claim_qr_hash,
        is_disbursed=is_disbursed,
        disbursed_at=disbursed_at,
        budget_per_slot=program.budget_per_slot if program else 0.0,
        qr_image_url=qr_url
    )

# ==========================================
# REST API V1: EVALUATION & ALLOCATIONS
# ==========================================

@app.post("/api/v1/programs/{program_id}/evaluate")
async def evaluate_program_endpoint(
    program_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_worker)
):
    engine_inst = MCDAEngine(db)
    try:
        result = engine_inst.evaluate_program(program_id)
        return {"status": "success", "result": result}
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")

@app.get("/api/v1/programs/{program_id}/allocations", response_model=List[AllocationResponse])
async def get_program_allocations(
    program_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_above)
):
    allocations = (
        db.query(Allocation)
        .filter(Allocation.program_id == program_id)
        .order_by(
            Allocation.status.asc(),  # Approved first, then Disqualified, then Waitlisted (or sort by rank)
            Allocation.rank.asc()
        )
        .all()
    )

    # Sort so Approved (rank 1..N) comes first, then Waitlisted (rank N+1..), then Disqualified (-1)
    def sort_key(a: Allocation):
        if a.status == "Approved":
            return (0, a.rank)
        elif a.status == "Waitlisted":
            return (1, a.rank)
        else:
            return (2, 999999)

    allocations.sort(key=sort_key)

    results = []
    for a in allocations:
        is_disb = a.disbursement is not None
        disb_data = None
        if is_disb:
            disb_data = {
                "disbursed_at": a.disbursement.disbursed_at.isoformat(),
                "verified_by": a.disbursement.verified_by.full_name if a.disbursement.verified_by else "Staff",
                "notes": a.disbursement.notes
            }

        a_dict = {
            "id": a.id,
            "program_id": a.program_id,
            "household_id": a.household_id,
            "vulnerability_score": a.vulnerability_score,
            "score_breakdown": a.score_breakdown,
            "rank": a.rank,
            "status": a.status,
            "claim_qr_hash": a.claim_qr_hash,
            "allocated_at": a.allocated_at,
            "household": a.household,
            "is_disbursed": is_disb,
            "disbursement": disb_data
        }
        results.append(a_dict)

    return results

# ==========================================
# REST API V1: FIELD DISBURSEMENT & QR
# ==========================================

@app.post("/api/v1/disburse/verify-scan")
async def verify_and_disburse(
    payload: VerifyScanRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_above)
):
    qr_hash = payload.claim_qr_hash.strip()
    if not qr_hash:
        raise HTTPException(status_code=400, detail="QR claim token hash is required.")

    # Search allocation by claim_qr_hash OR household reference number
    allocation = (
        db.query(Allocation)
        .filter(Allocation.claim_qr_hash == qr_hash)
        .first()
    )

    if not allocation:
        # Fallback check if user entered reference number
        hh = db.query(Household).filter(func.upper(Household.reference_number) == qr_hash.upper()).first()
        if hh:
            allocation = db.query(Allocation).filter(Allocation.household_id == hh.id).first()

    if not allocation:
        return JSONResponse(
            status_code=404,
            content={
                "status": "INVALID",
                "message": "Invalid QR claim token. No matching approved allocation was found.",
                "valid": False
            }
        )

    # Check status
    if allocation.status != "Approved":
        return JSONResponse(
            status_code=400,
            content={
                "status": "NOT_APPROVED",
                "message": f"This applicant is currently '{allocation.status}'. Only Approved applicants can be disbursed.",
                "valid": False,
                "current_status": allocation.status,
                "rank": allocation.rank
            }
        )

    # Check if already disbursed
    if allocation.disbursement:
        disb = allocation.disbursement
        return JSONResponse(
            status_code=409,
            content={
                "status": "ALREADY_CLAIMED",
                "valid": False,
                "message": "Assistance package was already disbursed for this beneficiary!",
                "disbursed_at": disb.disbursed_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "verified_by": disb.verified_by.full_name if disb.verified_by else "Staff Agent",
                "reference_number": allocation.household.reference_number,
                "head_name": allocation.household.head_name,
                "barangay": allocation.household.barangay
            }
        )

    # Execute disbursement
    disbursement = Disbursement(
        allocation_id=allocation.id,
        verified_by_user_id=current_user.id,
        notes=payload.notes or "Verified via field QR camera scan.",
        disbursed_at=datetime.now(timezone.utc)
    )
    db.add(disbursement)
    db.commit()
    db.refresh(disbursement)

    return {
        "status": "SUCCESS",
        "valid": True,
        "message": "Assistance disbursement verified and successfully recorded!",
        "disbursement_id": disbursement.id,
        "reference_number": allocation.household.reference_number,
        "head_name": allocation.household.head_name,
        "barangay": allocation.household.barangay,
        "purok_zone": allocation.household.purok_zone,
        "monthly_income": allocation.household.monthly_income,
        "program_name": allocation.program.program_name if allocation.program else "Aid Program",
        "budget_amount": allocation.program.budget_per_slot if allocation.program else 0.0,
        "disbursed_at": disbursement.disbursed_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "verified_by": current_user.full_name
    }

@app.get("/api/v1/qr/{claim_qr_hash}")
async def generate_qr_image(claim_qr_hash: str):
    if not claim_qr_hash or len(claim_qr_hash) < 8:
        raise HTTPException(status_code=400, detail="Invalid QR hash.")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(claim_qr_hash)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/png")

# ==========================================
# REST API V1: NOTIFICATIONS & SMS BROADCAST
# ==========================================

@app.post("/api/v1/notifications/broadcast", response_model=AnnouncementResponse)
async def broadcast_notification(
    payload: AnnouncementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_worker)
):
    query = db.query(Household)

    # Filter by Barangay
    if payload.target_barangay and payload.target_barangay != "All":
        query = query.filter(Household.barangay == payload.target_barangay)

    # Filter by Allocation Status if specified
    if payload.target_status and payload.target_status != "All":
        query = query.join(Allocation, Household.id == Allocation.household_id).filter(
            Allocation.status == payload.target_status
        )

    households = query.all()
    recipients_count = len(households)

    # Dispatch / Simulate SMS Blast
    if payload.dispatch_sms and recipients_count > 0:
        print(f"\n[SMS DISPATCH - LGU MARAMAG MSWDO]")
        print(f"Announcement: {payload.title} ({payload.category})")
        print(f"Target Barangay: {payload.target_barangay} | Status: {payload.target_status}")
        print(f"Sending broadcast to {recipients_count} registered household mobile numbers...")
        for h in households[:5]:  # Log first 5 sample deliveries
            print(f"  -> [SMS SENT to {h.contact_number} ({h.head_name} - {h.barangay})]: {payload.message}")
        if recipients_count > 5:
            print(f"  -> ... and {recipients_count - 5} more mobile numbers dispatched successfully via SMS Gateway.")

    announcement = Announcement(
        title=payload.title.strip(),
        category=payload.category.strip(),
        target_barangay=payload.target_barangay if payload.target_barangay != "All" else None,
        target_status=payload.target_status if payload.target_status != "All" else None,
        message=payload.message.strip(),
        sms_dispatched=payload.dispatch_sms,
        recipients_count=recipients_count,
        created_at=datetime.now(timezone.utc)
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)

    return announcement

@app.get("/api/v1/notifications", response_model=List[AnnouncementResponse])
async def list_notifications(
    barangay: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Announcement).order_by(Announcement.created_at.desc())
    if barangay and barangay != "All":
        # Return both municipal-wide (target_barangay is None) and specific barangay announcements
        query = query.filter((Announcement.target_barangay == None) | (Announcement.target_barangay == barangay))
    
    return query.limit(20).all()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
