import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON
)
from sqlalchemy.orm import relationship
from database import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    full_name = Column(String(255), nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="field_agent")  # 'admin', 'social_worker', 'field_agent'
    assigned_barangay = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    disbursements = relationship("Disbursement", back_populates="verified_by")

class Household(Base):
    __tablename__ = "households"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    reference_number = Column(String(50), unique=True, index=True, nullable=False)
    head_name = Column(String(255), index=True, nullable=False)
    contact_number = Column(String(50), index=True, nullable=False)
    barangay = Column(String(100), index=True, nullable=False)
    purok_zone = Column(String(100), nullable=False)
    street_address = Column(Text, nullable=False)
    monthly_income = Column(Float, nullable=False, default=0.0)
    member_count = Column(Integer, nullable=False, default=1)
    pwd_count = Column(Integer, default=0, nullable=False)
    elderly_count = Column(Integer, default=0, nullable=False)
    is_informal_settler = Column(Boolean, default=False, nullable=False)
    has_calamity_damage = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    members = relationship("HouseholdMember", back_populates="household", cascade="all, delete-orphan")
    allocations = relationship("Allocation", back_populates="household")

class HouseholdMember(Base):
    __tablename__ = "household_members"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    household_id = Column(String(36), ForeignKey("households.id", ondelete="CASCADE"), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    relationship_to_head = Column(String(50), nullable=False)
    is_pwd = Column(Boolean, default=False, nullable=False)
    is_senior = Column(Boolean, default=False, nullable=False)

    household = relationship("Household", back_populates="members")

class AidProgram(Base):
    __tablename__ = "aid_programs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    program_name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    target_barangay = Column(String(100), nullable=True)  # Nullable for municipality-wide
    total_quota_slots = Column(Integer, nullable=False, default=100)
    budget_per_slot = Column(Float, nullable=False, default=0.0)
    status = Column(String(50), nullable=False, default="Draft")  # 'Draft', 'Active', 'Closed'
    created_at = Column(DateTime, default=utc_now, nullable=False)

    rules = relationship("ProgramRule", back_populates="program", uselist=False, cascade="all, delete-orphan")
    allocations = relationship("Allocation", back_populates="program", cascade="all, delete-orphan")

class ProgramRule(Base):
    __tablename__ = "program_rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    program_id = Column(String(36), ForeignKey("aid_programs.id", ondelete="CASCADE"), unique=True, nullable=False)
    income_ceiling = Column(Float, nullable=False, default=15000.0)
    weight_income = Column(Float, default=0.35, nullable=False)
    weight_dependency = Column(Float, default=0.25, nullable=False)
    weight_calamity = Column(Float, default=0.20, nullable=False)
    weight_housing = Column(Float, default=0.20, nullable=False)
    cooldown_days = Column(Integer, default=14, nullable=False)

    program = relationship("AidProgram", back_populates="rules")

class Allocation(Base):
    __tablename__ = "allocations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    program_id = Column(String(36), ForeignKey("aid_programs.id", ondelete="CASCADE"), nullable=False)
    household_id = Column(String(36), ForeignKey("households.id"), nullable=False)
    vulnerability_score = Column(Float, nullable=False, default=0.0)
    score_breakdown = Column(JSON, nullable=True)
    rank = Column(Integer, nullable=False, default=-1)
    status = Column(String(100), nullable=False, default="Pending")  # 'Approved', 'Waitlisted', 'Disqualified'
    claim_qr_hash = Column(String(64), unique=True, index=True, nullable=True)
    allocated_at = Column(DateTime, default=utc_now, nullable=False)

    program = relationship("AidProgram", back_populates="allocations")
    household = relationship("Household", back_populates="allocations")
    disbursement = relationship("Disbursement", back_populates="allocation", uselist=False, cascade="all, delete-orphan")

class Disbursement(Base):
    __tablename__ = "disbursements"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    allocation_id = Column(String(36), ForeignKey("allocations.id", ondelete="CASCADE"), unique=True, nullable=False)
    verified_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    notes = Column(Text, nullable=True)
    signature_data = Column(Text, nullable=True)  # Base64 data URL of digital signature
    disbursed_at = Column(DateTime, default=utc_now, nullable=False)

    allocation = relationship("Allocation", back_populates="disbursement")
    verified_by = relationship("User", back_populates="disbursements")

class Announcement(Base):
    __tablename__ = "announcements"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)  # 'Relief Distribution', 'Scholarship / Education', 'Disaster Alert', 'General Notice'
    target_barangay = Column(String(100), nullable=True)  # Null or "All" for municipal-wide
    target_status = Column(String(50), nullable=True, default="All")  # 'All', 'Approved', 'Waitlisted'
    message = Column(Text, nullable=False)
    sms_dispatched = Column(Boolean, default=False, nullable=False)
    recipients_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    username = Column(String(100), nullable=False, default="SYSTEM")
    action = Column(String(100), nullable=False)  # e.g. 'UPDATE_MCDA_WEIGHTS', 'DISBURSE_PACKAGE'
    target_entity = Column(String(100), nullable=False)  # e.g. 'AidProgram', 'Household'
    target_id = Column(String(100), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

