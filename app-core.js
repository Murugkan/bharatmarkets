/* ═══════════════════════════════════════════════════════════
   BHARATMARKETS PRO v2 — CORE STATE & GESTURES
   Module: app-core.js
   Logic: Manages storage keys, global state, and iPhone gestures.
═══════════════════════════════════════════════════════════ */

// ── 1. Storage Configuration ──────────────────────────────
const SK = { 
  PORT: 'bmp_port_v2', 
  WL: 'bmp_wl_v2', 
  SETTINGS: 'bmp_settings_v2',
  LEDGER: 'bmp_ledger_v1' // Required for the Unified Engine Purge Logic
};

// ── 2. Cross-Module Globals ───────────────────────────────
let FUND        = {};     
let GUIDANCE    = {};     
let ISIN_MAP    = {};
let fundLoaded  = false;
let pfRefreshing  = false;
let pfLastRefresh = null;
let _staticDataReady = null;

// ── 3. App State ──────────────────────────────────────────
let S = {
  portfolio: [],    
  watchlist: [],
  settings:  { aiKey:'', ghToken:'', ghRepo:'' },
  curTab:    'portfolio',
  selStock:  null,
  drillTab:  'overview',
  chartRange:'1Y',
  search:    '',
  sortCol:   'marketValue',
  sortDir:   -1
};

// ── 4. Gesture Engine State (iPhone Swipe) ────────────────
let swipeStartX = 0;
let currentSwipedRow = null;

/**
 * Initialization: Loads basic state from LocalStorage
 */
function init() {
  const p = localStorage.getItem(SK.PORT);
  const w = localStorage.getItem(SK.WL);
  const s = localStorage.getItem(SK.SETTINGS);
  
  if (p) S.portfolio = JSON.parse(p);
  if (w) S.watchlist = JSON.parse(w);
  if (s) S.settings  = JSON.parse(s);
  
  const params = new URLSearchParams(window.location.search);
  const t = params.get('tab');
  if (t) S.curTab = t;

  console.log("💎 Core State Initialized");
}

// ── 5. Gesture Handlers (iPhone Optimized) ────────────────
function handleTouchStart(e) {
    swipeStartX = e.touches[0].clientX;
    const row = e.currentTarget;
    row.style.transition = 'none';
}

function handleTouchMove(e) {
    const touchX = e.touches[0].clientX;
    const diff = touchX - swipeStartX;
    const row = e.currentTarget;
    
    // Only allow left-swipe up to 120px
    if (diff < 0 && diff > -120) {
        row.style.transform = `translateX(${diff}px)`;
    }
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

// Global click-away listener for swipes
document.addEventListener('touchstart', (e) => {
    if (currentSwipedRow && !currentSwipedRow.contains(e.target)) {
        currentSwipedRow.style.transform = 'translateX(0px)';
        currentSwipedRow = null;
    }
}, { passive: true });

// ── 6. Navigation & Routing ───────────────────────────────
function showTab(t, btn) {
  S.curTab = t;
  S.selStock = null;
  
  const nav = document.getElementById('nav');
  if (nav) {
    Array.from(nav.children).forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
  }
  
  render();
  window.scrollTo(0, 0);
}

// ── 7. Global Render Orchestrator ─────────────────────────
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
    case 'analysis':  
      if (typeof renderAnalysis === 'function') renderAnalysis(content); 
      break;
    case 'upload':    
      if (typeof renderSettings === 'function') renderSettings(content); 
      break;
    default:
      content.innerHTML = `<div style="padding:60px; text-align:center; color:var(--tx3)">Tab "${S.curTab}" is active.</div>`;
  }
}

// ── 8. UI Utilities ───────────────────────────────────────
function showToast(msg, dur = 3000) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.innerText = msg;
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', dur);
}

function closePanel() {
  const p = document.querySelector('.bottom-panel.open');
  if (p) p.classList.remove('open');
  const ov = document.getElementById('ov');
  if (ov) ov.style.display = 'none';
}

function openPanel(id) {
  const p = document.getElementById(id);
  if (p) p.classList.add('open');
  const ov = document.getElementById('ov');
  if (ov) ov.style.display = 'block';
}

// ── 9. Stock View Logic ───────────────────────────────────
function viewStock(sym) {
  const f = FUND[sym] || {};
  const p = S.portfolio.find(x => x.sym === sym) || S.watchlist.find(x => x.sym === sym) || {sym};
  
  S.selStock = {
    sym:      sym,
    name:     p.name    || sym,
    sector:   p.sector  || f.sector || 'Other',
    qty:      p.qty     || 0,
    avgBuy:   p.avgBuy  || 0,
    ltp:      p.ltp     || f.ltp || 0,
    mcap:     f.mcap    || null,
    pe:       f.pe      || null,
    roe:      f.roe     || null,
    promoter: f.promoter|| null,
    pledge:   f.pledge  || null,
    ath_dist: f.ath_dist|| null,
    fcf:      f.fcf     || null,
    cfo:      f.cfo     || null,
    sales:    f.sales   || null,
    opm_pct:  f.opm_pct || null,
    npm_pct:  f.npm_pct || null,
    debt_eq:  f.debt_eq || null,
  };
  S.drillTab  = 'overview';
  S.chartRange= '1Y';
  document.getElementById('content').scrollTop = 0;
  render();
}

function closeStock() { S.selStock = null; render(); }

// ── 10. Data Resolution (ISIN to Ticker) ──────────────────
async function loadStaticData() {
    _staticDataReady = (async () => {
        try {
            const r = await fetch('./symbols.json?t=' + Date.now(), {cache:'no-store'});
            if (r.ok) {
                const syms = await r.json();
                syms.forEach(s => { if(s.isin && s.sym && s.resolved) ISIN_MAP[s.isin] = s.sym; });
                console.log('✅ ISIN Map Built: ' + Object.keys(ISIN_MAP).length);
            }
        } catch(e) { console.warn('symbols.json load failed:', e.message); }
    })();
    await _staticDataReady;
}
