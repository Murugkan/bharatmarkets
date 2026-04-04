/* ═══════════════════════════════════════════════════════════
   BHARATMARKETS PRO v2 — CORE & RESILIENT RENDERER
═══════════════════════════════════════════════════════════ */

const SK = { 
  PORT: 'bmp_port_v2', 
  WL: 'bmp_wl_v2', 
  SETTINGS: 'bmp_settings_v2',
  LEDGER: 'bmp_ledger_v1' 
};

let FUND = {}; let GUIDANCE = {}; let ISIN_MAP = {};
let S = {
  portfolio: [], watchlist: [], settings: { aiKey:'', ghToken:'', ghRepo:'' },
  curTab: 'portfolio', selStock: null
};

// ── 1. GLOBAL LOGGING ─────────────────────────────────────
function log(msg, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${msg}`);
    const consoleEl = document.getElementById('debug-console');
    if (consoleEl) {
        const entry = document.createElement('div');
        entry.style.cssText = "border-bottom:1px solid #222; padding:4px 0; word-break:break-all;";
        entry.innerHTML = `<span style="color:#708499">${new Date().toLocaleTimeString()}</span> [${type}] ${msg}`;
        consoleEl.prepend(entry);
    }
}

function toggleDebug() {
    const win = document.getElementById('debug-window');
    win.style.display = win.style.display === 'none' ? 'block' : 'none';
}

// ── 2. NAVIGATION & ROUTING ───────────────────────────────
function showTab(t, btn) {
    log(`Switching to tab: ${t}`);
    S.curTab = t;
    S.selStock = null;
    
    const nav = document.getElementById('nav');
    if (nav) {
        Array.from(nav.children).forEach(b => b.classList.remove('active'));
        if (btn) btn.classList.add('active');
    }

    if (t === 'upload') {
        openPanel('import-panel');
        renderImportUI();
    }
    
    render();
}

// ── 3. RESILIENT RENDERER ─────────────────────────────────
async function render() {
    const content = document.getElementById('content');
    if (!content) return;

    log(`Rendering ${S.curTab}...`);
    
    try {
        switch (S.curTab) {
            case 'portfolio':
                if (typeof renderPortfolio === 'function') {
                    // Added a safety check to prevent hanging
                    await renderPortfolio(content).catch(e => {
                        log(`Portfolio Render Error: ${e.message}`, 'error');
                        content.innerHTML = `<div style="padding:50px; color:var(--rd2)">Engine Load Error. Check Debug Logs.</div>`;
                    });
                } else {
                    log("renderPortfolio function missing!", "error");
                }
                break;
            case 'watchlist':
                if (typeof renderWatchlist === 'function') renderWatchlist(content);
                break;
            case 'analysis':
                if (typeof renderAnalysis === 'function') renderAnalysis(content);
                break;
        }
    } catch (err) {
        log(`Render Crash: ${err.message}`, 'error');
    }
}

// ── 4. UI HELPERS ──────────────────────────────────────────
function renderImportUI() {
    const body = document.getElementById('import-panel-body');
    if (!body) return;
    body.innerHTML = `
        <div style="margin-top:10px">
            <textarea id="import-area" placeholder="Paste CDSL text..." 
                style="width:100%; height:120px; background:var(--s2); border:1px solid var(--b1); color:var(--tx1); border-radius:8px; padding:10px; margin-bottom:12px"></textarea>
            <button onclick="handleImport()" style="width:100%; background:var(--b2); color:white; border:none; padding:14px; border-radius:8px; font-weight:700">Process Data</button>
        </div>`;
}

function handleImport() {
    if (typeof processImport === 'function') {
        processImport();
    } else {
        log("processImport() not found in app-import.js", "error");
    }
}

function openPanel(id) {
    document.getElementById(id).classList.add('open');
    document.getElementById('ov').style.display = 'block';
}

function closePanel() {
    const p = document.querySelector('.bottom-panel.open');
    if (p) p.classList.remove('open');
    document.getElementById('ov').style.display = 'none';
}

// ── 5. INITIALIZATION ─────────────────────────────────────
function init() {
    log("Initializing Core...");
    const p = localStorage.getItem(SK.PORT);
    if (p) S.portfolio = JSON.parse(p);
    log("Core Ready.");
}
