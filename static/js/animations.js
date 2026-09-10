/**
 * SmartAid Civic Tech Animation & Micro-Interactions Suite
 * Hardware-accelerated, lightweight vanilla JavaScript utilities.
 */

// =========================================================================
// 1. ROLLING NUMBER COUNTER (ODOMETER EFFECT)
// =========================================================================

/**
 * Animate a numeric element smoothly rolling up from its current value to the target.
 * @param {HTMLElement|string} el - The DOM element or element ID.
 * @param {number} target - The final numeric value.
 * @param {number} duration - Animation duration in ms (default 850ms).
 * @param {string} prefix - Optional prefix (e.g. '₱').
 * @param {string} suffix - Optional suffix (e.g. '%').
 * @param {boolean} isCurrency - Whether to format with commas.
 */
function animateCounter(el, target, duration = 850, prefix = '', suffix = '', isCurrency = false) {
    const element = typeof el === 'string' ? document.getElementById(el) : el;
    if (!element) return;

    // Check prefers-reduced-motion
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        element.textContent = `${prefix}${isCurrency ? target.toLocaleString() : target}${suffix}`;
        return;
    }

    // Extract current numeric value if already present
    let rawText = element.textContent.replace(/[^0-9.-]+/g, '');
    let start = parseFloat(rawText) || 0;
    let startTime = null;

    function step(timestamp) {
        if (!startTime) startTime = timestamp;
        const elapsed = timestamp - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Ease Out Quart: 1 - (1 - t)^4
        const easeProgress = 1 - Math.pow(1 - progress, 4);
        const current = start + (target - start) * easeProgress;

        let formatted = '';
        if (isCurrency) {
            formatted = Math.round(current).toLocaleString();
        } else if (Number.isInteger(target)) {
            formatted = Math.round(current);
        } else {
            formatted = current.toFixed(4);
        }

        element.textContent = `${prefix}${formatted}${suffix}`;

        if (progress < 1) {
            window.requestAnimationFrame(step);
        } else {
            element.textContent = `${prefix}${isCurrency ? target.toLocaleString() : target}${suffix}`;
        }
    }

    window.requestAnimationFrame(step);
}

// =========================================================================
// 2. CANVAS CONFETTI CELEBRATION SYSTEM (ZERO-DEPENDENCY)
// =========================================================================

/**
 * Trigger a festive confetti burst celebration on a full-screen canvas.
 * @param {Object} options - Custom options (colors, count, origin).
 */
function fireConfetti(options = {}) {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        return;
    }

    let canvas = document.getElementById('smart-confetti-canvas');
    if (!canvas) {
        canvas = document.createElement('canvas');
        canvas.id = 'smart-confetti-canvas';
        canvas.style.position = 'fixed';
        canvas.style.top = '0';
        canvas.style.left = '0';
        canvas.style.width = '100vw';
        canvas.style.height = '100vh';
        canvas.style.pointerEvents = 'none';
        canvas.style.zIndex = '99999';
        document.body.appendChild(canvas);
    }

    const ctx = canvas.getContext('2d');
    const width = (canvas.width = window.innerWidth);
    const height = (canvas.height = window.innerHeight);

    const colors = options.colors || [
        '#6366f1', // Indigo
        '#10b981', // Emerald
        '#f59e0b', // Amber
        '#ec4899', // Pink
        '#06b6d4', // Cyan
        '#8b5cf6', // Purple
        '#3b82f6'  // Blue
    ];

    const particleCount = options.count || 90;
    const originX = options.originX !== undefined ? options.originX : width * 0.5;
    const originY = options.originY !== undefined ? options.originY : height * 0.35;

    const particles = [];
    for (let i = 0; i < particleCount; i++) {
        const angle = Math.random() * Math.PI * 2;
        const velocity = 6 + Math.random() * 12;
        particles.push({
            x: originX,
            y: originY,
            vx: Math.cos(angle) * velocity,
            vy: Math.sin(angle) * velocity - 3,
            size: 6 + Math.random() * 6,
            color: colors[Math.floor(Math.random() * colors.length)],
            rotation: Math.random() * 360,
            rotationSpeed: (Math.random() - 0.5) * 15,
            opacity: 1,
            decay: 0.012 + Math.random() * 0.015,
            gravity: 0.38,
            shape: Math.random() > 0.4 ? 'rect' : 'circle'
        });
    }

    let animationId = null;

    function render() {
        ctx.clearRect(0, 0, width, height);

        let activeCount = 0;
        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];
            if (p.opacity <= 0) continue;
            activeCount++;

            p.x += p.vx;
            p.y += p.vy;
            p.vy += p.gravity;
            p.vx *= 0.98;
            p.rotation += p.rotationSpeed;
            p.opacity -= p.decay;

            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate((p.rotation * Math.PI) / 180);
            ctx.globalAlpha = Math.max(p.opacity, 0);
            ctx.fillStyle = p.color;

            if (p.shape === 'rect') {
                ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.65);
            } else {
                ctx.beginPath();
                ctx.arc(0, 0, p.size / 2, 0, Math.PI * 2);
                ctx.fill();
            }

            ctx.restore();
        }

        if (activeCount > 0) {
            animationId = window.requestAnimationFrame(render);
        } else {
            ctx.clearRect(0, 0, width, height);
            if (canvas && canvas.parentNode) {
                canvas.parentNode.removeChild(canvas);
            }
        }
    }

    animationId = window.requestAnimationFrame(render);
}

