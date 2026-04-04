/* ═══════════════════════════════════════════════════════════
   app-core.js — RESILIENT ARCHITECTURE
═══════════════════════════════════════════════════════════ */

const SK = { PORT:'bmp_port_v2', WL:'bmp_wl_v2', SETTINGS:'bmp_settings_v2', LEDGER:'bmp_ledger_v1' };
let S = { portfolio:[], watchlist:[], settings:{ aiKey:'', ghToken:'', ghRepo:'' }, curTab:'portfolio' };

function log(msg, type='info') {
    console.log(`[${type.toUpperCase()}] ${msg}`);
    const consoleEl = document.getElementById('debug-console');
    if (consoleEl) {
        const entry = document.createElement('div');
        entry.style.borderBottom = '1px solid #222';
        entry.innerHTML = `<span style="color:#708499">${new Date().toLocaleTimeString()}</span> [${type}] ${msg}`;
        consoleEl.prepend(entry);
    }
}

function toggleDebug() {
    const win = document.getElementById('debug-window');
    win.style.display = win.style.display === 'none' ? 'block' : 'none';
}

async function showTab(t, btn) {
    log(`Switching to: ${t}`);
    S.curTab = t;
    if (btn) {
        const nav = document.getElementById('nav');
        Array.from(nav.children).forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }
    if (t === 'upload') openPanel('import-panel');
    render();
}

async function render() {
    const content = document.getElementById('content');
    if (!content) return;
    log(`Attempting Render: ${S.curTab}`);

    // TIMEOUT PROTECTION: If the specific tab script hangs, show an error after 2s
    const timeout = setTimeout(() => {
        if (content.innerHTML === "") {
            log("Render timed out. Engine might be stuck.", "error");
            content.innerHTML = `<div style="padding:40px;text-align:center;color:var(--rd2)">Engine Timeout. Check Debug Logs.</div>`;
        }
    }, 2000);

    try {
        if (S.curTab === 'portfolio' && typeof renderPortfolio === 'function') {
            await renderPortfolio(content);
        } else if (S.curTab === 'watchlist' && typeof renderWatchlist === 'function') {
            await renderWatchlist(content);
        } else if (S.curTab === 'upload') {
            content.innerHTML = `<div style="padding:100px;text-align:center;color:var(--tx3)">Import Active</div>`;
            renderImportUI();
        }
        clearTimeout(timeout);
    } catch (e) {
        log(`Render Error: ${e.message}`, "error");
    }
}

function renderImportUI() {
    const body = document.getElementById('import-panel-body');
    if (!body) return;
    body.innerHTML = `
        <textarea id="import-area" style="width:100%;height:150px;background:var(--s2);color:white;border:1px solid var(--b1);border-radius:8px;padding:10px;margin-bottom:10px"></textarea>
        <button onclick="processImport()" style="width:100%;padding:15px;background:var(--b2);color:white;border:none;border-radius:8px;font-weight:bold">Process Data</button>
    `;
}

function openPanel(id) {
    document.getElementById(id).classList.add('open');
    document.getElementById('ov').style.display = 'block';
}

function closePanel() {
    document.querySelectorAll('.bottom-panel').forEach(p => p.classList.remove('open'));
    document.getElementById('ov').style.display = 'none';
}

function init() {
    log("Core Init...");
    const p = localStorage.getItem(SK.PORT);
    if (p) S.portfolio = JSON.parse(p);
    log("Core Ready.");
}
