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

let currentScanToken = null;
let signatureCanvas = null;
let signatureCtx = null;
let isDrawing = false;
let hasSignature = false;

document.addEventListener("DOMContentLoaded", () => {
    checkOfflineQueue();
    window.addEventListener("online", syncOfflineQueue);
});

function checkOfflineQueue() {
    try {
        const queue = JSON.parse(localStorage.getItem("smartaid_offline_scans") || "[]");
        let banner = document.getElementById("offline-queue-badge");
        if (queue.length > 0) {
            if (!banner) {
                banner = document.createElement("div");
                banner.id = "offline-queue-badge";
                banner.className = "mb-4 p-3 rounded-xl bg-amber-50 border border-amber-300 text-amber-800 text-xs font-semibold flex items-center justify-between shadow-xs";
                const wrapper = document.querySelector(".max-w-2xl");
                if (wrapper) wrapper.insertBefore(banner, wrapper.firstChild);
            }
            banner.innerHTML = `
                <div class="flex items-center gap-2">
                    <span class="beacon-dot-amber"></span>
                    <span>Offline Mode: <strong>${queue.length}</strong> claims pending upload</span>
                </div>
                <button onclick="syncOfflineQueue()" class="btn-press px-3 py-1 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-bold text-xs">
                    Sync Now
                </button>
            `;
        } else if (banner) {
            banner.remove();
        }
    } catch(e) {}
}

async function syncOfflineQueue() {
    const queue = JSON.parse(localStorage.getItem("smartaid_offline_scans") || "[]");
    if (!queue.length) return;
    let synced = 0;
    let remaining = [];

    for (const item of queue) {
        try {
            const res = await fetch("/api/v1/disburse/verify-scan", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(item)
            });
            if (res.ok || res.status === 409) synced++;
            else remaining.push(item);
        } catch(e) {
            remaining.push(item);
        }
    }
    localStorage.setItem("smartaid_offline_scans", JSON.stringify(remaining));
    checkOfflineQueue();
    if (synced > 0) {
        alert(`Successfully synced ${synced} offline relief disbursement records!`);
    }
}

async function verifyClaimToken(token) {
    currentScanToken = token;
    hasSignature = false;
    const container = document.getElementById('scan-result-container');
    container.innerHTML = `
        <div class="p-6 rounded-2xl bg-white border-2 border-indigo-500 shadow-xl space-y-4 animate-scale-in">
            <div class="flex items-center justify-between pb-3 border-b border-slate-100">
                <div class="flex items-center gap-2.5">
                    <div class="w-8 h-8 rounded-lg bg-indigo-600 text-white flex items-center justify-center">
                        <i data-lucide="pen-tool" class="w-4 h-4"></i>
                    </div>
                    <div>
                        <h4 class="font-extrabold text-sm text-slate-900">Beneficiary Voucher E-Signature</h4>
                        <p class="text-[11px] text-slate-500">Token: <span class="font-mono text-indigo-600">${token.slice(0, 18)}...</span></p>
                    </div>
                </div>
                <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
                    Step 2: Sign & Release
                </span>
            </div>

            <div class="space-y-1.5">
                <div class="flex justify-between items-center text-xs">
                    <span class="text-slate-600 font-semibold">Sign below with finger or stylus:</span>
                    <button type="button" onclick="clearSignatureCanvas()" class="text-indigo-600 hover:text-indigo-800 font-bold text-[11px]">
                        Clear
                    </button>
                </div>
                <div class="border-2 border-dashed border-slate-300 rounded-xl bg-slate-50 relative overflow-hidden touch-none">
                    <canvas id="sig-canvas" width="450" height="110" class="w-full h-28 block bg-white cursor-crosshair"></canvas>
                    <div id="sig-hint" class="absolute inset-0 flex items-center justify-center pointer-events-none text-slate-400 text-xs italic">
                        Draw claimant signature here
                    </div>
                </div>
            </div>

            <div class="pt-2 flex items-center justify-between gap-3 border-t border-slate-100">
                <button type="button" onclick="clearScanResult()" class="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:bg-slate-100">
                    Cancel
                </button>
                <button type="button" onclick="submitFinalDisbursement('${token}')" id="confirm-disburse-btn"
                    class="btn-press flex-1 sm:flex-initial px-6 py-2.5 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-md flex items-center justify-center gap-1.5 transition-all">
                    <i data-lucide="check-circle" class="w-4 h-4"></i>
                    <span>Confirm & Release Package</span>
                </button>
            </div>
        </div>
    `;
    lucide.createIcons();
    setupSignatureCanvas();
}

