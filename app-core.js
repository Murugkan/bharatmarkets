/* ═══════════════════════════════════════════════════════════
   BHARATMARKETS PRO v2 — CORE STATE & GESTURES
   Fix: Import Button & Routing Logic
═══════════════════════════════════════════════════════════ */

// ── Storage ──────────────────────────────────────────────
const SK = { 
  PORT:'bmp_port_v2', 
  WL:'bmp_wl_v2', 
  SETTINGS:'bmp_settings_v2',
  LEDGER:'bmp_ledger_v1' 
};

// ── Globals ──────────────────────────────────────────────
let FUND = {}; let GUIDANCE = {}; let ISIN_MAP = {};
let fundLoaded = false; let pfRefreshing = false;
let _staticDataReady = null;

let S = {
  portfolio: [], watchlist: [], settings: { aiKey:'', ghToken:'', ghRepo:'' },
  curTab: 'portfolio', selStock: null, drillTab: 'overview',
  chartRange:'1Y', search: '', sortCol: 'marketValue', sortDir: -1
};

let swipeStartX = 0; let currentSwipedRow = null;

// ── Initialization ────────────────────────────────────────
function init() {
  const p = localStorage.getItem(SK.PORT);
  const w = localStorage.getItem(SK.WL);
  const s = localStorage.getItem(SK.SETTINGS);
  if(p) S.portfolio = JSON.parse(p);
  if(w) S.watchlist = JSON.parse(w);
  if(s) S.settings  = JSON.parse(s);
  console.log("💎 Core Initialized");
}

// ── Navigation (The Fix for the Import Button) ───────────
function showTab(t, btn) {
  S.curTab = t;
  S.selStock = null;
  
  // Update Nav UI
  const nav = document.getElementById('nav');
  if (nav) {
    Array.from(nav.children).forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
  }

  // SPECIAL CASE: If 'upload' is clicked, we trigger the panel
  if (t === 'upload') {
    if (typeof openImport === 'function') {
        openImport(); 
    } else {
        // Fallback if app-import.js isn't ready
        openPanel('import-panel');
        const body = document.getElementById('import-panel-body');
        if(body) body.innerHTML = `<div style="padding:20px;color:var(--tx3)">Import module loading...</div>`;
    }
  }
  
  render();
  window.scrollTo(0, 0);
}

// ── Render Orchestrator ──────────────────────────────────
function render() {
  const content = document.getElementById('content');
  if (!content) return;

  if (S.selStock) {
    if (typeof renderDrill === 'function') renderDrill(content);
    return;
  }

  switch (S.curTab) {
    case 'portfolio': 
      if (typeof renderPortfolio === 'function') renderPortfolio(content); 
      break;
    case 'watchlist': 
      if (typeof renderWatchlist === 'function') renderWatchlist(content); 
      break;
    case 'upload':
      // The button triggers the panel, but we clear content to avoid confusion
      content.innerHTML = `<div style="padding:60px; text-align:center; color:var(--tx3)">
        <div style="font-size:40px;margin-bottom:10px">⬆️</div>
        Panel Opened Below
      </div>`;
      break;
    default:
      content.innerHTML = `<div style="padding:40px; text-align:center; color:var(--tx3)">Tab ${S.curTab} selected.</div>`;
  }
}

// ── UI Utilities ──────────────────────────────────────────
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

// ── Gesture Handlers ─────────────────────────────────────
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

// ── Data Resolution ──────────────────────────────────────
async function loadStaticData() {
    try {
        const r = await fetch('./symbols.json?t=' + Date.now(), {cache:'no-store'});
        if (r.ok) {
            const syms = await r.json();
            syms.forEach(s => { if(s.isin && s.sym && s.resolved) ISIN_MAP[s.isin] = s.sym; });
        }
    } catch(e) { console.warn('Static load failed'); }
}
