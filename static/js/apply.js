// SmartAid Public Beneficiary Intake Controller

let memberCount = 0;

document.addEventListener('DOMContentLoaded', () => {
    // Add 1 default dependent row
    addMemberRow();
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
                <label class="block text-[11px] font-semibold text-slate-600">First Name</label>
                <input type="text" class="member-first-name mt-0.5 block w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all" required placeholder="First name">
            </div>
            <div>
                <label class="block text-[11px] font-semibold text-slate-600">Last Name</label>
                <input type="text" class="member-last-name mt-0.5 block w-full px-2.5 py-1.5 border border-slate-300 rounded-lg text-xs focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all" required placeholder="Last name">
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
                <input type="checkbox" class="member-pwd rounded text-indigo-600 focus:ring-indigo-500 border-slate-300">
                <span>Person with Disability (PWD)</span>
            </label>
            <label class="flex items-center gap-2 cursor-pointer text-xs text-slate-700">
                <input type="checkbox" class="member-senior rounded text-indigo-600 focus:ring-indigo-500 border-slate-300">
                <span>Senior Citizen (60+ yrs)</span>
            </label>
        </div>
    `;

    container.appendChild(div);
    lucide.createIcons();
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

    // Extract members
    const memberElements = document.querySelectorAll('#members-container > div');
    const members = [];

    memberElements.forEach(el => {
        const fn = el.querySelector('.member-first-name').value.trim();
        const ln = el.querySelector('.member-last-name').value.trim();
        const rel = el.querySelector('.member-rel').value;
        const isPwd = el.querySelector('.member-pwd').checked;
        const isSen = el.querySelector('.member-senior').checked;

        if (fn && ln) {
            members.push({
                first_name: fn,
                last_name: ln,
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

        // Show confirmation view with animation
        document.getElementById('intake-form-container').classList.add('hidden');
        const confirmCard = document.getElementById('confirmation-card');
        confirmCard.classList.remove('hidden');
        confirmCard.classList.add('animate-scale-in');
        document.getElementById('confirmed-ref-number').textContent = data.reference_number;
        document.getElementById('track-confirmed-btn').href = `/track?ref=${encodeURIComponent(data.reference_number)}`;

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
    const submitBtn = document.getElementById('submit-intake-btn');
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<i data-lucide="send" class="w-4 h-4"></i><span>Submit Official Assistance Registration</span>`;
    lucide.createIcons();
}
