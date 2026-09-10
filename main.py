import io
import csv
import os
import sys
import random
import string
import json
import urllib.request
import urllib.parse
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

# Auto-load environment variables from .env if present
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
env_file = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_file):
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

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
from models import User, Household, HouseholdMember, AidProgram, ProgramRule, Allocation, Disbursement, Announcement, AuditLog
from schemas import (
    Token, UserLogin, UserCreate, UserResponse,
    HouseholdCreate, HouseholdResponse, HouseholdUpdate,
    AidProgramCreate, AidProgramResponse, ProgramRuleCreate, ProgramRuleUpdate, ProgramRuleResponse,
    AllocationResponse, VerifyScanRequest, DisbursementResponse, BeneficiaryTrackResponse,
    AnnouncementCreate, AnnouncementResponse, AuditLogResponse,
    AIChatRequest, AIChatResponse, AISimulateRequest, AIApplyWeightsRequest
)
from auth import (
    verify_password, get_password_hash, create_access_token,
    get_current_user, get_current_active_user_optional,
    require_admin, require_worker, require_agent_or_above, require_worker_or_barangay,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from engine import MCDAEngine
from ai_engine import (
    SmartAidAICopilot,
    generate_xai_narrative,
    evaluate_intake_risk,
    simulate_policy_scenario,
    SCENARIOS
)

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

def log_audit_event(
    db: Session,
    action: str,
    target_entity: str,
    target_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    user: Optional[User] = None,
    ip_address: Optional[str] = None
):
    try:
        log = AuditLog(
            user_id=user.id if user else None,
            username=user.username if user else "PUBLIC / SYSTEM",
            action=action,
            target_entity=target_entity,
            target_id=str(target_id) if target_id else None,
            details=details or {},
            ip_address=ip_address
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"[AUDIT LOG WARNING] {e}")

def dispatch_single_sms(phone: str, message: str) -> bool:
    api_key = os.environ.get("SEMAPHORE_API_KEY", "").strip()
    clean_phone = phone.replace(" ", "").replace("-", "").strip()
    if clean_phone.startswith("+63"):
        clean_phone = "0" + clean_phone[3:]
    
    if not clean_phone.startswith("09") or len(clean_phone) != 11:
        return False
        
    sender_name = os.environ.get("SEMAPHORE_SENDER_NAME", "SmartAid").strip()
    print(f"[SMS DISPATCH] To: {clean_phone} | Msg: {message}")
    if not api_key:
        print("[SMS SIMULATION] No SEMAPHORE_API_KEY set. Simulated delivery.")
        return True
        
    try:
        sms_data = urllib.parse.urlencode({
            "apikey": api_key,
            "number": clean_phone,
            "message": f"LGU MARAMAG MSWDO: {message}",
            "sendername": sender_name
        }).encode("utf-8")
        req = urllib.request.Request("https://api.semaphore.co/api/v4/messages", data=sms_data, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"[SMS WARNING] Failed sending SMS: {e}")
        return False

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
    if not user or user.role not in ["admin", "social_worker", "barangay_staff"]:
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
        data={"sub": user.username, "role": user.role, "full_name": user.full_name, "assigned_barangay": user.assigned_barangay},
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

    log_audit_event(
        db,
        action="UPDATE_MCDA_WEIGHTS",
        target_entity="ProgramRule",
        target_id=rules.id,
        details={
            "program_id": program_id,
            "weight_income": rules.weight_income,
            "weight_dependency": rules.weight_dependency,
            "weight_calamity": rules.weight_calamity,
            "weight_housing": rules.weight_housing,
            "income_ceiling": rules.income_ceiling
        },
        user=current_user
    )

    return rules

# ==========================================
# REST API V1: PUBLIC INTAKE & BENEFICIARY
# ==========================================

@app.post("/api/v1/apply", response_model=HouseholdResponse)
async def submit_application(household_in: HouseholdCreate, request: Request, db: Session = Depends(get_db)):
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

    log_audit_event(
        db,
        action="SUBMIT_INTAKE",
        target_entity="Household",
        target_id=household.id,
        details={
            "reference_number": household.reference_number,
            "head_name": household.head_name,
            "barangay": household.barangay,
            "income": household.monthly_income,
            "member_count": household.member_count
        },
        ip_address=request.client.host if request.client else None
    )

    if household.contact_number:
        dispatch_single_sms(
            household.contact_number,
            f"Kumusta {household.head_name}, nadawat ang imong rehistrasyon sa SmartAid. Imong Reference No: {household.reference_number}. Susiha sa smartaid.lgu/track"
        )

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

@app.post("/api/v1/households/reset")
async def reset_households(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    db.query(Disbursement).delete()
    db.query(Allocation).delete()
    db.query(HouseholdMember).delete()
    deleted_count = db.query(Household).delete()
    db.commit()
    return {"status": "SUCCESS", "deleted_count": deleted_count, "message": f"Successfully deleted {deleted_count} households and reset all allocations."}

@app.get("/api/v1/households/{household_id}", response_model=HouseholdResponse)
async def get_household(
    household_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_worker_or_barangay)
):
    household = db.query(Household).filter(Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="Household record not found.")
    return household

@app.put("/api/v1/households/{household_id}", response_model=HouseholdResponse)
async def update_household(
    household_id: str,
    household_update: HouseholdUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_worker_or_barangay)
):
    household = db.query(Household).filter(Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="Household record not found.")

    if household_update.head_name is not None:
        household.head_name = household_update.head_name.strip()
    if household_update.contact_number is not None:
        household.contact_number = household_update.contact_number.strip()
    if household_update.barangay is not None:
        household.barangay = household_update.barangay.strip()
    if household_update.purok_zone is not None:
        household.purok_zone = household_update.purok_zone.strip()
    if household_update.street_address is not None:
        household.street_address = household_update.street_address.strip()
    if household_update.monthly_income is not None:
        household.monthly_income = household_update.monthly_income
    if household_update.is_informal_settler is not None:
        household.is_informal_settler = household_update.is_informal_settler
    if household_update.has_calamity_damage is not None:
        household.has_calamity_damage = household_update.has_calamity_damage

    # Update members if provided
    if household_update.members is not None:
        db.query(HouseholdMember).filter(HouseholdMember.household_id == household.id).delete()
        
        pwd_c = 0
        eld_c = 0
        for m in household_update.members:
            if m.is_pwd:
                pwd_c += 1
            if m.is_senior:
                eld_c += 1
            member = HouseholdMember(
                household_id=household.id,
                first_name=m.first_name.strip(),
                last_name=m.last_name.strip(),
                relationship_to_head=m.relationship_to_head.strip(),
                is_pwd=m.is_pwd,
                is_senior=m.is_senior
            )
            db.add(member)
        
        household.member_count = len(household_update.members) + 1
        household.pwd_count = pwd_c
        household.elderly_count = eld_c

    db.commit()
    db.refresh(household)

    # Re-evaluate active program allocations automatically
    active_program = db.query(AidProgram).filter(AidProgram.status == "Active").first()
    if active_program:
        try:
            engine_inst = MCDAEngine(db)
            engine_inst.evaluate_program(active_program.id)
        except Exception as e:
            print(f"Re-evaluation after household update warning: {e}")

    log_audit_event(
        db,
        action="UPDATE_HOUSEHOLD",
        target_entity="Household",
        target_id=household.id,
        details={
            "reference_number": household.reference_number,
            "head_name": household.head_name,
            "barangay": household.barangay,
            "income": household.monthly_income,
            "member_count": household.member_count
        },
        user=current_user
    )

    return household

