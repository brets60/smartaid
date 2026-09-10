// SmartAid Public Beneficiary Intake Controller

let memberCount = 0;

document.addEventListener('DOMContentLoaded', () => {
    // Add 1 default dependent row
    addMemberRow();

    // Wire input listeners for real-time live estimator
    const form = document.getElementById('apply-form');
    if (form) {
        form.addEventListener('input', updateEstimator);
        form.addEventListener('change', updateEstimator);
    }
    updateEstimator();
});

function addMemberRow() {
    memberCount++;
    const container = document.getElementById('members-container');
    const rowId = `member-row-${memberCount}`;

    const div = document.createElement('div');
    div.id = rowId;
    div.className = 'p-4 rounded-xl border border-slate-200 bg-slate-50/70 space-y-3 animate-slide-up transition-all';
    div.innerHTML = `
        <div class="flex items-center justify-between pb-2 border-b border-slate-200/60">
            <span class="text-xs font-bold text-slate-700">Dependent Member #${container.children.length + 1}</span>
            <button type="button" onclick="removeMemberRow('${rowId}')" class="text-xs text-rose-500 hover:text-rose-700 font-medium flex items-center gap-1 transition-colors">
                <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
                <span>Remove</span>
            </button>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div>
                <label class="block text-[11px] font-semibold text-slate-600">First Name <span class="text-slate-400 font-normal">(Optional)</span></label>
                <input type="text" class="member-first-name mt-0.5 block w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all" placeholder="First name">
            </div>
            <div>
                <label class="block text-[11px] font-semibold text-slate-600">Last Name <span class="text-slate-400 font-normal">(Optional)</span></label>
                <input type="text" class="member-last-name mt-0.5 block w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all" placeholder="Last name">
            </div>
            <div>
                <label class="block text-[11px] font-semibold text-slate-600">Relationship to Head</label>
                <select class="member-rel mt-0.5 block w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all">
                    <option value="Spouse">Spouse</option>
                    <option value="Son">Son</option>
                    <option value="Daughter">Daughter</option>
                    <option value="Parent">Parent</option>
                    <option value="Grandchild">Grandchild</option>
                    <option value="Sibling">Sibling</option>
                    <option value="Relative">Other Relative</option>
                </select>
            </div>
        </div>

        <div class="flex items-center gap-6 pt-1">
            <label class="flex items-center gap-2 cursor-pointer text-xs text-slate-700">
                <input type="checkbox" class="member-pwd rounded text-indigo-600 focus:ring-indigo-500 border-slate-300" onchange="updateEstimator()">
                <span>Person with Disability (PWD)</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer text-xs text-slate-700">
                <input type="checkbox" class="member-senior rounded text-indigo-600 focus:ring-indigo-500 border-slate-300" onchange="updateEstimator()">
                <span>Senior Citizen (60+ yrs)</span>
            </label>
        </div>
    `;

    container.appendChild(div);
    lucide.createIcons();
    updateEstimator();
}

function removeMemberRow(rowId) {
    const row = document.getElementById(rowId);
    if (row) {
        row.style.opacity = '0';
        row.style.transform = 'translateY(-10px)';
        setTimeout(() => {
            row.remove();
            // Renumber labels
            const container = document.getElementById('members-container');
            Array.from(container.children).forEach((el, idx) => {
                const label = el.querySelector('span.text-xs.font-bold');
                if (label) label.textContent = `Dependent Member #${idx + 1}`;
            });
            updateEstimator();
        }, 200);
    }
}

