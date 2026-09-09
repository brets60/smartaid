// SmartAid Admin Dashboard Controller

let currentProgramId = null;
let allAllocations = [];
let currentProgramRules = null;
let activeFilter = 'ALL';

document.addEventListener('DOMContentLoaded', () => {
    const progSelect = document.getElementById('program-select');
    if (progSelect && progSelect.value) {
        currentProgramId = progSelect.value;
        loadProgramData(currentProgramId);
    }
});

async function loadProgramData(programId) {
    if (!programId) return;
    currentProgramId = programId;

    try {
        // Fetch program details & metrics
        const pRes = await fetch(`/api/v1/programs/${programId}`);
        const program = await pRes.json();
        
        if (pRes.ok) {
            updateDashboardMetrics(program);
            currentProgramRules = program.rules;
            populateWeightModalValues(program.rules);
            document.getElementById('active-program-name-display').textContent = program.program_name;
        }

        // Fetch allocations
        const aRes = await fetch(`/api/v1/programs/${programId}/allocations`);
        if (aRes.ok) {
            allAllocations = await aRes.json();
            renderAllocationsTable(allAllocations);
        }
    } catch (err) {
        console.error("Error loading program data:", err);
    }
}

function updateDashboardMetrics(program) {
    const stats = program.stats || {};
    document.getElementById('stat-quota').textContent = program.total_quota_slots || 0;
    document.getElementById('stat-approved').textContent = stats.approved_count || 0;
    document.getElementById('stat-quota-util').textContent = `${stats.utilization_percent || 0}% quota allocated`;
    document.getElementById('stat-disbursed').textContent = stats.disbursed_count || 0;
    
    const pctDisb = stats.approved_count > 0 ? Math.round((stats.disbursed_count / stats.approved_count) * 100) : 0;
    document.getElementById('stat-disbursed-pct').textContent = `${pctDisb}% of approved disbursed`;
    
    document.getElementById('stat-budget').textContent = `₱${(stats.disbursed_budget || 0).toLocaleString()}`;
    document.getElementById('stat-budget-total').textContent = `of ₱${(stats.total_budget || 0).toLocaleString()} total`;
}

function renderAllocationsTable(allocations) {
    const tbody = document.getElementById('allocations-tbody');
    if (!allocations || allocations.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="py-10 text-center text-slate-400">
                    No applicant allocations found for this program. Run evaluation or register applicants.
                </td>
            </tr>
        `;
        return;
    }

    const searchVal = document.getElementById('table-search')?.value.toLowerCase().trim() || '';

    const filtered = allocations.filter(a => {
        // Status filter
        if (activeFilter !== 'ALL' && a.status !== activeFilter) {
            return false;
        }
        // Search filter
        if (searchVal) {
            const hh = a.household || {};
            const matchName = (hh.head_name || '').toLowerCase().includes(searchVal);
            const matchRef = (hh.reference_number || '').toLowerCase().includes(searchVal);
            const matchBrgy = (hh.barangay || '').toLowerCase().includes(searchVal);
            return matchName || matchRef || matchBrgy;
        }
        return true;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="py-10 text-center text-slate-400">
                    No matching records found.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = filtered.map((a) => {
        const hh = a.household || {};
        
        // Status badge styling
        let statusBadge = '';
        if (a.status === 'Approved') {
            statusBadge = a.is_disbursed ? 
                `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-800 border border-indigo-200">
                    <i data-lucide="check" class="w-3 h-3"></i> Disbursed
                 </span>` :
                `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-200">
                    <i data-lucide="check-circle" class="w-3 h-3"></i> Approved
                 </span>`;
        } else if (a.status === 'Waitlisted') {
            statusBadge = `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-200">
                <i data-lucide="clock" class="w-3 h-3"></i> Waitlisted
            </span>`;
        } else {
            statusBadge = `<span class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-200" title="${a.score_breakdown?.allocation_decision?.reason || 'Disqualified'}">
                <i data-lucide="x-circle" class="w-3 h-3"></i> Disqualified
            </span>`;
        }

        // Rank pill
        const rankDisplay = a.rank > 0 ? 
            `<span class="inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-mono font-bold ${a.status === 'Approved' ? 'bg-indigo-600 text-white' : 'bg-slate-200 text-slate-700'}">#${a.rank}</span>` :
            `<span class="text-slate-300 text-sm font-bold pl-2.5">-</span>`;

        // Flags
        const flags = [];
        if (hh.is_informal_settler) flags.push(`<span class="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-medium border border-slate-200">Informal</span>`);
        if (hh.has_calamity_damage) flags.push(`<span class="px-1.5 py-0.5 rounded bg-amber-50 text-amber-700 text-[10px] font-medium border border-amber-200">Calamity</span>`);
        const flagsHtml = flags.length > 0 ? flags.join(' ') : `<span class="text-slate-300">-</span>`;

        return `
            <tr class="hover:bg-slate-50/80 transition-colors">
                <td class="py-3 pl-4 pr-3 sm:pl-6">${rankDisplay}</td>
                <td class="px-3 py-3">
                    <div class="font-bold text-slate-900">${hh.head_name || 'N/A'}</div>
                    <div class="text-[11px] font-mono text-slate-400">${hh.reference_number || ''}</div>
                </td>
                <td class="px-3 py-3 text-slate-600">
                    <div>${hh.barangay || ''}</div>
                    <div class="text-[11px] text-slate-400">${hh.purok_zone || ''}</div>
                </td>
                <td class="px-3 py-3 font-mono text-slate-700 font-medium">
                    ₱${(hh.monthly_income || 0).toLocaleString()}
                </td>
                <td class="px-3 py-3 text-slate-600">
                    <div class="flex items-center gap-1.5 text-[11px]">
                        ${hh.pwd_count > 0 ? `<span class="px-1.5 py-0.2 rounded bg-purple-100 text-purple-800 font-bold">${hh.pwd_count} PWD</span>` : ''}
                        ${hh.elderly_count > 0 ? `<span class="px-1.5 py-0.2 rounded bg-blue-100 text-blue-800 font-bold">${hh.elderly_count} Senior</span>` : ''}
                        ${hh.pwd_count === 0 && hh.elderly_count === 0 ? `<span class="text-slate-400">${hh.member_count || 1} members</span>` : ''}
                    </div>
                </td>
                <td class="px-3 py-3">${flagsHtml}</td>
                <td class="px-3 py-3 font-mono font-bold text-indigo-600">
                    ${(a.vulnerability_score || 0).toFixed(4)}
                </td>
                <td class="px-3 py-3">${statusBadge}</td>
                <td class="px-3 py-3 text-right pr-6">
                    <button onclick='openXaiDrawer(${JSON.stringify(a).replace(/'/g, "&#39;")})'
                        class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-white text-indigo-600 hover:bg-indigo-50 border border-indigo-200 shadow-2xs transition-all">
                        <i data-lucide="info" class="w-3.5 h-3.5"></i>
                        <span>Audit XAI</span>
                    </button>
                </td>
            </tr>
        `;
    }).join('');

    lucide.createIcons();
}