@app.delete("/api/v1/households/{household_id}")
async def delete_household(
    household_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    household = db.query(Household).filter(Household.id == household_id).first()
    if not household:
        raise HTTPException(status_code=404, detail="Household record not found.")

    log_audit_event(
        db,
        action="DELETE_HOUSEHOLD",
        target_entity="Household",
        target_id=household_id,
        details={
            "head_name": household.head_name,
            "reference_number": household.reference_number,
            "barangay": household.barangay
        },
        user=current_user
    )

    allocations = db.query(Allocation).filter(Allocation.household_id == household_id).all()
    for alloc in allocations:
        db.query(Disbursement).filter(Disbursement.allocation_id == alloc.id).delete()
    db.query(Allocation).filter(Allocation.household_id == household_id).delete()
    db.query(HouseholdMember).filter(HouseholdMember.household_id == household_id).delete()
    db.delete(household)
    db.commit()

    active_program = db.query(AidProgram).filter(AidProgram.status == "Active").first()
    if active_program:
        try:
            engine_inst = MCDAEngine(db)
            engine_inst.evaluate_program(active_program.id)
        except Exception as e:
            print(f"Re-evaluation after household delete warning: {e}")

    return {"status": "SUCCESS", "message": f"Household '{household.head_name}' and associated records deleted."}

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

    risk_info = evaluate_intake_risk(db, household)

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
            qr_image_url=None,
            ai_narrative={
                "en": "Application is pending official criteria evaluation by municipal social welfare officers.",
                "ceb": "Giproseso pa ang opisyal nga ebalwasyon sa aplikasyon sa buhatan sa MSWDO."
            },
            risk_analysis=risk_info
        )

    program = allocation.program
    is_disbursed = allocation.disbursement is not None
    disbursed_at = allocation.disbursement.disbursed_at if is_disbursed else None
    qr_url = f"/api/v1/qr/{allocation.claim_qr_hash}" if allocation.claim_qr_hash else None
    rules = program.rules if program else None
    narrative = generate_xai_narrative(allocation, household, rules)

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
        qr_image_url=qr_url,
        ai_narrative=narrative,
        risk_analysis=risk_info
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
    rules = None
    first_alloc = allocations[0] if allocations else None
    if first_alloc and first_alloc.program:
        rules = first_alloc.program.rules

    for a in allocations:
        is_disb = a.disbursement is not None
        disb_data = None
        if is_disb:
            disb_data = {
                "disbursed_at": a.disbursement.disbursed_at.isoformat(),
                "verified_by": a.disbursement.verified_by.full_name if a.disbursement.verified_by else "Staff",
                "notes": a.disbursement.notes,
                "has_signature": bool(a.disbursement.signature_data)
            }

        hh = a.household
        ai_narrative = generate_xai_narrative(a, hh, rules) if hh else None
        risk = evaluate_intake_risk(db, hh) if hh else None

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
            "disbursement": disb_data,
            "ai_narrative": ai_narrative,
            "risk_analysis": risk
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
        signature_data=payload.signature_data,
        disbursed_at=datetime.now(timezone.utc)
    )
    db.add(disbursement)
    db.commit()
    db.refresh(disbursement)

    log_audit_event(
        db,
        action="DISBURSE_PACKAGE",
        target_entity="Disbursement",
        target_id=disbursement.id,
        details={
            "reference_number": allocation.household.reference_number,
            "head_name": allocation.household.head_name,
            "barangay": allocation.household.barangay,
            "has_signature": bool(payload.signature_data)
        },
        user=current_user
    )

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
        "verified_by": current_user.full_name,
        "has_signature": bool(disbursement.signature_data)
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

