/* ═══════════════════════════════════════════════════════════
   BHARATMARKETS PRO v2 — CORE STATE & GESTURE ENGINE
   Logic: Manages global state, routing, and iPhone gestures.
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

// ── 4. Gesture Engine State ───────────────────────────────
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

// ── 5. Gesture Handlers (iPhone Swipe-to-Delete) ──────────
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
        // Snap open to reveal the PURGE button
        row.style.transform = 'translateX(-90px)';
        currentSwipedRow = row;
    } else {
        // Snap back shut
        row.style.transform = 'translateX(0px)';
        currentSwipedRow = null;
    }
}

// Close any open swipe if user taps elsewhere
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

// ── 8. Utility Components ─────────────────────────────────
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

// ── 9. Stock View & Static Data ───────────────────────────
function viewStock(sym) {
  // Logic to open the detailed view of a stock
  S.selStock = { sym: sym };
  S.drillTab = 'overview';
  render();
}

function closeStock() {
  S.selStock = null;
  render();
}

/**
 * Loads symbols.json to map ISINs to NSE Tickers
 */
async function loadStaticData() {
    try {
      const r = await fetch('./symbols.json?t=' + Date.now(), {cache:'no-store'});
      if (r.ok) {
        const syms = await r.json();
        syms.forEach(s => { 
            if(s.isin && s.sym && s.resolved) ISIN_MAP[s.isin] = s.sym; 
        });
        console.log(`✅ ISIN Map Loaded: ${Object.keys(ISIN_MAP).length} entries`);
      }
    } catch(e) { 
        console.warn('Static symbols load failed:', e.message); 
    }
}