function filterTable() {
    renderAllocationsTable(allAllocations);
}

function setStatusFilter(filter) {
    activeFilter = filter;
    ['ALL', 'Approved', 'Waitlisted', 'Disqualified'].forEach(f => {
        const btn = document.getElementById(`filter-${f}`);
        if (btn) {
            if (f === filter) {
                btn.className = 'px-2.5 py-1 rounded-md bg-white font-semibold text-slate-900 shadow-sm';
            } else {
                btn.className = 'px-2.5 py-1 rounded-md hover:text-slate-900';
            }
        }
    });
    renderAllocationsTable(allAllocations);
}

// ==========================================
// EVALUATION ENGINE TRIGGER
// ==========================================

async function triggerEvaluation() {
    if (!currentProgramId) return;
    const btn = document.getElementById('eval-btn');
    btn.disabled = true;
    btn.innerHTML = `<span class="animate-spin mr-1">⏳</span> Evaluating...`;

    try {
        const res = await fetch(`/api/v1/programs/${currentProgramId}/evaluate`, {
            method: 'POST'
        });
        const data = await res.json();
        
        if (res.ok) {
            await loadProgramData(currentProgramId);
            showToast(`MCDA Scoring Complete: ${data.result.approved} Approved within quota (${data.result.total_evaluated} evaluated).`);
        } else {
            alert(data.detail || 'Evaluation failed.');
        }
    } catch (err) {
        alert('Network error during evaluation.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="play" class="w-3.5 h-3.5"></i><span>Run MCDA Allocation</span>`;
        lucide.createIcons();
    }
}

// ==========================================
// DYNAMIC CRITERIA WEIGHTS MODAL
// ==========================================

function openWeightModal() {
    document.getElementById('weight-modal').classList.remove('hidden');
    lucide.createIcons();
}

function closeWeightModal() {
    document.getElementById('weight-modal').classList.add('hidden');
}

function populateWeightModalValues(rules) {
    if (!rules) return;
    const wInc = Math.round(rules.weight_income * 100);
    const wDep = Math.round(rules.weight_dependency * 100);
    const wCal = Math.round(rules.weight_calamity * 100);
    const wHou = Math.round(rules.weight_housing * 100);

    document.getElementById('slider-income').value = wInc;
    document.getElementById('slider-dep').value = wDep;
    document.getElementById('slider-calamity').value = wCal;
    document.getElementById('slider-housing').value = wHou;

    document.getElementById('weight-val-income').textContent = `${wInc}%`;
    document.getElementById('weight-val-dep').textContent = `${wDep}%`;
    document.getElementById('weight-val-calamity').textContent = `${wCal}%`;
    document.getElementById('weight-val-housing').textContent = `${wHou}%`;

    document.getElementById('input-ceiling').value = rules.income_ceiling;
    document.getElementById('input-cooldown').value = rules.cooldown_days;

    checkWeightSum();
}

function updateSliders(source) {
    const inc = parseInt(document.getElementById('slider-income').value) || 0;
    const dep = parseInt(document.getElementById('slider-dep').value) || 0;
    const cal = parseInt(document.getElementById('slider-calamity').value) || 0;
    const hou = parseInt(document.getElementById('slider-housing').value) || 0;

    document.getElementById('weight-val-income').textContent = `${inc}%`;
    document.getElementById('weight-val-dep').textContent = `${dep}%`;
    document.getElementById('weight-val-calamity').textContent = `${cal}%`;
    document.getElementById('weight-val-housing').textContent = `${hou}%`;

    checkWeightSum();
}

function checkWeightSum() {
    const inc = parseInt(document.getElementById('slider-income').value) || 0;
    const dep = parseInt(document.getElementById('slider-dep').value) || 0;
    const cal = parseInt(document.getElementById('slider-calamity').value) || 0;
    const hou = parseInt(document.getElementById('slider-housing').value) || 0;

    const sum = inc + dep + cal + hou;
    const sumBox = document.getElementById('weight-sum-box');
    const sumVal = document.getElementById('weight-sum-val');
    const saveBtn = document.getElementById('save-weights-btn');

    sumVal.textContent = `${sum}%`;

    if (sum === 100) {
        sumBox.className = 'p-3 rounded-lg flex items-center justify-between border border-emerald-200 bg-emerald-50 text-emerald-800';
        saveBtn.disabled = false;
        saveBtn.classList.remove('opacity-50', 'cursor-not-allowed');
    } else {
        sumBox.className = 'p-3 rounded-lg flex items-center justify-between border border-rose-200 bg-rose-50 text-rose-800';
        saveBtn.disabled = true;
        saveBtn.classList.add('opacity-50', 'cursor-not-allowed');
    }
}

function autoBalanceWeights() {
    const inc = parseInt(document.getElementById('slider-income').value) || 1;
    const dep = parseInt(document.getElementById('slider-dep').value) || 1;
    const cal = parseInt(document.getElementById('slider-calamity').value) || 1;
    const hou = parseInt(document.getElementById('slider-housing').value) || 1;

    const sum = inc + dep + cal + hou;
    if (sum <= 0) return;

    let nInc = Math.round((inc / sum) * 100);
    let nDep = Math.round((dep / sum) * 100);
    let nCal = Math.round((cal / sum) * 100);
    let nHou = 100 - (nInc + nDep + nCal);

    document.getElementById('slider-income').value = nInc;
    document.getElementById('slider-dep').value = nDep;
    document.getElementById('slider-calamity').value = nCal;
    document.getElementById('slider-housing').value = nHou;

    updateSliders();
}

async function saveCriteriaWeights(e) {
    e.preventDefault();
    if (!currentProgramId) return;

    const inc = parseInt(document.getElementById('slider-income').value) / 100;
    const dep = parseInt(document.getElementById('slider-dep').value) / 100;
    const cal = parseInt(document.getElementById('slider-calamity').value) / 100;
    const hou = parseInt(document.getElementById('slider-housing').value) / 100;
    const ceiling = parseFloat(document.getElementById('input-ceiling').value);
    const cooldown = parseInt(document.getElementById('input-cooldown').value);

    try {
        const res = await fetch(`/api/v1/programs/${currentProgramId}/rules`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                weight_income: inc,
                weight_dependency: dep,
                weight_calamity: cal,
                weight_housing: hou,
                income_ceiling: ceiling,
                cooldown_days: cooldown
            })
        });

        if (res.ok) {
            closeWeightModal();
            await triggerEvaluation();
        } else {
            const err = await res.json();
            alert(err.detail || 'Failed to update criteria rules.');
        }
    } catch (err) {
        alert('Network error while updating rules.');
    }
}

