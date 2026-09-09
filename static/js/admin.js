// SmartAid Admin Dashboard Controller

let currentProgramId = null;
let allAllocations = [];
let currentProgramRules = null;
let activeFilter = 'ALL';
let activeBarangayFilter = 'ALL';
let isGroupedByBarangay = true;

document.addEventListener('DOMContentLoaded', () => {
    // Check logged-in user context
    if (window.CURRENT_USER && window.CURRENT_USER.assignedBarangay) {
        activeBarangayFilter = window.CURRENT_USER.assignedBarangay;
        const bSelect = document.getElementById('filter-barangay');
        if (bSelect) {
            bSelect.value = window.CURRENT_USER.assignedBarangay;
            if (window.CURRENT_USER.role === 'barangay_staff') {
                bSelect.disabled = true;
                bSelect.title = `Locked to your assigned jurisdiction: Barangay ${window.CURRENT_USER.assignedBarangay}`;
            }
        }
    }

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
    const stats = program.statistics || {};
    document.getElementById('stat-total-households').textContent = stats.total_evaluated || 0;
    document.getElementById('stat-approved').textContent = stats.approved_count || 0;
    
    const quota = program.quota_limit || 10;
    document.getElementById('stat-quota-util').textContent = `${Math.min(100, Math.round((stats.approved_count / quota) * 100))}% of ${quota} quota filled`;
    
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
                <td colspan="9" class="py-12 text-center text-slate-400">
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
        // Barangay filter
        const hh = a.household || {};
        if (activeBarangayFilter !== 'ALL' && hh.barangay !== activeBarangayFilter) {
            return false;
        }
        // Search filter
        if (searchVal) {
            const matchName = (hh.head_name || '').toLowerCase().includes(searchVal);
            const matchRef = (hh.reference_number || '').toLowerCase().includes(searchVal);
            const matchBrgy = (hh.barangay || '').toLowerCase().includes(searchVal);
            const matchPurok = (hh.purok_zone || '').toLowerCase().includes(searchVal);
            return matchName || matchRef || matchBrgy || matchPurok;
        }
        return true;
    });

    if (filtered.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="9" class="py-12 text-center text-slate-400">
                    <div class="w-10 h-10 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-2">
                        <i data-lucide="search-x" class="w-5 h-5"></i>
                    </div>
                    <p class="text-xs font-semibold text-slate-600">No applicant records found.</p>
                    <p class="text-[11px] text-slate-400 mt-0.5">Try selecting a different barangay, status, or search term.</p>
                </td>
            </tr>
        `;
        lucide.createIcons();
        return;
    }

    const renderRowHtml = (a) => {
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
            `<span class="inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-mono font-bold ${a.status === 'Approved' ? 'bg-indigo-600 text-white shadow-xs' : 'bg-slate-200 text-slate-700'}">#${a.rank}</span>` :
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
                    <div class="font-semibold text-slate-800">${hh.barangay || ''}</div>
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
                    <div class="flex items-center justify-end gap-1.5">
                        <button onclick='openHouseholdModal("${hh.id}")'
                            class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-white text-slate-700 hover:bg-slate-50 border border-slate-300 shadow-2xs transition-all">
                            <i data-lucide="edit-3" class="w-3.5 h-3.5 text-slate-500"></i>
                            <span>View/Edit</span>
                        </button>
                        <button onclick='openXaiDrawer(${JSON.stringify(a).replace(/'/g, "&#39;")})'
                            class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-semibold bg-white text-indigo-600 hover:bg-indigo-50 border border-indigo-200 shadow-2xs transition-all">
                            <i data-lucide="info" class="w-3.5 h-3.5"></i>
                            <span>Audit XAI</span>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    };

    if (!isGroupedByBarangay) {
        tbody.innerHTML = filtered.map(renderRowHtml).join('');
    } else {
        // Group by Barangay
        const groups = {};
        filtered.forEach(a => {
            const b = a.household?.barangay || 'Unspecified Barangay';
            if (!groups[b]) groups[b] = [];
            groups[b].push(a);
        });

        let html = '';
        Object.keys(groups).sort().forEach(bName => {
            const bAllocs = groups[bName];
            const approvedCount = bAllocs.filter(x => x.status === 'Approved').length;
            const waitlistCount = bAllocs.filter(x => x.status === 'Waitlisted').length;
            const disqCount = bAllocs.filter(x => x.status === 'Disqualified').length;

            html += `
                <tr class="bg-indigo-50/70 border-t-2 border-indigo-200">
                    <td colspan="9" class="py-2.5 px-4 sm:px-6">
                        <div class="flex flex-wrap items-center justify-between gap-2">
                            <div class="flex items-center gap-2">
                                <span class="w-6 h-6 rounded-md bg-indigo-600 text-white flex items-center justify-center text-xs font-bold shadow-2xs">📍</span>
                                <span class="text-xs font-extrabold text-slate-900 tracking-wide">BARANGAY ${bName.toUpperCase()}</span>
                                <span class="text-[10.5px] px-2 py-0.5 rounded-full bg-white text-indigo-800 font-bold border border-indigo-200 shadow-2xs">
                                    ${bAllocs.length} Household${bAllocs.length > 1 ? 's' : ''} Registered
                                </span>
                            </div>
                            <div class="flex items-center gap-3 text-[11px] font-semibold">
                                <span class="text-emerald-700 font-bold flex items-center gap-1">
                                    <span class="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
                                    ${approvedCount} Approved
                                </span>
                                ${waitlistCount > 0 ? `<span class="text-amber-700 font-bold flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-amber-500 inline-block"></span>${waitlistCount} Waitlisted</span>` : ''}
                                ${disqCount > 0 ? `<span class="text-rose-600 font-bold flex items-center gap-1"><span class="w-2 h-2 rounded-full bg-rose-500 inline-block"></span>${disqCount} Disqualified</span>` : ''}
                            </div>
                        </div>
                    </td>
                </tr>
            `;
            html += bAllocs.map(renderRowHtml).join('');
        });

        tbody.innerHTML = html;
    }

    lucide.createIcons();
}

