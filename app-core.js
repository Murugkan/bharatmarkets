/**
 * ONYX SYSTEM v8.9 - HARDENED PRODUCTION CORE
 * Requirements: Manual Insert, iPhone Optimized, Exact Line Counts
 */

// 1. GLOBAL STATE INITIALIZATION
window.S = JSON.parse(localStorage.getItem('bm_settings')) || {
    settings: { ghToken: '', ghRepo: '', _ghStatus: 'dim' }
};
window.SYMBOLS = JSON.parse(localStorage.getItem('bm_symbols')) || [];
window.FUND = {}; 
window.PRICES = {}; 

// 2. AUTHENTICATION & HEADERS
const ghHeaders = () => ({
    'Authorization': `token ${S.settings.ghToken}`,
    'Accept': 'application/vnd.github.v3+json',
    'Cache-Control': 'no-cache'
});

// 3. FILE HANDLING (Post-Selection Logic)
async function processSelectedFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        // Preserves exact content including comments/line breaks
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = (e) => reject(e);
        reader.readAsText(file);
    });
}

// 4. CLOUD OPERATIONS
async function ghPut(path, content, message) {
    const url = `https://api.github.com/repos/${S.settings.ghRepo}/contents/${path}`;
    const getRes = await fetch(url, { headers: ghHeaders() });
    let sha = null;
    if (getRes.ok) { const d = await getRes.json(); sha = d.sha; }

    return fetch(url, {
        method: 'PUT',
        headers: ghHeaders(),
        body: JSON.stringify({
            message,
            content: btoa(unescape(encodeURIComponent(content))), // Maintains special chars
            sha
        })
    });
}

async function ghFetchRaw(path) {
    const url = `https://raw.githubusercontent.com/${S.settings.ghRepo}/main/${path}?t=${Date.now()}`;
    const res = await fetch(url, { headers: ghHeaders() });
    return res.ok ? await res.json() : null;
}

// 5. STORAGE & UI UTILS
function saveSettings() { 
    localStorage.setItem('bm_settings', JSON.stringify(S)); 
}

function dataLog(msg, icon = '') {
    const log = document.getElementById('data-log');
    if (!log) return;
    const div = document.createElement('div');
    div.style.borderBottom = "1px solid #111";
    div.style.padding = "4px 0";
    div.innerHTML = `<span style="color:#444; font-size:9px;">[${new Date().toLocaleTimeString()}]</span> ${icon} <span style="font-size:10px;">${msg}</span>`;
    log.prepend(div);
}

function toast(msg) { alert(msg); }
function fmt(n) { return n ? n.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '0'; }

function loadState() {
    const syms = localStorage.getItem('bm_symbols');
    if (syms) window.SYMBOLS = JSON.parse(syms);
}

loadState();