function setupSignatureCanvas() {
    signatureCanvas = document.getElementById('sig-canvas');
    if (!signatureCanvas) return;
    signatureCtx = signatureCanvas.getContext('2d');
    signatureCtx.lineWidth = 2.5;
    signatureCtx.lineCap = 'round';
    signatureCtx.strokeStyle = '#1e1b4b';

    function getPos(e) {
        const rect = signatureCanvas.getBoundingClientRect();
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;
        return {
            x: (clientX - rect.left) * (signatureCanvas.width / rect.width),
            y: (clientY - rect.top) * (signatureCanvas.height / rect.height)
        };
    }

    function start(e) {
        isDrawing = true;
        hasSignature = true;
        document.getElementById('sig-hint')?.classList.add('hidden');
        const pos = getPos(e);
        signatureCtx.beginPath();
        signatureCtx.moveTo(pos.x, pos.y);
        e.preventDefault();
    }

    function move(e) {
        if (!isDrawing) return;
        const pos = getPos(e);
        signatureCtx.lineTo(pos.x, pos.y);
        signatureCtx.stroke();
        e.preventDefault();
    }

    function end() {
        isDrawing = false;
        signatureCtx.closePath();
    }

    signatureCanvas.addEventListener('mousedown', start);
    signatureCanvas.addEventListener('mousemove', move);
    signatureCanvas.addEventListener('mouseup', end);

    signatureCanvas.addEventListener('touchstart', start, { passive: false });
    signatureCanvas.addEventListener('touchmove', move, { passive: false });
    signatureCanvas.addEventListener('touchend', end);
}

function clearSignatureCanvas() {
    if (!signatureCanvas || !signatureCtx) return;
    signatureCtx.clearRect(0, 0, signatureCanvas.width, signatureCanvas.height);
    hasSignature = false;
    document.getElementById('sig-hint')?.classList.remove('hidden');
}

async function submitFinalDisbursement(token) {
    const btn = document.getElementById('confirm-disburse-btn');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = `<span class="animate-spin mr-1">⏳</span> Verifying & Recording...`;
    }

    const canvas = document.getElementById('sig-canvas');
    const sigData = (canvas && hasSignature) ? canvas.toDataURL('image/png') : null;

    try {
        const res = await fetch('/api/v1/disburse/verify-scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                claim_qr_hash: token,
                notes: 'Verified via Field Station Camera Scanner.',
                signature_data: sigData
            })
        });

        const data = await res.json();
        renderVerificationResponse(data, res.status);
    } catch (err) {
        const queue = JSON.parse(localStorage.getItem('smartaid_offline_scans') || '[]');
        queue.push({
            claim_qr_hash: token,
            notes: 'Offline release in remote area.',
            signature_data: sigData,
            timestamp: new Date().toISOString()
        });
        localStorage.setItem('smartaid_offline_scans', JSON.stringify(queue));
        checkOfflineQueue();

        const container = document.getElementById('scan-result-container');
        container.innerHTML = `
            <div class="p-6 rounded-2xl bg-amber-50 border-2 border-amber-500 shadow-xl space-y-3 animate-scale-in">
                <div class="flex items-center gap-3 text-amber-800">
                    <div class="w-10 h-10 rounded-xl bg-amber-600 text-white flex items-center justify-center">
                        <i data-lucide="cloud-off" class="w-6 h-6"></i>
                    </div>
                    <div>
                        <h4 class="font-bold text-sm text-amber-950">Claim Recorded in Offline Storage</h4>
                        <p class="text-xs text-amber-700">Digital signature captured and queued locally. It will automatically upload once cellular reception resumes.</p>
                    </div>
                </div>
                <div class="pt-2 flex justify-end">
                    <button onclick="clearScanResult()" class="btn-press px-4 py-2 rounded-lg text-xs font-semibold bg-amber-700 text-white">
                        Scan Next Beneficiary
                    </button>
                </div>
            </div>
        `;
        lucide.createIcons();
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
                    <div class="p-2.5 rounded-xl bg-white border border-emerald-200/80 col-span-2">
                        <p class="text-[10px] font-bold text-slate-400 uppercase">Liquidation Proof / E-Signature</p>
                        <p class="font-semibold text-emerald-700 mt-0.5 flex items-center gap-1.5">
                            <i data-lucide="check-check" class="w-4 h-4 text-emerald-600"></i>
                            <span>${data.has_signature ? "Digitally Signed by Beneficiary & Recorded in Audit Trail" : "Verified by Field Officer"}</span>
                        </p>
                    </div>
                </div>

                <div class="pt-3 border-t border-emerald-200 flex justify-end relative z-10">
                    <button onclick="clearScanResult()" class="btn-press px-5 py-2.5 rounded-xl text-xs font-bold bg-emerald-600 hover:bg-emerald-700 text-white shadow-md transition-all">
                        Scan Next Beneficiary
                    </button>
                </div>

            </div>
        `;
        if (typeof fireConfetti === 'function') {
            fireConfetti({ colors: ['#10b981', '#059669', '#34d399', '#fbbf24', '#6366f1'], count: 90 });
        }
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
