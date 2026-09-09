import hashlib
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Tuple
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from models import Household, AidProgram, ProgramRule, Allocation, Disbursement

class MCDAEngine:
    def __init__(self, db: Session, secret_salt: str = "SMARTAID_SECURE_SALT_2026"):
        self.db = db
        self.salt = secret_salt

    def generate_claim_hash(self, program_id: str, household_id: str, ref_number: str) -> str:
        payload = f"{program_id}:{household_id}:{ref_number}:{self.salt}:{datetime.now(timezone.utc).isoformat()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def check_cooldown(self, household: Household, cooldown_days: int) -> Tuple[bool, str]:
        """
        Deduplication and Cooldown Filter:
        Checks if the household or another household with the same phone/head name
        received a disbursement within cooldown_days.
        """
        if cooldown_days <= 0:
            return False, ""

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=cooldown_days)

        # 1. Direct previous disbursements for this household
        past_disbursement = (
            self.db.query(Disbursement)
            .join(Allocation, Disbursement.allocation_id == Allocation.id)
            .filter(
                Allocation.household_id == household.id,
                Disbursement.disbursed_at >= cutoff_date
            )
            .first()
        )
        if past_disbursement:
            return True, f"Household received disbursement on {past_disbursement.disbursed_at.strftime('%Y-%m-%d')} (within {cooldown_days} days cooldown)"

        # 2. Duplicate check by phone number
        phone_disbursement = (
            self.db.query(Disbursement)
            .join(Allocation, Disbursement.allocation_id == Allocation.id)
            .join(Household, Allocation.household_id == Household.id)
            .filter(
                Household.contact_number == household.contact_number,
                Household.id != household.id,
                Disbursement.disbursed_at >= cutoff_date
            )
            .first()
        )
        if phone_disbursement:
            return True, f"Contact number {household.contact_number} already claimed assistance within {cooldown_days} days cooldown"

        return False, ""

    def evaluate_program(self, program_id: str) -> Dict[str, Any]:
        """
        Executes the full MCDA scoring and constrained allocation pipeline.
        Saves allocations to the database and returns summary statistics.
        """
        program = self.db.query(AidProgram).filter(AidProgram.id == program_id).first()
        if not program:
            raise ValueError(f"AidProgram with ID {program_id} does not exist.")

        rules = program.rules
        if not rules:
            # Fallback default rules if not defined
            rules = ProgramRule(
                program_id=program.id,
                income_ceiling=15000.0,
                weight_income=0.35,
                weight_dependency=0.25,
                weight_calamity=0.20,
                weight_housing=0.20,
                cooldown_days=14
            )
            self.db.add(rules)
            self.db.commit()
            self.db.refresh(rules)

        # Normalize weights to ensure sum = 1.0
        total_weight = (
            rules.weight_income +
            rules.weight_dependency +
            rules.weight_calamity +
            rules.weight_housing
        )
        if total_weight <= 0:
            total_weight = 1.0
        w_income = rules.weight_income / total_weight
        w_dep = rules.weight_dependency / total_weight
        w_calamity = rules.weight_calamity / total_weight
        w_housing = rules.weight_housing / total_weight

        # Fetch applicant households
        # If program has target_barangay, filter by it; otherwise all
        household_query = self.db.query(Household)
        if program.target_barangay and program.target_barangay.strip() and program.target_barangay != "All":
            household_query = household_query.filter(Household.barangay == program.target_barangay)

        households = household_query.all()
        if not households:
            return {
                "total_applicants": 0,
                "approved": 0,
                "waitlisted": 0,
                "disqualified": 0,
                "quota_slots": program.total_quota_slots,
                "records": []
            }

        # Clear previous allocations for this program that haven't been disbursed yet
        # If already disbursed, keep record intact
        existing_allocations = self.db.query(Allocation).filter(Allocation.program_id == program_id).all()
        existing_map = {alloc.household_id: alloc for alloc in existing_allocations}

        evaluated_records = []

        for hh in households:
            # Check existing disbursement
            existing_alloc = existing_map.get(hh.id)
            if existing_alloc and existing_alloc.disbursement:
                # Retain disbursed record as Approved
                evaluated_records.append({
                    "household": hh,
                    "existing_alloc": existing_alloc,
                    "is_already_disbursed": True,
                    "vpi": existing_alloc.vulnerability_score,
                    "breakdown": existing_alloc.score_breakdown,
                    "eligible": True,
                    "disqualified_reason": None,
                    "income": hh.monthly_income,
                    "created_at": hh.created_at
                })
                continue

            # 1. Cooldown & Deduplication check
            in_cooldown, cooldown_reason = self.check_cooldown(hh, rules.cooldown_days)
            if in_cooldown:
                evaluated_records.append({
                    "household": hh,
                    "existing_alloc": existing_alloc,
                    "is_already_disbursed": False,
                    "vpi": 0.0,
                    "breakdown": {
                        "vpi": 0.0,
                        "eligibility": {
                            "is_eligible": False,
                            "income_check_passed": hh.monthly_income <= rules.income_ceiling,
                            "cooldown_check_passed": False,
                            "disqualification_reason": cooldown_reason
                        },
                        "allocation_decision": {
                            "rank": -1,
                            "status": "Disqualified",
                            "reason": cooldown_reason
                        }
                    },
                    "eligible": False,
                    "disqualified_reason": cooldown_reason,
                    "income": hh.monthly_income,
                    "created_at": hh.created_at
                })
                continue

            # 2. Hard Eligibility Screening: Income Ceiling Gate
            if hh.monthly_income > rules.income_ceiling:
                reason = f"Monthly income (₱{hh.monthly_income:,.2f}) exceeds program ceiling (₱{rules.income_ceiling:,.2f})"
                evaluated_records.append({
                    "household": hh,
                    "existing_alloc": existing_alloc,
                    "is_already_disbursed": False,
                    "vpi": 0.0,
                    "breakdown": {
                        "vpi": 0.0,
                        "eligibility": {
                            "is_eligible": False,
                            "income_check_passed": False,
                            "cooldown_check_passed": True,
                            "disqualification_reason": reason
                        },
                        "allocation_decision": {
                            "rank": -1,
                            "status": "Disqualified",
                            "reason": reason
                        }
                    },
                    "eligible": False,
                    "disqualified_reason": reason,
                    "income": hh.monthly_income,
                    "created_at": hh.created_at
                })
                continue

            # 3. Factor Normalization (Vectors in [0.0, 1.0])
            # S_income = 1.0 - (min(income, ceiling) / ceiling)
            s_income = 1.0 - (min(hh.monthly_income, rules.income_ceiling) / rules.income_ceiling)
            s_income = float(np.clip(s_income, 0.0, 1.0))

            # S_dependency = min((pwd * 1.5 + elderly) / max(members, 1), 1.0)
            effective_dependents = (hh.pwd_count * 1.5) + (hh.elderly_count * 1.0)
            s_dependency = min(effective_dependents / max(hh.member_count, 1), 1.0)
            s_dependency = float(np.clip(s_dependency, 0.0, 1.0))

            # S_housing = 1.0 if informal_settler else 0.0
            s_housing = 1.0 if hh.is_informal_settler else 0.0

            # S_calamity = 1.0 if calamity_damage else 0.0
            s_calamity = 1.0 if hh.has_calamity_damage else 0.0

            # 4. Composite Vulnerability Priority Index (VPI)
            c_income = s_income * w_income
            c_dep = s_dependency * w_dep
            c_housing = s_housing * w_housing
            c_calamity = s_calamity * w_calamity

            vpi = float(c_income + c_dep + c_housing + c_calamity)
            vpi = round(vpi, 4)

            # Detailed XAI transparent breakdown
            total_vpi_safe = vpi if vpi > 0 else 1e-6
            breakdown = {
                "vpi": vpi,
                "weights": {
                    "income": round(w_income, 4),
                    "dependency": round(w_dep, 4),
                    "housing": round(w_housing, 4),
                    "calamity": round(w_calamity, 4)
                },
                "factors": {
                    "income": {
                        "name": "Income Factor",
                        "raw_value": hh.monthly_income,
                        "ceiling": rules.income_ceiling,
                        "normalized_score": round(s_income, 4),
                        "weight": round(w_income, 4),
                        "weighted_contribution": round(c_income, 4),
                        "percentage_of_vpi": round((c_income / total_vpi_safe) * 100, 1),
                        "description": f"₱{hh.monthly_income:,.2f} / ₱{rules.income_ceiling:,.2f} ceiling"
                    },
                    "dependency": {
                        "name": "Dependency Ratio",
                        "raw_pwd": hh.pwd_count,
                        "raw_elderly": hh.elderly_count,
                        "raw_members": hh.member_count,
                        "effective_dependents": effective_dependents,
                        "normalized_score": round(s_dependency, 4),
                        "weight": round(w_dep, 4),
                        "weighted_contribution": round(c_dep, 4),
                        "percentage_of_vpi": round((c_dep / total_vpi_safe) * 100, 1),
                        "description": f"{hh.pwd_count} PWD, {hh.elderly_count} Elderly out of {hh.member_count} members"
                    },
                    "housing": {
                        "name": "Housing Vulnerability",
                        "is_informal_settler": hh.is_informal_settler,
                        "normalized_score": round(s_housing, 4),
                        "weight": round(w_housing, 4),
                        "weighted_contribution": round(c_housing, 4),
                        "percentage_of_vpi": round((c_housing / total_vpi_safe) * 100, 1),
                        "description": "Informal Settler" if hh.is_informal_settler else "Formal Residence"
                    },
                    "calamity": {
                        "name": "Calamity & Disaster Impact",
                        "has_calamity_damage": hh.has_calamity_damage,
                        "normalized_score": round(s_calamity, 4),
                        "weight": round(w_calamity, 4),
                        "weighted_contribution": round(c_calamity, 4),
                        "percentage_of_vpi": round((c_calamity / total_vpi_safe) * 100, 1),
                        "description": "Severe Calamity Damage" if hh.has_calamity_damage else "No Disaster Damage Reported"
                    }
                },
                "eligibility": {
                    "is_eligible": True,
                    "income_check_passed": True,
                    "cooldown_check_passed": True,
                    "disqualification_reason": None
                }
            }

            evaluated_records.append({
                "household": hh,
                "existing_alloc": existing_alloc,
                "is_already_disbursed": False,
                "vpi": vpi,
                "breakdown": breakdown,
                "eligible": True,
                "disqualified_reason": None,
                "income": hh.monthly_income,
                "created_at": hh.created_at
            })

        # Separate eligible vs disqualified
        eligible_records = [r for r in evaluated_records if r["eligible"]]
        disqualified_records = [r for r in evaluated_records if not r["eligible"]]

        # 5. Constrained Quota Allocation using Pandas rank sorting
        if eligible_records:
            df = pd.DataFrame([
                {
                    "idx": i,
                    "vpi": r["vpi"],
                    "income": r["income"],
                    "created_at": r["created_at"],
                    "is_already_disbursed": r["is_already_disbursed"]
                }
                for i, r in enumerate(eligible_records)
            ])

            # Sort: Primary: vpi (Descending), Secondary: income (Ascending), Tertiary: created_at (Ascending)
            df.sort_values(
                by=["vpi", "income", "created_at"],
                ascending=[False, True, True],
                inplace=True
            )
            df.reset_index(drop=True, inplace=True)
            df["rank"] = df.index + 1

            total_quota = program.total_quota_slots

            for _, row in df.iterrows():
                rec = eligible_records[int(row["idx"])]
                assigned_rank = int(row["rank"])
                rec["rank"] = assigned_rank

                if assigned_rank <= total_quota:
                    rec["status"] = "Approved"
                    # Generate unique claim QR hash if not already set
                    if not rec.get("claim_qr_hash"):
                        if rec["existing_alloc"] and rec["existing_alloc"].claim_qr_hash:
                            rec["claim_qr_hash"] = rec["existing_alloc"].claim_qr_hash
                        else:
                            rec["claim_qr_hash"] = self.generate_claim_hash(
                                program.id, rec["household"].id, rec["household"].reference_number
                            )
                    decision_reason = f"Rank {assigned_rank} within program quota of {total_quota} slots."
                else:
                    rec["status"] = "Waitlisted"
                    rec["claim_qr_hash"] = None
                    decision_reason = f"Rank {assigned_rank} exceeds program quota limit ({total_quota} slots). Placed on priority waitlist."

                rec["breakdown"]["allocation_decision"] = {
                    "rank": assigned_rank,
                    "quota_cutoff": total_quota,
                    "status": rec["status"],
                    "reason": decision_reason
                }

        # For disqualified records
        for r in disqualified_records:
            r["rank"] = -1
            r["status"] = "Disqualified"
            r["claim_qr_hash"] = None

        # 6. Synchronize into database
        all_processed = eligible_records + disqualified_records
        approved_count = 0
        waitlisted_count = 0
        disqualified_count = 0

        for r in all_processed:
            hh = r["household"]
            existing_alloc = r["existing_alloc"]

            if r["status"] == "Approved":
                approved_count += 1
            elif r["status"] == "Waitlisted":
                waitlisted_count += 1
            else:
                disqualified_count += 1

            if existing_alloc:
                # Do not mutate if already disbursed
                if not r.get("is_already_disbursed"):
                    existing_alloc.vulnerability_score = r["vpi"]
                    existing_alloc.score_breakdown = r["breakdown"]
                    existing_alloc.rank = r["rank"]
                    existing_alloc.status = r["status"]
                    existing_alloc.claim_qr_hash = r["claim_qr_hash"]
                    existing_alloc.allocated_at = datetime.now(timezone.utc)
            else:
                new_alloc = Allocation(
                    program_id=program.id,
                    household_id=hh.id,
                    vulnerability_score=r["vpi"],
                    score_breakdown=r["breakdown"],
                    rank=r["rank"],
                    status=r["status"],
                    claim_qr_hash=r["claim_qr_hash"],
                    allocated_at=datetime.now(timezone.utc)
                )
                self.db.add(new_alloc)

        self.db.commit()

        return {
            "program_id": program.id,
            "program_name": program.program_name,
            "quota_slots": program.total_quota_slots,
            "total_evaluated": len(all_processed),
            "approved": approved_count,
            "waitlisted": waitlisted_count,
            "disqualified": disqualified_count,
            "rules_applied": {
                "income_ceiling": rules.income_ceiling,
                "weights": {
                    "income": round(w_income, 4),
                    "dependency": round(w_dep, 4),
                    "housing": round(w_housing, 4),
                    "calamity": round(w_calamity, 4)
                }
            }
        }
