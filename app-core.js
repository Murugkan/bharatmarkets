/* ═══════════════════════════════════════════════════════════
   BHARATMARKETS PRO v2 — ALL FIXES APPLIED
   1. High contrast dark theme ✓ (CSS above)
   2. News tab working ✓
   3. Macro tab populated ✓
   4. Portfolio import as textarea ✓
   5. Robust CDSL/text parsing ✓
   6. Proper candlestick chart ✓
   7. Portfolio P&L + sector allocation ✓
   8. Watchlist search from full NSE universe ✓
═══════════════════════════════════════════════════════════ */

// ── Storage ──────────────────────────────────────────────
// STORAGE KEYS — localStorage keys for persisting app state
const SK = { PORT:'bmp_port_v2', WL:'bmp_wl_v2', SETTINGS:'bmp_settings_v2' };

// ── Cross-module globals ───────────────────────────────────
let FUND        = {};     // { SYM: { roe, pe, opm_pct, ... } } — populated by app-portfolio.js
let GUIDANCE    = {};     // { SYM: { tone, summary, ... } }     — populated by app-analysis.js
let fundLoaded  = false;
let pfRefreshing  = false;
let pfLastRefresh = null;

// ── State ─────────────────────────────────────────────────
// APP STATE — single source of truth for all UI state
let S = {
  portfolio: [],    // [{sym,isin,name,sector,qty,avgBuy,ltp,change}]
  watchlist: [],
  settings:  { aiKey:'', ghToken:'', ghRepo:'' },
  curTab:    'portfolio',
  selStock:  null,
  drillTab:  'overview',
  expMacro:  null,
  chartRange:'3M',
  chartInterval:'D',
  maVis:     { sma20:true, sma50:true, ema200:true, vol:true, cfo:false, pe:false },
  kpiVis:    { pe:false, rev:false, net:false, cfo:false, opm:false, debt:false },
  macroFilter:'ALL',
  newsFilter: 'ALL',
  wlSearch:   '',
  wlLiveResults: [],
  pfFilter:   'All',
  pfSearch:    '',
  pfSector:   '',       // sector filter from legend click
  pfSort:     'wt',
  pfSortDir:  'desc',
};

// Chart caches
const chartCache = {};

// ── NSE Universe — 300+ symbols for search ───────────────
// ISIN_MAP built from symbols.json on boot — { ISIN: sym }
let ISIN_MAP = {};
let _staticDataReady = null; // Promise — resolves when ISIN_MAP is populated

// ── ISIN → Symbol map for portfolio parsing ───────────

// ── Macro Data ────────────────────────────────────────
// MACRO DATA — static India macro indicators shown in Macro tab
// Updated manually; supplement with live RSS news
// MACRO_DATA loaded from macro_data.json on boot
let MACRO_DATA = [];

// ── Indices ───────────────────────────────────────────
// GAINERS/LOSERS/INDICES derived live from prices.json — see renderMovers()

// ── Sector colours for allocation chart ───────────────
// SECTOR COLOURS — used in portfolio allocation bar + heatmap
const SECTOR_COLORS = {
  'Banking':'#2196f3','IT':'#9c27b0','Energy':'#f97316','Pharma':'#00d084','Diversified':'#5878a8',
  'Auto':'#00bcd4','FMCG':'#f5a623','Capital Goods':'#e91e63','Defence':'#4caf50',
  'Steel':'#607d8b','Power':'#ff5722','NBFC':'#3f51b5','Finance':'#009688',
  'Cement':'#795548','Consumer':'#ff9800','Chemicals':'#8bc34a','Real Estate':'#ff4081',
  'Infrastructure':'#76ff03','Retail':'#18ffff','Mining':'#ffd740','Metals':'#78909c',
  'Telecom':'#40c4ff','Renewable':'#69f0ae','Insurance':'#ea80fc','Media':'#ff6d00',
  'Healthcare':'#ff80ab','Conglomerate':'#ffcc02','Logistics':'#b9f6ca',
  'Consumer Tech':'#84ffff','Fertilisers':'#ccff90','Beverages':'#ffd180',
  'Aquaculture':'#a5d6a7','Agro':'#c8e6c9','Drones':'#b3e5fc',
};
function sectorColor(sec) {
  return SECTOR_COLORS[sec] || '#5878a8';
}

