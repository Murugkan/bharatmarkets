/* ═══════════════════════════════════════════════════════════
   app-core.js - FULL SYSTEM CONTROLLER
═══════════════════════════════════════════════════════════ */

const SK = { PORT: 'bmp_port_v2', WL: 'bmp_wl_v2', SETTINGS: 'bmp_settings_v2' };
let S = { portfolio: [], watchlist: [], settings: { aiKey:'', ghToken:'', ghRepo:'' }, curTab: 'portfolio' };

function log(msg, type = 'info') {
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

async function checkDatabase() {
    if (typeof initEngineDB !== 'function') return;
    const db = await initEngineDB();
    const tx = db.transaction('UnifiedStocks', 'readonly');
    tx.objectStore('UnifiedStocks').getAll().onsuccess = (e) => {
        log(`DB Stats: ${e.target.result.length} rows found.`);
    };
}

async function showTab(t, btn) {
    log(`Switching to: ${t}`);
    S.curTab = t;
    if (btn) {
        Array.from(document.getElementById('nav').children).forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }
    if (t === 'upload') {
        openPanel('import-panel');
        renderImportUI();
    }
    checkDatabase();
    render();
}

function renderImportUI() {
    const body = document.getElementById('import-panel-body');
    if (!body) return;
    body.innerHTML = `
        <textarea id="import-area" placeholder="RELIANCE 10" 
            style="width:100%; height:150px; background:var(--s2); border:1px solid var(--b1); color:var(--tx1); border-radius:8px; padding:12px; margin-bottom:16px; outline:none"></textarea>
        <button onclick="processImport()" style="width:100%; background:var(--gr1); color:var(--bg); border:none; padding:16px; border-radius:12px; font-weight:800;">PROCESS DATA</button>`;
}

async function render() {
    const content = document.getElementById('content');
    if (!content) return;
    if (S.curTab === 'portfolio' && typeof renderPortfolio === 'function') {
        await renderPortfolio(content);
    }
}

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
    if (t) {
        t.innerText = msg;
        t.style.display = 'block';
        setTimeout(() => t.style.display = 'none', 2000);
    }
}

function init() {
    log("System Ready.");
    render();
}