function onBarangayFilterChange() {
    const sel = document.getElementById('filter-barangay');
    if (sel) {
        activeBarangayFilter = sel.value;
        filterTable();
    }
}

function toggleBarangayGrouping() {
    isGroupedByBarangay = !isGroupedByBarangay;
    const btnLabel = document.getElementById('toggle-group-label');
    const btn = document.getElementById('toggle-group-btn');
    if (btnLabel && btn) {
        if (isGroupedByBarangay) {
            btnLabel.textContent = 'Grouped by Barangay: ON';
            btn.className = 'px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 flex items-center gap-1.5 shadow-2xs transition-all';
        } else {
            btnLabel.textContent = 'Grouped by Barangay: OFF';
            btn.className = 'px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-100 text-slate-600 border border-slate-300 hover:bg-slate-200 flex items-center gap-1.5 shadow-2xs transition-all';
        }
    }
    filterTable();
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

// ==========================================
// MUNICIPAL ANNOUNCEMENTS & SMS DISPATCH
// ==========================================

function openBroadcastModal() {
    document.getElementById('broadcast-modal').classList.remove('hidden');
    loadSmsSettings();
    loadRecentBroadcasts();

    // If logged in as Barangay Staff, lock target barangay to their jurisdiction
    if (window.CURRENT_USER && window.CURRENT_USER.assignedBarangay) {
        const bSelect = document.getElementById('broadcast-barangay');
        if (bSelect) {
            bSelect.value = window.CURRENT_USER.assignedBarangay;
            if (window.CURRENT_USER.role === 'barangay_staff') {
                bSelect.disabled = true;
                bSelect.title = `Locked to Barangay ${window.CURRENT_USER.assignedBarangay}`;
            }
        }
    }

    lucide.createIcons();
}

async function loadSmsSettings() {
    try {
        const res = await fetch('/api/v1/settings/sms');
        if (!res.ok) return;
        const data = await res.json();
        const badge = document.getElementById('sms-status-badge');
        const dot = document.getElementById('sms-status-dot');
        const helper = document.getElementById('sms-status-helper');
        const input = document.getElementById('sms-api-key-input');

        if (data.is_configured) {
            input.placeholder = `Configured (${data.masked_key}) - paste new key to change`;

            if (data.account) {
                const acc = data.account;
                if (acc.status === 'Active' && acc.credit_balance > 0) {
                    badge.textContent = `Live Ready (${acc.credit_balance} Credits)`;
                    badge.className = 'text-[10px] px-2 py-0.5 rounded font-bold bg-emerald-100 text-emerald-800 border border-emerald-300';
                    dot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-500';
                    helper.innerHTML = `<span class="text-emerald-700 font-semibold">✓ Connected to Semaphore:</span> "${acc.account_name}" (${acc.credit_balance} SMS credits available). Live cellular SMS text messages will be delivered to phones.`;
                } else {
                    badge.textContent = `Pending Approval (${acc.credit_balance} Credits)`;
                    badge.className = 'text-[10px] px-2 py-0.5 rounded font-bold bg-amber-100 text-amber-800 border border-amber-300';
                    dot.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse';
                    helper.innerHTML = `
                        <div class="p-2 rounded-lg bg-amber-50 border border-amber-200 text-amber-800 text-[11px] space-y-1">
                            <div class="font-bold flex items-center gap-1.5">
                                <i data-lucide="alert-circle" class="w-3.5 h-3.5 text-amber-600"></i>
                                <span>Semaphore Account: "${acc.account_name}" (Status: ${acc.status} • ${acc.credit_balance} Credits)</span>
                            </div>
                            <p class="leading-normal text-slate-600">
                                <strong>Why no SMS arrived:</strong> Semaphore newly registered accounts are in <em>Pending</em> status with <em>0 credits</em> until email verification or first top-up. Please check your email inbox to click the verification link from Semaphore, or log in to <a href="https://semaphore.co" target="_blank" class="text-indigo-600 underline font-semibold">semaphore.co</a>.
                            </p>
                        </div>
                    `;
                }
            } else if (data.error) {
                badge.textContent = 'API Key Error';
                badge.className = 'text-[10px] px-2 py-0.5 rounded font-bold bg-rose-100 text-rose-800 border border-rose-300';
                dot.className = 'w-2.5 h-2.5 rounded-full bg-rose-500';
                helper.innerHTML = `<span class="text-rose-600 font-semibold">API Error:</span> ${data.error}`;
            } else {
                badge.textContent = 'Live Gateway Active';
                badge.className = 'text-[10px] px-2 py-0.5 rounded font-bold bg-emerald-100 text-emerald-800 border border-emerald-300';
                dot.className = 'w-2.5 h-2.5 rounded-full bg-emerald-500';
                helper.innerHTML = `<span class="text-emerald-700 font-semibold">✓ Semaphore API Key Active:</span> ${data.masked_key}.`;
            }
        } else {
            badge.textContent = 'Simulation Mode';
            badge.className = 'text-[10px] px-2 py-0.5 rounded font-bold bg-amber-100 text-amber-800 border border-amber-300';
            dot.className = 'w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse';
            helper.textContent = 'No Semaphore key detected. SMS is simulated in server logs. Paste key above to send real text messages.';
        }
        lucide.createIcons();
    } catch(err) {
        console.error('Error loading SMS settings:', err);
    }
}

async function saveSmsApiKey() {
    const input = document.getElementById('sms-api-key-input');
    const key = input.value.trim();
    if (!key) {
        alert('Please paste your Semaphore API Key before saving.');
        return;
    }

    const btn = document.getElementById('sms-save-key-btn');
    btn.disabled = true;
    btn.innerHTML = `<span class="animate-spin mr-1">⏳</span> Saving...`;

    try {
        const res = await fetch('/api/v1/settings/sms', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: key })
        });
        const data = await res.json();
        if (res.ok) {
            input.value = '';
            showToast('Semaphore API Key saved! Live SMS mode is now active.');
            await loadSmsSettings();
        } else {
            alert(data.detail || 'Failed to save SMS API Key.');
        }
    } catch(err) {
        alert('Network error while saving SMS API Key.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="key" class="w-3.5 h-3.5"></i><span>Save Key</span>`;
        lucide.createIcons();
    }
}

