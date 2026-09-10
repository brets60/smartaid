// SmartAid Field QR Scanner Controller

let html5QrCode = null;
let isScanning = false;

document.addEventListener('DOMContentLoaded', () => {
    // Check if Html5Qrcode is loaded
    if (typeof Html5Qrcode !== 'undefined') {
        html5QrCode = new Html5Qrcode("reader");
    }
});

async function startScanner() {
    if (!html5QrCode) {
        alert("Camera QR Scanner library is still initializing. Please check network or use manual code entry.");
        return;
    }

    const idlePlaceholder = document.getElementById('camera-idle-placeholder');
    const startBtn = document.getElementById('start-scan-btn');
    const stopBtn = document.getElementById('stop-scan-btn');

    try {
        const qrConfig = { fps: 10, qrbox: { width: 250, height: 250 } };

        await html5QrCode.start(
            { facingMode: "environment" },
            qrConfig,
            onScanSuccess,
            onScanError
        );

        isScanning = true;
        idlePlaceholder.classList.add('hidden');
        startBtn.classList.add('hidden');
        stopBtn.classList.remove('hidden');
        
        // HUD updates
        document.getElementById('scanner-laser')?.classList.remove('hidden');
        const hudText = document.getElementById('hud-status-text');
        const hudDot = document.getElementById('hud-status-dot');
        if (hudText) hudText.textContent = 'OPTICAL SENSOR ACTIVE';
        if (hudDot) hudDot.className = 'beacon-dot';
    } catch (err) {
        console.warn("Camera start failed, trying any available camera:", err);
        try {
            const cameras = await Html5Qrcode.getCameras();
            if (cameras && cameras.length) {
                await html5QrCode.start(cameras[0].id, { fps: 10, qrbox: 250 }, onScanSuccess, onScanError);
                isScanning = true;
                idlePlaceholder.classList.add('hidden');
                startBtn.classList.add('hidden');
                stopBtn.classList.remove('hidden');
                
                // HUD updates
                document.getElementById('scanner-laser')?.classList.remove('hidden');
                const hudText = document.getElementById('hud-status-text');
                const hudDot = document.getElementById('hud-status-dot');
                if (hudText) hudText.textContent = 'OPTICAL SENSOR ACTIVE';
                if (hudDot) hudDot.className = 'beacon-dot';
            } else {
                alert("No camera device found on this system. You can verify vouchers using the manual entry box below.");
            }
        } catch (e) {
            alert("Camera access denied or unavailable. Please use the manual entry fallback below.");
        }
    }
}

async function stopScanner() {
    if (html5QrCode && isScanning) {
        await html5QrCode.stop();
        isScanning = false;
        document.getElementById('camera-idle-placeholder').classList.remove('hidden');
        document.getElementById('start-scan-btn').classList.remove('hidden');
        document.getElementById('stop-scan-btn').classList.add('hidden');
        
        // HUD updates
        document.getElementById('scanner-laser')?.classList.add('hidden');
        const hudText = document.getElementById('hud-status-text');
        const hudDot = document.getElementById('hud-status-dot');
        if (hudText) hudText.textContent = 'STANDBY';
        if (hudDot) hudDot.className = 'beacon-dot-amber';
    }
}

function onScanSuccess(decodedText, decodedResult) {
    // Beep / audio feedback if possible
    playScanBeep();
    // Stop camera or pause to avoid rapid multi-fires
    verifyClaimToken(decodedText);
}

function onScanError(errorMessage) {
    // Routine non-matching frame, no action needed
}

function handleManualVerify(e) {
    e.preventDefault();
    const token = document.getElementById('manual-token-input').value.trim();
    if (token) {
        verifyClaimToken(token);
    }
}

