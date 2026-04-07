/**
 * ONYX SYSTEM v8.7 - HARDENED PRODUCTION CORE
 * Fixed: Manual Credential Capture & Persistence
 */

// 1. GLOBAL STATE INITIALIZATION
window.S = JSON.parse(localStorage.getItem('bm_settings')) || {
    settings: { ghToken: '', ghRepo: '', _ghStatus: 'dim' }
};
window.SYMBOLS = JSON.parse(localStorage.getItem('bm_symbols')) || [];
window.FUND = {}; 
window.PRICES = {}; 

// 2. AUTHENTICATION (Captures manual inputs from UI)
const ghHeaders = () => ({
    'Authorization': `token ${S.settings.ghToken}`,
    'Accept': 'application/vnd.github.v3+json',
    'Cache-Control': 'no-cache'
});

// 3. CLOUD SYNC LOGIC
async function ghFetchRaw(path) {
    if (!S.settings.ghToken || !S.settings.ghRepo) {
        dataLog("Missing Config for Fetch", "⚠️");
        return null;
    }
    const url = `https://raw.githubusercontent.com/${S.settings.ghRepo}/main/${path}?t=${Date.now()}`;
    try {
        const res = await fetch(url, { headers: ghHeaders() });
        if (res.ok) return await res.json();
        dataLog(`Fetch Failed: ${res.status}`, "❌");
        return null;
    } catch (e) {
        dataLog(`Network Error: ${e.message}`, "⚠️");
        return null;
    }
}

// 4. STORAGE MANAGEMENT
function saveSettings() { 
    localStorage.setItem('bm_settings', JSON.stringify(S)); 
    if (typeof updateStatusDots === 'function') updateStatusDots();
}

function saveSymbols() {
    localStorage.setItem('bm_symbols', JSON.stringify(window.SYMBOLS));
}

// 5. UI FEEDBACK & DEBUGGING
function dataLog(msg, icon = '') {
    const log = document.getElementById('data-log');
    if (!log) return;
    const div = document.createElement('div');
    div.style.borderBottom = "1px solid #111";
    div.style.padding = "4px 0";
    div.innerHTML = `<span style="color:#555; font-size:9px;">[${new Date().toLocaleTimeString()}]</span> ${icon} <span style="font-size:10px;">${msg}</span>`;
    log.prepend(div);
    
    // Also push to debug window if visible
    const dbg = document.getElementById('debug-window');
    if (dbg && dbg.style.display !== 'none') {
        dbg.innerHTML += `<br>> [LOG] ${msg}`;
    }
}

// 6. UTILITIES
function toast(msg) { alert(msg); }
function fmt(n) { return n ? n.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '0'; }

function loadState() {
    const syms = localStorage.getItem('bm_symbols');
    if (syms) window.SYMBOLS = JSON.parse(syms);
    const sets = localStorage.getItem('bm_settings');
    if (sets) window.S = JSON.parse(sets);
}

function requirePAT() {
    if (!S.settings.ghToken || !S.settings.ghRepo) {
        toast("Missing GitHub Configuration");
        return false;
    }
    return true;
}

// Initialize on load
loadState();