// =========================================================================
// 3. ANIMATED TOAST NOTIFICATION WITH TIME PROGRESS METER
// =========================================================================

/**
 * Display a floating toast with entrance spring and animated countdown bar.
 * @param {string} message - Toast message.
 * @param {string} type - 'success', 'error', 'info', or 'warning'.
 * @param {number} duration - Display time in ms (default 3200ms).
 */
function showAnimatedToast(message, type = 'success', duration = 3200) {
    let container = document.getElementById('smart-toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'smart-toast-container';
        container.className = 'fixed bottom-6 right-6 z-50 flex flex-col gap-2 pointer-events-none';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = 'pointer-events-auto flex flex-col overflow-hidden rounded-2xl shadow-2xl border backdrop-blur-md transition-all duration-300 transform translate-y-4 opacity-0 max-w-sm';

    let bgClass = '';
    let icon = '';
    let barColor = '';

    if (type === 'success') {
        bgClass = 'bg-slate-900/95 text-white border-emerald-500/40';
        icon = '<span class="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>';
        barColor = 'bg-emerald-500';
    } else if (type === 'error') {
        bgClass = 'bg-rose-900/95 text-white border-rose-500/40';
        icon = '<span class="w-2.5 h-2.5 rounded-full bg-rose-400"></span>';
        barColor = 'bg-rose-400';
    } else {
        bgClass = 'bg-slate-900/95 text-white border-indigo-500/40';
        icon = '<span class="w-2.5 h-2.5 rounded-full bg-indigo-400"></span>';
        barColor = 'bg-indigo-500';
    }

    toast.className += ` ${bgClass}`;
    toast.innerHTML = `
        <div class="px-4 py-3 flex items-center gap-2.5 text-xs font-semibold">
            ${icon}
            <span class="flex-1 leading-snug">${message}</span>
        </div>
        <div class="w-full bg-white/10 h-1 overflow-hidden">
            <div class="toast-progress-meter ${barColor} h-1 transition-all" style="width: 100%; transition: width ${duration}ms linear;"></div>
        </div>
    `;

    container.appendChild(toast);

    // Trigger entrance transition
    requestAnimationFrame(() => {
        toast.classList.remove('translate-y-4', 'opacity-0');
        toast.classList.add('translate-y-0', 'opacity-100');
        // Trigger countdown bar
        setTimeout(() => {
            const meter = toast.querySelector('.toast-progress-meter');
            if (meter) meter.style.width = '0%';
        }, 50);
    });

    // Dismissal
    setTimeout(() => {
        toast.classList.add('opacity-0', 'translate-y-2');
        setTimeout(() => {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 300);
    }, duration);
}

// Global aliases for compatibility
window.showToast = showAnimatedToast;
window.showAnimatedToast = showAnimatedToast;
window.animateCounter = animateCounter;
window.fireConfetti = fireConfetti;