// ── Helpers ───────────────────────────────────────────
// ── Number formatters ───────────────────────────────────────
function fmt(n) {
  if(n==null||isNaN(n))return '—';
  return Number(n).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2});
}
function fmtCr(n) {
  if(!n||isNaN(n))return '—';
  if(n>=1e12)return (n/1e12).toFixed(2)+'L Cr';
  if(n>=1e7) return (n/1e7).toFixed(2)+' Cr';
  if(n>=1e5) return (n/1e5).toFixed(2)+' L';
  return '₹'+fmt(n);
}
function fmtVol(n){if(!n)return '—';if(n>=1e7)return(n/1e7).toFixed(1)+'Cr';if(n>=1e5)return(n/1e5).toFixed(1)+'L';if(n>=1e3)return(n/1e3).toFixed(0)+'K';return String(n);}
function trunc(s,n){return s&&s.length>n?s.slice(0,n)+'…':(s||'');}
function timeAgo(d){if(!d||isNaN(d))return '';const s=Math.floor((Date.now()-d)/1000);if(s<60)return 'just now';if(s<3600)return Math.floor(s/60)+'m ago';if(s<86400)return Math.floor(s/3600)+'h ago';return Math.floor(s/86400)+'d ago';}
function classifyNews(t){
  const u=t.toUpperCase();
  if(/RESULT|PROFIT|REVENUE|EARNING|Q[1-4]/.test(u))return{tag:'RESULTS',imp:'H'};
  if(/RBI|REPO|INFLATION|CPI|GDP|RATE CUT|RATE HIKE|MONETARY/.test(u))return{tag:'RBI',imp:'H'};
  if(/SEBI|REGULATION|PENALTY|PROBE|CBI|ED/.test(u))return{tag:'POLICY',imp:'H'};
  if(/OIL|CRUDE|OPEC|BRENT|PETROLEUM/.test(u))return{tag:'OIL',imp:'H'};
  if(/WAR|IRAN|ISRAEL|CONFLICT|SANCTION|GEO|MILITARY/.test(u))return{tag:'GEO',imp:'H'};
  if(/FII|FPI|DII|FOREIGN INFLOW|OUTFLOW/.test(u))return{tag:'FII',imp:'M'};
  if(/MERGER|ACQUI|DEAL|STAKE|BUYBACK|DIVIDEND/.test(u))return{tag:'CORP',imp:'M'};
  if(/SENSEX|NIFTY|RALLY|CRASH|SURGE|PLUNGE/.test(u))return{tag:'INDEX',imp:'M'};
  return{tag:'NEWS',imp:'L'};
}
function extractDomain(url){try{return new URL(url).hostname.replace(/^www\./,'').split('.')[0];}catch(_){return 'News';}}

function scoreColor(s){return s>=80?'var(--gr)':s>=65?'var(--yw)':'var(--rd)';}
function scoreLabel(s){return s>=80?'Strong':s>=65?'Watch':'Caution';}

let toastT=null;
function toast(msg){
  const el=document.getElementById('toast');
  el.textContent=msg;el.classList.add('show');
  clearTimeout(toastT);
  toastT=setTimeout(()=>el.classList.remove('show'),2800);
}

function updClock(){
  const now = new Date();
  const ist = new Date(now.getTime() + 5.5*60*60*1000);
  const t   = ist.toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Asia/Kolkata'});
  const day = ist.getUTCDay();
  const min = ist.getUTCHours()*60 + ist.getUTCMinutes();
  const open = day>=1&&day<=5 && min>=555&&min<=935;
  const el  = document.getElementById('clk');
  if(el) el.textContent = (open?'● ':'○ ')+'NSE '+t+' IST';
}
setInterval(updClock,10000);updClock();

// ── Storage ───────────────────────────────────────────
// PERSISTENCE — load/save portfolio, watchlist, settings
function loadState(){
  try{S.portfolio=JSON.parse(localStorage.getItem(SK.PORT))||[];}catch(_){}
  try{S.watchlist=JSON.parse(localStorage.getItem(SK.WL))||[];}catch(_){}
  try{Object.assign(S.settings,JSON.parse(localStorage.getItem(SK.SETTINGS))||{});}catch(_){}

}
// Save portfolio to localStorage + build export data
function savePF(){
  localStorage.setItem(SK.PORT,JSON.stringify(S.portfolio));
  // Also write portfolio.json to the repo root so GitHub Actions
  // can fetch fundamentals for ALL portfolio stocks (not just watchlist.txt).
  // This uses the Storage API if available, otherwise silently skips.
  try{
    const pfData = JSON.stringify({
      portfolio: S.portfolio.map(h=>({
        sym:    h.sym,
        isin:   h.isin||'',
        name:   h.name||h.sym,
        sector: h.sector||'',
      }))
    }, null, 2);
    // Store in window for the export button
    window._pfExportData = pfData;
  }catch(_){}
}

