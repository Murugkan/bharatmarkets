/* ═══════════════════════════════════════════════════════════
   BHARATMARKETS PRO v2 — CORE STATE & DEBUGGER
═══════════════════════════════════════════════════════════ */

const SK = { 
  PORT: 'bmp_port_v2', 
  WL: 'bmp_wl_v2', 
  SETTINGS: 'bmp_settings_v2',
  LEDGER: 'bmp_ledger_v1' 
};

let S = {
  portfolio: [], watchlist: [], settings: { aiKey:'', ghToken:'', ghRepo:'' },
  curTab: 'portfolio', selStock: null
};

// ── DEBUG SYSTEM ──────────────────────────────────────────
function log(msg, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${msg}`);
    const consoleEl = document.getElementById('debug-console');
    if (consoleEl) {
        const entry = document.createElement('div');
        entry.style.borderBottom = '1px solid #222';
        entry.style.padding = '4px 0';
        entry.innerHTML = `<span style="color:var(--tx3)">${new Date().toLocaleTimeString()}</span> [${type}] ${msg}`;
        consoleEl.prepend(entry);
    }
}

function toggleDebug() {
    const win = document.getElementById('debug-window');
    win.style.display = win.style.display === 'none' ? 'block' : 'none';
}

// ── INITIALIZATION ────────────────────────────────────────
function init() {
    log("Initializing Core State...");
    try {
        const p = localStorage.getItem(SK.PORT);
        if (p) S.portfolio = JSON.parse(p);
        log(`Loaded ${S.portfolio.length} portfolio items`);
    } catch (e) {
        log("Init Error: " + e.message, 'error');
    }
}

// ── NAVIGATION & IMPORT FIX ───────────────────────────────
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
        log("Opening Import Panel...");
        openPanel('import-panel');
        const body = document.getElementById('import-panel-body');
        
        // Inject UI directly to ensure it isn't blank
        body.innerHTML = `
            <div style="margin-top:10px">
                <textarea id="import-area" placeholder="Paste data here..." 
                    style="width:100%; height:120px; background:var(--s2); border:1px solid var(--b1); color:var(--tx1); border-radius:8px; padding:10px; font-family:monospace; margin-bottom:12px"></textarea>
                <button onclick="handleImportClick()" 
                    style="width:100%; background:var(--b2); color:white; border:none; padding:12px; border-radius:8px; font-weight:700">Process Import</button>
            </div>`;
    }
    render();
}

function handleImportClick() {
    log("Process Import clicked");
    if (typeof processImport === 'function') {
        processImport();
    } else {
        log("processImport() not found. Check if app-import.js is loaded.", "error");
    }
}

// ── UI HELPERS ────────────────────────────────────────────
function openPanel(id) {
    const p = document.getElementById(id);
    if (p) p.classList.add('open');
    document.getElementById('ov').style.display = 'block';
}

function closePanel() {
    const p = document.querySelector('.bottom-panel.open');
    if (p) p.classList.remove('open');
    document.getElementById('ov').style.display = 'none';
}

function render() {
    const content = document.getElementById('content');
    if (!content) return;
    if (S.curTab === 'portfolio' && typeof renderPortfolio === 'function') renderPortfolio(content);
}
