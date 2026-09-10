"""
SmartAid Decision Intelligence & AI Engine
Provides:
1. SmartAidAICopilot: Bilingual (EN / CEB) context-aware assistant with database grounding.
2. generate_xai_narrative: Human-centered Explainable AI justifications.
3. evaluate_intake_risk: Real-time fraud and anomaly detection.
4. simulate_policy_scenario: Disaster shock simulation and MCDA criteria balancing.
"""

import re
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
import models

MARAMAG_BARANGAYS = [
    "North Poblacion", "South Poblacion", "Base Camp", "Dologon", "Musuan",
    "Camp 1", "Panadtalan", "Dagumbaan", "Kuya", "San Miguel",
    "San Roque", "Colambugon", "Anahawon", "Bayabason", "Tubigon",
    "La Asuncion", "Dibulang", "Kisanayan", "Danggawan", "Panalsalan"
]

SCENARIOS = {
    "typhoon_flood": {
        "title": "Typhoon & Flash Flood Emergency Shock",
        "description": "Drastically elevates calamity impact weight to prioritize riverside and flood-basin communities.",
        "weights": {"income": 0.25, "dependency": 0.15, "calamity": 0.45, "housing": 0.15},
        "target_priority": "High Calamity Severity Barangays (Panadtalan, Base Camp, Kuya)"
    },
    "vulnerable_sectors": {
        "title": "Senior Citizens & PWD Caregiver Focus",
        "description": "Maximizes demographic dependency weight to favor households supporting bedridden, elderly, and disabled members.",
        "weights": {"income": 0.25, "dependency": 0.45, "calamity": 0.15, "housing": 0.15},
        "target_priority": "Households with multi-generational dependents"
    },
    "extreme_poverty": {
        "title": "Subsistence & Extreme Poverty Priority",
        "description": "Heavily weights household income deficit to ensure the most economically destitute receive relief packages first.",
        "weights": {"income": 0.50, "dependency": 0.20, "calamity": 0.15, "housing": 0.15},
        "target_priority": "Zero-income and minimum-wage casual workers"
    },
    "balanced_equilibrium": {
        "title": "MCDA Balanced Equilibrium (Default)",
        "description": "Standard balanced multicriteria weights optimized for fair distribution across all 20 barangays.",
        "weights": {"income": 0.35, "dependency": 0.25, "calamity": 0.20, "housing": 0.20},
        "target_priority": "Municipality-wide equitable distribution"
    }
}

# =========================================================================
# 1. GENERATIVE XAI NARRATIVE GENERATOR
# =========================================================================