// Export portfolio symbols — user downloads and commits to repo
// Manual fallback export — normally auto-synced on import
function exportPortfolioSymbols(){
  const syms = S.portfolio.map(h=>h.sym).filter(Boolean);
  if(!syms.length){toast('No portfolio to export');return;}
  // Format: SYM|CDSL Company Name  — name used by fetch_fundamentals for Yahoo search
  const txt = S.portfolio
    .filter(h=>h.sym)
    .map(h=>h.cdslName ? h.sym+'|'+h.cdslName : h.sym)
    .join('\n');

  // iOS Safari PWA blocks <a download> — show modal with text to copy instead
  const ov = document.getElementById('ov');
  const panel = document.getElementById('import-panel');
  const body  = document.getElementById('import-panel-body');
  body.innerHTML = `
    <div style="margin-bottom:10px;font-size:11px;color:var(--tx2);line-height:1.7">
      <b class="u-gr2">Step 1</b> — Long-press the text below → Select All → Copy<br>
      <b class="u-gr2">Step 2</b> — In GitHub repo → Add file → Create new file<br>
      <b class="u-gr2">Step 3</b> — Name it <code style="color:var(--ac)">portfolio_symbols.txt</code> → Paste → Commit
    </div>
    <div class="u-rel">
      <textarea id="sym-export-ta" readonly
        style="width:100%;height:220px;background:#02040a;border:1px solid var(--b2);
        border-radius:8px;padding:12px;color:var(--gr2);font-family:'JetBrains Mono',monospace;
        font-size:11px;line-height:1.8;resize:none;box-sizing:border-box;"
        onclick="this.select()">${txt}</textarea>
    </div>
    <button onclick="
      const ta=document.getElementById('sym-export-ta');
      ta.select();
      if(navigator.clipboard){
        navigator.clipboard.writeText(ta.value).then(()=>toast('✓ Copied to clipboard!'));
      } else {
        document.execCommand('copy');
        toast('✓ Copied!');
      }
    " style="width:100%;margin-top:10px;padding:13px;background:var(--gr3);border:1px solid var(--gr);
      border-radius:10px;color:var(--gr2);font-size:13px;font-weight:700;cursor:pointer;
      font-family:'Syne',sans-serif;">
      📋 Copy ${syms.length} Symbols to Clipboard
    </button>
    <div style="margin-top:10px;font-size:9px;color:var(--mu);text-align:center;font-family:var(--mono)">
      Auto-synced on import if GitHub is configured · or commit manually as fallback
    </div>
  `;
  ov.classList.add('on');
  panel.classList.add('on');
  // Select all text after render
  setTimeout(()=>{
    const ta=document.getElementById('sym-export-ta');
    if(ta) ta.select();
  },100);
}
// Save watchlist to localStorage
function saveWL(){localStorage.setItem(SK.WL,JSON.stringify(S.watchlist));}
// Save settings (GitHub token, repo, AI key) to localStorage
function saveSettings(){localStorage.setItem(SK.SETTINGS,JSON.stringify(S.settings));}