// ==========================================
// EXPLAINABLE AI (XAI) DRAWER
// ==========================================

function openXaiDrawer(alloc) {
    const hh = alloc.household || {};
    const bd = alloc.score_breakdown || {};
    const factors = bd.factors || {};

    document.getElementById('xai-head-name').textContent = hh.head_name || 'Applicant';
    document.getElementById('xai-ref-num').textContent = hh.reference_number || '';
    document.getElementById('xai-vpi-score').textContent = (alloc.vulnerability_score || 0).toFixed(4);
    
    // Status Badge
    const badge = document.getElementById('xai-status-badge');
    badge.textContent = alloc.status;
    if (alloc.status === 'Approved') {
        badge.className = 'px-3 py-1 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 border border-emerald-300';
    } else if (alloc.status === 'Waitlisted') {
        badge.className = 'px-3 py-1 rounded-full text-xs font-bold bg-amber-100 text-amber-800 border border-amber-300';
    } else {
        badge.className = 'px-3 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-300';
    }

    document.getElementById('xai-rank-display').textContent = alloc.rank > 0 ? `Priority Rank #${alloc.rank}` : `Unranked`;

    // Hard Constraint checks
    const elig = bd.eligibility || {};
    const checksContainer = document.getElementById('xai-hard-checks');
    checksContainer.innerHTML = `
        <div class="flex items-center justify-between pb-1.5 border-b border-slate-100">
            <span class="text-slate-600">Income Ceiling Screen (₱${(hh.monthly_income || 0).toLocaleString()} vs Ceiling):</span>
            <span class="font-semibold ${elig.income_check_passed ? 'text-emerald-600' : 'text-rose-600'}">
                ${elig.income_check_passed ? '✓ PASSED' : '✗ EXCEEDED'}
            </span>
        </div>
        <div class="flex items-center justify-between">
            <span class="text-slate-600">Cooldown / Deduplication Check:</span>
            <span class="font-semibold ${elig.cooldown_check_passed ? 'text-emerald-600' : 'text-rose-600'}">
                ${elig.cooldown_check_passed ? '✓ PASSED (0 recent claims)' : '✗ FAILED'}
            </span>
        </div>
        ${elig.disqualification_reason ? `<div class="mt-2 p-2 bg-rose-50 text-rose-700 rounded text-[11px] font-medium">${elig.disqualification_reason}</div>` : ''}
    `;

    // 1. Income Factor
    const incF = factors.income || {};
    document.getElementById('xai-income-contrib').textContent = `+${(incF.weighted_contribution || 0).toFixed(4)}`;
    document.getElementById('xai-income-bar').style.width = `${Math.min(100, (incF.normalized_score || 0) * 100)}%`;
    document.getElementById('xai-income-desc').textContent = `Raw: ₱${(incF.raw_value || 0).toLocaleString()} | Normalized: ${(incF.normalized_score || 0).toFixed(2)} × ${(incF.weight || 0.35) * 100}% weight`;

    // 2. Dependency Factor
    const depF = factors.dependency || {};
    document.getElementById('xai-dep-contrib').textContent = `+${(depF.weighted_contribution || 0).toFixed(4)}`;
    document.getElementById('xai-dep-bar').style.width = `${Math.min(100, (depF.normalized_score || 0) * 100)}%`;
    document.getElementById('xai-dep-desc').textContent = `${depF.raw_pwd || 0} PWD (1.5x), ${depF.raw_elderly || 0} Senior out of ${depF.raw_members || 1} members`;

    // 3. Calamity Factor
    const calF = factors.calamity || {};
    document.getElementById('xai-calamity-contrib').textContent = `+${(calF.weighted_contribution || 0).toFixed(4)}`;
    document.getElementById('xai-calamity-bar').style.width = `${(calF.normalized_score || 0) * 100}%`;
    document.getElementById('xai-calamity-desc').textContent = calF.has_calamity_damage ? 'Severe Disaster Damage (Score: 1.00)' : 'No Calamity Damage (Score: 0.00)';

    // 4. Housing Factor
    const houF = factors.housing || {};
    document.getElementById('xai-housing-contrib').textContent = `+${(houF.weighted_contribution || 0).toFixed(4)}`;
    document.getElementById('xai-housing-bar').style.width = `${(houF.normalized_score || 0) * 100}%`;
    document.getElementById('xai-housing-desc').textContent = houF.is_informal_settler ? 'Informal Settler (Score: 1.00)' : 'Formal Residence (Score: 0.00)';

    // Decision rationale
    const dec = bd.allocation_decision || {};
    document.getElementById('xai-decision-rationale').textContent = dec.reason || 'Decision computed via vector MCDA engine.';

    document.getElementById('xai-drawer').classList.remove('hidden');
    lucide.createIcons();
}

function closeXaiDrawer() {
    document.getElementById('xai-drawer').classList.add('hidden');
}

function showToast(msg) {
    const toast = document.createElement('div');
    toast.className = 'fixed bottom-5 right-5 z-50 px-4 py-3 rounded-xl bg-slate-900 text-white text-xs font-semibold shadow-2xl flex items-center gap-2 border border-slate-700 animate-bounce';
    toast.innerHTML = `<i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-400"></i><span>${msg}</span>`;
    document.body.appendChild(toast);
    lucide.createIcons();
    setTimeout(() => toast.remove(), 4000);
}