function closeBroadcastModal() {
    document.getElementById('broadcast-modal').classList.add('hidden');
}

async function loadRecentBroadcasts() {
    const list = document.getElementById('recent-broadcasts-list');
    try {
        const res = await fetch('/api/v1/notifications');
        const items = await res.json();
        if (items && items.length > 0) {
            list.innerHTML = items.map(n => `
                <div class="p-2.5 rounded-lg border border-slate-200 bg-slate-50 space-y-1">
                    <div class="flex items-center justify-between">
                        <span class="font-bold text-slate-800">${n.title}</span>
                        <span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 font-semibold">${n.category}</span>
                    </div>
                    <p class="text-[11px] text-slate-600 line-clamp-2">${n.message}</p>
                    <div class="flex justify-between text-[10px] text-slate-400 pt-0.5">
                        <span>Target: ${n.target_barangay || 'All Barangays'} (${n.recipients_count} recipients)</span>
                        <span>${new Date(n.created_at).toLocaleDateString()}</span>
                    </div>
                </div>
            `).join('');
        } else {
            list.innerHTML = `<p class="text-slate-400 text-center py-2">No broadcast announcements dispatched yet.</p>`;
        }
    } catch(e) {
        list.innerHTML = `<p class="text-rose-400 text-center py-2">Failed to load dispatch history.</p>`;
    }
}