async function handleApplicationSubmit(e) {
    e.preventDefault();

    const errBox = document.getElementById('apply-error');
    const errMsg = document.getElementById('apply-error-msg');
    const submitBtn = document.getElementById('submit-intake-btn');

    errBox.classList.add('hidden');
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="animate-spin mr-2">⏳</span> Registering in MCDA Engine...`;

    // Extract members (gracefully ignore empty dependent rows)
    const memberElements = document.querySelectorAll('#members-container > div');
    const members = [];

    memberElements.forEach(el => {
        const fn = (el.querySelector('.member-first-name')?.value || '').trim();
        const ln = (el.querySelector('.member-last-name')?.value || '').trim();
        const rel = el.querySelector('.member-rel')?.value || 'Relative';
        const isPwd = el.querySelector('.member-pwd')?.checked || false;
        const isSen = el.querySelector('.member-senior')?.checked || false;

        if (fn || ln || isPwd || isSen) {
            members.push({
                first_name: fn || 'Family',
                last_name: ln || 'Dependent',
                relationship_to_head: rel,
                is_pwd: isPwd,
                is_senior: isSen
            });
        }
    });

    const payload = {
        head_name: document.getElementById('head_name').value.trim(),
        contact_number: document.getElementById('contact_number').value.trim(),
        barangay: document.getElementById('barangay').value,
        purok_zone: document.getElementById('purok_zone').value.trim(),
        street_address: document.getElementById('street_address').value.trim(),
        monthly_income: parseFloat(document.getElementById('monthly_income').value) || 0.0,
        is_informal_settler: document.getElementById('is_informal_settler').checked,
        has_calamity_damage: document.getElementById('has_calamity_damage').checked,
        members: members
    };

    try {
        const res = await fetch('/api/v1/apply', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || 'Submission failed');
        }

        // Broadcast to admin dashboard tabs
        try {
            const bc = new BroadcastChannel('smartaid_channel');
            bc.postMessage({
                type: 'NEW_APPLICATION',
                reference_number: data.reference_number,
                head_name: payload.head_name,
                barangay: payload.barangay
            });
        } catch (bErr) {}

        try {
            localStorage.setItem('smartaid_last_application', JSON.stringify({
                ref: data.reference_number,
                name: payload.head_name,
                barangay: payload.barangay,
                timestamp: Date.now()
            }));
        } catch (lErr) {}

        // Show confirmation view with animation
        document.getElementById('intake-form-container').classList.add('hidden');
        document.getElementById('estimator-panel')?.classList.add('hidden');
        const confirmCard = document.getElementById('confirmation-card');
        confirmCard.classList.remove('hidden');
        confirmCard.classList.add('animate-scale-in');
        document.getElementById('confirmed-ref-number').textContent = data.reference_number;
        document.getElementById('track-confirmed-btn').href = `/track?ref=${encodeURIComponent(data.reference_number)}`;

        // Trigger celebratory confetti burst
        if (typeof fireConfetti === 'function') {
            fireConfetti({ count: 120 });
        }

        // Scroll to top
        window.scrollTo({ top: 0, behavior: 'smooth' });

    } catch (err) {
        errMsg.textContent = err.message;
        errBox.classList.remove('hidden');
        errBox.classList.add('animate-shake');
        submitBtn.disabled = false;
        submitBtn.innerHTML = `<i data-lucide="send" class="w-4 h-4"></i><span>Submit Official Assistance Registration</span>`;
        lucide.createIcons();
    }
}

function copyReferenceNumber() {
    const ref = document.getElementById('confirmed-ref-number').textContent;
    navigator.clipboard.writeText(ref).then(() => {
        showCopyToast(`Reference number ${ref} copied!`);
    }).catch(() => {
        prompt('Copy your reference number:', ref);
    });
}

function showCopyToast(msg) {
    let toast = document.getElementById('copy-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'copy-toast';
        toast.className = 'fixed bottom-6 right-6 z-50 px-4 py-2.5 rounded-xl bg-slate-900 text-white text-xs font-bold shadow-xl flex items-center gap-2 animate-slide-up';
        document.body.appendChild(toast);
    }
    toast.innerHTML = `<span class="beacon-dot"></span><span>${msg}</span>`;
    toast.classList.remove('hidden');
    setTimeout(() => {
        toast.classList.add('hidden');
    }, 2500);
}

function resetIntakeForm() {
    document.getElementById('apply-form').reset();
    document.getElementById('members-container').innerHTML = '';
    addMemberRow();
    document.getElementById('confirmation-card').classList.add('hidden');
    document.getElementById('intake-form-container').classList.remove('hidden');
    document.getElementById('estimator-panel')?.classList.remove('hidden');
    const submitBtn = document.getElementById('submit-intake-btn');
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<i data-lucide="send" class="w-4 h-4"></i><span>Submit Official Assistance Registration</span>`;
    lucide.createIcons();
    updateEstimator();
}

