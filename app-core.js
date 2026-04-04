/* ═══════════════════════════════════════════════════════════
   app-core.js - CORE STATE, NAVIGATION & DEBUGGER
═══════════════════════════════════════════════════════════ */

const SK = { 
  PORT: 'bmp_port_v2', 
  WL: 'bmp_wl_v2', 
  SETTINGS: 'bmp_settings_v2',
  LEDGER: 'bmp_ledger_v1' 
};

let S = {
  portfolio: [], 
  watchlist: [], 
  settings: { aiKey:'', ghToken:'', ghRepo:'' },
  curTab: 'portfolio', 
  selStock: null
};

let swipeStartX = 0;

// ── 1. LOGGING SYSTEM ─────────────────────────────────────
function log(msg, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${msg}`);
    const consoleEl = document.getElementById('debug-console');
    if (consoleEl) {
        const entry = document.createElement('div');
        entry.style.cssText = "border-bottom:1px solid #222; padding:4px 0; font-size:11px;";
        entry.innerHTML = `<span style="color:#708499">${new Date().toLocaleTimeString()}</span> [${type}] ${msg}`;
        consoleEl.prepend(entry);
    }
}

function toggleDebug() {
    const win = document.getElementById('debug-window');
    win.style.display = win.style.display === 'none' ? 'block' : 'none';
}

// ── 2. DATABASE INSPECTOR ─────────────────────────────────
async function checkDatabase() {
    log("🔍 Inspecting Database...");
    try {
        if (typeof initEngineDB !== 'function') return;
        const db = await initEngineDB();
        const tx = db.transaction('UnifiedStocks', 'readonly');
        const store = tx.objectStore('UnifiedStocks');
        
        store.getAll().onsuccess = (e) => {
            const rows = e.target.result;
            log(`DB Stats: ${rows ? rows.length : 0} rows found.`);
        };
    } catch (e) { log("DB Check Failed", "error"); }
}

// ── 3. NAVIGATION ─────────────────────────────────────────
function showTab(t, btn) {
    log(`Switching to: ${t}`);
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
    
    // Auto-check DB on tab switch
    checkDatabase();
    render();
}

function renderImportUI() {
    const body = document.getElementById('import-panel-body');
    if (!body) return;
    body.innerHTML = `
        <div style="margin-top:10px">
            <textarea id="import-area" placeholder="RELIANCE 10&#10;TCS 5" 
                style="width:100%; height:150px; background:var(--s2); border:1px solid var(--b1); color:var(--tx1); border-radius:8px; padding:12px; font-family:monospace; margin-bottom:16px; outline:none"></textarea>
            <button onclick="processImport()" 
                style="width:100%; background:var(--gr1); color:var(--bg); border:none; padding:16px; border-radius:12px; font-weight:800; cursor:pointer">
                PROCESS DATA
            </button>
        </div>`;
}

// ── 4. RENDERER ───────────────────────────────────────────
async function render() {
    const content = document.getElementById('content');
    if (!content) return;

    if (S.curTab === 'portfolio' && typeof renderPortfolio === 'function') {
        await renderPortfolio(content);
    } else if (S.curTab === 'watchlist' && typeof renderWatchlist === 'function') {
        renderWatchlist(content);
    }
}

// ── 5. UI UTILS ───────────────────────────────────────────
function openPanel(id) {
    document.getElementById(id).classList.add('open');
    document.getElementById('ov').style.display = 'block';
}

function closePanel() {
    document.querySelectorAll('.bottom-panel').forEach(p => p.classList.remove('open'));
    document.getElementById('ov').style.display = 'none';
}

function showToast(msg) {
    const t = document.getElementById('toast');
    if (!t) return;
    t.innerText = msg;
    t.style.display = 'block';
    setTimeout(() => t.style.display = 'none', 3000);
}

function init() {
    log("Core Initialized.");
    checkDatabase();
}