def send_semaphore_sms(phone_numbers: List[str], message: str) -> dict:
    api_key = os.getenv("SEMAPHORE_API_KEY", "").strip()
    if not api_key:
        print("\n[SMS GATEWAY STATUS]: No SEMAPHORE_API_KEY detected in .env. Dispatched in simulation mode.")
        return {"status": "SIMULATED", "message": "Simulated dispatch - paste SEMAPHORE_API_KEY in .env to send real SMS."}

    import urllib.request
    import urllib.parse
    import json

    cleaned = []
    for p in phone_numbers:
        num = p.replace("-", "").replace(" ", "").replace("+63", "0").strip()
        if len(num) >= 10:
            cleaned.append(num)

    if not cleaned:
        return {"status": "EMPTY", "message": "No valid phone numbers to send."}

    payload = {
        "apikey": api_key,
        "number": ",".join(cleaned),
        "message": f"LGU MARAMAG MSWDO: {message}"
    }

    try:
        req = urllib.request.Request(
            "https://api.semaphore.co/api/v4/messages",
            data=urllib.parse.urlencode(payload).encode("utf-8"),
            headers={"User-Agent": "SmartAid-LGU-Maramag"}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_json = json.loads(response.read().decode("utf-8"))
            print(f"\n[SEMAPHORE LIVE SMS SENT] Successfully delivered to {len(cleaned)} mobile numbers!")
            return {"status": "LIVE_SENT", "count": len(cleaned), "response": res_json}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore").strip()
        print(f"\n[SEMAPHORE GATEWAY ERROR HTTP {e.code}]: {err_body}")
        return {"status": "GATEWAY_ERROR", "code": e.code, "error": err_body}
    except Exception as e:
        print(f"\n[SEMAPHORE GATEWAY ERROR]: Failed to send live SMS: {e}")
        return {"status": "GATEWAY_ERROR", "error": str(e)}

@app.get("/api/v1/settings/sms")
async def get_sms_settings(current_user: User = Depends(require_worker)):
    key = os.getenv("SEMAPHORE_API_KEY", "").strip()
    masked = f"{key[:4]}••••••••{key[-4:]}" if len(key) >= 10 else ("Configured" if key else "")
    account_info = None
    account_error = None

    if key:
        try:
            import urllib.request
            req = urllib.request.Request(
                f"https://api.semaphore.co/api/v4/account?apikey={key}",
                headers={"User-Agent": "SmartAid-LGU-Maramag"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                account_info = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            account_error = e.read().decode("utf-8", errors="ignore").strip()
        except Exception as e:
            account_error = str(e)

    return {
        "is_configured": bool(key),
        "masked_key": masked,
        "provider": "Semaphore.co (Globe / Smart / DITO Gateway)",
        "account": account_info,
        "error": account_error
    }

@app.post("/api/v1/settings/sms")
async def save_sms_settings(
    request: Request,
    current_user: User = Depends(require_worker)
):
    body = await request.json()
    new_key = body.get("api_key", "").strip()
    os.environ["SEMAPHORE_API_KEY"] = new_key

    # Save to .env file
    env_path = os.path.join(BASE_DIR, ".env")
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.startswith("SEMAPHORE_API_KEY="):
            new_lines.append(f"SEMAPHORE_API_KEY={new_key}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"\nSEMAPHORE_API_KEY={new_key}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    return {
        "status": "SUCCESS",
        "is_configured": bool(new_key),
        "message": "Semaphore SMS API Key saved successfully! Live SMS text messages will now be sent to Philippine mobile phones."
    }

@app.post("/api/v1/notifications/broadcast", response_model=AnnouncementResponse)
async def broadcast_notification(
    payload: AnnouncementCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_worker_or_barangay)
):
    target_barangay = payload.target_barangay

    # Enforce jurisdiction for barangay staff
    if current_user.role == "barangay_staff" and current_user.assigned_barangay:
        target_barangay = current_user.assigned_barangay

    query = db.query(Household)

    # Filter by Barangay
    if target_barangay and target_barangay != "All":
        query = query.filter(Household.barangay == target_barangay)

    # Filter by Allocation Status if specified
    if payload.target_status and payload.target_status != "All":
        query = query.join(Allocation, Household.id == Allocation.household_id).filter(
            Allocation.status == payload.target_status
        )

    households = query.all()
    recipients_count = len(households)
    phone_numbers = [h.contact_number for h in households if h.contact_number]

    # Dispatch via Semaphore Gateway (Real if key exists, Simulated if no key)
    sms_result = None
    if payload.dispatch_sms and phone_numbers:
        agency_name = f"BARANGAY {target_barangay.upper()}" if (current_user.role == "barangay_staff" and target_barangay) else "LGU MARAMAG MSWDO"
        print(f"\n[SMS DISPATCH - {agency_name}]")
        print(f"Announcement: {payload.title} ({payload.category})")
        print(f"Target Barangay: {target_barangay} | Status: {payload.target_status}")
        print(f"Sending broadcast to {len(phone_numbers)} registered household mobile numbers...")
        for h in households[:5]:
            print(f"  -> [Target: {h.contact_number} ({h.head_name} - {h.barangay})]: {payload.message}")
        
        # Trigger Semaphore API dispatch
        sms_result = send_semaphore_sms(phone_numbers, payload.message)

    announcement = Announcement(
        title=payload.title.strip(),
        category=payload.category.strip(),
        target_barangay=target_barangay if target_barangay != "All" else None,
        target_status=payload.target_status if payload.target_status != "All" else None,
        message=payload.message.strip(),
        sms_dispatched=payload.dispatch_sms,
        recipients_count=recipients_count,
        created_at=datetime.now(timezone.utc)
    )
    db.add(announcement)
    db.commit()
    db.refresh(announcement)

    # Attach sms_result for API response
    response_data = AnnouncementResponse.model_validate(announcement)
    response_data.sms_result = sms_result
    return response_data

@app.get("/api/v1/notifications", response_model=List[AnnouncementResponse])
async def list_notifications(
    barangay: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Announcement).order_by(Announcement.created_at.desc())
    if barangay and barangay != "All":
        query = query.filter((Announcement.target_barangay == None) | (Announcement.target_barangay == barangay))
    
    return query.limit(20).all()

# ==========================================
# REST API V1: OFFICIAL COA REPORTS & AUDIT
# ==========================================

@app.get("/api/v1/reports/allocations/export")
async def export_allocations_csv(
    program_id: Optional[str] = None,
    barangay: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_worker_or_barangay)
):
    query = db.query(Allocation).join(Household, Allocation.household_id == Household.id)
    if program_id:
        query = query.filter(Allocation.program_id == program_id)
    else:
        active_prog = db.query(AidProgram).filter(AidProgram.status == "Active").first()
        if active_prog:
            query = query.filter(Allocation.program_id == active_prog.id)

    # Enforce barangay desk officer restriction
    if current_user.role == "barangay_staff" and current_user.assigned_barangay:
        query = query.filter(Household.barangay == current_user.assigned_barangay)
    elif barangay and barangay != "All":
        query = query.filter(Household.barangay == barangay)

    if status and status != "All":
        query = query.filter(Allocation.status == status)

    allocations = query.all()

    def alloc_sort(a: Allocation):
        if a.status == "Approved":
            return (0, a.rank if a.rank > 0 else 9999)
        elif a.status == "Waitlisted":
            return (1, a.rank if a.rank > 0 else 9999)
        return (2, 999999)
    allocations.sort(key=alloc_sort)

    output = io.StringIO()
    output.write("\ufeff")  # UTF-8 BOM for Microsoft Excel compatibility
    writer = csv.writer(output)
    
    writer.writerow(["MUNICIPALITY OF MARAMAG, BUKIDNON - MSWDO"])
    writer.writerow(["OFFICIAL BENEFICIARY ALLOCATION & PAYROLL MASTERLIST"])
    writer.writerow([f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", f"Generated By: {current_user.full_name} ({current_user.role})"])
    writer.writerow([])
    
    headers = [
        "Priority Rank",
        "Application Ref",
        "Head of Household",
        "Barangay",
        "Purok / Zone",
        "Street Address",
        "Contact Number",
        "Monthly Income (PHP)",
        "Family Members",
        "PWD Count",
        "Senior Count",
        "Informal Settler",
        "Calamity Damage",
        "VPI Vulnerability Score",
        "Allocation Status",
        "QR Claim Token",
        "Disbursement Status",
        "Disbursed Date & Time",
        "Disbursing Officer",
        "Beneficiary Signature / Thumbmark"
    ]
    writer.writerow(headers)

    for a in allocations:
        h = a.household
        disb = a.disbursement
        is_disb = disb is not None
        disb_time = disb.disbursed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if is_disb else "Unclaimed"
        officer = disb.verified_by.full_name if (is_disb and disb.verified_by) else ""
        has_sig = "Digital Signed" if (is_disb and disb.signature_data) else ("Signed" if is_disb else "")

        writer.writerow([
            f"#{a.rank}" if a.rank > 0 else "N/A",
            h.reference_number,
            h.head_name,
            h.barangay,
            h.purok_zone,
            h.street_address,
            h.contact_number,
            f"{h.monthly_income:.2f}",
            h.member_count,
            h.pwd_count,
            h.elderly_count,
            "YES" if h.is_informal_settler else "NO",
            "YES" if h.has_calamity_damage else "NO",
            f"{a.vulnerability_score:.4f}",
            a.status,
            a.claim_qr_hash or "",
            "CLAIMED" if is_disb else ("READY_TO_CLAIM" if a.status == "Approved" else "PENDING"),
            disb_time,
            officer,
            has_sig or "[ _________________________ ]"
        ])

    csv_data = output.getvalue()
    output.close()

    filename = f"smartaid_masterlist_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"",
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )

@app.get("/api/v1/audit-logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()

# ==========================================
# REST API V1: SMARTAID AI & DECISION INTELLIGENCE
# ==========================================

@app.post("/api/v1/ai/chat", response_model=AIChatResponse)
async def ai_copilot_chat(
    payload: AIChatRequest,
    db: Session = Depends(get_db)
):
    """
    Bilingual (EN / CEB) context-aware conversational copilot.
    Grounds answers on live registry lookups, poverty thresholds, and Maramag welfare criteria.
    """
    result = SmartAidAICopilot.chat(payload.message, db, language=payload.language or "en")
    return AIChatResponse(
        reply=result["reply"],
        suggestions=result.get("suggestions"),
        household=result.get("household")
    )

@app.post("/api/v1/ai/simulate")
async def ai_simulate_scenario(
    payload: AISimulateRequest,
    program_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_above)
):
    """
    In-memory scenario simulation lab. Recomputes MCDA rankings and barangay allocations
    without mutating the live database.
    """
    if not program_id:
        prog = db.query(AidProgram).filter(AidProgram.status == "Active").first()
        if not prog:
            prog = db.query(AidProgram).first()
        if not prog:
            raise HTTPException(status_code=404, detail="No aid program found to simulate.")
        program_id = prog.id

    try:
        return simulate_policy_scenario(db, program_id, payload.scenario, payload.custom_weights)
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(e)}")

@app.post("/api/v1/ai/apply-simulated-weights")
async def ai_apply_simulated_weights(
    payload: AIApplyWeightsRequest,
    program_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Commits simulated scenario weights to an active program's rules, triggers full MCDA re-evaluation,
    and logs an auditable governance trail event.
    """
    if not program_id:
        prog = db.query(AidProgram).filter(AidProgram.status == "Active").first()
        if not prog:
            prog = db.query(AidProgram).first()
        if not prog:
            raise HTTPException(status_code=404, detail="No aid program found.")
        program_id = prog.id
    else:
        prog = db.query(AidProgram).filter(AidProgram.id == program_id).first()
        if not prog:
            raise HTTPException(status_code=404, detail="Program not found.")

    scenario_info = SCENARIOS.get(payload.scenario)
    if scenario_info:
        weights = scenario_info["weights"]
    elif payload.custom_weights:
        weights = payload.custom_weights
    else:
        raise HTTPException(status_code=400, detail="Invalid scenario or custom weights provided.")

    if not prog.rules:
        rule = ProgramRule(
            program_id=prog.id,
            income_ceiling=15000.0,
            weight_income=weights.get("income", 0.35),
            weight_dependency=weights.get("dependency", 0.25),
            weight_calamity=weights.get("calamity", 0.20),
            weight_housing=weights.get("housing", 0.20),
            cooldown_days=14
        )
        db.add(rule)
    else:
        prog.rules.weight_income = weights.get("income", 0.35)
        prog.rules.weight_dependency = weights.get("dependency", 0.25)
        prog.rules.weight_calamity = weights.get("calamity", 0.20)
        prog.rules.weight_housing = weights.get("housing", 0.20)

    db.commit()
    db.refresh(prog)

    # Re-evaluate
    engine_inst = MCDAEngine(db)
    eval_result = engine_inst.evaluate_program(prog.id)

    log_audit_event(
        db=db,
        action="AI_POLICY_WEIGHTS_APPLIED",
        target_entity="AidProgram",
        target_id=prog.id,
        details={
            "scenario": payload.scenario,
            "weights": weights,
            "eval_result": eval_result
        },
        user=current_user
    )

    return {
        "status": "SUCCESS",
        "message": f"Successfully applied AI policy weights for scenario '{payload.scenario}' to {prog.program_name}.",
        "weights": weights,
        "eval_result": eval_result
    }

@app.get("/api/v1/ai/risk-analysis")
async def ai_registry_risk_analysis(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_worker_or_barangay)
):
    """
    Runs real-time anomaly detection across registered applicant households to detect
    recycled contact numbers, suspicious ₱0 income declarations, and address clustering.
    """
    households = db.query(Household).all()
    results = []
    summary = {"total": 0, "LOW": 0, "MEDIUM": 0, "HIGH": 0}
    for h in households:
        if current_user.role == "barangay_staff" and current_user.assigned_barangay and h.barangay != current_user.assigned_barangay:
            continue
        summary["total"] += 1
        r = evaluate_intake_risk(db, h)
        summary[r["risk_level"]] += 1
        if r["risk_level"] in ("MEDIUM", "HIGH"):
            results.append({
                "household_id": h.id,
                "reference_number": h.reference_number,
                "head_name": h.head_name,
                "barangay": h.barangay,
                "contact_number": h.contact_number,
                "monthly_income": h.monthly_income,
                "member_count": h.member_count,
                "risk_score": r["risk_score"],
                "risk_level": r["risk_level"],
                "risk_flags": r["risk_flags"]
            })
    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return {
        "summary": summary,
        "flagged_count": len(results),
        "flagged_records": results
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
