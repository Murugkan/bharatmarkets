/**
 * ONYX SYSTEM v8.2 - COMPLETE PRODUCTION CORE
 * Supporting: data.html (DQA, Imports) & index.html (Portfolio)
 * Features: GitHub Sync, Yahoo/NSE Resolution, Local Storage Persistence
 */

// 1. GLOBAL STATE
window.S = JSON.parse(localStorage.getItem('bm_settings')) || {
    settings: { ghToken: '', ghRepo: '', _ghStatus: 'dim' }
};
window.SYMBOLS = []; 
window.FUND = {}; 
window.PRICES = {}; 

// 2. GITHUB / API UTILS
const ghHeaders = () => ({
    'Authorization': `token ${S.settings.ghToken}`,
    'Accept': 'application/vnd.github.v3+json',
    'Cache-Control': 'no-cache'
});

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
            content: btoa(unescape(encodeURIComponent(content))),
            sha
        })
    });
}

async function ghFetchRaw(path) {
    const url = `https://raw.githubusercontent.com/${S.settings.ghRepo}/main/${path}?t=${Date.now()}`;
    const res = await fetch(url, { headers: ghHeaders() });
    return res.ok ? await res.json() : null;
}

// 3. SEARCH & RESOLUTION (Yahoo + NSE)
async function searchYahoo(query) {
    try {
        const res = await fetch(`https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(query)}&region=IN`);
        const data = await res.json();
        const match = data.quotes?.find(q => q.symbol.endsWith('.NS'));
        if (match) return { sym: match.symbol.replace('.NS', ''), confidence: 90, isin: match.isin || '' };
    } catch (e) { return null; }
}

async function searchNSE(query) {
    try {
        const res = await fetch(`https://www.nseindia.com/api/suggest?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        if (data && data.length) return { sym: data[0].symbol, confidence: 80 };
    } catch (e) { return null; }
}

// 4. DATA MANAGEMENT
function saveSettings() { 
    localStorage.setItem('bm_settings', JSON.stringify(S)); 
    updateStatusDots();
}

function migrateSymbols(arr) {
    return arr.map(s => {
        if (s.source && !s.category) s.category = s.source[0] === 'p' ? 'portfolio' : 'watchlist';
        if (!s.category) s.category = 'portfolio';
        return s;
    });
}

// 5. UI HELPERS & LOGGING
function dataLog(msg, icon = '') {
    const log = document.getElementById('data-log');
    if (!log) return;
    const div = document.createElement('div');
    div.style.marginBottom = '4px';
    div.innerHTML = `<span style="color:var(--tx3); font-size:9px;">[${new Date().toLocaleTimeString()}]</span> ${icon} <span style="font-size:10px;">${msg}</span>`;
    log.prepend(div);
}

function updateStatusDots() {
    const setDot = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.className = `dot ${val ? 'dot-ok' : 'dot-off'}`;
    };
    setDot('dot-token', S.settings.ghToken);
    setDot('dot-repo', S.settings.ghRepo);
}

function toast(msg) { alert(msg); }
function fmt(n) { return n ? n.toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '0'; }
function fmtTs(ts) { return ts ? new Date(parseInt(ts)).toLocaleString('en-IN') : '—'; }

function daysSince(ts) {
    if (!ts) return null;
    const diff = Date.now() - new Date(ts).getTime();
    return Math.floor(diff / (1000 * 60 * 60 * 24));
}

function requirePAT() {
    if (!S.settings.ghToken || !S.settings.ghRepo) {
        toast("Missing GitHub Configuration");
        return false;
    }
    return true;
}

function loadState() {
    const syms = localStorage.getItem('bm_symbols');
    if (syms) window.SYMBOLS = JSON.parse(syms);
    updateStatusDots();
}

function nameSimilarity(a, b) {
    const s1 = a.toLowerCase(); const s2 = b.toLowerCase();
    if (s1 === s2) return 100;
    return s1.includes(s2) || s2.includes(s1) ? 80 : 0;
}