def generate_xai_narrative(allocation: models.Allocation, household: models.Household, rules: Optional[models.ProgramRule] = None, lang: str = "en") -> Dict[str, str]:
    """
    Generates human-readable, plain-language AI justification summaries
    for both approved and waitlisted/disqualified beneficiaries.
    """
    is_ceb = (lang == "ceb")
    bd = allocation.score_breakdown or {}
    income = household.monthly_income
    vpi = allocation.vulnerability_score
    status = allocation.status
    rank = allocation.rank
    
    # Check primary contributor
    factors = [
        ("income", bd.get("contrib_income", 0.0), "Low Household Income", "Ubos nga Kita sa Panimalay"),
        ("dependency", bd.get("contrib_dependency", 0.0), "High Dependent Burden (PWD / Seniors)", "Daghan Nagsalig nga PWD o Senior"),
        ("calamity", bd.get("contrib_calamity", 0.0), "Severe Disaster Damage", "Kadaot sa Bagyo o Kalamidad"),
        ("housing", bd.get("contrib_housing", 0.0), "Informal Settlement Tenure", "Walay Kaugalingong Yuta / Informal Settler")
    ]
    factors.sort(key=lambda x: x[1], reverse=True)
    primary_factor_en = factors[0][2]
    primary_factor_ceb = factors[0][3]

    if "Disqualified" in status:
        if income > (rules.income_ceiling if rules else 15000.0):
            en = f"Ineligible for emergency relief package. The declared monthly income of ₱{income:,.2f} exceeds the official municipal poverty threshold ceiling of ₱15,000.00."
            ceb = f"Wala makapasar sa ayuda. Ang gideklarar nga kita nga ₱{income:,.2f} kada bulan milapas sa gitakda nga limitasyon sa kakabus sa munisipyo nga ₱15,000.00."
        else:
            en = f"Application screened out under municipal relief program criteria rules: {status}."
            ceb = f"Wala makapasar sumala sa mga sumbanan sa programa sa hinabang: {status}."
    elif status == "Approved":
        en = (
            f"Officially APPROVED with Priority Rank #{rank} (VPI Score: {vpi:.4f}). "
            f"Primary justification: {primary_factor_en}. "
            f"With a household income of ₱{income:,.2f}, {household.pwd_count} PWD member(s), and {household.elderly_count} senior(s), "
            f"this family ranked within the authorized relief quota slots for Barangay {household.barangay}."
        )
        ceb = (
            f"Opisyal nga NAAPROBAHAN sa Ranggo #{rank} (Grado sa Kalisud VPI: {vpi:.4f}). "
            f"Pangulong rason: {primary_factor_ceb}. "
            f"Tungod sa kita nga ₱{income:,.2f}, {household.pwd_count} ka PWD, ug {household.elderly_count} ka senior citizen, "
            f"ang pamilya nasulod sa gitagana nga quota sa hinabang alang sa Barangay {household.barangay}."
        )
    else:  # Waitlisted
        en = (
            f"Placed on PRIORITY WAITLIST at Rank #{rank} (VPI Score: {vpi:.4f}). "
            f"Eligible under all criteria screening gates. "
            f"The application remains active and will be automatically promoted as additional quota batches or unclaimed slots become available."
        )
        ceb = (
            f"Nalakip sa PRIORITY WAITLIST sa Ranggo #{rank} (Grado sa Kalisud VPI: {vpi:.4f}). "
            f"Nakapasar sa tanang sukdanan sa kalisud. "
            f"Pabiling aktibo ang aplikasyon ug awtomatikong masulod sa hinabang kon adunay dugang pundo o quota nga ablihan sa munisipyo."
        )

    return {"en": en, "ceb": ceb}

# =========================================================================
# 2. AI INTAKE ANOMALY & FRAUD DETECTION ENGINE
# =========================================================================

def evaluate_intake_risk(db: Session, household: models.Household) -> Dict[str, Any]:
    """
    Evaluates an applicant household for duplicate contacts, unnatural poverty declarations,
    and geographic address clusters.
    Returns: { risk_score: int, risk_level: 'LOW'|'MEDIUM'|'HIGH', risk_flags: List[str] }
    """
    flags = []
    risk_points = 0

    # 1. Phone number recycling check
    phone_digits = re.sub(r"\D", "", household.contact_number or "")
    if len(phone_digits) >= 7:
        last_digits = phone_digits[-7:]
        all_other_hhs = db.query(models.Household).filter(models.Household.id != household.id).all()
        dup_contacts = [
            h for h in all_other_hhs
            if re.sub(r"\D", "", h.contact_number or "").endswith(last_digits)
        ]
        if dup_contacts:
            other_names = ", ".join([h.head_name for h in dup_contacts[:2]])
            flags.append(f"Phone number recycled across multiple household heads ({other_names})")
            risk_points += 40

    # 2. Suspicious zero-income with large family size and non-calamity status
    if household.monthly_income == 0.0 and household.member_count >= 5 and not household.has_calamity_damage:
        flags.append(f"Declared ₱0.00 income with {household.member_count} dependents without disaster loss (Requires social worker home visit)")
        risk_points += 25

    # 3. Address clustering / duplicate entry check
    addr_clean = household.street_address.strip().lower()
    if len(addr_clean) > 8:
        same_address = db.query(models.Household).filter(
            models.Household.barangay == household.barangay,
            func.lower(models.Household.street_address) == addr_clean,
            models.Household.id != household.id
        ).count()
        if same_address >= 2:
            flags.append(f"High address density: {same_address} other applications share exact address in {household.barangay}")
            risk_points += 30

    # 4. Income borderline check (within ₱500 of ₱15,000 threshold)
    if 14500.0 <= household.monthly_income <= 15000.0:
        flags.append(f"Income (₱{household.monthly_income:,.2f}) sits within 3% of poverty ceiling threshold")
        risk_points += 10

    # Determine risk level
    if risk_points >= 40:
        level = "HIGH"
    elif risk_points >= 20:
        level = "MEDIUM"
    else:
        level = "LOW"

    return {
        "risk_score": min(100, risk_points),
        "risk_level": level,
        "risk_flags": flags if flags else ["No anomalies detected - socioeconomic data consistent"]
    }

