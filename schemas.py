from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

# --- User & Auth Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    username: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: str = "field_agent"
    assigned_barangay: Optional[str] = None

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    full_name: str
    username: str
    role: str
    assigned_barangay: Optional[str] = None
    is_active: bool
    created_at: datetime

# --- Household Member Schemas ---
class HouseholdMemberCreate(BaseModel):
    first_name: str
    last_name: str
    relationship_to_head: str
    is_pwd: bool = False
    is_senior: bool = False

class HouseholdMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    first_name: str
    last_name: str
    relationship_to_head: str
    is_pwd: bool
    is_senior: bool

# --- Household Schemas ---
class HouseholdCreate(BaseModel):
    head_name: str
    contact_number: str
    barangay: str
    purok_zone: str
    street_address: str
    monthly_income: float = Field(ge=0.0)
    is_informal_settler: bool = False
    has_calamity_damage: bool = False
    members: List[HouseholdMemberCreate] = []

class HouseholdResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    reference_number: str
    head_name: str
    contact_number: str
    barangay: str
    purok_zone: str
    street_address: str
    monthly_income: float
    member_count: int
    pwd_count: int
    elderly_count: int
    is_informal_settler: bool
    has_calamity_damage: bool
    created_at: datetime
    members: List[HouseholdMemberResponse] = []

class HouseholdUpdate(BaseModel):
    head_name: Optional[str] = None
    contact_number: Optional[str] = None
    barangay: Optional[str] = None
    purok_zone: Optional[str] = None
    street_address: Optional[str] = None
    monthly_income: Optional[float] = Field(default=None, ge=0.0)
    is_informal_settler: Optional[bool] = None
    has_calamity_damage: Optional[bool] = None
    members: Optional[List[HouseholdMemberCreate]] = None

# --- Program & Rules Schemas ---
class ProgramRuleCreate(BaseModel):
    income_ceiling: float = 15000.0
    weight_income: float = 0.35
    weight_dependency: float = 0.25
    weight_calamity: float = 0.20
    weight_housing: float = 0.20
    cooldown_days: int = 14

class ProgramRuleUpdate(BaseModel):
    income_ceiling: Optional[float] = None
    weight_income: Optional[float] = None
    weight_dependency: Optional[float] = None
    weight_calamity: Optional[float] = None
    weight_housing: Optional[float] = None
    cooldown_days: Optional[int] = None

class ProgramRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    program_id: str
    income_ceiling: float
    weight_income: float
    weight_dependency: float
    weight_calamity: float
    weight_housing: float
    cooldown_days: int

class AidProgramCreate(BaseModel):
    program_name: str
    description: Optional[str] = None
    target_barangay: Optional[str] = None
    total_quota_slots: int = Field(gt=0, default=100)
    budget_per_slot: float = Field(ge=0.0, default=0.0)
    rules: Optional[ProgramRuleCreate] = None

class AidProgramResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    program_name: str
    description: Optional[str] = None
    target_barangay: Optional[str] = None
    total_quota_slots: int
    budget_per_slot: float
    status: str
    created_at: datetime
    rules: Optional[ProgramRuleResponse] = None
    stats: Optional[Dict[str, Any]] = None

# --- Allocation Schemas ---
class AllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    program_id: str
    household_id: str
    vulnerability_score: float
    score_breakdown: Optional[Dict[str, Any]] = None
    rank: int
    status: str
    claim_qr_hash: Optional[str] = None
    allocated_at: datetime
    household: Optional[HouseholdResponse] = None
    is_disbursed: bool = False
    disbursement: Optional[Dict[str, Any]] = None

# --- Disbursement Schemas ---
class VerifyScanRequest(BaseModel):
    claim_qr_hash: str
    notes: Optional[str] = None
    signature_data: Optional[str] = None

class DisbursementResponse(BaseModel):
    id: str
    allocation_id: str
    reference_number: str
    head_name: str
    barangay: str
    disbursed_at: datetime
    verified_by_name: str
    notes: Optional[str] = None
    signature_data: Optional[str] = None

# --- Audit Log Schemas ---
class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    action: str
    target_entity: str
    target_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime

# --- Beneficiary Tracking Response ---
class BeneficiaryTrackResponse(BaseModel):
    reference_number: str
    head_name: str
    contact_number: str
    barangay: str
    purok_zone: str
    street_address: str
    program_id: Optional[str] = None
    program_name: Optional[str] = None
    status: str
    rank: Optional[int] = None
    total_quota: Optional[int] = None
    vulnerability_score: Optional[float] = None
    score_breakdown: Optional[Dict[str, Any]] = None
    claim_qr_hash: Optional[str] = None
    is_disbursed: bool = False
    disbursed_at: Optional[datetime] = None
    budget_per_slot: Optional[float] = None
    qr_image_url: Optional[str] = None

# --- Announcement & Notification Schemas ---
class AnnouncementCreate(BaseModel):
    title: str
    category: str = "Relief Distribution"  # 'Relief Distribution', 'Scholarship / Education', 'Disaster Alert', 'General Notice'
    target_barangay: Optional[str] = "All"
    target_status: Optional[str] = "All"  # 'All', 'Approved', 'Waitlisted'
    message: str
    dispatch_sms: bool = True

class AnnouncementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    category: str
    target_barangay: Optional[str] = None
    target_status: Optional[str] = None
    message: str
    sms_dispatched: bool
    recipients_count: int
    created_at: datetime
    sms_result: Optional[Dict[str, Any]] = None
