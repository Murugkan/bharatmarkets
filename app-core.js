/* ═══════════════════════════════════════════════════════════
   BHARATMARKETS PRO v2 — CORE STATE & GESTURES
   Fix: Populates the Import Panel when triggered
═══════════════════════════════════════════════════════════ */

// ── 1. Storage Configuration ──────────────────────────────
const SK = { 
  PORT: 'bmp_port_v2', 
  WL: 'bmp_wl_v2', 
  SETTINGS: 'bmp_settings_v2',
  LEDGER: 'bmp_ledger_v1' 
};

// ── 2. Cross-Module Globals ───────────────────────────────
let FUND = {}; let GUIDANCE = {}; let ISIN_MAP = {};
let fundLoaded = false; let pfRefreshing = false;

// ── 3. App State ──────────────────────────────────────────
let S = {
  portfolio: [], watchlist: [], settings: { aiKey:'', ghToken:'', ghRepo:'' },
  curTab: 'portfolio', selStock: null, drillTab: 'overview',
  chartRange:'1Y', search: '', sortCol: 'marketValue', sortDir: -1
};

// ── 4. Initialization ─────────────────────────────────────
function init() {
  const p = localStorage.getItem(SK.PORT);
  const w = localStorage.getItem(SK.WL);
  const s = localStorage.getItem(SK.SETTINGS);
  if (p) S.portfolio = JSON.parse(p);
  if (w) S.watchlist = JSON.parse(w);
  if (s) S.settings  = JSON.parse(s);
  console.log("💎 Core State Initialized");
}

// ── 5. Navigation & Routing (FIX FOR EMPTY PANEL) ─────────
function showTab(t, btn) {
  S.curTab = t;
  S.selStock = null;
  
  const nav = document.getElementById('nav');
  if (nav) {
    Array.from(nav.children).forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
  }

  // IF UPLOAD TAB IS CLICKED
  if (t === 'upload') {
    openPanel('import-panel');
    // Check if app-import.js is loaded and has the render function
    if (typeof renderImportUI === 'function') {
        renderImportUI(); 
    } else {
        // Emergency Fallback UI if app-import.js failed to load
        document.getElementById('import-panel-body').innerHTML = `
            <div style="padding:20px; text-align:center">
                <p style="color:var(--tx3)">Import Module not detected.</p>
                <button onclick="location.reload()" style="background:var(--b2);color:white;border:none;padding:8px 16px;border-radius:4px">Reload App</button>
            </div>`;
    }
  }
  
  render();
}

// ── 6. Global Render Orchestrator ─────────────────────────
function render() {
  const content = document.getElementById('content');
  if (!content) return;

  if (S.selStock) {
    if (typeof renderDrill === 'function') renderDrill(content);
    return;
  }

  switch (S.curTab) {
    case 'portfolio': if (typeof renderPortfolio === 'function') renderPortfolio(content); break;
    case 'watchlist': if (typeof renderWatchlist === 'function') renderWatchlist(content); break;
    case 'analysis':  if (typeof renderAnalysis === 'function') renderAnalysis(content); break;
    case 'upload':
        content.innerHTML = `<div style="padding:100px 20px; text-align:center; color:var(--tx3)">
            <div style="font-size:40px; margin-bottom:10px">📂</div>
            Import Panel Active Below
        </div>`;
        break;
  }
}

// ── 7. UI Utilities ───────────────────────────────────────
function showToast(msg, dur = 3000) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.innerText = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', dur);
}

function openPanel(id) {
  const p = document.getElementById(id);
  if (p) p.classList.add('open');
  const ov = document.getElementById('ov');
  if (ov) ov.style.display = 'block';
}

function closePanel() {
  const p = document.querySelector('.bottom-panel.open');
  if (p) p.classList.remove('open');
  const ov = document.getElementById('ov');
  if (ov) ov.style.display = 'none';
}

// ── 8. iPhone Gesture Handlers ────────────────────────────
function handleTouchStart(e) {
    swipeStartX = e.touches[0].clientX;
    e.currentTarget.style.transition = 'none';
}

function handleTouchMove(e) {
    const diff = e.touches[0].clientX - swipeStartX;
    if (diff < 0 && diff > -120) e.currentTarget.style.transform = `translateX(${diff}px)`;
}

function handleTouchEnd(e, sym) {
    const row = e.currentTarget;
    const diff = e.changedTouches[0].clientX - swipeStartX;
    row.style.transition = 'transform 0.3s cubic-bezier(0.18, 0.89, 0.32, 1.28)';
    if (diff < -70) {
        row.style.transform = 'translateX(-90px)';
        currentSwipedRow = row;
    } else {
        row.style.transform = 'translateX(0px)';
        currentSwipedRow = null;
    }
}

// ── 9. Static Data (Symbols) ──────────────────────────────
async function loadStaticData() {
    try {
        const r = await fetch('./symbols.json?t=' + Date.now());
        if (r.ok) {
            const syms = await r.json();
            syms.forEach(s => { if(s.isin && s.sym && s.resolved) ISIN_MAP[s.isin] = s.sym; });
        }
    } catch(e) { console.warn('Static load failed'); }
}