# =========================================================================
# 3. AI POLICY SIMULATOR & SCENARIO LAB
# =========================================================================

def simulate_policy_scenario(db: Session, program_id: str, scenario_key: str, custom_weights: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
    """
    Simulates what-if disaster policy scenarios by re-scoring all allocations in-memory
    without modifying the database, reporting rank shifts and barangay distribution impact.
    """
    if scenario_key in SCENARIOS:
        scenario = SCENARIOS[scenario_key]
        weights = scenario["weights"]
        scenario_title = scenario["title"]
        scenario_desc = scenario["description"]
    elif custom_weights:
        weights = custom_weights
        scenario_title = "Custom Simulated Weights"
        scenario_desc = f"Simulated distribution using: {weights}"
    else:
        scenario = SCENARIOS["balanced_equilibrium"]
        weights = scenario["weights"]
        scenario_title = scenario["title"]
        scenario_desc = scenario["description"]

    # Fetch active program allocations
    program = db.query(models.AidProgram).filter(models.AidProgram.id == program_id).first()
    if not program:
        raise ValueError(f"Program {program_id} not found.")

    quota = program.total_quota_slots
    rules = program.rules
    income_ceiling = rules.income_ceiling if rules else 15000.0
    cooldown = rules.cooldown_days if rules else 14

    allocations = db.query(models.Allocation).filter(models.Allocation.program_id == program_id).all()
    if not allocations:
        return {"scenario": scenario_title, "results": [], "summary": "No allocations to simulate."}

    # In-memory re-computation
    simulated_roster = []
    for a in allocations:
        h = a.household
        # Hard screening
        if h.monthly_income > income_ceiling:
            sim_score = 0.0
            is_disqualified = True
        else:
            is_disqualified = False
            s_inc = max(0.0, 1.0 - (min(h.monthly_income, income_ceiling) / income_ceiling))
            s_dep = min(1.0, (h.pwd_count * 1.5 + h.elderly_count) / max(h.member_count, 1))
            s_cal = 1.0 if h.has_calamity_damage else 0.0
            s_house = 1.0 if h.is_informal_settler else 0.0

            sim_score = (
                s_inc * weights.get("income", 0.35) +
                s_dep * weights.get("dependency", 0.25) +
                s_cal * weights.get("calamity", 0.20) +
                s_house * weights.get("housing", 0.20)
            )

        simulated_roster.append({
            "allocation_id": a.id,
            "household_id": h.id,
            "head_name": h.head_name,
            "barangay": h.barangay,
            "monthly_income": h.monthly_income,
            "member_count": h.member_count,
            "pwd_count": h.pwd_count,
            "elderly_count": h.elderly_count,
            "is_informal_settler": h.is_informal_settler,
            "has_calamity_damage": h.has_calamity_damage,
            "old_rank": a.rank,
            "old_status": a.status,
            "old_score": a.vulnerability_score,
            "sim_score": round(sim_score, 4),
            "is_disqualified": is_disqualified
        })

    # Sort eligible by sim_score desc, tie-breaker: lower income
    eligible = [x for x in simulated_roster if not x["is_disqualified"]]
    disqualified = [x for x in simulated_roster if x["is_disqualified"]]

    eligible.sort(key=lambda x: (-x["sim_score"], x["monthly_income"]))

    barangay_quota_dist = {}
    rank_changes = []

    for idx, item in enumerate(eligible):
        new_rank = idx + 1
        new_status = "Approved" if new_rank <= quota else "Waitlisted"
        item["new_rank"] = new_rank
        item["new_status"] = new_status
        rank_delta = (item["old_rank"] - new_rank) if item["old_rank"] > 0 else 0
        item["rank_delta"] = rank_delta

        if new_status == "Approved":
            b = item["barangay"]
            barangay_quota_dist[b] = barangay_quota_dist.get(b, 0) + 1

        if item["old_status"] != new_status or abs(rank_delta) >= 2:
            rank_changes.append({
                "head_name": item["head_name"],
                "barangay": item["barangay"],
                "old_rank": item["old_rank"],
                "new_rank": new_rank,
                "old_status": item["old_status"],
                "new_status": new_status,
                "rank_delta": rank_delta
            })

    for item in disqualified:
        item["new_rank"] = -1
        item["new_status"] = "Disqualified"
        item["rank_delta"] = 0

    return {
        "scenario_key": scenario_key,
        "scenario_title": scenario_title,
        "scenario_description": scenario_desc,
        "applied_weights": weights,
        "total_evaluated": len(simulated_roster),
        "total_approved": min(len(eligible), quota),
        "total_waitlisted": max(0, len(eligible) - quota),
        "total_disqualified": len(disqualified),
        "barangay_distribution": barangay_quota_dist,
        "significant_rank_shifts": rank_changes[:15]
    }

# =========================================================================
# 4. SMARTAID AI BILINGUAL COPILOT CONVERSATIONAL AGENT
# =========================================================================

class SmartAidAICopilot:
    """
    Context-aware bilingual conversational agent capable of querying live applicant status,
    answering policy questions, and guiding beneficiaries and municipal officers.
    """

    @staticmethod
    def chat(user_message: str, db: Session, language: str = "en") -> Dict[str, Any]:
        msg_lower = user_message.lower().strip()
        is_ceb = (language == "ceb") or any(w in msg_lower for w in ["unsa", "pila", "unsaon", "asa", "ngano", "tabang", "ayuda", "hinabang"])

        # 1. Reference number lookup intent (e.g. APP-2026-00101)
        ref_match = re.search(r"APP-\d{4}-\d+", user_message, re.IGNORECASE)
        if ref_match:
            ref_num = ref_match.group(0).upper()
            return SmartAidAICopilot._handle_reference_lookup(ref_num, db, is_ceb)

        # 2. Check general status query without ref
        if any(w in msg_lower for w in ["check status", "my status", "track", "kumusta akong status", "status sa akong"]):
            if is_ceb:
                return {
                    "reply": "Palihug ihatag ang imong **Application Reference Number** (pananglitan: `APP-2026-00101`) aron masusi nako ang imong opisyal nga estado sa SmartAid registry.",
                    "suggestions": ["APP-2026-00101", "APP-2026-00102", "Pila ang income ceiling?"]
                }
            return {
                "reply": "Please provide your **Application Reference Number** (e.g., `APP-2026-00101`) so I can retrieve your real-time MCDA score, priority ranking, and relief voucher status.",
                "suggestions": ["APP-2026-00101", "APP-2026-00102", "How are scores computed?"]
            }

        # 3. Income ceiling / eligibility questions
        if any(w in msg_lower for w in ["income", "ceiling", "threshold", "limit", "pila ang kita", "pobre", "poverty"]):
            if is_ceb:
                return {
                    "reply": "Ang gitakda nga **Income Ceiling** sa LGU Maramag alang sa emergency assistance mao ang **₱15,000.00 matag bulan**. Ang mga panimalay nga mokita og sobra sa ₱15,000 awtomatikong ma-disqualify aron masiguro nga ang labing kabus ang unahon.",
                    "suggestions": ["Unsaon pag-aplay?", "Unsa ang mga criteria?", "Susiha akong reference"]
                }
            return {
                "reply": "The official **Income Ceiling** for Maramag social welfare assistance is strictly **₱15,000.00/month**. Households earning above ₱15,000 are automatically screened out via hard constraint gates to guarantee relief goods go to the most vulnerable.",
                "suggestions": ["How to apply?", "MCDA Criteria Weights", "Check status for APP-2026-00101"]
            }

        # 4. How to apply questions
        if any(w in msg_lower for w in ["how to apply", "apply", "register", "unsaon pag-aplay", "unsaon pag apil", "requirements"]):
            if is_ceb:
                return {
                    "reply": "Sayon ra ang pag-aplay! Adto sa **[Apply for Aid](/apply)** nga panid ug sunda kining 3 ka lakang:\n1. **Punoan sa Panimalay**: Isulat ang ngalan, selpon, ug barangay sa Maramag.\n2. **Kahimtang sa Panginabuhi**: Ibutang ang binuwan nga kita ug i-tsek kon naapektuhan sa bagyo o nagpuyo sa informal settlement.\n3. **Mga Nagsalig**: Ilista ang mga sakop sa pamilya ilabina ang mga PWD ug Senior Citizens.",
                    "suggestions": ["Adto sa /apply", "Pila ang income ceiling?", "Check status"]
                }
            return {
                "reply": "Applying is fast and straightforward! Visit **[Apply for Aid](/apply)** and complete 3 easy steps:\n1. **Household Head**: Enter full name, active contact number, and your Maramag barangay.\n2. **Vulnerability Factors**: State combined monthly income, informal settlement status, and calamity damage.\n3. **Dependents**: Register family members (tagging PWD or Senior Citizen dependents increases your priority score).",
                "suggestions": ["Go to /apply", "Income Ceiling Limit", "Criteria Breakdown"]
            }

        # 5. MCDA Criteria & weights explanation
        if any(w in msg_lower for w in ["criteria", "weights", "mcda", "vpi", "algorithm", "score", "puntos", "sukdanan"]):
            if is_ceb:
                return {
                    "reply": "Ang SmartAid naggamit og **Multi-Criteria Decision Analysis (MCDA)** nga sistema nga walay pabor-pabor:\n- **Kita sa Panimalay (35%)**: Kon mas ubos ang kita, mas taas ang puntos.\n- **Mga Nagsalig / Dependents (25%)**: Dugang puntos alang sa PWD (1.5x) ug Senior Citizens (1.0x).\n- **Kadaot sa Kalamidad (20%)**: Alang sa mga balay nga naguba sa bagyo o baha.\n- **Puy-anan / Informal Settler (20%)**: Alang sa mga walay kaugalingong yuta.",
                    "suggestions": ["Pila ang quota slots?", "Unsaon pag-aplay?", "Check status"]
                }
            return {
                "reply": "SmartAid computes a deterministic **Vulnerability Priority Index (VPI)** to eliminate human bias:\n- **Income Vulnerability (35%)**: Inversely proportional; lowest earners receive the highest score.\n- **Demographic Dependency (25%)**: Ratio of PWDs (1.5x weight) and Senior Citizens (1.0x weight) to total family size.\n- **Disaster Impact (20%)**: Validated flood or typhoon destruction.\n- **Housing Tenure (20%)**: Informal settlements and temporary dwellings.",
                "suggestions": ["How to apply?", "Poverty Threshold", "Check APP-2026-00101"]
            }

        # 6. Barangays coverage question
        if any(w in msg_lower for w in ["barangay", "maramag", "coverage", "lokasyon", "lugar"]):
            brgy_str = ", ".join(MARAMAG_BARANGAYS[:10]) + ", ug uban pa." if is_ceb else ", ".join(MARAMAG_BARANGAYS[:10]) + ", etc."
            if is_ceb:
                return {
                    "reply": f"Ang SmartAid naglangkob sa tanang **20 ka mga opisyal nga barangay sa Maramag, Bukidnon**, lakip ang: {brgy_str}\n\nAng matag barangay aduna usab kaugalingong desk officer account alang sa lokal nga pagsusi.",
                    "suggestions": ["Unsaon pag-aplay?", "Check status", "Pila ang income ceiling?"]
                }
            return {
                "reply": f"SmartAid covers all **20 official barangays of the Municipality of Maramag, Bukidnon**, including: {brgy_str}\n\nEach barangay operates its own localized workstation desk to monitor resident allocations.",
                "suggestions": ["Check APP-2026-00101", "How are scores computed?", "Go to /apply"]
            }

        # Default helpful fallback
        if is_ceb:
            return {
                "reply": "Kumusta! Ako ang **SmartAid AI Assistant** sa LGU Maramag MSWDO. Makatabang ko nimo sa pagsusi sa imong reference status (`APP-2026-XXXXX`), pagpatin-aw sa criteria ug kita limitasyon, o giya sa pagparehistro sa hinabang.",
                "suggestions": ["Susiha akong Reference Status", "Pila ang Income Ceiling?", "Unsaon pag-aplay ug hinabang?"]
            }
        return {
            "reply": "Hello! I am your **SmartAid AI Assistant** for LGU Maramag MSWDO. I can look up your application status (e.g. `APP-2026-00101`), explain your MCDA vulnerability rank, clarify income thresholds, and guide you through emergency relief intake.",
            "suggestions": ["Check Reference Status", "What is the Income Ceiling?", "How are MCDA scores calculated?"]
        }

    @staticmethod
    def _handle_reference_lookup(ref_num: str, db: Session, is_ceb: bool) -> Dict[str, Any]:
        household = db.query(models.Household).filter(func.upper(models.Household.reference_number) == ref_num).first()
        if not household:
            if is_ceb:
                return {
                    "reply": f"Pasayloa, wala nako nakit-an ang reference number nga **{ref_num}** sa registry sa Maramag. Palihug susiha kon sakto ba ang letra ug numero, o magparehistro sa [Apply for Aid](/apply).",
                    "suggestions": ["Sulayi ang APP-2026-00101", "Unsaon pag-aplay?"]
                }
            return {
                "reply": f"I could not locate reference number **{ref_num}** in the Maramag SmartAid database. Please double check the code from your intake stub, or register a new household at [Apply for Aid](/apply).",
                "suggestions": ["Try APP-2026-00101", "How to apply?"]
            }

        alloc = db.query(models.Allocation).filter(models.Allocation.household_id == household.id).first()
        rules = alloc.program.rules if (alloc and alloc.program) else None
        narrative = generate_xai_narrative(alloc, household, rules, lang="ceb" if is_ceb else "en") if alloc else None

        status = alloc.status if alloc else "Under Review"
        rank_text = f"#{alloc.rank}" if (alloc and alloc.rank > 0) else "N/A"
        is_disb = bool(alloc and alloc.disbursement)

        if is_ceb:
            reply = (
                f"### Rekord sa Aplikasyon: **{household.reference_number}**\n"
                f"- **Punoan sa Panimalay**: {household.head_name}\n"
                f"- **Barangay**: {household.barangay} ({household.purok_zone})\n"
                f"- **Estado**: **{status.upper()}** (Ranggo: {rank_text})\n"
                f"- **Hinabang**: {'Nakuha Na (Claimed)' if is_disb else ('Andam nang Kuhaon (Ready to Claim)' if status == 'Approved' else 'Nakahulat')}\n\n"
                f"**Patin-aw sa AI**:\n{narrative['ceb'] if narrative else 'Giproseso pa ang ebalwasyon.'}"
            )
        else:
            reply = (
                f"### Application Record: **{household.reference_number}**\n"
                f"- **Beneficiary Head**: {household.head_name}\n"
                f"- **Barangay**: {household.barangay} ({household.purok_zone})\n"
                f"- **Status**: **{status.upper()}** (Priority Rank: {rank_text})\n"
                f"- **Disbursement**: {'Claimed & Disbursed' if is_disb else ('Ready to Claim via Digital QR' if status == 'Approved' else 'On Waitlist')}\n\n"
                f"**AI Decision Summary**:\n{narrative['en'] if narrative else 'Evaluation pending.'}"
            )

        return {
            "reply": reply,
            "household": {
                "reference_number": household.reference_number,
                "head_name": household.head_name,
                "status": status,
                "rank": alloc.rank if alloc else None,
                "claim_qr_hash": alloc.claim_qr_hash if alloc else None
            },
            "suggestions": [f"View Voucher for {household.reference_number}", "Pila ang income ceiling?", "Check another reference"]
        }
