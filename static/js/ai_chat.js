/**
 * SmartAid AI Copilot - Bilingual (EN / CEB) Conversational Assistant
 * Injects a floating intelligent copilot into any page to assist
 * beneficiaries and caseworkers with instant eligibility, live tracking,
 * and policy explanations.
 */

(function () {
    if (window.__SMARTAID_AI_COPILOT_LOADED__) return;
    window.__SMARTAID_AI_COPILOT_LOADED__ = true;

    let currentLanguage = 'en';
    let isChatOpen = false;

    function initAICopilotUI() {
        const container = document.createElement('div');
        container.id = 'smartaid-copilot-root';
        container.className = 'fixed bottom-5 right-5 z-50 flex flex-col items-end pointer-events-none font-sans';

        container.innerHTML = `
            <!-- Chat Window Panel -->
            <div id="copilot-window" class="pointer-events-auto w-[92vw] sm:w-96 max-w-sm h-[520px] max-h-[82vh] bg-white rounded-3xl shadow-2xl border border-slate-200/90 flex flex-col overflow-hidden mb-3.5 transition-all duration-300 transform scale-95 opacity-0 pointer-events-none origin-bottom-right">
                
                <!-- Chat Window Header -->
                <div class="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-4 flex items-center justify-between border-b border-indigo-500/20 shadow-md">
                    <div class="flex items-center gap-2.5">
                        <div class="w-8 h-8 rounded-xl bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center shadow-inner shadow-white/30">
                            <i data-lucide="sparkles" class="w-4 h-4 text-amber-300"></i>
                        </div>
                        <div>
                            <div class="flex items-center gap-1.5">
                                <h3 class="font-bold text-sm text-white tracking-tight">SmartAid AI Copilot</h3>
                                <span class="flex h-2 w-2 relative">
                                    <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                                    <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                                </span>
                            </div>
                            <p class="text-[10.5px] text-indigo-200/80 font-medium">LGU Maramag Welfare Assistant</p>
                        </div>
                    </div>
                    
                    <div class="flex items-center gap-1">
                        <button id="copilot-lang-toggle" onclick="toggleCopilotLanguage()" class="px-2 py-0.5 rounded-lg text-[11px] font-bold bg-indigo-900/80 hover:bg-indigo-800 text-indigo-200 border border-indigo-700/50 transition-colors" title="Switch English / Bisaya">
                            EN
                        </button>
                        <button onclick="toggleCopilotWindow()" class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors" title="Close chat">
                            <i data-lucide="x" class="w-4 h-4"></i>
                        </button>
                    </div>
                </div>

                <!-- Chat Messages History Area -->
                <div id="copilot-messages" class="flex-1 p-4 overflow-y-auto space-y-3.5 bg-slate-50/60 text-xs">
                    <!-- Dynamic Messages Inserted Here -->
                </div>

                <!-- Suggested Quick Query Chips Area -->
                <div id="copilot-suggestions" class="px-3.5 py-2 bg-white/90 border-t border-slate-100 flex flex-wrap gap-1.5 overflow-x-auto">
                    <!-- Suggested Chips Inserted Here -->
                </div>

                <!-- Chat Input Footer -->
                <form id="copilot-form" onsubmit="handleCopilotSubmit(event)" class="p-3 bg-white border-t border-slate-200 flex items-center gap-2">
                    <input type="text" id="copilot-input" autocomplete="off" placeholder="Ask in English or Bisaya..." 
                        class="flex-1 px-3.5 py-2 bg-slate-100/80 hover:bg-slate-100 focus:bg-white border border-slate-200 rounded-xl text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-600 transition-all">
                    <button type="submit" id="copilot-send-btn" class="p-2 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white shadow-md shadow-indigo-500/20 transition-all flex items-center justify-center">
                        <i data-lucide="send" class="w-4 h-4"></i>
                    </button>
                </form>

            </div>

            <!-- Floating Launcher Button -->
            <button id="copilot-launcher" onclick="toggleCopilotWindow()" class="pointer-events-auto group relative flex items-center gap-2.5 px-4 py-3 rounded-full bg-gradient-to-r from-slate-900 via-indigo-900 to-slate-900 hover:from-slate-800 hover:to-indigo-800 text-white shadow-xl shadow-indigo-950/30 border border-indigo-400/30 transition-all duration-300 hover:scale-105 active:scale-95">
                <div class="relative w-7 h-7 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 flex items-center justify-center text-white shadow-sm">
                    <i data-lucide="sparkles" class="w-4 h-4 text-amber-300"></i>
                    <span class="absolute -top-0.5 -right-0.5 flex h-2 w-2">
                        <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                        <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-400"></span>
                    </span>
                </div>
                <div class="text-left pr-1">
                    <p class="text-xs font-black tracking-tight leading-tight">AI Copilot</p>
                    <p class="text-[9.5px] text-indigo-300 font-medium leading-none">Maramag MSWDO</p>
                </div>
            </button>
        `;

        document.body.appendChild(container);
        if (window.lucide) lucide.createIcons();

        const savedLang = localStorage.getItem('smartaid_lang');
        if (savedLang === 'ceb') {
            currentLanguage = 'ceb';
            updateLangButton();
        }

        appendInitialWelcome();
    }

    function appendInitialWelcome() {
        const isCeb = (currentLanguage === 'ceb');
        const welcomeText = isCeb ?
            "Kumusta! Ako ang **SmartAid AI Assistant** sa LGU Maramag. Makatabang ko nimo sa pagsusi sa imong reference status (`APP-2026-XXXXX`), pagsabot sa criteria, o pag-aplay ug hinabang." :
            "Hello! I am your **SmartAid AI Copilot** for LGU Maramag MSWDO. I can verify your application reference status (e.g. `APP-2026-00101`), explain the ₱15,000 income threshold, or describe how MCDA rankings are computed.";

        const initialChips = isCeb ?
            ["Susiha ang APP-2026-00101", "Pila ang income ceiling?", "Unsaon pag-aplay?", "MCDA Criteria"] :
            ["Check status APP-2026-00101", "What is the income ceiling?", "How to apply?", "MCDA Criteria Breakdown"];

        renderAssistantMessage(welcomeText);
        renderSuggestions(initialChips);
    }

    function formatMarkdown(text) {
        let escaped = text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
        
        escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        escaped = escaped.replace(/`([^`]+)`/g, '<code class="px-1 py-0.5 bg-slate-100 font-mono text-[11px] font-bold text-indigo-700 rounded border border-slate-200">$1</code>');
        escaped = escaped.replace(/^### (.*$)/gim, '<h4 class="font-black text-slate-900 mt-2 mb-1">$1</h4>');
        escaped = escaped.replace(/^- (.*$)/gim, '<li class="ml-3 list-disc text-slate-700">$1</li>');
        escaped = escaped.replace(/^\d+\. (.*$)/gim, '<li class="ml-3 list-decimal text-slate-700">$1</li>');
        escaped = escaped.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="font-semibold text-indigo-600 hover:underline">$1</a>');
        escaped = escaped.replace(/\n/g, '<br>');

        return escaped;
    }

    function renderUserMessage(text) {
        const msgContainer = document.getElementById('copilot-messages');
        const bubble = document.createElement('div');
        bubble.className = 'flex justify-end animate-slide-up';
        bubble.innerHTML = `
            <div class="max-w-[82%] px-3.5 py-2.5 rounded-2xl rounded-tr-xs bg-indigo-600 text-white font-medium shadow-sm leading-relaxed">
                ${formatMarkdown(text)}
            </div>
        `;
        msgContainer.appendChild(bubble);
        msgContainer.scrollTop = msgContainer.scrollHeight;
    }

    function renderAssistantMessage(text, household = null) {
        const msgContainer = document.getElementById('copilot-messages');
        const bubble = document.createElement('div');
        bubble.className = 'flex items-start gap-2 animate-slide-up';

        let extraCard = '';
        if (household && household.reference_number) {
            extraCard = `
                <div class="mt-2.5 p-2.5 rounded-xl bg-white border border-indigo-100 shadow-2xs flex items-center justify-between">
                    <div>
                        <span class="text-[10px] font-mono font-bold text-indigo-600">${household.reference_number}</span>
                        <p class="font-bold text-slate-900">${household.head_name}</p>
                    </div>
                    <a href="/track?ref=${encodeURIComponent(household.reference_number)}" class="btn-press px-2.5 py-1 rounded-lg text-[10.5px] font-bold bg-indigo-600 text-white hover:bg-indigo-700 flex items-center gap-1">
                        <i data-lucide="ticket" class="w-3 h-3"></i>
                        <span>View Pass</span>
                    </a>
                </div>
            `;
        }

        bubble.innerHTML = `
            <div class="w-6 h-6 rounded-lg bg-gradient-to-tr from-indigo-600 to-purple-600 text-white flex items-center justify-center flex-shrink-0 mt-0.5 shadow-xs">
                <i data-lucide="bot" class="w-3.5 h-3.5"></i>
            </div>
            <div class="max-w-[85%] px-3.5 py-2.5 rounded-2xl rounded-tl-xs bg-white text-slate-800 border border-slate-200/80 shadow-xs leading-relaxed space-y-1">
                ${formatMarkdown(text)}
                ${extraCard}
            </div>
        `;
        msgContainer.appendChild(bubble);
        msgContainer.scrollTop = msgContainer.scrollHeight;
        if (window.lucide) lucide.createIcons();
    }

    function renderSuggestions(suggestions) {
        const sugContainer = document.getElementById('copilot-suggestions');
        if (!suggestions || suggestions.length === 0) {
            sugContainer.innerHTML = '';
            sugContainer.classList.add('hidden');
            return;
        }
        sugContainer.classList.remove('hidden');
        sugContainer.innerHTML = suggestions.map(s => `
            <button type="button" onclick="sendSuggestionQuery('${s.replace(/'/g, "\\'")}')" class="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-slate-100 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 border border-slate-200 hover:border-indigo-300 transition-all flex items-center gap-1">
                <span>${s}</span>
            </button>
        `).join('');
    }

    window.sendSuggestionQuery = function (query) {
        const input = document.getElementById('copilot-input');
        input.value = query;
        document.getElementById('copilot-form').dispatchEvent(new Event('submit', { cancelable: true }));
    };

    window.toggleCopilotWindow = function () {
        const win = document.getElementById('copilot-window');
        isChatOpen = !isChatOpen;
        if (isChatOpen) {
            win.classList.remove('scale-95', 'opacity-0', 'pointer-events-none');
            win.classList.add('scale-100', 'opacity-100');
            setTimeout(() => {
                document.getElementById('copilot-input')?.focus();
            }, 100);
        } else {
            win.classList.remove('scale-100', 'opacity-100');
            win.classList.add('scale-95', 'opacity-0', 'pointer-events-none');
        }
    };

    window.toggleCopilotLanguage = function () {
        currentLanguage = (currentLanguage === 'en') ? 'ceb' : 'en';
        updateLangButton();
        const notice = currentLanguage === 'ceb' ?
            "Nabalhin sa **Binisaya**. Unsa akong ikatabang kanimo kabahin sa SmartAid?" :
            "Switched to **English**. How can I assist you with SmartAid today?";
        renderAssistantMessage(notice);
        renderSuggestions(currentLanguage === 'ceb' ?
            ["Susiha ang APP-2026-00101", "Pila ang income ceiling?", "Unsaon pag-aplay?"] :
            ["Check status APP-2026-00101", "Income ceiling limit", "How to apply?"]
        );
    };

    function updateLangButton() {
        const btn = document.getElementById('copilot-lang-toggle');
        if (btn) btn.textContent = currentLanguage.toUpperCase();
    }

    window.handleCopilotSubmit = async function (e) {
        e.preventDefault();
        const input = document.getElementById('copilot-input');
        const message = input.value.trim();
        if (!message) return;

        input.value = '';
        renderUserMessage(message);

        const msgContainer = document.getElementById('copilot-messages');
        const typingId = 'copilot-typing-indicator';
        const typing = document.createElement('div');
        typing.id = typingId;
        typing.className = 'flex items-center gap-2 text-slate-400 text-xs italic pl-8';
        typing.innerHTML = `
            <span class="animate-bounce">●</span>
            <span class="animate-bounce delay-100">●</span>
            <span class="animate-bounce delay-200">●</span>
            <span class="ml-1 text-[11px]">Analyzing registry...</span>
        `;
        msgContainer.appendChild(typing);
        msgContainer.scrollTop = msgContainer.scrollHeight;

        try {
            const res = await fetch('/api/v1/ai/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    language: currentLanguage
                })
            });

            const data = await res.json();
            document.getElementById(typingId)?.remove();

            if (res.ok) {
                renderAssistantMessage(data.reply, data.household);
                renderSuggestions(data.suggestions || []);
            } else {
                renderAssistantMessage("Apologies, I encountered an issue accessing the registry. Please verify your connection or try again.");
            }
        } catch (err) {
            document.getElementById(typingId)?.remove();
            renderAssistantMessage(`Network error connecting to SmartAid AI: ${err.message}`);
        }
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAICopilotUI);
    } else {
        initAICopilotUI();
    }

})();