function updateEstimator() {
    const incomeInput = document.getElementById('monthly_income');
    const income = incomeInput ? parseFloat(incomeInput.value) || 0 : 0;
    const isInformal = document.getElementById('is_informal_settler')?.checked || false;
    const hasCalamity = document.getElementById('has_calamity_damage')?.checked || false;

    // Dependents counts
    const memberElements = document.querySelectorAll('#members-container > div');
    const memberCountTotal = 1 + memberElements.length; // Household head + dependents
    let pwdCount = 0;
    let seniorCount = 0;

    memberElements.forEach(el => {
        if (el.querySelector('.member-pwd')?.checked) pwdCount++;
        if (el.querySelector('.member-senior')?.checked) seniorCount++;
    });

    const ceiling = 15000;
    const isEligible = income <= ceiling;

    const elBox = document.getElementById('est-eligibility-box');
    const elBadge = document.getElementById('est-eligibility-badge');
    const elDesc = document.getElementById('est-eligibility-desc');
    const elScore = document.getElementById('est-vpi-score');
    const elProgress = document.getElementById('est-vpi-progress');
    const elTier = document.getElementById('est-tier-badge');
    const elInc = document.getElementById('est-score-income');
    const elDep = document.getElementById('est-score-dep');
    const elHouse = document.getElementById('est-score-housing');
    const elCalamity = document.getElementById('est-score-calamity');

    if (!isEligible) {
        if (elBox) {
            elBox.className = 'mt-4 p-3.5 rounded-xl bg-rose-50 border border-rose-200 text-center transition-all';
        }
        if (elBadge) {
            elBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-rose-500"></span><span class="text-rose-700 font-bold">Exceeds ₱15,000 Ceiling</span>`;
        }
        if (elDesc) {
            elDesc.className = 'text-[11px] text-rose-600/80 mt-1';
            elDesc.textContent = `Reported ₱${income.toLocaleString()} exceeds statutory threshold.`;
        }
        if (elScore) elScore.textContent = '0.0000';
        if (elProgress) {
            elProgress.style.width = '0%';
            elProgress.className = 'bg-rose-500 h-2.5 rounded-full transition-all duration-300';
        }
        if (elTier) {
            elTier.className = 'font-bold px-2 py-0.5 rounded-md bg-rose-100 text-rose-800 text-[10px]';
            elTier.textContent = 'Ineligible (Disqualified)';
        }
        if (elInc) elInc.textContent = '+0.000';
        if (elDep) elDep.textContent = '+0.000';
        if (elHouse) elHouse.textContent = '+0.000';
        if (elCalamity) elCalamity.textContent = '+0.000';
        return;
    }

    // MCDA Normalization formulas
    const s_income = Math.max(0, Math.min(1.0, 1.0 - (income / ceiling)));
    const effective_dependents = (pwdCount * 1.5) + (seniorCount * 1.0);
    const s_dep = Math.max(0, Math.min(1.0, effective_dependents / Math.max(memberCountTotal, 1)));
    const s_housing = isInformal ? 1.0 : 0.0;
    const s_calamity = hasCalamity ? 1.0 : 0.0;

    const w_income = 0.35;
    const w_dep = 0.25;
    const w_housing = 0.20;
    const w_calamity = 0.20;

    const c_income = s_income * w_income;
    const c_dep = s_dep * w_dep;
    const c_housing = s_housing * w_housing;
    const c_calamity = s_calamity * w_calamity;

    const vpi = c_income + c_dep + c_housing + c_calamity;
    const vpiPercent = Math.min(100, Math.round(vpi * 100));

    if (elBox) {
        elBox.className = 'mt-4 p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-center transition-all';
    }
    if (elBadge) {
        elBadge.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-500"></span><span class="text-emerald-800 font-bold">Eligible (Meets Income Criteria)</span>`;
    }
    if (elDesc) {
        elDesc.className = 'text-[11px] text-emerald-700/80 mt-1';
        elDesc.textContent = `Monthly income of ₱${income.toLocaleString()} is within ₱15,000 threshold.`;
    }
    if (elScore) {
        if (typeof animateCounter === 'function') {
            animateCounter('est-vpi-score', vpi, 350);
        } else {
            elScore.textContent = vpi.toFixed(4);
        }
    }
    if (elProgress) {
        elProgress.style.width = `${vpiPercent}%`;
        elProgress.className = 'bg-gradient-to-r from-indigo-500 via-indigo-600 to-emerald-500 h-2.5 rounded-full transition-all duration-300';
    }
    if (elTier) {
        if (vpi >= 0.60) {
            elTier.className = 'font-bold px-2 py-0.5 rounded-md bg-purple-100 text-purple-800 text-[10px]';
            elTier.textContent = 'High Priority (Tier 1)';
        } else if (vpi >= 0.35) {
            elTier.className = 'font-bold px-2 py-0.5 rounded-md bg-indigo-100 text-indigo-800 text-[10px]';
            elTier.textContent = 'Moderate Priority (Tier 2)';
        } else {
            elTier.className = 'font-bold px-2 py-0.5 rounded-md bg-slate-100 text-slate-700 text-[10px]';
            elTier.textContent = 'Baseline Priority (Tier 3)';
        }
    }

    if (elInc) elInc.textContent = `+${c_income.toFixed(3)}`;
    if (elDep) elDep.textContent = `+${c_dep.toFixed(3)}`;
    if (elHouse) elHouse.textContent = `+${c_housing.toFixed(3)}`;
    if (elCalamity) elCalamity.textContent = `+${c_calamity.toFixed(3)}`;
}