async function verifyClaimToken(token) {
    const container = document.getElementById('scan-result-container');
    container.innerHTML = `
        <div class="p-6 rounded-2xl bg-slate-100 text-center text-slate-500 space-y-2 animate-pulse">
            <span class="animate-spin inline-block text-xl">⏳</span>
            <p class="text-xs font-semibold">Validating cryptographic QR claim token...</p>
        </div>
    `;

    try {
        const res = await fetch('/api/v1/disburse/verify-scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                claim_qr_hash: token,
                notes: "Verified via Field Station Camera Scanner."
            })
        });

        const data = await res.json();
        renderVerificationResponse(data, res.status);

    } catch (err) {
        container.innerHTML = `
            <div class="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold animate-shake">
                Network connection error: ${err.message}
            </div>
        `;
    }
}

function renderVerificationResponse(data, httpStatus) {
    const container = document.getElementById('scan-result-container');

    if (data.status === "SUCCESS") {
        // GREEN CARD: SUCCESSFUL DISBURSEMENT RECORDED
        container.innerHTML = `
            <div class="p-6 sm:p-7 rounded-2xl bg-emerald-50 border-2 border-emerald-500 shadow-2xl space-y-5 animate-scale-in relative overflow-hidden">
                <div class="absolute top-0 right-0 w-40 h-40 bg-emerald-400/10 rounded-full blur-2xl pointer-events-none"></div>

                <div class="flex items-center justify-between pb-3 border-b border-emerald-200 relative z-10">
                    <div class="flex items-center gap-3 text-emerald-800">
                        <div class="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center shadow-lg shadow-emerald-500/30 animate-bounce-success">
                            <i data-lucide="check" class="w-6 h-6"></i>
                        </div>
                        <div>
                            <h3 class="font-black text-base sm:text-lg uppercase tracking-tight text-emerald-950">Disbursement Verified & Approved!</h3>
                            <p class="text-xs text-emerald-700 font-medium">Relief package successfully issued to beneficiary</p>
                        </div>
                    </div>
                    <span class="inline-flex items-center gap-1 px-3 py-1 rounded-full bg-emerald-600 text-white text-xs font-bold uppercase shadow-sm">
                        <span class="beacon-dot bg-white"></span>
                        Claimed
                    </span>
                </div>

                <div class="grid grid-cols-2 gap-3 text-xs relative z-10">
                    <div class="p-2.5 rounded-xl bg-white border border-emerald-200/80">
                        <p class="text-[10px] font-bold text-slate-400 uppercase">Beneficiary Head</p>
                        <p class="font-extrabold text-slate-900 text-sm mt-0.5">${data.head_name}</p>
                    </div>
                    <div class="p-2.5 rounded-xl bg-white border border-emerald-200/80">
                        <p class="text-[10px] font-bold text-slate-400 uppercase">Reference Number</p>
                        <p class="font-mono font-bold text-indigo-600 text-sm mt-0.5">${data.reference_number}</p>
                    </div>
                    <div class="p-2.5 rounded-xl bg-white border border-emerald-200/80">
                        <p class="text-[10px] font-bold text-slate-400 uppercase">Barangay & Zone</p>
                        <p class="font-semibold text-slate-700 mt-0.5">${data.barangay}, ${data.purok_zone}</p>
                    </div>
                    <div class="p-2.5 rounded-xl bg-white border border-emerald-200/80">
                        <p class="text-[10px] font-bold text-slate-400 uppercase">Relief Package Value</p>
                        <p class="font-bold text-slate-900 mt-0.5">₱${(data.budget_amount || 5000).toLocaleString()} / Food Pack</p>
                    </div>
                    <div class="p-2.5 rounded-xl bg-white border border-emerald-200/80">
                        <p class="text-[10px] font-bold text-slate-400 uppercase">Verification Timestamp</p>
                        <p class="font-mono text-slate-600 mt-0.5">${data.disbursed_at}</p>
                    </div>
                    <div class="p-2.5 rounded-xl bg-white border border-emerald-200/80">
                        <p class="text-[10px] font-bold text-slate-400 uppercase">Field Verifier</p>
                        <p class="font-semibold text-slate-700 mt-0.5">${data.verified_by}</p>
                    </div>
                </div>

                <div class="pt-3 border-t border-emerald-200 flex justify-end relative z-10">
                    <button onclick="clearScanResult()" class="btn-press px-5 py-2.5 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-md transition-all">
                        Scan Next Beneficiary
                    </button>
                </div>

            </div>
        `;
    } else if (data.status === "ALREADY_CLAIMED") {
        // RED CARD: DOUBLE-CLAIM PREVENTION TRIGGERED
        container.innerHTML = `
            <div class="p-6 rounded-2xl bg-rose-50 border-2 border-rose-500 shadow-2xl space-y-4 animate-shake">
                
                <div class="flex items-center justify-between pb-3 border-b border-rose-200">
                    <div class="flex items-center gap-3 text-rose-800">
                        <div class="w-10 h-10 rounded-xl bg-rose-600 text-white flex items-center justify-center shadow-lg shadow-rose-500/30">
                            <i data-lucide="alert-octagon" class="w-6 h-6"></i>
                        </div>
                        <div>
                            <h3 class="font-black text-base uppercase tracking-tight text-rose-950">Double-Claim Prevented!</h3>
                            <p class="text-xs text-rose-700 font-medium">${data.message}</p>
                        </div>
                    </div>
                    <span class="px-2.5 py-1 rounded-full bg-rose-600 text-white text-xs font-bold uppercase shadow-sm">
                        Duplicate
                    </span>
                </div>

                <div class="p-4 rounded-xl bg-white border border-rose-200 text-xs space-y-2 shadow-inner">
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <span class="text-slate-400">Beneficiary:</span>
                            <strong class="text-slate-900 block mt-0.5">${data.head_name}</strong>
                        </div>
                        <div>
                            <span class="text-slate-400">Reference:</span>
                            <strong class="text-slate-900 block font-mono mt-0.5">${data.reference_number}</strong>
                        </div>
                        <div>
                            <span class="text-slate-400">Claimed At:</span>
                            <strong class="text-rose-700 block font-mono mt-0.5">${data.disbursed_at}</strong>
                        </div>
                        <div>
                            <span class="text-slate-400">Disbursed By:</span>
                            <strong class="text-slate-900 block mt-0.5">${data.verified_by}</strong>
                        </div>
                    </div>
                </div>

                <div class="pt-2 flex justify-end">
                    <button onclick="clearScanResult()" class="btn-press px-5 py-2.5 rounded-xl text-xs font-bold bg-slate-800 hover:bg-slate-700 text-white shadow-sm transition-all">
                        Dismiss Alert & Ready Next
                    </button>
                </div>

            </div>
        `;
    } else {
        // RED CARD: INVALID OR NOT APPROVED
        container.innerHTML = `
            <div class="p-6 rounded-2xl bg-rose-50 border border-rose-300 shadow-md space-y-3 animate-shake">
                <div class="flex items-center gap-2 text-rose-800">
                    <i data-lucide="x-circle" class="w-6 h-6 text-rose-600"></i>
                    <h4 class="font-bold text-sm">Voucher Verification Rejected</h4>
                </div>
                <p class="text-xs text-rose-700 leading-relaxed">${data.message || 'Token not recognized in database.'}</p>
                <div class="pt-2 flex justify-end">
                    <button onclick="clearScanResult()" class="btn-press px-4 py-2 rounded-lg text-xs font-semibold bg-slate-700 hover:bg-slate-800 text-white transition-all">
                        Try Again
                    </button>
                </div>
            </div>
        `;
    }

    lucide.createIcons();
}

function clearScanResult() {
    document.getElementById('scan-result-container').innerHTML = '';
    document.getElementById('manual-token-input').value = '';
}

function playScanBeep() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.frequency.value = 880;
        gain.gain.value = 0.1;
        osc.start();
        setTimeout(() => {
            osc.stop();
            audioCtx.close();
        }, 120);
    } catch(e) {}
}
