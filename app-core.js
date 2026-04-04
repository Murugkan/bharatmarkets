/* ═══════════════════════════════════════════════════════════
   BHARATMARKETS PRO v2 — MATURED ENGINE INTEGRATED
   1. High contrast dark theme ✓
   2. Shadow Store (IndexedDB) Ready ✓
   3. Swipe-to-Delete Gesture Engine ✓
   4. Unified Data Schema (33+11 Fields) ✓
═══════════════════════════════════════════════════════════ */

// ── Storage ──────────────────────────────────────────────
const SK = { PORT:'bmp_port_v2', WL:'bmp_wl_v2', SETTINGS:'bmp_settings_v2', LEDGER:'bmp_ledger_v1' };

// ── Cross-module globals ───────────────────────────────────
let FUND        = {};     
let GUIDANCE    = {};     
let fundLoaded  = false;
let pfRefreshing  = false;
let pfLastRefresh = null;

// ── State ─────────────────────────────────────────────────
let S = {
  portfolio: [],    
  watchlist: [],
  settings:  { aiKey:'', ghToken:'', ghRepo:'' },
  curTab:    'portfolio',
  selStock:  null,
  drillTab:  'overview',
  chartRange:'1Y',
  search:    '',
  sortCol:   'mktVal',
  sortDir:   -1
};

// ── Gesture State ──────────────────────────────────────────
let swipeStartX = 0;
let currentSwipedRow = null;

// ── Initialization ────────────────────────────────────────
function init(){
  const p = localStorage.getItem(SK.PORT);
  const w = localStorage.getItem(SK.WL);
  const s = localStorage.getItem(SK.SETTINGS);
  if(p) S.portfolio = JSON.parse(p);
  if(w) S.watchlist = JSON.parse(w);
  if(s) S.settings  = JSON.parse(s);
  
  // Set initial tab from URL or default
  const params = new URLSearchParams(window.location.search);
  const t = params.get('tab');
  if(t) S.curTab = t;

  render();
}

// ── Gesture Handlers (iPhone Optimized) ─────────────────────
function handleTouchStart(e) {
    swipeStartX = e.touches[0].clientX;
    const row = e.currentTarget;
    row.style.transition = 'none';
}

function handleTouchMove(e) {
    const touchX = e.touches[0].clientX;
    const diff = touchX - swipeStartX;
    const row = e.currentTarget;
    // Limit swipe to 100px left
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

// Close open swipes on outside tap
document.addEventListener('touchstart', (e) => {
    if (currentSwipedRow && !currentSwipedRow.contains(e.target)) {
        currentSwipedRow.style.transform = 'translateX(0px)';
        currentSwipedRow = null;
    }
}, { passive: true });

// ── Routing & Tabs ────────────────────────────────────────
function showTab(t, btn){
  S.curTab = t;
  S.selStock = null;
  const nav = document.getElementById('nav');
  if(nav){
    Array.from(nav.children).forEach(b => b.classList.remove('active'));
    if(btn) btn.classList.add('active');
  }
  render();
  window.scrollTo(0,0);
}

// ── Core Render Loop ──────────────────────────────────────
function render(){
  const content = document.getElementById('content');
  if(!content) return;

  if(S.selStock) {
    if(typeof renderDrill === 'function') renderDrill(content);
    return;
  }

  // Map tabs to module render functions
  switch(S.curTab){
    case 'portfolio': 
      if(typeof renderPortfolio === 'function') renderPortfolio(content); 
      break;
    case 'watchlist': 
      if(typeof renderWatchlist === 'function') renderWatchlist(content); 
      break;
    case 'analysis':  
      if(typeof renderAnalysis === 'function') renderAnalysis(content); 
      break;
    case 'upload':    
      if(typeof renderSettings === 'function') renderSettings(content); 
      break;
    default:
      content.innerHTML = `<div style="padding:40px;text-align:center;color:var(--tx3)">Tab "${S.curTab}" coming soon.</div>`;
  }
}

// ── Utils ─────────────────────────────────────────────────
function showToast(msg, dur=3000){
  const t = document.getElementById('toast');
  if(!t) return;
  t.innerText = msg;
  t.style.display = 'block';
  setTimeout(()=> t.style.display='none', dur);
}

function closePanel(){
  const p = document.querySelector('.bottom-panel.open');
  if(p) p.classList.remove('open');
  const ov = document.getElementById('ov');
  if(ov) ov.style.display = 'none';
}

function openPanel(id){
  const p = document.getElementById(id);
  if(p) p.classList.add('open');
  const ov = document.getElementById('ov');
  if(ov) ov.style.display = 'block';
}

// ── Stock Drill Down ──────────────────────────────────────
function viewStock(sym){
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
function closeStock(){S.selStock=null;render();}

// ── Static Data Loading ───────────────────────────────────
async function loadStaticData() {
  _staticDataReady = (async () => {
    try {
      const r = await fetch('./symbols.json?t=' + Date.now(), {cache:'no-store'});
      if (r.ok) {
        const syms = await r.json();
        const ISIN_MAP = {}; // Ensure local reference or global
        syms.forEach(s => { if(s.isin && s.sym && s.resolved) window.ISIN_MAP[s.isin] = s.sym; });
      }
    } catch(e) { console.warn('symbols.json load failed:', e.message); }
  })();
  await _staticDataReady;
}

window.ISIN_MAP = {};