// ── Ticker ────────────────────────────────────────────
// TICKER BAR — index prices scrolling at top (currently hidden)
function buildTicker(){
  // Build from FUND index data if available, else show placeholder
  const indexMap = {
    'NIFTY':'NIFTY 50','BANKNIFTY':'Bank Nifty',
    'NIFTYMIDCAP100':'Midcap 100','CNXIT':'Nifty IT',
  };
  let items = Object.entries(indexMap).map(([sym,name])=>{
    const f = FUND[sym];
    if(!f||!f.ltp) return null;
    return {name, val: f.ltp.toLocaleString('en-IN'), chg: f.chg1d||0};
  }).filter(Boolean);

  // Fallback if FUND not loaded yet
  if(!items.length){
    items = [{name:'NIFTY 50',val:'—',chg:0},{name:'Bank Nifty',val:'—',chg:0}];
  }

  const all = [...items,...items]; // double for seamless loop
  document.getElementById('tkinner').innerHTML = all.map(i=>
    `<div class="ti">
      <span class="ti-n">${i.name}</span>
      <div class="ti-r">
        <span class="ti-v">${i.val}</span>
        <span class="ti-c" style="color:${i.chg>=0?'var(--gr2)':'var(--rd2)'}">${i.chg>=0?'▲':'▼'} ${Math.abs(i.chg).toFixed(2)}%</span>
      </div>
    </div>`
  ).join('');
}

// ── Navigation ────────────────────────────────────────
// ── Tab navigation ──────────────────────────────────────────
function showTab(t,btn){
  S.curTab=t;S.selStock=null;S.drillTab='overview';S.expMacro=null;
  document.querySelectorAll('.nb').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  render();
}
// ── Main render dispatcher ──────────────────────────────────
function render(){
  const c=document.getElementById('content');
  if(!c) return;
  try{
    if(S.selStock){renderDrill(c);return;}
    if(S.curTab==='portfolio')renderPortfolio(c);
    else if(S.curTab==='watchlist')renderWatchlist(c);
    else if(S.curTab==='macro')renderMacro(c);
    else if(S.curTab==='movers')renderMovers(c);
    else if(S.curTab==='analysis')renderAnalysis(c);
    else if(S.curTab==='upload')renderUpload(c);
  } catch(err){
    console.error('render() error:', err);
  }
}
function openStock(w){
  // w is the watchlist item (already FUND-merged by renderWatchlist)
  const sym = w.symbol;
  const f   = FUND[sym] || {};
  const info= FUND[sym] || {name:sym, sector:'Diversified'};
  const ltp = w.ltp || f.ltp || 0;

  S.selStock = {
    symbol:   sym,
    name:     f.name    || w.name    || info.name || sym,
    sector:   f.sector  || w.sector  || info.sector || 'Diversified',
    ltp,
    prev:     f.prev    || null,
    change:   w.change  || f.chg1d   || 0,
    qty:      null,   // not a portfolio holding
    avgBuy:   null,
    pe:       f.pe      || null,
    pb:       f.pb      || null,
    roe:      f.roe     || null,
    roce:     f.roce    || null,
    debtEq:   f.debt_eq || null,
    divYield: f.div_yield || null,
    promoter: f.prom_pct  || null,
    eps:      f.eps     || null,
    mcap:     f.mcap    ? f.mcap+'Cr' : null,
    week52H:  f.w52h    || null,
    week52L:  f.w52l    || null,
    beta:     f.beta    || null,
    sma20:null, sma50:null, ema200:null,
    rsi:null, macd:null, macdSignal:null,
    adx:null, stochK:null, stochD:null,
    atr:null, support1:null, resist1:null,
    candles:  [],
    quarterly: f.quarterly || [],
    fwd_pe:   f.fwd_pe  || null,
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

// ── Panel ─────────────────────────────────────────────
async function loadStaticData() {
  // Build ISIN_MAP from symbols.json (nse_db.json deprecated)
  // Use same-origin Pages URL — no CORS issues, symbols.json rarely changes
  _staticDataReady = (async () => {
    try {
      const r = await fetch('./symbols.json?t=' + Date.now(), {cache:'no-store'});
      if (r.ok) {
        const syms = await r.json();
        syms.forEach(s => { if(s.isin && s.sym && s.resolved) ISIN_MAP[s.isin] = s.sym; });
        console.warn('ISIN_MAP built: ' + Object.keys(ISIN_MAP).length + ' entries');
      }
    } catch(e) { console.warn('symbols.json load failed:', e.message); }
  })();
  await _staticDataReady;

  try {
    const r = await fetch('./macro_data.json?t=' + Date.now(), {cache:'force-cache'});
    if (r.ok) { MACRO_DATA = await r.json(); }
  } catch(e) { console.warn('macro_data.json load failed:', e.message); }
}

// Ensure ISIN_MAP is ready before using it (call from import)
async function ensureStaticData() {
  if(_staticDataReady) await _staticDataReady;
}

// boot() is defined in app-boot.js (loads last, after all modules)