async function handleSendBroadcast(e) {
    e.preventDefault();
    const btn = document.getElementById('broadcast-submit-btn');
    btn.disabled = true;
    btn.innerHTML = `<span class="animate-spin mr-1">⏳</span> Dispatching SMS...`;

    const payload = {
        title: document.getElementById('broadcast-title').value.trim(),
        category: document.getElementById('broadcast-category').value,
        target_barangay: (window.CURRENT_USER && window.CURRENT_USER.assignedBarangay) ? window.CURRENT_USER.assignedBarangay : document.getElementById('broadcast-barangay').value,
        target_status: document.getElementById('broadcast-status').value,
        message: document.getElementById('broadcast-message').value.trim(),
        dispatch_sms: document.getElementById('broadcast-dispatch-sms').checked
    };

    try {
        const res = await fetch('/api/v1/notifications/broadcast', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (res.ok) {
            document.getElementById('broadcast-form').reset();
            closeBroadcastModal();

            if (data.sms_result && data.sms_result.status === 'GATEWAY_ERROR') {
                alert(`⚠️ ANNOUNCEMENT SAVED, BUT PHYSICAL SMS COULD NOT BE SENT:\n\n${data.sms_result.error}\n\nReason: Your Semaphore account is currently in 'Pending' status with 0 credits. Please check your email inbox to confirm your Semaphore account or top-up on semaphore.co to enable live cellular SMS.`);
            } else if (data.sms_result && data.sms_result.status === 'LIVE_SENT') {
                showToast(`✓ Live SMS successfully delivered to ${data.sms_result.count} mobile numbers!`);
            } else {
                showToast(`Broadcast published to ${data.recipients_count} household portals.`);
            }
        } else {
            alert(data.detail || 'Failed to dispatch broadcast.');
        }
    } catch (err) {
        alert('Network error while dispatching broadcast.');
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="send" class="w-3.5 h-3.5"></i><span>Send Broadcast Now</span>`;
        lucide.createIcons();
    }
}

async function confirmResetHouseholds() {
    const ok = confirm("Are you sure you want to clear all applicant households?\n\nThis will remove all applicant records so you can input fresh data. Staff accounts and program criteria will be kept.");
    if (!ok) return;

    try {
        const res = await fetch('/api/v1/households/reset', { method: 'POST' });
        const data = await res.json();
        if (res.ok) {
            showToast("All applicant households cleared successfully. Ready for new intake!");
            if (currentProgramId) {
                await loadProgramData(currentProgramId);
            }
        } else {
            alert(data.detail || "Failed to reset households.");
        }
    } catch (e) {
        alert("Network error while resetting households.");
    }
}

// ==========================================
// HOUSEHOLD VIEW & EDIT CONTROLLER
// ==========================================

let currentEditingHouseholdId = null;

async function openHouseholdModal(householdId) {
    currentEditingHouseholdId = householdId;
    const modal = document.getElementById('household-modal');
    modal.classList.remove('hidden');

    try {
        const res = await fetch(`/api/v1/households/${householdId}`);
        if (!res.ok) {
            alert('Failed to load household details.');
            closeHouseholdModal();
            return;
        }
        const hh = await res.json();
        renderHouseholdModal(hh);
    } catch(err) {
        alert('Network error while loading household: ' + err.message);
        closeHouseholdModal();
    }
}

function closeHouseholdModal() {
    document.getElementById('household-modal').classList.add('hidden');
    currentEditingHouseholdId = null;
}

function renderHouseholdModal(hh) {
    document.getElementById('edit-hh-id').value = hh.id;
    document.getElementById('edit-hh-modal-title').textContent = hh.head_name || 'Household Profile';
    document.getElementById('edit-hh-ref-badge').textContent = hh.reference_number || '';
    
    const trackLink = document.getElementById('edit-hh-track-link');
    trackLink.href = `/track?ref=${encodeURIComponent(hh.reference_number)}`;

    document.getElementById('edit-hh-head-name').value = hh.head_name || '';
    document.getElementById('edit-hh-contact').value = hh.contact_number || '';
    document.getElementById('edit-hh-barangay').value = hh.barangay || 'North Poblacion';
    document.getElementById('edit-hh-purok').value = hh.purok_zone || '';
    document.getElementById('edit-hh-street').value = hh.street_address || '';
    document.getElementById('edit-hh-income').value = hh.monthly_income || 0;
    document.getElementById('edit-hh-informal').checked = Boolean(hh.is_informal_settler);
    document.getElementById('edit-hh-calamity').checked = Boolean(hh.has_calamity_damage);

    // Render members
    const container = document.getElementById('edit-hh-members-container');
    container.innerHTML = '';
    const members = hh.members || [];
    members.forEach(m => addHouseholdMemberRow(m));
    updateHouseholdMemberCountBadge();

    lucide.createIcons();
}

function addHouseholdMemberRow(m = null) {
    const container = document.getElementById('edit-hh-members-container');
    const row = document.createElement('div');
    row.className = 'member-row p-2.5 bg-slate-50 border border-slate-200 rounded-xl grid grid-cols-1 sm:grid-cols-12 gap-2 items-center';
    
    const fn = m ? (m.first_name || '') : '';
    const ln = m ? (m.last_name || '') : '';
    const rel = m ? (m.relationship_to_head || '') : 'Dependent';
    const isPwd = m ? Boolean(m.is_pwd) : false;
    const isSenior = m ? Boolean(m.is_senior) : false;

    row.innerHTML = `
        <div class="sm:col-span-3">
            <input type="text" placeholder="First Name" value="${fn}" required
                class="member-fn w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white">
        </div>
        <div class="sm:col-span-3">
            <input type="text" placeholder="Last Name" value="${ln}" required
                class="member-ln w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs bg-white">
        </div>
        <div class="sm:col-span-2">
            <select class="member-rel w-full px-2 py-1.5 border border-slate-300 rounded-lg text-xs bg-white">
                <option value="Spouse" ${rel === 'Spouse' ? 'selected' : ''}>Spouse</option>
                <option value="Son" ${rel === 'Son' ? 'selected' : ''}>Son</option>
                <option value="Daughter" ${rel === 'Daughter' ? 'selected' : ''}>Daughter</option>
                <option value="Parent" ${rel === 'Parent' ? 'selected' : ''}>Parent</option>
                <option value="Sibling" ${rel === 'Sibling' ? 'selected' : ''}>Sibling</option>
                <option value="Grandchild" ${rel === 'Grandchild' ? 'selected' : ''}>Grandchild</option>
                <option value="Other" ${!['Spouse','Son','Daughter','Parent','Sibling','Grandchild'].includes(rel) ? 'selected' : ''}>Other</option>
            </select>
        </div>
        <div class="sm:col-span-3 flex items-center gap-3">
            <label class="flex items-center gap-1 text-[11px] font-semibold text-purple-700 cursor-pointer">
                <input type="checkbox" class="member-pwd rounded text-purple-600 border-slate-300" ${isPwd ? 'checked' : ''}>
                <span>PWD</span>
            </label>
            <label class="flex items-center gap-1 text-[11px] font-semibold text-blue-700 cursor-pointer">
                <input type="checkbox" class="member-senior rounded text-blue-600 border-slate-300" ${isSenior ? 'checked' : ''}>
                <span>Senior</span>
            </label>
        </div>
        <div class="sm:col-span-1 text-right">
            <button type="button" onclick="removeHouseholdMemberRow(this)" class="p-1 text-slate-400 hover:text-rose-600">
                <i data-lucide="x" class="w-4 h-4"></i>
            </button>
        </div>
    `;

    container.appendChild(row);
    updateHouseholdMemberCountBadge();
    lucide.createIcons();
}

function removeHouseholdMemberRow(btn) {
    const row = btn.closest('.member-row');
    if (row) {
        row.remove();
        updateHouseholdMemberCountBadge();
    }
}

function updateHouseholdMemberCountBadge() {
    const rows = document.querySelectorAll('#edit-hh-members-container .member-row');
    const badge = document.getElementById('edit-hh-member-count-badge');
    if (badge) {
        const total = rows.length + 1;
        badge.textContent = `${total} household member${total > 1 ? 's' : ''}`;
    }
}

async function saveHouseholdChanges(e) {
    e.preventDefault();
    const id = document.getElementById('edit-hh-id').value;
    if (!id) return;

    const btn = document.getElementById('edit-hh-save-btn');
    btn.disabled = true;
    btn.innerHTML = `<span class="animate-spin mr-1">⏳</span> Saving & Re-evaluating...`;

    // Collect members
    const memberRows = document.querySelectorAll('#edit-hh-members-container .member-row');
    const members = [];
    memberRows.forEach(row => {
        const fn = row.querySelector('.member-fn').value.trim();
        const ln = row.querySelector('.member-ln').value.trim();
        const rel = row.querySelector('.member-rel').value;
        const isPwd = row.querySelector('.member-pwd').checked;
        const isSenior = row.querySelector('.member-senior').checked;
        if (fn && ln) {
            members.push({
                first_name: fn,
                last_name: ln,
                relationship_to_head: rel,
                is_pwd: isPwd,
                is_senior: isSenior
            });
        }
    });

    const payload = {
        head_name: document.getElementById('edit-hh-head-name').value.trim(),
        contact_number: document.getElementById('edit-hh-contact').value.trim(),
        barangay: document.getElementById('edit-hh-barangay').value,
        purok_zone: document.getElementById('edit-hh-purok').value.trim(),
        street_address: document.getElementById('edit-hh-street').value.trim(),
        monthly_income: parseFloat(document.getElementById('edit-hh-income').value) || 0,
        is_informal_settler: document.getElementById('edit-hh-informal').checked,
        has_calamity_damage: document.getElementById('edit-hh-calamity').checked,
        members: members
    };

    try {
        const res = await fetch(`/api/v1/households/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (res.ok) {
            closeHouseholdModal();
            showToast(`Household profile for ${data.head_name} updated & roster re-evaluated!`);
            if (currentProgramId) {
                await loadProgramData(currentProgramId);
            }
        } else {
            alert(data.detail || 'Failed to update household.');
        }
    } catch(err) {
        alert('Network error while saving household: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="check" class="w-3.5 h-3.5"></i><span>Save & Re-evaluate</span>`;
        lucide.createIcons();
    }
}

async function deleteHouseholdRecord() {
    const id = document.getElementById('edit-hh-id').value;
    const name = document.getElementById('edit-hh-head-name').value;
    if (!id) return;

    const ok = confirm(`Are you sure you want to permanently delete the household record for "${name}"?\n\nThis will remove their intake registration, family members, and allocation records.`);
    if (!ok) return;

    const btn = document.getElementById('edit-hh-delete-btn');
    btn.disabled = true;
    btn.innerHTML = `<span class="animate-spin mr-1">⏳</span> Deleting...`;

    try {
        const res = await fetch(`/api/v1/households/${id}`, {
            method: 'DELETE'
        });
        const data = await res.json();
        if (res.ok) {
            closeHouseholdModal();
            showToast(`Household "${name}" deleted and allocation roster updated.`);
            if (currentProgramId) {
                await loadProgramData(currentProgramId);
            }
        } else {
            alert(data.detail || 'Failed to delete household.');
        }
    } catch(err) {
        alert('Network error while deleting household: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = `<i data-lucide="trash-2" class="w-3.5 h-3.5"></i><span>Delete Household</span>`;
        lucide.createIcons();
    }
}
