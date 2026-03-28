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
// NSE_DB loaded from nse_db.json on boot
let NSE_DB = [];
let ISIN_MAP = {};

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
      <b style="color:var(--gr2)">Step 1</b> — Long-press the text below → Select All → Copy<br>
      <b style="color:var(--gr2)">Step 2</b> — In GitHub repo → Add file → Create new file<br>
      <b style="color:var(--gr2)">Step 3</b> — Name it <code style="color:var(--ac)">portfolio_symbols.txt</code> → Paste → Commit
    </div>
    <div style="position:relative">
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
  const info= NSE_DB.find(s=>s.sym===sym) || {name:sym, sector:'Diversified'};
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
function openPanel(){document.getElementById('ov').classList.add('on');document.getElementById('import-panel').classList.add('on');}
function closePanel(){document.getElementById('ov').classList.remove('on');document.getElementById('import-panel').classList.remove('on');}
// PORTFOLIO IMPORT — CDSL XLS, CSV, or manual entry
// Parses holdings, saves, then triggers full data refresh
function openImport(){
  parsedHoldings = [];   // always start fresh
  document.getElementById('import-panel-body').innerHTML=renderImportPanel();
  openPanel();
}

function renderImportPanel(){
  return `
  <style>
  .imp-tabs{display:flex;gap:0;border-bottom:2px solid var(--b2);margin-bottom:14px;}
  .imp-tab{flex:1;padding:9px 6px;text-align:center;font-size:11px;font-weight:700;
    font-family:'Syne',sans-serif;cursor:pointer;color:var(--tx3);
    border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .15s;}
  .imp-tab.on{color:var(--ac);border-bottom-color:var(--ac);}
  .imp-pane{display:none;} .imp-pane.on{display:block;}
  .file-drop{border:2px dashed var(--b2);border-radius:12px;padding:28px 16px;
    text-align:center;cursor:pointer;transition:all .2s;background:var(--s1);}
  .file-drop:hover,.file-drop.drag{border-color:var(--ac);background:rgba(249,115,22,.06);}
  .file-drop input[type=file]{display:none;}
  .file-drop-icon{font-size:32px;margin-bottom:8px;}
  .file-drop-title{font-size:13px;font-weight:700;color:var(--tx);font-family:'Syne',sans-serif;margin-bottom:4px;}
  .file-drop-sub{font-size:10px;color:var(--tx3);line-height:1.6;}
  .file-drop-sub b{color:var(--gr2);}
  .imp-fmt{background:var(--bg);border:1px solid var(--b1);border-radius:8px;
    padding:10px 12px;font-size:9px;color:var(--tx3);line-height:1.9;
    font-family:var(--mono);margin-bottom:12px;}
  .imp-report{margin-top:10px;border-radius:8px;overflow:hidden;font-size:10px;}
  .imp-report-row{padding:6px 10px;border-bottom:1px solid var(--b1);display:flex;gap:8px;align-items:flex-start;}
  .imp-report-sym{font-family:var(--mono);font-weight:700;min-width:90px;color:var(--tx1);}
  .imp-report-reason{color:var(--tx3);}
  </style>

  <!-- Tabs -->
  <div class="imp-tabs">
    <div class="imp-tab on" id="itab-file" onclick="switchImpTab('file')">📁 CDSL XLS</div>
    <div class="imp-tab" id="itab-paste" onclick="switchImpTab('paste')">📋 CDSL Text</div>
    <div class="imp-tab" id="itab-manual" onclick="switchImpTab('manual')">✏ Manual</div>
  </div>

  <!-- Tab: XLS File Upload -->
  <div class="imp-pane on" id="ipane-file">
    <div class="file-drop" id="file-drop-zone"
      onclick="document.getElementById('file-input').click()"
      ondragover="event.preventDefault();this.classList.add('drag')"
      ondragleave="this.classList.remove('drag')"
      ondrop="handleFileDrop(event)">
      <input type="file" id="file-input" accept=".xls,.xlsx,.csv"
        onchange="handleFileSelect(this.files[0])">
      <div class="file-drop-icon">📂</div>
      <div class="file-drop-title">Tap to select CDSL XLS file</div>
      <div class="file-drop-sub">
        <b>CDSL Easiest → Portfolio → Equity Summary Details → Download XLS</b><br>
        Has: symbol, sector, qty, avg buy price — single file, full import
      </div>
    </div>
    <div id="file-status" style="margin-top:10px;font-size:10px;color:var(--tx3);font-family:var(--mono);min-height:20px"></div>
    <!-- Error/warning report -->
    <div id="imp-report" style="display:none;margin-top:8px"></div>
  </div>

  <!-- Tab: CDSL Text Paste -->
  <div class="imp-pane" id="ipane-paste">
    <div class="imp-fmt">
      <b style="color:var(--gr2)">How to get this:</b><br>
      CDSL Easiest → Statement → Holdings → Select All → Copy → Paste below<br><br>
      <b style="color:var(--yw2)">Format:</b><br>
      INE040A01034 HDFC BANK LIMITED - EQ Beneficiary 84 68628.00<br><br>
      <b style="color:var(--rd2)">⚠ No avg buy price in this format</b> — use XLS tab for full data
    </div>
    <textarea class="import-textarea" id="import-ta"
      placeholder="Paste CDSL statement text here…&#10;&#10;INE040A01034 HDFC BANK LIMITED - EQ Beneficiary 84 68628"
      oninput="liveParseImport(this.value)" rows="9"></textarea>
  </div>

  <!-- Tab: Manual Entry -->
  <div class="imp-pane" id="ipane-manual">
    <div class="imp-fmt">
      <b style="color:var(--gr2)">Format:</b>  SYMBOL, QTY, AVG_BUY<br>
      One stock per line. AVG_BUY is optional.<br><br>
      <b style="color:var(--bl2)">Examples:</b><br>
      RELIANCE, 10, 2450<br>
      HDFCBANK, 84, 817.50<br>
      TATAPOWER, 100<br><br>
      <b style="color:var(--tx3)">Find your symbol:</b> use NSE website or Screener.in
    </div>
    <textarea class="import-textarea" id="import-ta-manual"
      placeholder="RELIANCE, 10, 2450&#10;HDFCBANK, 84, 817&#10;TATAPOWER, 100, 385"
      oninput="liveParseImport(this.value,'manual')" rows="9"></textarea>
  </div>

  <!-- Preview -->
  <div class="import-err" id="import-err"></div>
  <div class="import-preview" id="import-preview">
    <div class="import-preview-title" id="import-preview-title">Preview</div>
    <div id="import-preview-rows"></div>
  </div>

  <button class="import-btn" onclick="applyImport('replace')">✓ Import (Replace All)</button>
  <button class="import-btn" style="background:var(--s2);border:1px solid var(--b2);color:var(--tx2);margin-top:6px"
    onclick="applyImport('append')">+ Append to Existing</button>
  `;
}

function switchImpTab(tab){
  ['file','paste','manual'].forEach(t=>{
    document.getElementById('itab-'+t).classList.toggle('on', t===tab);
    document.getElementById('ipane-'+t).classList.toggle('on', t===tab);
  });
}

// ── File Upload Handler ─────────────────────────────
function handleFileDrop(e){
  e.preventDefault();
  document.getElementById('file-drop-zone').classList.remove('drag');
  const file = e.dataTransfer.files[0];
  if(file) handleFileSelect(file);
}

function handleFileSelect(file){
  if(!file) return;
  const status = document.getElementById('file-status');
  status.innerHTML = `<span style="color:var(--yw2)">⏳ Reading ${file.name}…</span>`;

  const ext = file.name.split('.').pop().toLowerCase();

  // XLS/XLSX — use SheetJS (CDN)
  if(ext==='xls'||ext==='xlsx'){
    loadSheetJS(()=>{
      const reader = new FileReader();
      reader.onload = e=>{
        try{
          const wb  = XLSX.read(e.target.result, {type:'binary'});
          const ws  = wb.Sheets[wb.SheetNames[0]];
          const csv = XLSX.utils.sheet_to_csv(ws);
          processImportText(csv, file.name, status);
        } catch(err){
          status.innerHTML = `<span style="color:var(--rd2)">✗ Could not read XLS: ${err.message}</span>`;
        }
      };
      reader.readAsBinaryString(file);
    });
    return;
  }

  // CSV / TXT — read as text
  const reader = new FileReader();
  reader.onload = e => processImportText(e.target.result, file.name, status);
  reader.onerror = ()=>{ status.innerHTML='<span style="color:var(--rd2)">✗ Could not read file</span>'; };
  reader.readAsText(file);
}

let _sheetJSLoaded = false;
function loadSheetJS(cb){
  if(_sheetJSLoaded){ cb(); return; }
  if(window.XLSX){ _sheetJSLoaded=true; cb(); return; }
  const s = document.createElement('script');
  s.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js';
  s.onload = ()=>{ _sheetJSLoaded=true; cb(); };
  s.onerror = ()=>{
    document.getElementById('file-status').innerHTML=
      '<span style="color:var(--rd2)">✗ Could not load XLS reader — try saving as CSV first</span>';
  };
  document.head.appendChild(s);
}

// ── CDSL XLS parser — full import with error/warning report ─────
function parseCDSLXls(csv){
  const imported = [], warnings = [], rejected = [];
  const lines = csv.split(/\r?\n/).map(l=>l.trim()).filter(l=>l.length>0);

  // Find header row
  let headerIdx = -1;
  for(let i=0;i<Math.min(10,lines.length);i++){
    if(/stock name/i.test(lines[i]) && /isin/i.test(lines[i]) && /quantity/i.test(lines[i])){
      headerIdx = i; break;
    }
  }
  if(headerIdx<0){ return {imported,warnings,rejected,error:'Header row not found — check file format'}; }

  const hdrs = lines[headerIdx].split(',').map(h=>h.replace(/"/g,'').trim().toLowerCase());
  const col = k => hdrs.findIndex(h=>h.includes(k));
  const iC  = col('isin'),  nC  = col('stock name'), secC = col('sector');
  const qC  = col('quantity'), avgC = col('average cost'), ltpC = col('current market price');

  for(let i=headerIdx+1; i<lines.length; i++){
    const cols = lines[i].split(',').map(c=>c.replace(/"/g,'').trim());
    if(cols.length < 4) continue;

    const name   = nC>=0   ? cols[nC]   : '';
    const isin   = iC>=0   ? cols[iC]   : '';
    const sector = secC>=0 ? cols[secC] : '';
    const qtyRaw = qC>=0   ? cols[qC]   : '';
    const avgRaw = avgC>=0 ? cols[avgC] : '';
    const ltpRaw = ltpC>=0 ? cols[ltpC] : '';

    if(!name && !isin) continue; // blank row

    // Reject bonds/ETFs/SGBs
    if(/goldbond|sgb|ETF/i.test(isin) || /^INF/.test(isin) || /ETF|Bond|SGB/i.test(name)){
      rejected.push({name:name||isin, reason:'Bond/ETF/SGB — equity only'});
      continue;
    }

    // Reject missing ISIN
    if(!isin || !/^IN[A-Z0-9]{10,12}$/.test(isin)){
      rejected.push({name:name||'(unknown)', reason:'Invalid or missing ISIN'});
      continue;
    }

    const qty    = Math.round(parseFloat(qtyRaw.replace(/,/g,''))||0);
    const avgBuy = Math.round(parseFloat(avgRaw.replace(/,/g,''))*100)/100 || 0;
    const snapLtp= Math.round(parseFloat(ltpRaw.replace(/,/g,''))*100)/100 || 0;

    // Reject zero qty
    if(qty<=0){
      rejected.push({name, reason:'Quantity is 0 or missing'});
      continue;
    }

    // Resolve symbol from ISIN
    let sym = ISIN_MAP[isin] || '';
    if(!sym){
      // Try name match in NSE_DB
      const nameParts = name.toUpperCase().replace(/\s+/g,' ').split(' ').slice(0,2).join(' ');
      const found = NSE_DB.find(s=>s.name.toUpperCase().startsWith(nameParts));
      sym = found ? found.sym : name.replace(/[^A-Z0-9]/g,'').slice(0,12).toUpperCase();
      warnings.push({name, sym, reason:'ISIN not in map — symbol derived from name, may not have live prices'});
    }

    const info = NSE_DB.find(s=>s.sym===sym)||{};
    imported.push({
      sym, isin,
      name:   info.name || name,
      sector: info.sector || sector || 'Diversified',
      qty,
      avgBuy,
      ltp:    snapLtp,   // CDSL snapshot — will be replaced by live fetch
      liveLtp: 0,
      change: 0,
    });
  }
  return {imported, warnings, rejected};
}

function renderImportReport(result, filename){
  const {imported, warnings, rejected, error} = result;
  if(error) return '<div style="color:var(--rd2);padding:8px">❌ '+error+'</div>';

  let html = '<div style="padding:8px 0">';

  // Summary line
  html += '<div style="display:flex;gap:10px;margin-bottom:8px;font-weight:700;font-size:11px">';
  html += '<span style="color:#00e896">✅ '+imported.length+' imported</span>';
  if(warnings.length) html += '<span style="color:#ffbf47">⚠ '+warnings.length+' warnings</span>';
  if(rejected.length) html += '<span style="color:#ff6b85">❌ '+rejected.length+' rejected</span>';
  html += '</div>';

  // Warnings
  if(warnings.length){
    html += '<div style="background:rgba(245,166,35,.06);border:1px solid rgba(245,166,35,.2);border-radius:6px;margin-bottom:6px">';
    html += '<div style="padding:5px 10px;font-size:9px;font-weight:700;color:#ffbf47;border-bottom:1px solid rgba(245,166,35,.15)">⚠ WARNINGS</div>';
    warnings.forEach(w=>{
      html += '<div class="imp-report-row"><span class="imp-report-sym">'+(w.sym||w.name).slice(0,14)+'</span><span class="imp-report-reason">'+w.reason+'</span></div>';
    });
    html += '</div>';
  }

  // Rejected
  if(rejected.length){
    html += '<div style="background:rgba(255,59,92,.06);border:1px solid rgba(255,59,92,.2);border-radius:6px">';
    html += '<div style="padding:5px 10px;font-size:9px;font-weight:700;color:#ff6b85;border-bottom:1px solid rgba(255,59,92,.15)">❌ REJECTED</div>';
    rejected.forEach(r=>{
      html += '<div class="imp-report-row"><span class="imp-report-sym">'+r.name.slice(0,14)+'</span><span class="imp-report-reason">'+r.reason+'</span></div>';
    });
    html += '</div>';
  }

  html += '</div>';
  return html;
}

function processImportText(text, filename, statusEl){
  // Check if this looks like CDSL XLS (has the known header)
  const isCDSLXls = /stock name.*isin.*sector.*quantity.*average cost/i.test(text.slice(0,500));

  if(isCDSLXls){
    const result = parseCDSLXls(text);
    if(result.error){
      statusEl.innerHTML = '<span style="color:var(--rd2)">✗ '+result.error+'</span>';
      return;
    }
    parsedHoldings = result.imported;
    statusEl.innerHTML = '<span style="color:var(--gr2)">✓ '+filename+' parsed</span>';
    // Show report
    const rpt = document.getElementById('imp-report');
    if(rpt){ rpt.style.display='block'; rpt.innerHTML=renderImportReport(result, filename); }
    showImportPreview();
  } else {
    // Generic parser (CDSL text or manual CSV)
    parsedHoldings = parsePortfolioText(text);
    const rpt = document.getElementById('imp-report');
    if(rpt) rpt.style.display='none';
    if(parsedHoldings.length){
      statusEl.innerHTML = '<span style="color:var(--gr2)">✓ '+filename+' — '+parsedHoldings.length+' holdings detected</span>';
      showImportPreview();
    } else {
      statusEl.innerHTML = '<span style="color:var(--rd2)">✗ No holdings found in '+filename+' — check format</span>';
    }
  }
}

let parsedHoldings = [];

function liveParseImport(text, mode){
  parsedHoldings = parsePortfolioText(text);
  const errEl = document.getElementById('import-err');
  const preEl = document.getElementById('import-preview');
  if(!errEl||!preEl) return;

  if(!text.trim()){
    errEl.classList.remove('show');
    preEl.classList.remove('show');
    return;
  }
  if(!parsedHoldings.length){
    errEl.textContent = 'No valid holdings detected. Check format.';
    errEl.classList.add('show');
    preEl.classList.remove('show');
    return;
  }
  errEl.classList.remove('show');
  showImportPreview();
}

function showImportPreview(){
  const preEl    = document.getElementById('import-preview');
  const preRows  = document.getElementById('import-preview-rows');
  const preTitle = document.getElementById('import-preview-title');
  if(!preEl) return;
  preTitle.textContent = `✓ ${parsedHoldings.length} holdings detected`;
  preRows.innerHTML = parsedHoldings.slice(0,10).map(h=>`
    <div style="display:flex;justify-content:space-between;align-items:center;
      padding:5px 0;border-bottom:1px solid var(--b1);font-size:10px">
      <div>
        <span style="font-family:var(--mono);font-weight:700;color:var(--tx)">${h.sym}</span>
        <span style="color:var(--tx3);margin-left:6px;font-size:8px">${h.isin||''}</span>
      </div>
      <div style="display:flex;gap:10px;font-family:var(--mono)">
        <span style="color:var(--bl2)">×${h.qty}</span>
        <span style="color:${h.avgBuy>0?'var(--gr2)':'var(--mu)'}">
          ${h.avgBuy>0?'₹'+fmt(h.avgBuy):'avg?'}
        </span>
        ${h.ltp>0?`<span style="color:var(--tx3)">@₹${h.ltp.toFixed(1)}</span>`:''}
      </div>
    </div>`).join('') +
    (parsedHoldings.length>10
      ? `<div style="font-size:9px;color:var(--mu);padding:5px 0">+${parsedHoldings.length-10} more…</div>`
      : '');
  preEl.classList.add('show');
}

// Robust multi-format parser
// Multi-format parser: CDSL XLS export, plain CSV, CDSL PDF text
// Priority: CDSL export format → Key:Value → numbered list
function parsePortfolioText(text){
  const results = [];
  const seen    = new Set();

  // ── Detect CDSL XLS/CSV export format ─────────────────────────
  // Header: Stock Name,ISIN,Sector Name,Quantity,Average Cost Price,Value At Cost,
  //         Current Market Price,Current Market Price % Change,Valuation at Current Market Price,
  //         Unrealized Profit/Loss,...
  const isCDSLExport = /Stock Name.*ISIN.*Sector.*Quantity.*Average Cost Price/i.test(text) ||
                       /ISIN.*Sector.*Quantity.*Average Cost/i.test(text);

  if(isCDSLExport){
    // Parse as CSV — split by lines, skip header rows and summary rows
    const lines = text.replace(/\r/g,'').split('\n');
    for(const line of lines){
      const cols = line.split(',').map(c=>c.replace(/^"|"$/g,'').trim());
      // Need at least: name, isin, sector, qty, avgBuy
      if(cols.length < 5) continue;
      const isin = cols[1];
      if(!/^IN[A-Z0-9]{10,12}$/.test(isin)) continue; // must have valid ISIN

      const name    = cols[0].trim();
      const sector  = cols[2].trim();
      const qty     = Math.round(parseFloat(cols[3].replace(/,/g,''))||0);
      const avgBuy  = Math.round(parseFloat(cols[4].replace(/,/g,''))*100)/100 || 0;
      const ltp     = Math.round(parseFloat((cols[6]||'').replace(/,/g,''))*100)/100 || 0;
      const pnl     = parseFloat((cols[9]||'').replace(/,/g,'')) || 0;

      if(!name || qty <= 0 || seen.has(isin)) continue;

      // Skip ETFs and Bonds (no NSE equity symbol)
      if(/ETF|BOND|GOLDBOND|SGB|SBI ETF|MIRAEAMC/i.test(name)) continue;

      // Resolve NSE symbol from ISIN map first, then name
      let sym = ISIN_MAP[isin] || '';
      if(!sym){
        // Try matching name against NSE_DB
        const nameUp = name.toUpperCase();
        const found  = NSE_DB.find(s=>
          nameUp.startsWith(s.name.toUpperCase().slice(0,8)) ||
          s.name.toUpperCase().startsWith(nameUp.slice(0,8))
        );
        sym = found ? found.sym : name.replace(/[^A-Z0-9]/g,'').slice(0,12);
      }

      seen.add(isin);
      const info = NSE_DB.find(s=>s.sym===sym)||{name,sector};
      results.push({
        sym,
        isin,
        cdslName: name,   // original CDSL company name — used for Yahoo search fallback
        name:    info.name || name,
        sector:  info.sector || sector || 'Diversified',
        qty,
        avgBuy,           // ✅ Real avg buy price from CDSL
        ltp,              // Current market price from CDSL
        change:  0,
        pnl,              // Unrealized P&L from CDSL
        cdslImport: true,
      });
    }
    console.log('CDSL export parsed:', results.length, 'holdings');
    return results;
  }

  // ── Fallback: Plain text / manual paste ────────────────────────
  // Step 1: Join wrapped CDSL lines (ISIN on line 1, Beneficiary on line 2)
  const rawLines = text.replace(/\r/g,'').split('\n').map(l=>l.trim()).filter(l=>l.length>2);
  const joined   = [];
  let i = 0;
  while(i < rawLines.length){
    const cur    = rawLines[i];
    const hasISIN = /\bIN[A-Z0-9]{10,12}\b/.test(cur);
    const hasBen  = /beneficiary/i.test(cur);
    if(hasISIN && !hasBen && i+1 < rawLines.length){
      let merged = cur, j = i+1;
      while(j < rawLines.length && !/beneficiary/i.test(merged)){
        merged = merged + ' ' + rawLines[j]; j++;
      }
      joined.push(merged); i = j;
    } else {
      joined.push(cur); i++;
    }
  }

  for(const line of joined){
    if(/^(symbol|name|isin|sr\.?no|total|date|page|user|holding|demat|client)/i.test(line)) continue;
    if(/saturday|sunday|monday|tuesday|wednesday|thursday|friday/i.test(line)) continue;
    if(/mutual fund|government of india|SGB|sovereign/i.test(line)) continue;
    if(line.length < 5) continue;

    let sym='', isin='', qty=0, avgBuy=0, ltp=0;

    // Pattern 1: CDSL text — has ISIN + Beneficiary
    const cdslMatch = line.match(/\b(IN[A-Z0-9]{10,12})\b/);
    if(cdslMatch){
      isin = cdslMatch[1];
      sym  = ISIN_MAP[isin] || '';
      const benIdx  = line.search(/beneficiary/i);
      const numPart = benIdx >= 0 ? line.slice(benIdx) : line;
      const nums    = [...numPart.matchAll(/[\d,]+\.?\d*/g)]
        .map(m=>parseFloat(m[0].replace(/,/g,'')))
        .filter(n=>n>0&&n<1e10);
      if(nums.length>=2){
        qty = Math.round(nums[0]);
        // CDSL text last number = current market value (qty × LTP)
        // Derive LTP from value/qty — this is the CDSL snapshot price, not avg buy
        // avgBuy is NOT available in CDSL text format — leave as 0
        // But we store the CDSL value/qty as ltp so at least we have a price reference
        const totalVal = nums[nums.length-1];
        ltp = qty>0 ? Math.round(totalVal/qty*100)/100 : 0;
        avgBuy = 0; // CDSL text format does not include avg buy price
        // Note: to get avgBuy, use CDSL XLS/CSV export (Equity_Summary_Details)
      } else if(nums.length===1){
        qty = Math.round(nums[0]);
      }
      if(!sym){
        const nameMatch = line.replace(isin,'')
          .replace(/new\s+fv\s+r[se]\.?\s*[\d./]+\s*/gi,'')
          .replace(/fv\s+r[se]\.?\s*[\d./]+\s*/gi,'')
          .match(/([A-Z][A-Z\s&.()\-]+?(?:LTD\.?|LIMITED|CORP|CO\.?|IND|BANK|POWER|TECH|SOLAR|ENERGY|FINANCE))/i);
        if(nameMatch){
          const nu = nameMatch[1].toUpperCase().replace(/\s+/g,' ').trim();
          const found = NSE_DB.find(s=>
            s.name.toUpperCase().startsWith(nu.split(' ').slice(0,2).join(' ')) ||
            nu.startsWith(s.name.toUpperCase().split(' ').slice(0,2).join(' '))
          );
          sym = found ? found.sym : nu.replace(/[^A-Z0-9]/g,'').slice(0,12);
        }
      }
      if(sym && qty>0 && !seen.has(isin)){
        seen.add(isin);
        const info = NSE_DB.find(s=>s.sym===sym)||{name:sym,sector:'Diversified'};
        results.push({sym,isin,name:info.name||sym,sector:info.sector||'Diversified',
          qty:Math.round(qty),avgBuy,ltp,change:0});
      }
      continue;
    }

    // Pattern 2: CSV / manual — Symbol, Qty, AvgBuy  OR  Symbol, ISIN, Qty, AvgBuy
    const parts = line.split(/[,\t|;]+/).map(p=>p.trim()).filter(Boolean);
    if(parts.length>=2){
      const maybeISIN = parts.find(p=>/^IN[A-Z0-9]{10,12}$/.test(p));
      const maybeSym  = parts[0].toUpperCase().replace(/[^A-Z0-9&\-]/g,'').replace(/\.NS$/,'');
      const nums      = parts.map(p=>parseFloat(p.replace(/[,₹]/g,''))).filter(n=>!isNaN(n)&&n>0);
      isin = maybeISIN || '';
      sym  = isin ? (ISIN_MAP[isin]||maybeSym) : maybeSym;
      if(nums.length>=2){ qty=Math.round(nums[0]); avgBuy=nums[1]; }
      // If 3 numbers and nums[1] looks like a total invested amount (not per-share):
      // heuristic — if nums[1]/nums[0] gives a price < nums[2] then nums[1] is total
      if(nums.length>=3){
        const perShare = nums[1]/Math.max(nums[0],1);
        if(perShare > 1 && perShare < nums[2] * 0.95){
          qty = Math.round(nums[0]);
          avgBuy = Math.round(perShare*100)/100;
        }
      }
      if(sym&&sym.length>=2&&sym.length<=15&&qty>0&&avgBuy>0&&!seen.has(sym)){
        seen.add(sym);
        const info=NSE_DB.find(s=>s.sym===sym)||{name:sym,sector:'Diversified'};
        results.push({sym,isin,name:info.name||sym,sector:info.sector||'Diversified',
          qty:Math.round(qty),avgBuy,ltp:0,change:0});
      }
    }
  }
  return results;
}

// Apply parsed holdings to portfolio, then trigger data refresh
function applyImport(mode){
  if(!parsedHoldings.length){toast('Nothing to import — paste data first');return;}

  // Save avgBuy values keyed by sym AND isin before any changes
  // so they survive both replace and append modes
  const savedAvg = {};
  S.portfolio.forEach(h=>{
    if(h.avgBuy>0){
      if(h.sym)  savedAvg[h.sym]  = h.avgBuy;
      if(h.isin) savedAvg[h.isin] = h.avgBuy;
    }
  });

  if(mode==='replace') S.portfolio=[];
  const existing = new Set(S.portfolio.map(h=>h.sym));
  parsedHoldings.forEach(h=>{
    if(existing.has(h.sym)){
      const idx=S.portfolio.findIndex(p=>p.sym===h.sym);
      if(idx>=0) Object.assign(S.portfolio[idx],h);
    } else {
      S.portfolio.push({...h});
      existing.add(h.sym);
    }
  });

  // Restore avgBuy values that were lost during import
  S.portfolio.forEach(h=>{
    if(!h.avgBuy || h.avgBuy===0){
      const restored = savedAvg[h.sym] || savedAvg[h.isin] || 0;
      if(restored) h.avgBuy = restored;
    }
  });
  savePF();
  closePanel();
  parsedHoldings = [];

  // ── Switch to portfolio tab immediately ───────────────────────
  S.curTab = 'portfolio';
  document.querySelectorAll('.nb').forEach(b=>b.classList.remove('active'));
  const pfBtn = document.querySelector('.nb');
  if(pfBtn) pfBtn.classList.add('active');

  // Set sync status to show live progress in portfolio tab
  S._importStatus = { state:'syncing', msg:'Imported — refreshing data…', ts: Date.now() };
  render();

  // ── Data refresh pipeline (sequential, with visible status) ──
  (async ()=>{
    // Step 1: Clear stale fund cache + reload fundamentals.json
    localStorage.removeItem('fund_cache');
    localStorage.removeItem('fund_cache_ts');
    S._importStatus = { state:'syncing', msg:'Step 1/3 — Loading fundamentals…', ts: Date.now() };
    updateImportStatus();
    await loadFundamentals(true);
    render();

    // Step 2: Fetch live prices
    S._importStatus = { state:'syncing', msg:'Step 2/3 — Fetching live prices…', ts: Date.now() };
    updateImportStatus();
    await refreshPortfolioData();

    // Step 3: Sync to GitHub + trigger Actions
    S._importStatus = { state:'syncing', msg:'Step 3/3 — Syncing to GitHub…', ts: Date.now() };
    updateImportStatus();
    await autoSyncPortfolioSymbols();
  })();
}

// ── Update the status strip in portfolio tab without full re-render ──
function updateImportStatus(){
  const el = document.getElementById('import-status-strip');
  if(el && S._importStatus) el.innerHTML = importStatusHtml();
}

function importStatusHtml(){
  const st = S._importStatus;
  if(!st) return '';
  const col = st.state==='ok'?'#00e896':st.state==='error'?'#ff6b85':'#ffbf47';
  const icon = st.state==='ok'?'✅':st.state==='error'?'❌':'⏳';
  return `<div style="padding:8px 13px;background:rgba(${st.state==='ok'?'0,208,132':st.state==='error'?'255,59,92':'245,166,35'},.08);
    border-bottom:1px solid rgba(${st.state==='ok'?'0,208,132':st.state==='error'?'255,59,92':'245,166,35'},.2);
    font-size:11px;color:${col};font-family:'JetBrains Mono',monospace;display:flex;justify-content:space-between;align-items:center">
    <span>${icon} ${st.msg}</span>
    ${st.state!=='syncing'?`<span style="font-size:9px;color:var(--tx3)">${new Date(st.ts).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:true})}</span>`:'<span style="font-size:9px;color:var(--tx3)">working…</span>'}
  </div>`;
}

// ── Auto-sync portfolio symbols to GitHub after import ────────────
// AUTO-SYNC — commits portfolio_symbols.txt to GitHub
// and triggers fundamentals_only workflow after import

async function autoSyncPortfolioSymbols(){
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  if(!token || !repo) return; // silent — user hasn't configured GitHub

  const txt = S.portfolio
    .filter(h=>h.sym)
    .map(h=>h.cdslName ? h.sym+'|'+h.cdslName : h.sym)
    .join('\n');

  const encoded = btoa(unescape(encodeURIComponent(txt)));
  const headers = { 'Authorization':'token '+token, 'Content-Type':'application/json', 'Accept':'application/vnd.github.v3+json' };
  const fileUrl = 'https://api.github.com/repos/'+repo+'/contents/portfolio_symbols.txt';

  try{
    // Get current SHA
    let sha = null;
    const get = await fetch(fileUrl, {headers});
    if(get.ok){ const d = await get.json(); sha = d.sha; }

    // Commit updated portfolio_symbols.txt
    const body = { message:'portfolio: update symbols', content: encoded };
    if(sha) body.sha = sha;
    const put = await fetch(fileUrl, { method:'PUT', headers, body:JSON.stringify(body) });
    if(!put.ok){
      const err = await put.json().catch(()=>({}));
      const msg = 'portfolio_symbols.txt commit failed: '+(err.message||put.status)+' — check PAT has repo scope';
      S.settings._lastSync = Date.now();
      S.settings._lastSyncOk = false;
      S.settings._lastSyncMsg = msg;
      saveSettings();
      S._importStatus = { state:'error', msg, ts: Date.now() };
      updateImportStatus();
      toast('❌ '+msg);
      return;
    }

    // Trigger fundamentals fetch workflow
    await new Promise(r=>setTimeout(r, 1500)); // let commit land
    const wfUrl = 'https://api.github.com/repos/'+repo+'/actions/workflows/fetch-prices.yml/dispatches';
    const wfRes = await fetch(wfUrl, {
      method:'POST', headers,
      body: JSON.stringify({ ref:'main', inputs:{ fetch_type:'fundamentals_only' } })
    });

    if(wfRes.status === 204){
      S.settings._lastSync    = Date.now();
      S.settings._lastSyncOk  = true;
      S.settings._lastSyncMsg = 'Symbols synced + workflow triggered';
      saveSettings();
      S._importStatus = { state:'ok', msg:'Synced ✓ — fundamentals fetching in background (~5 min)', ts: Date.now() };
      updateImportStatus();
    } else if(wfRes.status === 403){
      const msg = 'GitHub PAT needs "workflow" scope — run diagnostic in Watchlist settings';
      S.settings._lastSync    = Date.now();
      S.settings._lastSyncOk  = false;
      S.settings._lastSyncMsg = msg;
      saveSettings();
      S._importStatus = { state:'error', msg: msg, ts: Date.now() };
      updateImportStatus();
    } else if(wfRes.status === 422){
      const msg = 'Workflow not found — check fetch-prices.yml exists in .github/workflows/';
      S._importStatus = { state:'error', msg, ts: Date.now() };
      updateImportStatus();
    } else {
      const e2 = await wfRes.json().catch(()=>({}));
      const msg = 'Workflow trigger failed ('+wfRes.status+'): '+(e2.message||'unknown');
      S._importStatus = { state:'error', msg, ts: Date.now() };
      updateImportStatus();
    }
  } catch(e){
    const msg = 'Sync error: '+e.message;
    S.settings._lastSync    = Date.now();
    S.settings._lastSyncOk  = false;
    S.settings._lastSyncMsg = msg;
    saveSettings();
    S._importStatus = { state:'error', msg, ts: Date.now() };
    updateImportStatus();
  }
}

//  PORTFOLIO TAB — Bloomberg Terminal Style Screener Grid
//  Matches: color-coded rows, dense columns, signal badges

// Refresh state

// Signal logic for each stock
// Color a numeric cell based on value vs threshold
function cellColor(val, goodAbove, badBelow) {
  if(val==null||isNaN(val)) return 'color:var(--tx3)';
  if(val>=goodAbove) return 'color:var(--gr2)';
  if(val<=badBelow)  return 'color:var(--rd2)';
  return 'color:var(--yw2)';
}

//  BLOOMBERG-STYLE 37-COLUMN PORTFOLIO SCREENER
//  Data sources:
//    prices.json       → LTP, %1D, %5D, P/E, P/B, EPS, MCAP, 52Wk
//    fundamentals.json → ATH%, Prom%, Pledge%, OPM%, NPM%, ROE,
//                        Sales, CFO, EBITDA, Signal, Pos, Neg

// App-level fundamentals cache (loaded from ./fundamentals.json)
let FUND = {};   // { SYM: { roe, pe, opm_pct, ... } }
let GUIDANCE = {}; // { SYM: { tone, summary, revenue_guidance, ... } }
let pfRefreshing = false;
let pfLastRefresh = null;
let fundLoaded = false;

// Load fundamentals.json on boot (same-origin, CORS-safe)
const FUND_CACHE_TTL = 60 * 60 * 1000; // 1 hour in ms

async function loadFundamentals(forceRefresh){
  try{
    // Check localStorage cache first — fundamentals only update once daily
    const cached   = localStorage.getItem('fund_cache');
    const cacheTs  = parseInt(localStorage.getItem('fund_cache_ts') || '0');
    const cacheAge = Date.now() - cacheTs;

    if(!forceRefresh && cached && cacheAge < FUND_CACHE_TTL){
      const d = JSON.parse(cached);
      FUND = d.stocks || {};
      fundLoaded = true;
      console.log(`✓ fundamentals from cache (${Math.round(cacheAge/60000)}m old):`, Object.keys(FUND).length, 'stocks');
      // Restore timestamp from cache so KPI strip shows it on boot
      if(d.updated && !S.settings._fundUpdated){
        S.settings._fundUpdated = d.updated;
        S.settings._fundStatus  = 'ok';
        saveSettings();
      }
      return;
    }

    // Cache miss or stale — fetch fresh
    const r = await fetch('./fundamentals.json?t='+Date.now(), {cache:'no-store'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const d = await r.json();
    FUND = d.stocks || {};
    fundLoaded = true;

    // Save to cache
    try{
      localStorage.setItem('fund_cache', JSON.stringify(d));
      localStorage.setItem('fund_cache_ts', Date.now().toString());
    } catch(_){ /* storage full — skip cache */ }

    console.log('✓ fundamentals.json loaded fresh:', Object.keys(FUND).length, 'stocks');
    // Store fund timestamp in state so it survives re-renders
    if(d && d.updated){
      S.settings._fundUpdated = d.updated;
      S.settings._fundStatus  = 'ok';
    }
    saveSettings();
  } catch(e){
    // Try stale cache as fallback
    try{
      const cached = localStorage.getItem('fund_cache');
      if(cached){
        const cd = JSON.parse(cached);
        FUND = cd.stocks || {}; fundLoaded = true;
        console.warn('fundamentals: using stale cache (fetch failed)');
        if(cd.updated){
          S.settings._fundUpdated = cd.updated;
          S.settings._fundStatus  = 'stale';
          saveSettings();
        }
        return;
      }
    } catch(_){}
    console.warn('fundamentals.json not found — run GitHub Action to generate');
  }
}

// Merge portfolio holding with fundamentals data
function mergeHolding(h){
  const f = FUND[h.sym] || {};
  const liveLtp = h.liveLtp || f.ltp || 0;  // single source of truth for live price
  return {
    // From portfolio import
    sym:       h.sym,
    isin:      h.isin||'',
    name:      f.name || h.name || h.sym,
    sector:    f.sector || h.sector || '—',
    qty:       h.qty||0,
    avgBuy:    h.avgBuy||0,
    // Live prices — web sources only, never computed or CDSL snapshot:
    // 1. h.liveLtp = live from Refresh button or prices.json (freshest)
    // 2. f.ltp     = from fundamentals.json (updated daily by GitHub Actions)
    // 3. 0         = no live price yet — shows NO PRICE badge
    // h.ltp (CDSL snapshot) deliberately excluded — it is stale point-in-time data
    ltp:       liveLtp,
    chg1d:     h.change || f.chg1d || 0,
    chg5d:     f.chg5d || 0,
    // NSE/Yahoo fundamentals — use ?? not || so 0 values are preserved
    pe:        h.pe   ?? f.pe   ?? null,
    pb:        h.pb   ?? f.pb   ?? null,
    eps:       h.eps  ?? f.eps  ?? null,
    roe:       h.roe  ?? f.roe  ?? null,
    roce:      h.roce ?? f.roce ?? null,
    mcap:      h.mcapRaw ? h.mcapRaw/1e7 : (f.mcap ?? null),
    w52h:      h.week52H ?? f.w52h ?? null,
    w52l:      h.week52L ?? f.w52l ?? null,
    // Derived 52W%
    w52_pct:   (liveLtp&&(h.week52H??f.w52h)) ? round2((liveLtp/(h.week52H??f.w52h)-1)*100) : (f.w52_pct??null),
    ath:       f.ath  ?? null,
    ath_pct:   f.ath_pct ?? null,
    prom_pct:  f.prom_pct ?? h.promoter ?? null,
    public_pct:f.public_pct ?? null,
    opm_pct:   f.opm_pct ?? h.ebitdaMargin ?? null,
    npm_pct:   f.npm_pct ?? h.netMargin ?? null,
    ebitda:    f.ebitda ?? null,
    sales:     f.sales ?? null,
    cfo:       f.cfo ?? null,
    // Signal
    signal:    f.signal || calcSignalLocal(h, f),
    pos:       f.pos||0,
    neg:       f.neg||0,
  };
}

function round2(n){ return Math.round(n*100)/100; }

// Local signal computation when fundamentals.json not available
// ── Signal calculation from local data (no fundamentals.json) ─
function calcSignalLocal(h, f){
  let pos=0, neg=0;
  const roe = h.roe||f.roe||0;
  const pe  = h.pe||f.pe||0;
  const chg = h.change||0;
  const prom= h.promoter||f.prom_pct||0;
  if(roe>15) pos++; else if(roe<8) neg++;
  if(pe>0&&pe<18) pos++; else if(pe>35) neg++;
  if(chg>1) pos++; else if(chg<-1) neg++;
  if(prom>50) pos++; else if(prom&&prom<35) neg++;
  const net=pos-neg;
  return net>=2?'BUY':net<=-2?'SELL':'HOLD';
}

// ── Color helpers ──────────────────────────────────────
// Returns inline style string for a cell
function cc(val, greenAbove, redBelow, neutralRange){
  if(val===null||val===undefined||isNaN(val)) return '';
  if(val>=greenAbove) return 'background:#003a20;color:#fff;font-weight:600';
  if(val<=redBelow)   return 'background:#3a0010;color:#fff;font-weight:600';
  return 'color:#c8dff5';
}

// Row background based on signal
function rowBg(sig){
  if(sig==='BUY')  return 'background:rgba(0,160,80,.13)';
  if(sig==='SELL') return 'background:rgba(200,30,50,.13)';
  return '';
}

// Signal badge HTML
function sigBadge(sig){
  const cfg = {
    BUY:  {bg:'#00a050',bd:'#00d084'},
    SELL: {bg:'#c01e32',bd:'#ff3b5c'},
    HOLD: {bg:'#7a6010',bd:'#f5a623'},
  }[sig]||{bg:'#1a3050',bd:'#4a6888'};
  return `<span style="display:inline-block;font-size:8px;font-weight:800;
    padding:2px 7px;border-radius:3px;letter-spacing:.6px;
    background:${cfg.bg};border:1px solid ${cfg.bd};color:#fff">
    ${sig}
  </span>`;
}

// Format a number cell — show '—' for null
function fn(v, dp=1, prefix='', suffix=''){
  if(v===null||v===undefined||isNaN(v)) return '<span style="color:#3a5a72">—</span>';
  return prefix+Number(v).toFixed(dp)+suffix;
}
function fnCr(v){
  if(v===null||v===undefined||isNaN(v)) return '<span style="color:#3a5a72">—</span>';
  if(v>=100000) return (v/100000).toFixed(1)+'LCr';
  if(v>=1000)   return (v/1000).toFixed(1)+'KCr';
  return v.toFixed(0)+'Cr';
}

// ── MAIN RENDER ────────────────────────────────────────
// PORTFOLIO TAB — Bloomberg-style 29-column screener
// Data: portfolio holdings (CDSL import) + fundamentals.json

function sortRows(rows, skey, sdir) {
  rows.sort((a,b) => {
    let av, bv;
    switch(skey) {
      case 'sym':    av=a.sym; bv=b.sym; break;
      case 'sector': av=a.sector||''; bv=b.sector||''; break;
      case 'pos':    av=a.pos||0; bv=b.pos||0; break;
      case 'neg':    av=a.neg||0; bv=b.neg||0; break;
      case 'pledge': av=0; bv=0; break;
      case 'pub':    av=a.public_pct||0; bv=b.public_pct||0; break;
      case 'name':   av=a.name||''; bv=b.name||''; break;
      case 'chg1d':  av=a.chg1d||0; bv=b.chg1d||0; break;
      case 'chg5d':  av=a.chg5d||0; bv=b.chg5d||0; break;
      case 'pe':     av=a.pe||999; bv=b.pe||999; break;
      case 'pb':     av=a.pb||0; bv=b.pb||0; break;
      case 'eps':    av=a.eps||0; bv=b.eps||0; break;
      case 'roe':    av=a.roe||0; bv=b.roe||0; break;
      case 'opm':    av=a.opm_pct||0; bv=b.opm_pct||0; break;
      case 'npm':    av=a.npm_pct||0; bv=b.npm_pct||0; break;
      case 'ebi':    av=a.ebitda||0; bv=b.ebitda||0; break;
      case 'prom':   av=a.prom_pct||0; bv=b.prom_pct||0; break;
      case 'mcap':   av=a.mcap||0; bv=b.mcap||0; break;
      case 'sales':  av=a.sales||0; bv=b.sales||0; break;
      case 'cfo':    av=a.cfo||0; bv=b.cfo||0; break;
      case 'ltp':    av=a.ltp||0; bv=b.ltp||0; break;
      case 'qty':    av=a.qty||0; bv=b.qty||0; break;
      case 'avg':    av=a.avgBuy||0; bv=b.avgBuy||0; break;
      case 'pnl':    av=a.ltp>0?a.qty*a.ltp-a.qty*a.avgBuy:-Infinity;
                     bv=b.ltp>0?b.qty*b.ltp-b.qty*b.avgBuy:-Infinity; break;
      case 'pnlpct': av=a.ltp>0&&a.avgBuy>0?(a.ltp-a.avgBuy)/a.avgBuy*100:-Infinity;
                     bv=b.ltp>0&&b.avgBuy>0?(b.ltp-b.avgBuy)/b.avgBuy*100:-Infinity; break;
      case 'wt':     av=a.ltp>0?a.qty*a.ltp:0; bv=b.ltp>0?b.qty*b.ltp:0; break;
      case 'sig':    av=a.signal||'HOLD'; bv=b.signal||'HOLD'; break;
      case 'ath':    av=a.ath_pct??-999; bv=b.ath_pct??-999; break;
      case 'w52':    av=a.w52_pct??-999; bv=b.w52_pct??-999; break;
      default:       av=a.qty*(a.ltp||0); bv=b.qty*(b.ltp||0);
    }
    if(typeof av==='string') return sdir==='asc'?av.localeCompare(bv):bv.localeCompare(av);
    return sdir==='asc'?av-bv:bv-av;
  });
}

function renderPortfolio(c){
  if(!S.portfolio.length){
    c.innerHTML = `<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:50px 24px;text-align:center">
      <div style="font-size:42px;margin-bottom:14px;opacity:.6">💼</div>
      <div style="font-family:'Syne',sans-serif;font-size:16px;font-weight:700;color:#fff;margin-bottom:6px">No Portfolio Yet</div>
      <div style="font-size:12px;color:#8eb0d0;line-height:1.7;margin-bottom:18px">Import your holdings from CDSL statement,<br>CSV, or type manually</div>
      <button onclick="openImport()" style="background:#f97316;border:none;border-radius:10px;padding:12px 28px;color:#fff;font-size:14px;font-weight:700;font-family:'Syne',sans-serif;cursor:pointer;">📂 Import Holdings</button>
    </div>`;
    return;
  }

  // Merge all holdings with fundamentals
  const pf = S.portfolio.map(mergeHolding);

  // Totals
  const priced   = pf.filter(h=>h.ltp>0);
  const totalInv = pf.reduce((a,h)=>a+h.qty*(h.avgBuy||0), 0);       // all holdings cost basis
  const totalCur = priced.reduce((a,h)=>a+h.qty*h.ltp, 0);           // only priced stocks mkt value
  const invPriced= priced.reduce((a,h)=>a+h.qty*(h.avgBuy||0), 0);   // cost basis of priced stocks only

  const totalPnL = totalCur - invPriced;                              // P&L on priced stocks only
  const pnlPct   = invPriced>0 ? (totalPnL/invPriced*100) : 0;

  const dayPnL   = priced.reduce((a,h)=>{ const c=h.chg1d||0; return a+(h.qty*h.ltp*c/(100+c)); }, 0);
  const buys     = pf.filter(h=>h.signal==='BUY').length;
  const sells    = pf.filter(h=>h.signal==='SELL').length;
  const holds    = pf.length-buys-sells;
  const gainers  = pf.filter(h=>h.chg1d>0).length;
  const losers   = pf.filter(h=>h.chg1d<0).length;
  const pnlUp    = totalPnL>=0;
  const dayUp    = dayPnL>=0;
  const lastRef  = pfLastRefresh
    ? new Date(pfLastRefresh).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:true})
    : '—';

  // Sector allocation — use ltp if available, else avgBuy as proxy value
  // Also normalise CDSL sector names to our color-map keys
  const SECTOR_NORM = {
    // ── CDSL sector names ──
    'Auto Ancillaries':'Auto','Automobiles':'Auto','Banks':'Banking','Bank':'Banking',
    'Pharmaceutical':'Pharma','Pharmaceuticals':'Pharma','IT - Software':'IT',
    'Information Technology':'IT','Telecomm Equipment & Infra Services':'Telecom',
    'Telecom Services':'Telecom','Power Generation & Distribution':'Power',
    'Capital Goods-Non Electrical Equipment':'Capital Goods',
    'Capital Goods - Electrical Equipment':'Capital Goods',
    'Capital Goods':'Capital Goods','Infrastructure Developers & Operators':'Infrastructure',
    'Ship Building':'Defence','Dry cells':'Capital Goods','Cables':'Capital Goods',
    'Non Ferrous Metals':'Metals','Mining & Mineral products':'Mining',
    'Consumer Durables':'Consumer','Miscellaneous':'Diversified',
    'Alcoholic Beverages':'Consumer','Tobacco Products':'FMCG','FMCG':'FMCG',
    'Others':'Diversified','ETF':'Diversified','Finance':'Finance',
    'Refineries':'Energy','Crude Oil & Natural Gas':'Energy','Trading':'Diversified',
    'Insurance':'Finance','Entertainment':'Consumer','Retail':'Consumer',
    'Healthcare':'Pharma','Shipping':'Infrastructure','Steel':'Metals',
    'Construction':'Infrastructure','POWER':'Power',
    // ── yfinance sector names (what fundamentals.json returns) ──
    'Technology':'IT','Financial Services':'Finance','Basic Materials':'Metals',
    'Consumer Cyclical':'Consumer','Consumer Defensive':'FMCG',
    'Industrials':'Capital Goods','Communication Services':'Telecom',
    'Utilities':'Power','Real Estate':'Real Estate','Energy':'Energy',
    'Health Care':'Pharma','Services':'Diversified',
    // ── NSE industry names ──
    'Diversified':'Diversified','Other':'Diversified',
  };
  const sMap={};
  pf.forEach(h=>{
    const rawSec = h.sector||'Other';
    const s = SECTOR_NORM[rawSec] || rawSec;
    const v = h.qty*(h.ltp||h.avgBuy||0);  // use avgBuy if ltp not yet fetched
    sMap[s]=(sMap[s]||0)+v;
  });
  const sTotal=Object.values(sMap).reduce((a,b)=>a+b,0)||1;
  const sectors=Object.entries(sMap).sort((a,b)=>b[1]-a[1]).slice(0,10);

  // Apply filter & sort
  const filt   = S.pfFilter||'All';
  const secFilt= S.pfSector||'';
  const srch   = (S.pfSearch||'').toUpperCase().trim();
  let rows = pf
    .filter(h=> filt==='All' || h.signal===filt)
    .filter(h=> !secFilt || (h.sector||'').includes(secFilt) ||
                (h.sector && secFilt && sectorNorm(h.sector)===secFilt))
    .filter(h=> !srch || h.sym.includes(srch) || (h.name||'').toUpperCase().includes(srch));
  // helper to normalise sector names for matching
  function sectorNorm(raw){
    const map={'Technology':'IT','Financial Services':'Finance','Basic Materials':'Metals',
      'Consumer Cyclical':'Consumer','Consumer Defensive':'FMCG','Industrials':'Capital Goods',
      'Communication Services':'Telecom','Utilities':'Power','Health Care':'Pharma',
      'Healthcare':'Pharma','Energy':'Energy'};
    return map[raw]||raw;
  }
    sortRows(rows, S.pfSort||'wt', S.pfSortDir||'desc');

  // Inject status strip separately to avoid template literal contamination
  c.innerHTML=`
<style>
/* ════ BLOOMBERG TERMINAL SCREENER ════ */
.bls{background:#02040a;font-family:'JetBrains Mono',monospace;font-size:10px;}

/* KPI Summary strip */
.kpi-strip{display:flex;overflow-x:auto;background:#060c18;border-bottom:2px solid #1e3350;scrollbar-width:none;}
.kpi-strip::-webkit-scrollbar{display:none;}
.kpi{flex:1;min-width:80px;padding:9px 10px;border-right:1px solid #182840;text-align:center;}
.kpi-l{font-size:7px;color:#5878a8;text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:4px;}
.kpi-v{font-size:15px;font-weight:700;line-height:1;font-family:'JetBrains Mono',monospace;}
.kpi-s{font-size:8px;color:#4a6888;margin-top:3px;font-family:'JetBrains Mono',monospace;}
.kpi-status{flex-shrink:0;min-width:90px;padding:6px 10px;display:flex;flex-direction:column;justify-content:center;gap:5px;}
.kpi-srow{display:flex;align-items:center;gap:5px;cursor:pointer;padding:3px 5px;border-radius:5px;transition:background .15s;}
.kpi-srow:active{background:rgba(255,255,255,.05);}
.kpi-sdot{width:6px;height:6px;border-radius:50%;flex-shrink:0;}
.kpi-slbl{font-size:9px;font-family:'JetBrains Mono',monospace;flex:1;}
.kpi-sico{font-size:10px;color:#3a5a72;}
.kpi-sico.spin{animation:rfSpin .7s linear infinite;}

/* Sector bar */
.sec-bar{height:5px;display:flex;border-bottom:1px solid #182840;}
.sec-bar-seg{height:100%;}
.sec-legend{display:flex;flex-wrap:wrap;gap:5px;padding:4px 8px;background:#070c18;border-bottom:1px solid #182840;}
.sec-leg-item{display:flex;align-items:center;gap:3px;font-size:7px;color:#5878a8;font-family:'JetBrains Mono',monospace;transition:color .15s;}
.sec-leg-active{color:#c8dff5 !important;}
.sec-leg-dot{width:7px;height:7px;border-radius:1px;flex-shrink:0;}

/* Toolbar */
.bls-tb{display:flex;align-items:center;gap:5px;padding:5px 8px;background:#0a1020;border-bottom:1px solid #182840;flex-wrap:wrap;}
.tb-btn{display:flex;align-items:center;gap:3px;padding:4px 9px;border-radius:4px;font-size:9px;font-weight:700;font-family:'JetBrains Mono',monospace;cursor:pointer;border:1px solid;transition:all .15s;white-space:nowrap;}
.tb-rf{background:rgba(33,150,243,.1);border-color:rgba(33,150,243,.3);color:#64b5f6;}
.tb-imp{background:rgba(249,115,22,.1);border-color:rgba(249,115,22,.3);color:#fb923c;}
.tb-cl{background:rgba(255,59,92,.08);border-color:rgba(255,59,92,.2);color:#ff6b85;}
.tb-chips{display:flex;gap:3px;overflow-x:auto;flex:1;scrollbar-width:none;}
.tb-chips::-webkit-scrollbar{display:none;}
.tb-chip{padding:3px 8px;border-radius:3px;font-size:8px;font-weight:700;cursor:pointer;white-space:nowrap;border:1px solid #182840;background:#0d1525;color:#4a6888;font-family:'JetBrains Mono',monospace;transition:all .12s;}
.tb-chip.on{background:rgba(249,115,22,.12);border-color:#f97316;color:#fb923c;}
.rf-spin{display:inline-block;}
.rf-spin.spin{animation:rfSpin .6s linear infinite;}
@keyframes rfSpin{to{transform:rotate(360deg);}}
.bls-ts{font-size:7px;color:#2e4a62;white-space:nowrap;}
.fund-status{
  font-size:8px;padding:4px 8px;border-radius:4px;border:1px solid;
  font-weight:700;font-family:'JetBrains Mono',monospace;
  display:flex;align-items:center;gap:3px;white-space:nowrap;
}

/* Table container — dual scroll: x for columns, y for rows, sticky headers work */
.bls-table-outer{
  overflow-x:auto;
  overflow-y:auto;
  -webkit-overflow-scrolling:touch;
  position:relative;
  max-height:calc(100vh - 240px);
}
.bls-table-outer::-webkit-scrollbar{height:4px;}
.bls-table-outer::-webkit-scrollbar-track{background:#02040a;}
.bls-table-outer::-webkit-scrollbar-thumb{background:#1e3350;border-radius:2px;}

/* Table */
.bls-t{border-collapse:collapse;white-space:nowrap;font-family:'JetBrains Mono',monospace;font-size:10px;}
.bls-t th{
  padding:4px 6px;text-align:right;font-size:7px;font-weight:700;
  color:#6a8aaa;text-transform:uppercase;letter-spacing:.5px;
  background:#060c18;border-bottom:2px solid #1e3350;
  border-right:1px solid #0f1d30;
  cursor:pointer;user-select:none;white-space:nowrap;
  position:sticky;top:0;z-index:15;  /* freeze on vertical scroll */
}
.bls-t th.th-l{text-align:left;}
.bls-t th.th-fix{position:sticky;z-index:25;background:#060c18;}  /* top-left corner: highest z */
.bls-t th.th-fix1{left:0;min-width:90px;}
.bls-t th.th-fix2{left:90px;min-width:70px;}
.bls-t th:hover{color:#8eb0d0;background:#0a1525;}
.bls-t th.sorted{color:#64b5f6;}

.bls-t td{
  padding:0 6px;height:28px;text-align:right;
  border-bottom:1px solid rgba(15,29,48,.9);
  border-right:1px solid rgba(15,29,48,.7);
  color:#c8dff5;white-space:nowrap;
}
.bls-t td.td-l{text-align:left;}
.bls-t td.td-fix{position:sticky;z-index:5;}
.bls-t td.td-fix1{left:0;min-width:90px;background:inherit;}
.bls-t td.td-fix2{left:90px;min-width:70px;background:inherit;}
.bls-t tr{cursor:pointer;}
.bls-t tr:hover td{filter:brightness(1.25);}
.bls-t tr:active td{filter:brightness(1.5);}

/* Grand total footer */
.bls-t tfoot td{
  position:sticky;bottom:0;z-index:10;
  background:#060c18;
  border-top:2px solid #1e3350;
  font-weight:700;font-size:10px;
  color:#c8dff5;
  padding:0 6px;height:28px;text-align:right;
  white-space:nowrap;
}
.bls-t tfoot td.td-fix{position:sticky;z-index:20;background:#060c18;}
.bls-t tfoot td.td-fix1{left:0;}

/* Sym cell */
.sym-main{font-size:11px;font-weight:700;color:#f0f6ff;font-family:'JetBrains Mono',monospace;}
.sym-name{font-size:7px;color:#4a6888;max-width:88px;overflow:hidden;text-overflow:ellipsis;margin-top:1px;}

/* Pos/Neg pill */
.pos-neg{display:flex;gap:2px;justify-content:center;align-items:center;}
.pn-p{background:#003a20;color:#fff;padding:1px 4px;border-radius:2px;font-size:8px;font-weight:700;}
.pn-n{background:#3a0010;color:#fff;padding:1px 4px;border-radius:2px;font-size:8px;font-weight:700;}
</style>

<div class="bls">
<div id="pf-status-strip"></div>

<!-- ── KPI Strip ── -->
<div class="kpi-strip" id="kpi-strip-el">
  <div class="kpi">
    <div class="kpi-l">Invested</div>
    <div class="kpi-v" style="color:#64b5f6">₹${(totalInv/100000).toFixed(2)}L</div>
    <div class="kpi-s">${pf.length} stocks</div>
  </div>
  <div class="kpi">
    <div class="kpi-l">Mkt Value</div>
    <div class="kpi-v" style="color:#c8dff5">₹${(totalCur/100000).toFixed(2)}L</div>
    <div class="kpi-s">${priced.length}/${pf.length} priced</div>
  </div>
  <div class="kpi">
    <div class="kpi-l">Total P&L</div>
    <div class="kpi-v" style="color:${pnlUp?'#00e896':'#ff6b85'}">₹${(Math.abs(totalPnL)/100000).toFixed(2)}L</div>
    <div class="kpi-s" style="color:${pnlUp?'#00d084':'#ff3b5c'}">${pnlPct.toFixed(2)}%</div>
  </div>
  <div class="kpi">
    <div class="kpi-l">Day P&L</div>
    <div class="kpi-v" style="color:${dayUp?'#00e896':'#ff6b85'}">${dayUp?'+':''}₹${(Math.abs(dayPnL)/100000).toFixed(2)}L</div>
    <div class="kpi-s">${gainers}▲ ${losers}▼</div>
  </div>
  <div class="kpi-status">
    <div class="kpi-srow" onclick="headerPricesTap()">
      <span class="kpi-sdot" style="background:${S.settings._pricesStatus==='ok'?'#00d084':S.settings._pricesStatus==='fail'?'#ff3b5c':'#4a6888'}"></span>
      <span class="kpi-slbl" style="color:${S.settings._pricesStatus==='ok'?'#00e896':S.settings._pricesStatus==='fail'?'#ff6b85':'#4a6888'}">${S.settings._pricesUpdated?'prices '+new Date(S.settings._pricesUpdated).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:false}):'prices —'}</span>
      <span class="kpi-sico" id="hdr-prices-spin">↻</span>
    </div>
    <div class="kpi-srow" onclick="headerFundTap()">
      <span class="kpi-sdot" style="background:${S.settings._fundStatus==='ok'?'#00d084':S.settings._fundStatus==='stale'?'#ffbf47':'#4a6888'}"></span>
      <span class="kpi-slbl" style="color:${S.settings._fundStatus==='ok'?'#00e896':S.settings._fundStatus==='stale'?'#ffbf47':'#4a6888'}">${S.settings._fundUpdated?'fund '+new Date(S.settings._fundUpdated).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:false}):'fund —'}</span>
      <span class="kpi-sico" id="hdr-fund-spin">↻</span>
    </div>
  </div>
</div>

<!-- ── Sector Bar ── -->
<div class="sec-bar">
  ${sectors.map(([s,v])=>`<div class="sec-bar-seg" style="width:${(v/sTotal*100).toFixed(1)}%;background:${sectorColor(s)}" title="${s} ${(v/sTotal*100).toFixed(1)}%"></div>`).join('')}
</div>
<div class="sec-legend">
  <div class="sec-leg-item ${!S.pfSector?'sec-leg-active':''}" onclick="setSectorFilter('')"
    style="cursor:pointer;border:1px solid ${!S.pfSector?'#4a6888':'transparent'};border-radius:4px;padding:1px 5px">
    All
  </div>
  ${sectors.map(([s,v])=>`
  <div class="sec-leg-item ${S.pfSector===s?'sec-leg-active':''}"
    onclick="setSectorFilter('${s}')"
    style="cursor:pointer;border:1px solid ${S.pfSector===s?sectorColor(s):'transparent'};border-radius:4px;padding:1px 5px;color:${S.pfSector===s?sectorColor(s):'#5878a8'}">
    <div class="sec-leg-dot" style="background:${sectorColor(s)}"></div>${s} ${(v/sTotal*100).toFixed(0)}%
  </div>`).join('')}
</div>

<!-- ── Toolbar ── -->
<div class="bls-tb" style="gap:6px;flex-wrap:nowrap">
  <input id="pf-search" value="${S.pfSearch||''}"
    placeholder="Search…"
    oninput="pfSearchUpdate(this.value)"
    style="width:72px;flex-shrink:0;background:#0d1525;border:1px solid #182840;border-radius:4px;
    padding:4px 6px;color:#f0f6ff;font-size:11px;font-family:'JetBrains Mono',monospace;
    outline:none;text-transform:uppercase"/>
  <div class="tb-chips">
    ${['All','BUY','SELL','HOLD'].map(f=>`<div class="tb-chip ${(S.pfFilter||'All')===f?'on':''}" onclick="setPfFilter('${f}')">${f}</div>`).join('')}
    <div class="tb-chip ${S.pfSort==='chg1d'?'on':''}" onclick="togglePfSort('chg1d')">%1D ${S.pfSort==='chg1d'?(S.pfSortDir==='desc'?'↓':'↑'):''}</div>
  </div>
</div>

<!-- ── 37-Column Bloomberg Screener Table ── -->
<div class="bls-table-outer">
<table class="bls-t" id="bls-tbl">
<thead><tr>
  <th class="th-l th-fix th-fix1" onclick="togglePfSort('sym')">${pfSortArrow('sym')}Ticker</th>
  <th class="th-l th-fix th-fix2" onclick="togglePfSort('sector')" style="cursor:pointer">${pfSortArrow('sector')}Sector</th>
  <th title="Bullish signals" onclick="togglePfSort('pos')" style="cursor:pointer">${pfSortArrow('pos')}Pos</th>
  <th title="Bearish signals" onclick="togglePfSort('neg')" style="cursor:pointer">${pfSortArrow('neg')}Neg</th>
  <th onclick="togglePfSort('ath')"  class="${S.pfSort==='ath'?'sorted':''}">${pfSortArrow('ath')}ATH%</th>
  <th onclick="togglePfSort('w52')"  class="${S.pfSort==='w52'?'sorted':''}">${pfSortArrow('w52')}52W%</th>
  <th onclick="togglePfSort('prom')" class="${S.pfSort==='prom'?'sorted':''}">${pfSortArrow('prom')}Prom%</th>
  <th title="Pledge %" onclick="togglePfSort('pledge')" style="cursor:pointer">${pfSortArrow('pledge')}Pl%</th>
  <th title="Public holding %" onclick="togglePfSort('pub')" style="cursor:pointer">${pfSortArrow('pub')}Pub%</th>
  <th onclick="togglePfSort('pb')"   class="${S.pfSort==='pb'?'sorted':''}">${pfSortArrow('pb')}P/B</th>
  <th onclick="togglePfSort('eps')"  class="${S.pfSort==='eps'?'sorted':''}">${pfSortArrow('eps')}EPS</th>
  <th onclick="togglePfSort('sales')" class="${S.pfSort==='sales'?'sorted':''}">${pfSortArrow('sales')}Sales</th>
  <th onclick="togglePfSort('cfo')"  class="${S.pfSort==='cfo'?'sorted':''}">${pfSortArrow('cfo')}CFO</th>
  <th onclick="togglePfSort('roe')"  class="${S.pfSort==='roe'?'sorted':''}">${pfSortArrow('roe')}ROE%</th>
  <th onclick="togglePfSort('pe')"   class="${S.pfSort==='pe'?'sorted':''}">${pfSortArrow('pe')}P/E</th>
  <th onclick="togglePfSort('name')" class="${S.pfSort==='name'?'sorted':''}">${pfSortArrow('name')}Name</th>
  <th onclick="togglePfSort('opm')"  class="${S.pfSort==='opm'?'sorted':''}">${pfSortArrow('opm')}OPM%</th>
  <th onclick="togglePfSort('ebi')"  class="${S.pfSort==='ebi'?'sorted':''}">${pfSortArrow('ebi')}EBI</th>
  <th onclick="togglePfSort('npm')"  class="${S.pfSort==='npm'?'sorted':''}">${pfSortArrow('npm')}NPM%</th>
  <th onclick="togglePfSort('mcap')" class="${S.pfSort==='mcap'?'sorted':''}">${pfSortArrow('mcap')}MCAP</th>
  <th onclick="togglePfSort('chg1d')" class="${S.pfSort==='chg1d'?'sorted':''}">${pfSortArrow('chg1d')}%1D</th>
  <th onclick="togglePfSort('chg5d')" class="${S.pfSort==='chg5d'?'sorted':''}">${pfSortArrow('chg5d')}%5D</th>
  <th onclick="togglePfSort('ltp')"  class="${S.pfSort==='ltp'?'sorted':''}">${pfSortArrow('ltp')}LTP</th>
  <th onclick="togglePfSort('qty')"  class="${S.pfSort==='qty'?'sorted':''}">${pfSortArrow('qty')}Qty</th>
  <th onclick="togglePfSort('avg')"  class="${S.pfSort==='avg'?'sorted':''}">${pfSortArrow('avg')}Avg</th>
  <th onclick="togglePfSort('pnl')"  class="${S.pfSort==='pnl'?'sorted':''}">${pfSortArrow('pnl')}P&L</th>
  <th onclick="togglePfSort('pnlpct')" class="${S.pfSort==='pnlpct'?'sorted':''}">${pfSortArrow('pnlpct')}P&L%</th>
  <th onclick="togglePfSort('wt')"   class="${S.pfSort==='wt'?'sorted':''}">${pfSortArrow('wt')}Wt%</th>
  <th onclick="togglePfSort('sig')"  class="${S.pfSort==='sig'?'sorted':''}">${pfSortArrow('sig')}Sig</th>
</tr></thead>
<tbody id="bls-tbody">
${renderBLSRows(rows, totalCur)}
</tbody>
<tfoot id="bls-tfoot">
${(()=>{
  // Use pf (full merged set) for totals so avgBuy is always current
  const totQty    = pf.reduce((a,h)=>a+h.qty, 0);
  const totInv    = pf.reduce((a,h)=>a+h.qty*(h.avgBuy||0), 0);
  const totCur    = pf.filter(h=>h.ltp>0).reduce((a,h)=>a+h.qty*h.ltp, 0);
  const totInvPr  = pf.filter(h=>h.ltp>0).reduce((a,h)=>a+h.qty*(h.avgBuy||0), 0);
  const totPnL    = totCur - totInvPr;
  const totPnLPct = totInvPr>0 ? (totPnL/totInvPr*100) : 0;
  const pnlUp     = totPnL >= 0;
  const pnlCol    = pnlUp ? '#00e896' : '#ff6b85';
  // 29 columns: Ticker(1) Sector(2) Pos(3) Neg(4) ATH%(5) 52W%(6) Prom%(7) Pl%(8) Pub%(9)
  //             P/B(10) EPS(11) Sales(12) CFO(13) ROE%(14) P/E(15) Name(16) OPM%(17) EBI(18)
  //             NPM%(19) MCAP(20) %1D(21) %5D(22) LTP(23) Qty(24) Avg(25) P&L(26) P&L%(27) Wt%(28) Sig(29)
  const cells = Array(29).fill('<td></td>');
  cells[0]  = '<td class="td-l td-fix td-fix1" style="color:#8eb0d0;font-size:9px;letter-spacing:.5px;text-transform:uppercase">TOTAL</td>';
  cells[23] = '<td style="color:#c8dff5">'+totQty.toLocaleString('en-IN')+'</td>';
  cells[24] = '<td></td>';
  cells[25] = '<td style="color:'+pnlCol+'">'+(pnlUp?'+':'')+'₹'+(Math.abs(totPnL)/100000).toFixed(2)+'L</td>';
  cells[26] = '<td style="color:'+pnlCol+'">'+(totPnLPct>=0?'+':'')+totPnLPct.toFixed(2)+'%</td>';
  cells[27] = '<td></td>';
  cells[28] = '<td></td>';
  return '<tr>'+cells.join('')+'</tr>';
})()}
</tfoot>
</table>
</div>

${!fundLoaded?`
<div style="margin:10px 12px;padding:12px;background:rgba(245,166,35,.06);border:1px solid rgba(245,166,35,.25);border-radius:8px;font-size:10px;color:#8eb0d0;font-family:'JetBrains Mono',monospace;line-height:2">
  <div style="color:#ffbf47;font-weight:700;margin-bottom:6px">⚠ Fundamentals not loaded — ATH%, Prom%, OPM%, ROE, Signal all show —</div>
  ${S.settings.ghToken&&S.settings.ghRepo ? `
  <div style="color:#4a6888">Auto-sync is configured. If this persists after import:</div>
  <div><span style="color:#4dd0e1;font-weight:700">1</span> — Re-import your portfolio (triggers auto-sync)</div>
  <div><span style="color:#4dd0e1;font-weight:700">2</span> — Wait ~5 min → tap ↻ Refresh</div>
  <div><span style="color:#4dd0e1;font-weight:700">3</span> — If still empty → run diagnostic in Watchlist → GitHub Sync</div>
  ` : `
  <div><span style="color:#4dd0e1;font-weight:700">1</span> — Configure GitHub in <b style="color:#fff">Watchlist → GitHub Sync</b> (repo + PAT)</div>
  <div><span style="color:#4dd0e1;font-weight:700">2</span> — Run diagnostic to verify connection</div>
  <div><span style="color:#4dd0e1;font-weight:700">3</span> — Re-import portfolio → data auto-fetches (~5 min)</div>
  `}
  <div style="margin-top:4px;color:#4a6888;font-size:9px">Once configured, every import auto-syncs symbols and triggers data fetch.</div>
  <button onclick="exportPortfolioSymbols()" style="margin-top:8px;width:100%;padding:7px;background:rgba(100,181,246,.06);border:1px solid rgba(100,181,246,.2);border-radius:6px;color:#64b5f6;font-size:10px;font-weight:600;cursor:pointer;font-family:'JetBrains Mono',monospace;">
    📤 Manual fallback — export portfolio_symbols.txt
  </button>
</div>`:''}

</div>`;

  // Inject status strip via DOM after render
  requestAnimationFrame(()=>{
    const strip = document.getElementById('pf-status-strip');
    if(strip && S._importStatus){
      const st = S._importStatus;
      const col = st.state==='ok'?'#00e896':st.state==='error'?'#ff6b85':'#ffbf47';
      const icon = st.state==='ok'?'✅':st.state==='error'?'❌':'⏳';
      strip.style.cssText = 'padding:8px 13px;font-size:11px;font-family:JetBrains Mono,monospace;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid '+col+'40;color:'+col+';background:'+col+'0a';
      strip.innerHTML = icon+' '+st.msg;
    }

  });
}

// ── Render table rows ──────────────────────────────────
// Render table rows for the portfolio screener
function renderBLSRows(rows, totalCur){
  return rows.map(h=>{
    const ltp    = h.ltp||0;   // already web-only from mergeHolding
    const inv    = h.qty*(h.avgBuy||0);
    const cur    = ltp>0 ? h.qty*ltp : null;  // null = price not loaded
    const pnl    = cur!==null ? cur-inv : null;
    const pnlP   = cur!==null && inv>0 ? (pnl/inv*100) : null;
    const wt     = cur!==null && totalCur>0 ? (cur/totalCur*100) : 0;
    const sig    = h.signal||'HOLD';
    const rb     = rowBg(sig);

    // Individual cell styles (color-coded per spec)
    const c1d  = h.chg1d>=0  ? 'background:#003a20;color:#fff;font-weight:700' : 'background:#3a0010;color:#fff;font-weight:700';
    const c5d  = h.chg5d>=0  ? 'background:#003a20;color:#fff' : 'background:#3a0010;color:#fff';
    const cROE = cc(h.roe,   15, 8);
    const cPE  = h.pe===null||h.pe===undefined ? '' :
                 h.pe<18  ? 'background:#003a20;color:#fff;font-weight:600' :
                 h.pe>35  ? 'background:#3a0010;color:#fff;font-weight:600' : 'color:#c8dff5';
    const cOPM = cc(h.opm_pct, 15, 8);
    const cNPM = cc(h.npm_pct, 10, 5);
    const cATH = h.ath_pct===null ? '' :
                 h.ath_pct>-10 ? 'background:#003a20;color:#fff;font-weight:600' :
                 h.ath_pct<-20 ? 'background:#3a0010;color:#fff;font-weight:600' : 'color:#c8dff5';
    const cW52 = h.w52_pct===null ? '' :
                 h.w52_pct>-10 ? 'background:#003a20;color:#fff;font-weight:600' :
                 h.w52_pct<-20 ? 'background:#3a0010;color:#fff;font-weight:600' : 'color:#c8dff5';
    const cPR  = h.prom_pct===null ? '' :
                 h.prom_pct>50 ? 'background:#003a20;color:#fff;font-weight:600' :
                 h.prom_pct<35 ? 'background:#3a0010;color:#fff;font-weight:600' : 'color:#c8dff5';
    const cPnL = pnl>=0 ? 'background:#003a20;color:#fff;font-weight:700' : 'background:#3a0010;color:#fff;font-weight:700';

    // Fixed-left bg must match row bg
    const fixBg = sig==='BUY' ? 'background:#030e07' :
                  sig==='SELL'? 'background:#0e0306' : 'background:#03060f';

    return `<tr style="${rb}" onclick="openPortfolioStock('${h.sym}')">
      <!-- Fixed left -->
      <td class="td-l td-fix td-fix1" style="${fixBg}">
        <div class="sym-main">${h.sym}</div>
        <div class="sym-name">${trunc(h.name,14)}</div>
      </td>
      <td class="td-l td-fix td-fix2" style="${fixBg};color:#7a9ab8;font-size:8px;max-width:70px;overflow:hidden;text-overflow:ellipsis">${trunc(h.sector||"—",10)}</td>
      <!-- Scrollable -->
      <td><div class="pos-neg"><span class="pn-p">${h.pos||0}</span></div></td>
      <td><div class="pos-neg"><span class="pn-n">${h.neg||0}</span></div></td>
      <td style="${cATH}">${fn(h.ath_pct,1,'','%')}</td>
      <td style="${cW52}">${fn(h.w52_pct,1,'','%')}</td>
      <td style="${cPR}">${fn(h.prom_pct,1,'','%')}</td>
      <td style="color:#3a5a72">—</td>
      <td>${fn(h.public_pct,1,'','%')}</td>
      <td>${fn(h.pb,1,'','x')}</td>
      <td style="color:#c8dff5">${fn(h.eps,1,'₹')}</td>
      <td>${fnCr(h.sales)}</td>
      <td style="${h.cfo>0?'background:#003a20;color:#fff':'background:#3a0010;color:#fff'}">${fnCr(h.cfo)}</td>
      <td style="${cROE}">${fn(h.roe,1,'','%')}</td>
      <td style="${cPE}">${fn(h.pe,1,'','x')}</td>
      <td style="color:#8eb0d0;font-size:8px;max-width:90px;text-align:left;overflow:hidden;text-overflow:ellipsis">${trunc(h.name,12)}</td>
      <td style="${cOPM}">${fn(h.opm_pct,1,'','%')}</td>
      <td>${fnCr(h.ebitda)}</td>
      <td style="${cNPM}">${fn(h.npm_pct,1,'','%')}</td>
      <td style="color:#8eb0d0">${fnCr(h.mcap)}</td>
      <td style="${c1d}">${h.chg1d>=0?'+':''}${fn(h.chg1d,2,'','%')}</td>
      <td style="${c5d}">${h.chg5d>=0?'+':''}${fn(h.chg5d,2,'','%')}</td>
      <td style="${ltp>0?(h.chg1d>0?'background:#003a20;color:#fff':h.chg1d<0?'background:#3a0010;color:#fff':'color:#f0f6ff'):'color:#4a6888'};font-weight:${ltp>0?'600':'400'}">
        ${ltp>0?'₹'+ltp.toFixed(1):'<span style="font-size:7px;background:rgba(245,166,35,.15);border:1px solid rgba(245,166,35,.3);color:#ffbf47;padding:1px 4px;border-radius:3px">NO PRICE</span>'}
      </td>
      <td style="color:#8eb0d0">${h.qty.toLocaleString('en-IN')}</td>
      <td style="${h.avgBuy>0?'background:#3a1a00;color:#fff;font-weight:600':'color:#3a5a72'}">${h.avgBuy>0?'₹'+h.avgBuy.toFixed(1):'—'}</td>
      <td style="${ltp>0?cPnL:'color:#3a5a72'}">${ltp>0?(pnl>=0?'+':'')+pnl.toFixed(0):'—'}</td>
      <td style="${ltp>0?cPnL:'color:#3a5a72'}">${ltp>0&&pnlP!=null?(pnlP>=0?'+':'')+pnlP.toFixed(1)+'%':'—'}</td>
      <td style="color:#8eb0d0">${wt.toFixed(1)}%</td>
      <td>${sigBadge(sig)}</td>
    </tr>`;
  }).join('');
}

// ── Sort / Filter Controls ──────────────────────────────
// ── Sort / filter controls ──────────────────────────────────
function setPfFilter(f){S.pfFilter=f;if(S.curTab==='portfolio')render();}

// Search: update only tbody so input keeps focus (full render kills focus after 1 char)
function pfSearchUpdate(val){
  S.pfSearch = val.toUpperCase();
  const tbody = document.getElementById('bls-tbody');
  if(!tbody){ render(); return; }
  const tc = S.portfolio.map(mergeHolding);
  const filt = S.pfFilter||'All';
  const srch = S.pfSearch.trim();
  const secFilt = S.pfSector||'';
  let rows = filt==='All' ? [...tc] : tc.filter(h=>h.signal===filt);
  if(srch) rows = rows.filter(h=>h.sym.includes(srch)||(h.name||'').toUpperCase().includes(srch));
  if(secFilt) rows = rows.filter(h=>(h.sector||'').includes(secFilt));
  sortRows(rows, S.pfSort||'wt', S.pfSortDir||'desc');
  const totalCur = tc.filter(h=>h.ltp>0).reduce((a,h)=>a+h.qty*h.ltp,0);
  tbody.innerHTML = renderBLSRows(rows, totalCur);
}
function setSectorFilter(s){
  S.pfSector = S.pfSector===s ? '' : s;  // toggle off if same
  if(S.curTab==='portfolio') render();
}
// Sort arrow indicator
function pfSortArrow(k){
  if(S.pfSort!==k) return '';
  return S.pfSortDir==='asc'
    ? '<span style="color:#64b5f6;margin-right:2px">↑</span>'
    : '<span style="color:#64b5f6;margin-right:2px">↓</span>';
}

function togglePfSort(k){
  if(S.pfSort===k) S.pfSortDir=S.pfSortDir==='desc'?'asc':'desc';
  else{ S.pfSort=k; S.pfSortDir='desc'; }
  const tbody=document.getElementById('bls-tbody');
  if(!tbody){ render(); return; }

  const tc = S.portfolio.map(mergeHolding);
  const filt = S.pfFilter||'All';
  let rows = filt==='All' ? [...tc] : tc.filter(h=>h.signal===filt);
  if(S.pfSearch) rows = rows.filter(h=>h.sym.includes(S.pfSearch)||(h.name||'').toUpperCase().includes(S.pfSearch));
  if(S.pfSector) rows = rows.filter(h=>(h.sector||'').includes(S.pfSector));
  const totalCur = tc.filter(h=>h.ltp>0).reduce((a,h)=>a+h.qty*h.ltp,0);
  const invPriced= tc.filter(h=>h.ltp>0).reduce((a,h)=>a+h.qty*(h.avgBuy||0),0);

    sortRows(rows, S.pfSort, S.pfSortDir);

  // Update header arrows
  document.querySelectorAll('th.sorted').forEach(th=>th.classList.remove('sorted'));
  tbody.innerHTML = renderBLSRows(rows, totalCur);

  // Also update tfoot totals with fresh pf data
  const tfoot = document.getElementById('bls-tfoot');
  if(tfoot){
    const totInv2    = tc.reduce((a,h)=>a+h.qty*(h.avgBuy||0), 0);
    const totCur2    = tc.filter(h=>h.ltp>0).reduce((a,h)=>a+h.qty*h.ltp, 0);
    const totInvPr2  = tc.filter(h=>h.ltp>0).reduce((a,h)=>a+h.qty*(h.avgBuy||0), 0);
    const totPnL2    = totCur2 - totInvPr2;
    const totPnLPct2 = totInvPr2>0 ? (totPnL2/totInvPr2*100) : 0;
    const totQty2    = tc.reduce((a,h)=>a+h.qty, 0);
    const pnlUp2     = totPnL2>=0;
    const pnlCol2    = pnlUp2 ? '#00e896' : '#ff6b85';
    const cells2 = Array(29).fill('<td></td>');
    cells2[0]  = '<td class="td-l td-fix td-fix1" style="color:#8eb0d0;font-size:9px;letter-spacing:.5px;text-transform:uppercase">TOTAL</td>';
    cells2[23] = '<td style="color:#c8dff5">'+totQty2.toLocaleString('en-IN')+'</td>';
    cells2[24] = '<td></td>';
    cells2[25] = '<td style="color:'+pnlCol2+'">'+(pnlUp2?'+':'')+'₹'+(Math.abs(totPnL2)/100000).toFixed(2)+'L</td>';
    cells2[26] = '<td style="color:'+pnlCol2+'">'+(totPnLPct2>=0?'+':'')+totPnLPct2.toFixed(2)+'%</td>';
    cells2[27] = '<td></td>';
    cells2[28] = '<td></td>';
    tfoot.innerHTML = '<tr>'+cells2.join('')+'</tr>';
  }
}

// ── Manual Refresh — Yahoo Finance via proxy ────────────
// ── Refresh: Load prices.json from GitHub first, then Yahoo for live ──
// PRICE REFRESH — fetches prices.json from GitHub Pages
// Runs: on boot, every 5min during market hours, on import
async function refreshPortfolioData(){
  if(pfRefreshing||!S.portfolio.length)return;
  pfRefreshing=true;
  const ico=document.getElementById('rf-icon');
  if(ico)ico.classList.add('spin');
  toast('Loading prices…');

  let updated=0, d=null;
  try{
    // prices.json covers all portfolio stocks — single fast same-origin fetch
    const r = await fetch('./prices.json?t='+Date.now(), {cache:'no-store'});
    if(r.ok){
      d = await r.json();
      const quotes = d.quotes || d;
      S.portfolio.forEach(h=>{
        const q = quotes[h.sym];
        if(!q) return;
        if(q.ltp)       { h.ltp = q.ltp; h.liveLtp = q.ltp; updated++; }
        if(q.changePct) { h.change = q.changePct; }
        if(q.chg5d)     { h.chg5d  = q.chg5d; }
        if(q.w52h)      { h.week52H= q.w52h; }
        if(q.w52l)      { h.week52L= q.w52l; }
      });
      // Also update watchlist LTP
      S.watchlist.forEach(w=>{
        const q = quotes[w.symbol];
        if(!q) return;
        if(q.ltp)       { w.ltp    = q.ltp; }
        if(q.changePct) { w.change = q.changePct; }
      });
    }
  } catch(e){ console.warn('prices.json fetch failed:', e); }
  finally {
    pfLastRefresh=Date.now();
    pfRefreshing=false;
    if(ico)ico.classList.remove('spin');
    savePF();
    // Store prices timestamp in state so it survives re-renders
    if(d && d.updated){ S.settings._pricesUpdated = d.updated; }
    S.settings._pricesStatus = updated>0 ? 'ok' : 'fail';
    saveSettings();
    render();
    toast(updated>0
      ? `✓ ${updated}/${S.portfolio.length} prices updated`
      : '⚠ No prices — commit portfolio_symbols.txt and run Actions');
  }
}

// ── Auto-refresh every 5 min during NSE market hours (IST 9:15–15:35, Mon–Fri) ──
// ── Session activity tracking ──────────────────────────
let lastActivity = Date.now();
['touchstart','mousedown','scroll','keydown','visibilitychange'].forEach(evt=>{
  document.addEventListener(evt, ()=>{ lastActivity = Date.now(); }, {passive:true});
});
function isActiveSession(){
  // Page must be visible AND user interacted within last 10 minutes
  if(document.visibilityState === 'hidden') return false;
  return (Date.now() - lastActivity) < 10 * 60 * 1000;
}

// ── Market hours check (IST 9:15–15:35, Mon–Fri) ───────
function isMarketHours(){
  const now = new Date();
  const ist = new Date(now.getTime() + 5.5 * 60 * 60 * 1000);
  const day = ist.getUTCDay();
  if(day===0||day===6) return false;
  const min = ist.getUTCHours()*60 + ist.getUTCMinutes();
  return min >= 555 && min <= 935; // 9:15=555, 15:35=935
}

// Fetch on load — always fetch prices.json on boot (no market hours gate)
// prices.json is always valid even outside hours — it's a static file
setTimeout(()=>{
  if(S.portfolio.length) refreshPortfolioData();
}, 1500);

// Every 5 min during market hours (live prices change)
// Every 30 min outside market hours (stale file still useful after refresh)
setInterval(()=>{
  if(!pfRefreshing && S.portfolio.length){
    if(isMarketHours()){
      refreshPortfolioData();
    } else if((Date.now() - pfLastRefresh) > 30 * 60 * 1000){
      refreshPortfolioData();
    }
  }
}, 5 * 60 * 1000);

// Fetch when user returns to app from background
document.addEventListener('visibilitychange', ()=>{
  if(document.visibilityState==='visible' && S.portfolio.length && !pfRefreshing){
    // During market hours: refresh if >2 min stale
    // Outside hours: refresh if >15 min stale
    const staleThreshold = isMarketHours() ? 2*60*1000 : 15*60*1000;
    if((Date.now() - pfLastRefresh) > staleThreshold)
      refreshPortfolioData();
  }
});
function openPortfolioStock(sym){
  const h=S.portfolio.find(p=>p.sym===sym);
  if(!h)return;
  const f=FUND[sym]||{};
  const info=NSE_DB.find(s=>s.sym===sym)||{name:sym,sector:'Diversified'};
  // LTP from web only — never avgBuy, never computed
  const liveLtp = h.liveLtp || f.ltp || 0;
  S.selStock={
    symbol:sym,
    name:f.name||h.name||info.name||sym,
    sector:f.sector||h.sector||info.sector||'Diversified',
    ltp:liveLtp,
    prev:f.prev||null,           // null if not available — no fabrication
    change:h.change||f.chg1d||0,
    qty:h.qty,avgBuy:h.avgBuy,
    holdingValue:liveLtp>0 ? h.qty*liveLtp : null,
    pe:h.pe||f.pe||null,
    pb:h.pb||f.pb||null,
    roe:h.roe||f.roe||null,
    roce:h.roce||f.roce||null,
    debtEq:f.debt_eq||null,
    divYield:f.div_yield||null,
    promoter:f.prom_pct||null,

    eps:h.eps||f.eps||null,
    mcap:f.mcap?f.mcap+'Cr':null,
    week52H:h.week52H||f.w52h||null,  // null if not fetched — no fabrication
    week52L:h.week52L||f.w52l||null,
    sma20:null,   // requires chart data — not computed from LTP
    sma50:null,
    ema200:null,
    rsi:null,macd:null,macdSignal:null,adx:null,stochK:null,stochD:null,
    beta:f.beta||null,
    atr:null,
    support1:null,
    resist1:null,
    candles:liveLtp>0 ? genCandles(liveLtp,20) : [],
    quarterly: f.quarterly || [],
    fwd_pe: f.fwd_pe || null,
    fcf: f.fcf || null,
    cfo: f.cfo || null,
    sales: f.sales || null,
    opm_pct: f.opm_pct || null,
    npm_pct: f.npm_pct || null,
    debt_eq: f.debt_eq || null,
  };
  S.drillTab='overview';
  render();
}

function clearPortfolio(){
  // confirm() is blocked in iOS Safari PWA — use custom modal
  const ov    = document.getElementById('ov');
  const panel = document.getElementById('import-panel');
  const body  = document.getElementById('import-panel-body');
  body.innerHTML = `
    <div style="text-align:center;padding:20px 0 10px">
      <div style="font-size:36px;margin-bottom:12px">🗑</div>
      <div style="font-family:'Syne',sans-serif;font-size:16px;font-weight:700;
        color:var(--tx);margin-bottom:8px">Clear Portfolio?</div>
      <div style="font-size:12px;color:var(--tx3);margin-bottom:24px">
        This will delete all ${S.portfolio.length} holdings.<br>This cannot be undone.
      </div>
      <button onclick="
        S.portfolio=[];savePF();
        document.getElementById('ov').classList.remove('on');
        document.getElementById('import-panel').classList.remove('on');
        render();
        toast('Portfolio cleared');
      " style="width:100%;padding:14px;background:rgba(255,59,92,.15);
        border:1px solid var(--rd);border-radius:10px;color:var(--rd2);
        font-size:14px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif;
        margin-bottom:10px;">
        Yes, Clear All
      </button>
      <button onclick="
        document.getElementById('ov').classList.remove('on');
        document.getElementById('import-panel').classList.remove('on');
      " style="width:100%;padding:14px;background:var(--s2);
        border:1px solid var(--b2);border-radius:10px;color:var(--tx3);
        font-size:14px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif;">
        Cancel
      </button>
    </div>
  `;
  ov.classList.add('on');
  panel.classList.add('on');
}

function genCandles(ltp,n){
  const cs=[];let p=ltp*(1-(n*0.002));
  for(let i=0;i<n;i++){
    const c=p*(1+(Math.random()-.47)*.015);
    const o=p,h=Math.max(o,c)*(1+Math.random()*.005),l=Math.min(o,c)*(1-Math.random()*.005);
    cs.push({o:Math.round(o),h:Math.round(h),l:Math.round(l),c:Math.round(c),v:parseFloat((1+Math.random()*3).toFixed(1))});
    p=c;
  }
  cs[cs.length-1].c=Math.round(ltp);
  return cs;
}

//  WATCHLIST TAB — FIX #8: Real NSE search
let wlSearchTimer=null;
let wlSearchVal='';

// WATCHLIST TAB — search, track, and manage NSE stocks
// GitHub sync auto-triggers price fetch on add/remove
function renderWatchlist(c){
  // Merge live fundamentals into each watchlist item
  const wl = S.watchlist.map(w=>{
    const f = FUND[w.symbol] || {};
    const ltp = f.ltp || w.ltp || 0;
    return {
      ...w,
      ltp,
      change:   w.change || f.chg1d || 0,
      pe:       f.pe     || null,
      pb:       f.pb     || null,
      roe:      f.roe    || null,
      roce:     f.roce   || null,
      opm:      f.opm_pct|| null,
      week52H:  f.w52h   || null,
      week52L:  f.w52l   || null,
      mcap:     f.mcap   || null,
      eps:      f.eps    || null,
      beta:     f.beta   || null,
      div:      f.div_yield || null,
      debt_eq:  f.debt_eq  || null,
      score:    w.score  || 65,
    };
  });
  const gainers=wl.filter(s=>s.change>0);
  const avg=wl.length?Math.round(wl.reduce((a,s)=>a+(s.score||65),0)/wl.length):0;

  c.innerHTML=`<div class="fin">

  ${!wl.length?`<div class="empty-state"><div class="empty-icon">👁</div><div class="empty-title">Watchlist Empty</div><div class="empty-sub">Search below to add stocks</div></div>`:`
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;padding:10px 13px 8px">
    <div class="card" style="text-align:center;border-top:2px solid var(--ac)">
      <div style="font-size:8px;color:var(--label);text-transform:uppercase;font-weight:700;letter-spacing:.8px">Watching</div>
      <div style="font-family:var(--mono);font-size:18px;font-weight:700;color:var(--ac);margin-top:4px">${wl.length}</div>
    </div>
    <div class="card" style="text-align:center;border-top:2px solid var(--gr)">
      <div style="font-size:8px;color:var(--label);text-transform:uppercase;font-weight:700;letter-spacing:.8px">Rising</div>
      <div style="font-family:var(--mono);font-size:18px;font-weight:700;color:var(--gr2);margin-top:4px">${gainers.length}/${wl.length}</div>
    </div>
  </div>
  <div style="padding:0 13px 80px">
    ${wl.map(s=>{
      const bull=s.change>=0, col=bull?'var(--gr2)':'var(--rd2)';
      const m2 = (k,v,u) => v!=null&&v!==0&&v!==''?'<span style="color:var(--tx3);font-size:8px">'+k+'</span><span style="color:var(--tx2);font-size:9px;font-family:var(--mono);margin-right:8px"> '+v+u+'</span>':'';
      return '<div style="padding:8px 0;border-bottom:1px solid var(--b1)">'
        +'<div style="display:flex;justify-content:space-between;align-items:center;cursor:pointer;margin-bottom:3px" onclick="openStock('+JSON.stringify(s).replace(/"/g,"'")+')"><div>'
        +'<span style="font-size:12px;font-weight:700;color:var(--tx1);font-family:var(--mono)">'+s.symbol+'</span>'
        +'<span style="font-size:9px;color:var(--tx3);margin-left:6px">'+trunc(s.name,22)+'</span>'
        +'</div><div style="display:flex;align-items:center;gap:8px">'
        +'<span style="font-size:12px;font-weight:700;color:var(--tx1);font-family:var(--mono)">'+(s.ltp>0?'₹'+s.ltp.toFixed(1):'—')+'</span>'
        +'<span style="font-size:10px;font-weight:600;color:'+col+'">'+(bull?'▲':'▼')+Math.abs(s.change).toFixed(1)+'%</span>'
        +'<button onclick="event.stopPropagation();removeFromWL(this.getAttribute(\'data-sym\'))" data-sym="'+s.symbol+'" style="background:none;border:none;color:#3a5a72;font-size:12px;cursor:pointer;padding:0 4px">✕</button>'
        +'</div></div>'
        +'<div style="display:flex;flex-wrap:wrap;gap:0;align-items:center">'
        +m2('PE',s.pe?fn(s.pe,1):null,'x')
        +m2('ROE',s.roe?fn(s.roe,1):null,'%')
        +m2('OPM',s.opm?fn(s.opm,1):null,'%')
        +m2('PB',s.pb?fn(s.pb,1):null,'x')
        +m2('DE',s.debt_eq!=null?fn(s.debt_eq,1):null,'x')
        +m2('EPS',s.eps?'₹'+fn(s.eps,1):null,'')
        +(s.mcap?'<span style="color:var(--tx3);font-size:8px">MCap</span><span style="color:var(--tx2);font-size:9px;font-family:var(--mono);margin-right:8px"> '+s.mcap+'Cr</span>':'')
        +'</div></div>';
    }).join('')}
  </div>`}

  <div style="padding:10px 13px;background:var(--bg);border-top:1px solid var(--b1);position:sticky;bottom:56px">
    <div class="search-box" style="margin:0">
      <span class="srch-ico">🔍</span>
      <input class="srch-inp" id="wl-add-inp" type="text"
        placeholder="Search symbol or name to add…"
        autocapitalize="characters" autocomplete="off" spellcheck="false"
        oninput="wlSearch(this.value)"
        value="${S.wlSearch||''}"/>
    </div>
    <div id="wl-results" style="margin-top:4px"></div>
  </div>

  </div>`;

  // Re-render search results if there's an active query
  if(S.wlSearch) wlSearch(S.wlSearch);
}

// Live search across NSE_DB (300+ symbols)
function wlSearch(val){
  S.wlSearch = val.trim();
  const el = document.getElementById('wl-results');
  if(!el) return;
  if(!S.wlSearch){el.innerHTML='';return;}

  const q = S.wlSearch.toUpperCase();
  const already = new Set(S.watchlist.map(w=>w.symbol));

  // Search NSE_DB — by symbol prefix first, then name contains
  const exact   = NSE_DB.filter(s=>s.sym===q);
  const prefix  = NSE_DB.filter(s=>s.sym!==q&&s.sym.startsWith(q));
  const partial = NSE_DB.filter(s=>!s.sym.startsWith(q)&&(s.sym.includes(q)||s.name.toUpperCase().includes(q)||s.sector.toUpperCase().includes(q)));
  const hits = [...exact,...prefix,...partial].filter(s=>!already.has(s.sym)).slice(0,8);

  if(!hits.length){
    el.innerHTML=`<div class="srch-results"><div style="padding:12px;text-align:center;font-size:11px;color:var(--mu)">No results for "${S.wlSearch}"</div></div>`;
    return;
  }

  el.innerHTML=`<div class="srch-results">
    ${hits.map(h=>`
      <div class="sr-row" onclick="addToWL('${h.sym}')">
        <div>
          <div class="sr-sym">${h.sym}</div>
          <div class="sr-name">${h.name}</div>
          <div class="sr-sect">${h.sector}</div>
        </div>
        <span class="sr-add">+ Add</span>
      </div>`).join('')}
  </div>`;
}

// Add stock to watchlist + sync to GitHub
function addToWL(sym){
  sym = sym.toUpperCase().replace(/\.NS$/,'');
  if(S.watchlist.find(w=>w.symbol===sym)){toast(sym+' already in watchlist');return;}
  const info = NSE_DB.find(s=>s.sym===sym)||{name:sym,sector:'Diversified'};
  S.watchlist.push({
    symbol:sym, name:info.name, sector:info.sector,
    ltp:0, change:0,
  });
  S.wlSearch='';
  saveWL();
  syncWatchlistToGitHub(sym);
  render();
}

// Remove stock from watchlist + sync to GitHub
function removeFromWL(sym){
  S.watchlist=S.watchlist.filter(w=>w.symbol!==sym);
  saveWL();
  syncWatchlistToGitHub(null);
  render();
}

// ── GitHub API: Push index.html to repo ───────────────────
// GITHUB API — push index.html, sync watchlist, diagnostics
async function pushIndexToGitHub(){
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  if(!token || !repo){
    toast('⚠ Set GitHub repo and PAT in Settings first');
    return;
  }

  toast('⬆ Pushing to GitHub…');

  try {
    const headers = {
      'Authorization': 'token '+token,
      'Content-Type':  'application/json',
      'Accept':        'application/vnd.github.v3+json',
    };

    const fileUrl = `https://api.github.com/repos/${repo}/contents/index.html`;

    // Get current SHA
    let sha = null;
    try {
      const get = await fetch(fileUrl, {headers});
      if(get.ok){ const d = await get.json(); sha = d.sha; }
    } catch(e){}

    // Get HTML from document directly — no network fetch needed
    const html = '<!DOCTYPE html>\n' + document.documentElement.outerHTML;
    
    // Encode to base64
    const encoded = btoa(unescape(encodeURIComponent(html)));

    const body = {
      message: 'BharatMarkets: update ' + new Date().toLocaleString('en-IN',{timeZone:'Asia/Kolkata'}),
      content: encoded,
    };
    if(sha) body.sha = sha;

    const put = await fetch(fileUrl, {method:'PUT', headers, body:JSON.stringify(body)});

    if(put.ok){
      toast('✅ Pushed to '+repo+' — Pages rebuilding (~1 min)');
      const btn = document.getElementById('push-btn');
      if(btn){ btn.textContent='✅ Pushed!'; btn.style.background='rgba(0,232,150,.2)'; }
      setTimeout(()=>{
        if(btn){ btn.textContent='⬆ Push index.html to GitHub'; btn.style.background=''; }
      }, 4000);
    } else {
      const err = await put.json();
      toast('❌ Push failed: '+(err.message||put.status));
    }
  } catch(e){
    toast('❌ Error: '+e.message);
  }
}

function headerPricesTap(){
  // Spin the ↻ while fetching
  const spin = document.getElementById('hdr-prices-spin');
  if(spin){ spin.classList.add('spin'); }
  refreshPortfolioData().finally(()=>{
    if(spin) spin.classList.remove('spin');
  });
}

async function headerFundTap(){
  const spin = document.getElementById('hdr-fund-spin');
  if(spin){ spin.classList.add('spin'); }
  try{
    await manualTriggerWorkflow('fundamentals_only');
  } finally {
    if(spin) spin.classList.remove('spin');
  }
}

function toggleKeyVis(id){
  const el = document.getElementById(id);
  if(!el) return;
  el.type = el.type==='password' ? 'text' : 'password';
}

function updateGhDots(){
  // Re-render watchlist to reflect new dot states
  if(S.curTab==='watchlist') render();
}

// 3-step diagnostic: ① repo access ② workflow file ③ trigger
async function manualTriggerWorkflow(fetchType){
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  if(!token || !repo){
    toast('⚠ Configure GitHub repo + PAT in settings first');
    return;
  }
  const diag = document.getElementById('fetch-result') || document.getElementById('gh-diag');
  if(diag){ diag.style.display='block'; diag.innerHTML='<span style="color:#ffbf47">⏳ Triggering '+fetchType+' fetch…</span>'; }

  const headers = { 'Authorization':'token '+token, 'Content-Type':'application/json', 'Accept':'application/vnd.github.v3+json' };
  try{
    const r = await fetch('https://api.github.com/repos/'+repo+'/actions/workflows/fetch-prices.yml/dispatches', {
      method:'POST', headers,
      body: JSON.stringify({ ref:'main', inputs:{ fetch_type: fetchType } })
    });
    if(r.status === 204){
      const msg = '✅ Workflow triggered — check GitHub Actions tab for progress (~5 min)';
      if(diag){ diag.innerHTML='<span style="color:#00e896">'+msg+'</span>'; }
      S.settings._lastSync = Date.now();
      S.settings._lastSyncOk = true;
      S.settings._lastSyncMsg = fetchType+' triggered manually';
      saveSettings();
      toast('✅ '+fetchType+' workflow triggered');
    } else if(r.status === 403){
      const msg = '❌ 403 — PAT needs "workflow" scope. Go to github.com/settings/tokens and regenerate with repo + workflow scopes.';
      if(diag){ diag.innerHTML='<div style="color:#ff6b85">'+msg+'</div>'; }
      toast('❌ PAT missing workflow scope');
    } else if(r.status === 422){
      const msg = '❌ 422 — workflow file not found. Ensure fetch-prices.yml is in .github/workflows/ on main branch.';
      if(diag){ diag.innerHTML='<div style="color:#ff6b85">'+msg+'</div>'; }
    } else {
      const e = await r.json().catch(()=>({}));
      const msg = '❌ '+r.status+': '+(e.message||'unknown error');
      if(diag){ diag.innerHTML='<div style="color:#ff6b85">'+msg+'</div>'; }
      toast(msg);
    }
  } catch(e){
    const msg = '❌ Network error: '+e.message;
    if(diag){ diag.innerHTML='<div style="color:#ff6b85">'+msg+'</div>'; }
    toast(msg);
  }
}

async function testGitHubConnection(){
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  const diag  = document.getElementById('gh-diag');
  if(!diag) return;

  if(!token || !repo){
    diag.style.display = 'block';
    diag.innerHTML = diagRow('⚠ Enter Repository and GitHub PAT first', null, null);
    return;
  }

  diag.style.display = 'block';
  diag.innerHTML = '<div style="color:#ffbf47;font-size:11px">Running…</div>';

  const headers = { 'Authorization':'token '+token, 'Accept':'application/vnd.github.v3+json' };
  const results = [{step:'① Repo',ok:null,fix:null},{step:'② Workflow',ok:null,fix:null},{step:'③ Trigger',ok:null,fix:null}];
  let allOk = true, failMsg = '';

  function render(){
    const rows = results.map(r=>{
      const icon = r.ok===null?'<span style="color:#4a6888">—</span>':r.ok?'<span style="color:#00e896">✓</span>':'<span style="color:#ff6b85">✗</span>';
      const fix  = (!r.ok&&r.ok!==null&&r.fix)?` <a href="${r.fix}" target="_blank" style="font-size:10px;color:#64b5f6;text-decoration:none;margin-left:4px">Fix ↗</a>`:'';
      return `<div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid var(--b1)">
        <span style="font-size:11px;color:var(--tx3);width:80px;flex-shrink:0">${r.step}</span>
        <span style="font-size:12px">${icon}</span>${fix}
      </div>`;
    }).join('');
    const summary = allOk && results.every(r=>r.ok!==null)
      ? '<div style="margin-top:8px;font-size:11px;font-weight:700;color:#00e896">✅ Auto-fetch working</div>'
      : failMsg ? '<div style="margin-top:8px;font-size:11px;font-weight:700;color:#ff6b85">❌ '+failMsg+'</div>' : '';
    diag.innerHTML = rows + summary;
  }
  render();

  // ① Repo
  try{
    const r = await fetch('https://api.github.com/repos/'+repo, {headers});
    results[0].ok = r.ok;
    if(!r.ok){ allOk=false; failMsg='Auth failed — check PAT'; results[0].fix='https://github.com/settings/tokens'; }
  } catch(e){ results[0].ok=false; allOk=false; failMsg='Network error'; }
  render();

  // ② Workflow
  try{
    const r = await fetch('https://api.github.com/repos/'+repo+'/contents/.github/workflows/fetch-prices.yml', {headers});
    results[1].ok = r.ok;
    if(!r.ok){ allOk=false; failMsg='fetch-prices.yml not found'; results[1].fix='https://github.com/'+repo+'/tree/main/.github/workflows'; }
  } catch(e){ results[1].ok=false; allOk=false; failMsg='Network error'; }
  render();

  // ③ Trigger
  try{
    const r = await fetch('https://api.github.com/repos/'+repo+'/actions/workflows/fetch-prices.yml/dispatches', {
      method:'POST', headers,
      body: JSON.stringify({ ref:'main', inputs:{ fetch_type:'prices_only' } })
    });
    results[2].ok = r.status===204;
    if(!results[2].ok){
      allOk=false;
      if(r.status===403){ failMsg='PAT needs "workflow" scope'; results[2].fix='https://github.com/settings/tokens/new?scopes=repo,workflow&description=BharatMarkets'; }
      else if(r.status===422){ failMsg='Workflow not found on main branch'; }
      else { failMsg='Trigger failed ('+r.status+')'; }
    }
  } catch(e){ results[2].ok=false; allOk=false; failMsg='Network error'; }
  render();

  S.settings._ghStatus = allOk ? 'ok' : 'fail';
  saveSettings();
  if(S.curTab==='watchlist') render();
}

// Commit watchlist.txt to GitHub + trigger workflow for new symbols
async function syncWatchlistToGitHub(newSym){
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  if(!token || !repo){
    if(newSym) toast('⚠ GitHub not configured — set PAT in Watchlist settings');
    return;
  }

  const headers = {
    'Authorization': 'token '+token,
    'Content-Type':  'application/json',
    'Accept':        'application/vnd.github.v3+json',
  };

  try {
    // Step 1: Commit updated watchlist.txt
    const symbols = S.watchlist.map(w=>w.symbol).join('\n');
    const encoded = btoa(unescape(encodeURIComponent(symbols)));
    const fileUrl = `https://api.github.com/repos/${repo}/contents/watchlist.txt`;

    let sha = null;
    const get = await fetch(fileUrl, {headers});
    if(get.ok){ const d = await get.json(); sha = d.sha; }

    const fileBody = { message: newSym ? 'watchlist: add '+newSym : 'watchlist: update', content: encoded };
    if(sha) fileBody.sha = sha;
    const put = await fetch(fileUrl, { method:'PUT', headers, body:JSON.stringify(fileBody) });
    if(!put.ok){
      const err = await put.json();
      S.settings._lastSync=Date.now();S.settings._lastSyncOk=false;S.settings._lastSyncMsg=err.message||put.status;saveSettings();
      toast('⚠ GitHub sync failed: '+(err.message||put.status));
      return;
    }

    // Step 2: Trigger workflow_dispatch — wait 2s for watchlist.txt commit to land
    if(newSym){
      await new Promise(r=>setTimeout(r, 2000));
      const wfUrl = `https://api.github.com/repos/${repo}/actions/workflows/fetch-prices.yml/dispatches`;
      const wfRes = await fetch(wfUrl, {
        method: 'POST',
        headers,
        body: JSON.stringify({ ref:'main', inputs:{ fetch_type:'new_symbol', symbol:newSym } })
      });
      if(wfRes.status === 204){
        S.settings._lastSync=Date.now();S.settings._lastSyncOk=true;S.settings._lastSyncMsg=newSym+' added';saveSettings();
      toast('✅ '+newSym+' synced — fetching data (~3 min)');
      } else if(wfRes.status === 403){
        toast('⚠ PAT needs "workflow" scope — regenerate at github.com/settings/tokens');
      } else if(wfRes.status === 422){
        toast('⚠ Workflow not found — commit fetch-prices.yml to .github/workflows/');
      } else {
        const e = await wfRes.json().catch(()=>({}));
        toast('⚠ Trigger failed ('+wfRes.status+'): '+(e.message||'run Actions manually'));
      }
    } else {
      S.settings._lastSync=Date.now();S.settings._lastSyncOk=true;S.settings._lastSyncMsg='watchlist updated';saveSettings();
      toast('✅ watchlist.txt synced to GitHub');
    }
  } catch(e){
    toast('⚠ GitHub error: '+e.message);
  }
}

//  FIX #2: MACRO TAB — fully populated
// MACRO TAB — India macro indicators + live RSS news
function renderMacro(c){
  const filtered = S.macroFilter==='ALL'
    ? MACRO_DATA
    : MACRO_DATA.filter(m=>m.tag===S.macroFilter);

  c.innerHTML=`<div class="fin">
  <div style="padding:12px 13px 8px;display:flex;justify-content:space-between;align-items:center">
    <div>
      <div style="font-family:'Syne',sans-serif;font-size:15px;font-weight:700;color:var(--title)">India Macro Dashboard</div>
      <div style="font-size:10px;color:var(--tx3);margin-top:2px">Tap any indicator for detailed analysis</div>
    </div>
  </div>

  <!-- Filter chips -->
  <div class="chip-row">
    ${['ALL','RBI','MACRO','OIL','FII','GEO'].map(f=>`
      <div class="chip ${S.macroFilter===f?'active':''}" onclick="setMacroFilter('${f}')">${f}</div>`).join('')}
  </div>

  <!-- Macro cards -->
  <div style="padding:8px 13px 14px">
    ${filtered.map((m,i)=>`
      <div class="macro-card ${S.expMacro===i?'exp':''}" onclick="toggleMacro(${i})" style="border-left:3px solid ${m.ic}">
        <div style="display:flex;justify-content:space-between;align-items:flex-start">
          <div style="flex:1">
            <div style="display:flex;align-items:center;gap:7px;margin-bottom:4px">
              <span style="font-size:16px">${m.icon}</span>
              <span class="macro-name">${m.label}</span>
            </div>
            <div class="macro-val">${m.val}</div>
            <div class="macro-trend" style="color:${m.ic}">${m.trend}</div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:5px">
            <span class="pill" style="background:${m.ic}18;color:${m.ic};border:1px solid ${m.ic}40">${m.impact}</span>
            <span class="pill pill-ac">${m.tag}</span>
          </div>
        </div>
        ${S.expMacro===i?`<div class="macro-detail">${m.detail}</div>`:''}
      </div>`).join('')}
  </div>

  <!-- FIX #2: Live news section from RSS -->
  <div style="padding:0 13px">
    <div class="sec-lbl">Live Market News</div>
    <div id="macro-news-list">
      <div style="text-align:center;padding:20px;color:var(--mu);font-size:11px">Loading news…</div>
    </div>
  </div>
  </div>`;

  // Load news asynchronously
  loadMacroNews();
}

function setMacroFilter(f){
  S.macroFilter=f;
  if(S.curTab==='macro')renderMacro(document.getElementById('content'));
}
function toggleMacro(i){
  S.expMacro=S.expMacro===i?null:i;
  if(S.curTab==='macro')renderMacro(document.getElementById('content'));
}

// FIX #2 & #3: RSS News loader
async function loadMacroNews(){
  const el=document.getElementById('macro-news-list');
  if(!el)return;
  const FEEDS=[
    'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms',
    'https://economictimes.indiatimes.com/economy/rssfeeds/1373380680.cms',
  ];
  const all=[];
  for(const feed of FEEDS){
    try{
      const url='https://api.rss2json.com/v1/api.json?rss_url='+encodeURIComponent(feed)+'&count=10';
      const res=await fetch(url,{signal:AbortSignal.timeout?AbortSignal.timeout(8000):undefined});
      const d=await res.json();
      if(d.status==='ok')all.push(...(d.items||[]));
    }catch(_){}
  }
  // Deduplicate
  const seen=new Set();
  const items=all.filter(i=>{if(seen.has(i.title))return false;seen.add(i.title);return true;})
    .sort((a,b)=>new Date(b.pubDate)-new Date(a.pubDate))
    .slice(0,12);

  if(!items.length){
    el.innerHTML=`<div style="padding:14px;text-align:center;font-size:11px;color:var(--mu)">Could not load news — check connection</div>`;
    return;
  }

  const filterTag=S.macroFilter;
  const filtered=filterTag==='ALL'?items:items.filter(i=>classifyNews(i.title).tag===filterTag);

  el.innerHTML=(filtered.length?filtered:items).map(item=>{
    const{tag,imp}=classifyNews(item.title);
    const src=item.source?.name||extractDomain(item.link)||'ET Markets';
    const body=item.description?item.description.replace(/<[^>]+>/g,'').slice(0,120)+'…':'';
    return `<div class="news-item">
      <div class="news-src">
        <span>${src}</span>
        <span class="imp-badge imp-${imp}">${imp==='H'?'HIGH':imp==='M'?'MED':'LOW'}</span>
        <span class="pill pill-bl" style="font-size:7px">${tag}</span>
        <span>${timeAgo(new Date(item.pubDate))}</span>
      </div>
      <div class="news-title">${item.title}</div>
      ${body?`<div class="news-body">${body}</div>`:''}
    </div>`;
  }).join('');
}

//  MOVERS TAB
// MOVERS TAB — gainers/losers/sector heatmap from live prices
// Data: portfolio + watchlist stocks with live LTP
function renderMovers(c){
  // Universe = portfolio + watchlist stocks only (not stale/irrelevant symbols)
  const pfSyms = new Set(S.portfolio.map(h=>h.sym));
  const wlSyms = new Set(S.watchlist.map(w=>w.symbol));
  const tracked = new Set([...pfSyms, ...wlSyms]);

  // Build live price lookup from portfolio + watchlist (updated by refreshPortfolioData)
  const livePrices = {};
  S.portfolio.forEach(h=>{ if(h.ltp>0) livePrices[h.sym] = {ltp:h.ltp, chg:h.change||h.chg1d||0}; });
  S.watchlist.forEach(w=>{ if(w.ltp>0) livePrices[w.symbol] = {ltp:w.ltp, chg:w.change||0}; });

  const universe = [...tracked]
    .map(sym=>{
      const f    = FUND[sym] || {};
      const live = livePrices[sym] || {};
      return {
        sym,
        ltp:    live.ltp  || f.ltp    || 0,
        chg:    live.chg  || f.chg1d  || 0,
        sector: f.sector  || '—',
        name:   f.name    || sym,
        mcap:   f.mcap    || 0,
        pe:     f.pe      || null,
        inPF:   pfSyms.has(sym),
      };
    })
    .filter(s => s.ltp > 0 && s.chg !== 0);

  // Sort for gainers/losers
  const gainers = [...universe].sort((a,b)=>b.chg-a.chg).slice(0,8);
  const losers  = [...universe].sort((a,b)=>a.chg-b.chg).slice(0,8);

  // Index data from FUND (fetched as special symbols)
  const indexMap = {
    'NIFTY':            'NIFTY 50',
    'BANKNIFTY':        'Bank Nifty',
    'NIFTYMIDCAP100':   'Midcap 100',
    'CNXIT':            'Nifty IT',
    'NIFTYPSE':         'Nifty PSE',
    'NIFTYSMALLCAP100': 'Smallcap 100',
  };
  const indices = Object.entries(indexMap).map(([sym, name])=>{
    const f = FUND[sym] || {};
    return { name, ltp: f.ltp||0, chg: f.chg1d||0, prev: f.prev||0 };
  }).filter(i=>i.ltp>0);

  // Sector performance — average chg1d by sector
  const sectorData = {};
  universe.forEach(s=>{
    if(!s.sector||s.sector==='—') return;
    if(!sectorData[s.sector]) sectorData[s.sector] = {sum:0, n:0};
    sectorData[s.sector].sum += s.chg;
    sectorData[s.sector].n++;
  });
  const sectors = Object.entries(sectorData)
    .map(([s,d])=>({name:s, avg: d.sum/d.n}))
    .filter(s=>s.avg!==0)
    .sort((a,b)=>Math.abs(b.avg)-Math.abs(a.avg))
    .slice(0,10);

  const fundLoaded = Object.keys(FUND).length > 0;
  const fundKeys = Object.keys(FUND);
  const dataTime = fundKeys.length > 0 && FUND[fundKeys[0]]?.updated
    ? new Date(FUND[fundKeys[0]].updated).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:true})
    : '—';

  c.innerHTML=`<div class="fin" style="padding:12px 13px 14px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <div style="font-family:'Syne',sans-serif;font-size:15px;font-weight:700;color:var(--title)">Market Movers</div>
      <div style="font-size:9px;color:var(--tx3);font-family:var(--mono)">
        ${fundLoaded ? universe.length+' stocks · '+dataTime : '⚠ Run Actions to load data'}
      </div>
    </div>

    ${!fundLoaded ? `<div style="padding:30px;text-align:center;color:var(--tx3);font-size:11px">
      No data yet — import portfolio or configure GitHub Sync in Watchlist settings
    </div>` : `

    <!-- Indices -->
    ${indices.length ? `<div class="card" style="margin-bottom:10px">
      <div style="font-weight:700;font-size:11px;color:var(--title);margin-bottom:8px;font-family:'Syne',sans-serif">📊 Index Snapshot</div>
      ${indices.map(i=>{
        const up=i.chg>=0;
        const pts = i.prev>0 ? ((i.chg/100)*i.prev).toFixed(0) : '—';
        return `<div style="display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--b1)">
          <div style="font-size:11px;font-weight:600;color:var(--tx2)">${i.name}</div>
          <div style="text-align:right">
            <div style="font-size:12px;font-weight:700;font-family:var(--mono);color:var(--tx1)">₹${i.ltp.toLocaleString('en-IN')}</div>
            <div style="font-size:10px;font-weight:700;color:${up?'#00e896':'#ff6b85'}">${up?'▲':'▼'} ${Math.abs(i.chg).toFixed(2)}% ${up?'+':''}${pts}pts</div>
          </div>
        </div>`;
      }).join('')}
    </div>` : ''}

    <!-- Gainers / Losers -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px">
      <div class="card">
        <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:12px;color:var(--gr2);padding-bottom:7px;margin-bottom:8px;border-bottom:1px solid var(--b1)">🟢 Top Gainers</div>
        ${gainers.length ? gainers.map(s=>`
          <div class="mover-row" style="border-left-color:var(--gr)">
            <div style="min-width:0;flex:1">
              <div class="mover-sym">${s.sym}</div>
              <div class="mover-why">${s.sector}</div>
            </div>
            <div style="text-align:right;flex-shrink:0">
              <div style="color:#00e896;font-weight:700;font-size:11px">+${s.chg.toFixed(2)}%</div>
              <div style="color:var(--tx3);font-size:9px">₹${s.ltp.toFixed(1)}</div>
            </div>
          </div>`).join('') : '<div style="color:var(--tx3);font-size:10px">No gainers today</div>'}
      </div>
      <div class="card">
        <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:12px;color:var(--rd2);padding-bottom:7px;margin-bottom:8px;border-bottom:1px solid var(--b1)">🔴 Top Losers</div>
        ${losers.length ? losers.map(s=>`
          <div class="mover-row" style="border-left-color:var(--rd)">
            <div style="min-width:0;flex:1">
              <div class="mover-sym">${s.sym}</div>
              <div class="mover-why">${s.sector}</div>
            </div>
            <div style="text-align:right;flex-shrink:0">
              <div style="color:#ff6b85;font-weight:700;font-size:11px">${s.chg.toFixed(2)}%</div>
              <div style="color:var(--tx3);font-size:9px">₹${s.ltp.toFixed(1)}</div>
            </div>
          </div>`).join('') : '<div style="color:var(--tx3);font-size:10px">No losers today</div>'}
      </div>
    </div>

    <!-- Sector Heatmap — canvas treemap -->
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:11px;color:var(--title)">🗺 Sector Heatmap</div>
        <div style="display:flex;gap:6px;font-size:9px;color:var(--tx3)">
          <span>Size = Portfolio Value</span>
          <span style="color:#00e896">■ Up</span>
          <span style="color:#ff6b85">■ Down</span>
        </div>
      </div>
      <canvas id="cv-heatmap" style="width:100%;border-radius:6px;cursor:pointer"></canvas>
      <div id="hm-tooltip" style="display:none;position:fixed;background:#0d1929;border:1px solid #1e3350;border-radius:8px;padding:8px 12px;font-family:var(--mono);font-size:10px;color:var(--tx1);pointer-events:none;z-index:999"></div>
    </div>

    <!-- My sector bar chart -->
    ${sectors.length ? `<div class="card" style="margin-top:10px">
      <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:11px;color:var(--title);margin-bottom:10px">📊 My Sectors</div>
      <div style="display:flex;flex-direction:column;gap:5px">
        ${sectors.map(s=>{
          const up = s.avg>=0;
          const barW = Math.min(100, Math.abs(s.avg)*15).toFixed(0);
          return `<div style="display:flex;align-items:center;gap:8px">
            <div style="width:90px;font-size:9px;color:var(--tx2);text-align:right;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.name}</div>
            <div style="flex:1;background:var(--s2);border-radius:3px;height:13px;position:relative;overflow:hidden">
              <div style="position:absolute;${up?'left:0':'right:0'};top:0;height:100%;width:${barW}%;background:${up?'rgba(0,208,132,.4)':'rgba(255,59,92,.4)'};border-radius:3px"></div>
            </div>
            <div style="width:40px;font-size:9px;font-weight:700;color:${up?'#00e896':'#ff6b85'};font-family:var(--mono);text-align:right">${up?'+':''}${s.avg.toFixed(2)}%</div>
          </div>`;
        }).join('')}
      </div>
    </div>` : ''}
    `}
  </div>`;

  // Draw heatmap after DOM renders
  requestAnimationFrame(()=>requestAnimationFrame(()=>drawSectorHeatmap(universe)));
}

// ── Sector Heatmap Treemap ────────────────────────────
// Squarified treemap — size = portfolio holding value, colour = %chg
function drawSectorHeatmap(universe){
  const cv = document.getElementById('cv-heatmap');
  if(!cv) return;

  const dpr = window.devicePixelRatio || 1;
  const W = Math.max(cv.offsetWidth || window.innerWidth - 30, 180);
  const H = W; // perfect square
  cv.width  = W * dpr; cv.height = H * dpr;
  cv.style.width = W+'px'; cv.style.height = H+'px';
  const ctx = cv.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.fillStyle = '#060c18';
  ctx.fillRect(0, 0, W, H);

  if(!universe.length){
    ctx.fillStyle='rgba(140,176,208,.4)';
    ctx.font='11px sans-serif'; ctx.textAlign='center';
    ctx.fillText('Add stocks to see heatmap', W/2, H/2);
    return;
  }

  // Group by sector
  const sMap = {};
  universe.forEach(s=>{
    const sec = (s.sector && s.sector!=='—') ? s.sector : 'Other';
    if(!sMap[sec]) sMap[sec]={name:sec, holdVal:0, mcap:0, chgSum:0, n:0, stocks:[]};
    // Use portfolio holding value as size (qty*ltp) — most meaningful for personal portfolio
    // For watchlist stocks without qty, use mcap rank as proxy
    const pf = S.portfolio.find(h=>h.sym===s.sym);
    const holdingVal = pf && pf.ltp>0 ? pf.qty*pf.ltp : 0;
    sMap[sec].holdVal += holdingVal;
    sMap[sec].mcap    += (s.mcap||0);
    sMap[sec].chgSum  += (s.chg||0);
    sMap[sec].n++;
    sMap[sec].stocks.push(s);
  });

  const nodes = Object.values(sMap)
    .map(d=>({
      name:   d.name,
      // Size priority: 1) portfolio holding value, 2) mcap if available, 3) stock count
      size:   d.holdVal > 0 ? d.holdVal :
              d.mcap    > 0 ? d.mcap    :
              d.n * 1000,
      chg:    d.chgSum / d.n,
      n:      d.n,
      stocks: [...d.stocks].sort((a,b)=>Math.abs(b.chg)-Math.abs(a.chg)),
    }))
    .sort((a,b)=>b.size-a.size);

  // Normalise sizes to W*H
  const totalSize = nodes.reduce((a,b)=>a+b.size, 0);
  nodes.forEach(n=>{ n.size = (n.size/totalSize) * W * H; });

  // Squarified treemap — standard Bruls algorithm
  const rects = [];

  function worstRatio(row, w){
    if(!w||!row.length) return Infinity;
    const s = row.reduce((a,b)=>a+b.size, 0);
    const maxS = Math.max(...row.map(r=>r.size));
    const minS = Math.min(...row.map(r=>r.size));
    return Math.max((w*w*maxS)/(s*s), (s*s)/(w*w*minS));
  }

  function layoutRow(row, x, y, w, h){
    const s = row.reduce((a,b)=>a+b.size, 0);
    let cx=x, cy=y;
    if(w >= h){
      // horizontal strip
      const stripW = s/h;
      row.forEach(item=>{
        const ih = item.size / stripW;
        rects.push({...item,
          x: Math.max(0,cx), y: Math.max(0,cy),
          w: Math.min(stripW, W-cx), h: Math.min(ih, H-cy)
        });
        cy += ih;
      });
      return {x:x+stripW, y:y, w:w-stripW, h:h};
    } else {
      // vertical strip
      const stripH = s/w;
      row.forEach(item=>{
        const iw = item.size / stripH;
        rects.push({...item,
          x: Math.max(0,cx), y: Math.max(0,cy),
          w: Math.min(iw, W-cx), h: Math.min(stripH, H-cy)
        });
        cx += iw;
      });
      return {x:x, y:y+stripH, w:w, h:h-stripH};
    }
  }

  function squarify(children, x, y, w, h){
    if(!children.length||w<1||h<1) return;
    let row=[], rem=[...children];
    const shortest = Math.min(w,h);
    while(rem.length){
      const test=[...row, rem[0]];
      if(row.length>0 && worstRatio(test,shortest) > worstRatio(row,shortest)) break;
      row.push(rem.shift());
    }
    const next = layoutRow(row, x, y, w, h);
    squarify(rem, next.x, next.y, next.w, next.h);
  }

  squarify(nodes, 0, 0, W, H);

  // Color by % change — use distinct bands for easy reading
  // -3% and below = deep red, 0 = dark neutral, +3% and above = deep green
  function tileColor(chg){
    // Clamp to [-4, +4] range
    const c = Math.max(-4, Math.min(4, chg));
    if(c === 0) return 'rgba(35,50,75,0.85)';
    if(c > 0){
      // Green intensity: 0.1% = dim, 4% = full bright
      const t = c / 4;
      const g = Math.round(80  + 150*t);   // 80 → 230
      const r = Math.round(5   + 15*t);    // keeps it green not yellow
      const b = Math.round(10  + 20*t);
      return 'rgba('+r+','+g+','+b+',0.90)';
    } else {
      const t = (-c) / 4;
      const r = Math.round(80  + 150*t);   // 80 → 230
      const g = Math.round(10  + 15*t);
      const b = Math.round(15  + 20*t);
      return 'rgba('+r+','+g+','+b+',0.90)';
    }
  }

  const PAD = 2;
  rects.forEach(r=>{
    const rx=r.x+PAD, ry=r.y+PAD, rw=r.w-PAD*2, rh=r.h-PAD*2;
    if(rw<3||rh<3) return;

    ctx.fillStyle = tileColor(r.chg);
    ctx.beginPath();
    if(ctx.roundRect) ctx.roundRect(rx,ry,rw,rh,3); else ctx.rect(rx,ry,rw,rh);
    ctx.fill();
    ctx.strokeStyle='rgba(6,12,24,0.8)'; ctx.lineWidth=1; ctx.stroke();

    if(rw<16||rh<12) return;
    ctx.save();
    ctx.beginPath(); ctx.rect(rx,ry,rw,rh); ctx.clip();
    ctx.textAlign='center';
    const sign = r.chg>=0?'+':'';
    const pct  = sign+r.chg.toFixed(2)+'%';
    const cx   = rx+rw/2;

    if(rw>=54&&rh>=36){
      const fs=Math.min(12,Math.max(8,Math.floor(Math.min(rw/7,rh/3.5))));
      ctx.font='700 '+fs+'px \'JetBrains Mono\',monospace';
      ctx.fillStyle='rgba(255,255,255,0.96)';
      const lbl=r.name.length>13?r.name.slice(0,12)+'\u2026':r.name;
      ctx.fillText(lbl, cx, ry+rh*0.42);
      ctx.font=Math.max(7,fs-1)+'px \'JetBrains Mono\',monospace';
      ctx.fillStyle=r.chg>=0?'rgba(190,255,210,0.95)':'rgba(255,195,195,0.95)';
      ctx.fillText(pct, cx, ry+rh*0.42+fs+4);
    } else if(rw>=34&&rh>=22){
      const fs=Math.min(9,Math.max(6,Math.floor(Math.min(rw/6,rh/3))));
      ctx.font='700 '+fs+'px monospace';
      ctx.fillStyle='rgba(255,255,255,0.92)';
      ctx.fillText(r.name.slice(0,9), cx, ry+rh*0.40);
      ctx.font=Math.max(6,fs-1)+'px monospace';
      ctx.fillStyle=r.chg>=0?'rgba(190,255,210,0.9)':'rgba(255,195,195,0.9)';
      ctx.fillText(pct, cx, ry+rh*0.40+fs+3);
    } else {
      ctx.font='6px monospace';
      ctx.fillStyle='rgba(255,255,255,0.85)';
      ctx.fillText(pct, cx, ry+rh/2+3);
    }
    ctx.restore();
  });

  // Tap tooltip
  cv.onclick=(e)=>{
    const br=cv.getBoundingClientRect();
    const scX=W/br.width, scY=H/br.height;
    const mx=(e.clientX-br.left)*scX, my=(e.clientY-br.top)*scY;
    const hit=rects.find(r=>mx>=r.x&&mx<=r.x+r.w&&my>=r.y&&my<=r.y+r.h);
    const tip=document.getElementById('hm-tooltip');
    if(hit&&tip){
      const sign=hit.chg>=0?'+':'';
      tip.innerHTML='<b style="color:'+(hit.chg>=0?'#00e896':'#ff6b85')+'">'+hit.name+'</b>'
        +' <b>'+sign+hit.chg.toFixed(2)+'%</b><br>'
        +'<span style="color:var(--tx3)">'+hit.n+' stock'+(hit.n>1?'s':'')+'</span><br>'
        +'<span style="font-size:8px;color:var(--tx2)">'+hit.stocks.slice(0,5).map(s=>s.sym+' '+(s.chg>=0?'+':'')+s.chg.toFixed(1)+'%').join('  ')+'</span>';
      tip.style.display='block';
      tip.style.left=Math.min(e.clientX+10,window.innerWidth-170)+'px';
      tip.style.top=Math.max(e.clientY-70,8)+'px';
      setTimeout(()=>{tip.style.display='none';},3500);
    }
  };
}

// STOCK DRILL-DOWN — tabbed detail view for any stock
// Tabs: Overview · Technical · Fundamentals · News · Insights
function renderDrill(c){
  const s=S.selStock;
  if(!s){closeStock();return;}
  const bull=s.change>=0;
  const col=bull?'var(--gr2)':'var(--rd2)';
  c.innerHTML=`<div class="drill-wrap">
    <div class="drill-hdr">
      <button class="back-btn" onclick="closeStock()">← Back</button>
      <div style="flex:1;min-width:0">
        <div style="display:flex;align-items:baseline;gap:8px;flex-wrap:wrap">
          <span class="dsym">${s.symbol}</span>
          <span class="dchg" style="color:${col}">₹${fmt(s.ltp)} ${bull?'▲':'▼'} ${Math.abs(s.change||0).toFixed(2)}%</span>
        </div>
        <div style="font-size:11px;color:var(--tx3);margin-top:2px">${trunc(s.name,40)} · ${s.sector||''}</div>
      </div>
      <div class="score-ring" style="border-color:${scoreColor(s.score||65)};background:${scoreColor(s.score||65)}15">
        <div class="score-num" style="color:${scoreColor(s.score||65)}">${s.score||65}</div>
        <div class="score-lbl" style="color:${scoreColor(s.score||65)}">${scoreLabel(s.score||65)}</div>
      </div>
    </div>
    <div class="dtabs">
      ${['overview','technical','fundamentals','news','insights'].map(t=>`
        <button class="dtab ${S.drillTab===t?'active':''}" data-t="${t}" onclick="setDrillTab('${t}')">
          ${{overview:'Overview',technical:'📉 Technical',fundamentals:'📊 Fundamentals',news:'📰 News',insights:'💡 Insights'}[t]}
        </button>`).join('')}
    </div>
    <div id="dc">${renderDC(s)}</div>
  </div>`;

}

// ── Insights Tab ──────────────────────────────────────────
function renderDC(s){
  if(S.drillTab==='overview')     return renderOverview(s);
  if(S.drillTab==='technical')    return renderTechnical(s);
  if(S.drillTab==='fundamentals') return renderFundamentals(s);
  if(S.drillTab==='news')         return renderNewsTab(s);
  if(S.drillTab==='insights')     return renderInsights(s);
  return '';
}

// Insights tab: AI portfolio signal generated from concall + holding data
// Distinct from concall signal: this is personal to YOUR position
function renderInsights(s){
  const sym  = s.symbol;
  const f    = FUND[sym]||{};
  const g    = GUIDANCE[sym];
  const h    = S.portfolio.find(p=>p.sym===sym);
  const ins  = g?.insights;

  // Build insight prompt from all available data
  function buildInsightPrompt(){
    const qtrs = (f.quarterly||[]).slice(0,8);
    const yoyRevs = [];
    for(let i=0;i<Math.min(4,qtrs.length-4);i++){
      if(qtrs[i]?.rev&&qtrs[i+4]?.rev)
        yoyRevs.push(+((qtrs[i].rev-qtrs[i+4].rev)/qtrs[i+4].rev*100).toFixed(1));
    }
    const opmTrend = qtrs.length>=8
      ? +(qtrs.slice(0,4).reduce((a,q)=>a+(q.opm||0),0)/4 - qtrs.slice(4,8).reduce((a,q)=>a+(q.opm||0),0)/4).toFixed(1)
      : null;

    // Sector peers from portfolio
    const peers = S.portfolio.map(p=>mergeHolding(p))
      .filter(p=>p.sym!==sym && (FUND[p.sym]?.sector||'')===f.sector)
      .map(p=>p.sym+' PE:'+( FUND[p.sym]?.pe||'?')+'x ROE:'+(FUND[p.sym]?.roe||'?')+'%');

    // Guidance summary
    const gLines = g ? Object.entries(g)
      .filter(([k,v])=>v && typeof v==='string' && !['sym','updated','raw_table','insights'].includes(k))
      .map(([k,v])=>`${k.replace(/_/g,' ')}: ${v}`)
      .slice(0,25).join('\n') : 'No guidance data available';

    return `You are a senior portfolio manager. Analyse this stock and generate sharp, actionable insights.

STOCK: ${sym} — ${f.name||sym}
SECTOR: ${f.sector||'Unknown'}

VALUATION:
- Current PE: ${f.pe||'?'}x | Forward PE: ${f.fwd_pe||'?'}x
- ROE: ${f.roe||'?'}% | OPM: ${f.opm_pct||'?'}% | Debt/Equity: ${f.debt_eq||'?'}
- 52W position: ${f.ath_pct||'?'}% from ATH | MCap: ₹${f.mcap||'?'}Cr

${h?`MY HOLDING:
- Avg Buy: ₹${h.avgBuy||'?'} | Qty: ${h.qty||'?'} | CMP: ₹${f.ltp||'?'}
- Unrealised P&L: ${f.ltp&&h.avgBuy?((f.ltp-h.avgBuy)/h.avgBuy*100).toFixed(1)+'%':'?'}
- Invested: ₹${h.qty&&h.avgBuy?(h.qty*h.avgBuy/100000).toFixed(2)+'L':'?'}`:'Not in portfolio'}

REVENUE DELIVERY (YoY growth last ${yoyRevs.length} quarters): ${yoyRevs.map(v=>(v>=0?'+':'')+v+'%').join(', ')||'Insufficient data'}
MARGIN TREND: ${opmTrend!==null?(opmTrend>0?'Expanding +':'Contracting ')+Math.abs(opmTrend)+'% (4Q avg)':'Insufficient data'}

SECTOR PEERS IN MY PORTFOLIO: ${peers.length?peers.join(' | '):'None'}

CONCALL GUIDANCE EXTRACTED:
${gLines}

---
Generate EXACTLY 6 insights in this format. Each must be sharp, specific, and tell me what to DO:

INSIGHT 1 — [CATEGORY in caps]: [2-3 sentence insight connecting data points]
INSIGHT 2 — [CATEGORY]: [insight]
INSIGHT 3 — [CATEGORY]: [insight]  
INSIGHT 4 — [CATEGORY]: [insight]
INSIGHT 5 — [CATEGORY]: [insight]
INSIGHT 6 — MOAT: [Is the competitive advantage real, widening or narrowing? Rate moat as WIDE/NARROW/NONE. Identify which moat type applies: Switching Cost, Scale Advantage, Intangible Assets, Cost Moat, or Network Effect. Will it protect returns at scale and justify the current valuation?]

Then on a new line:
ACTION: [BUY MORE / AVERAGE DOWN / HOLD / REDUCE / EXIT] — [specific reason with price or trigger]
TRIGGER: [One specific event or price that would change your view]

CATEGORIES to use (pick most relevant): VALUATION | GROWTH QUALITY | MARGIN RISK | SECTOR CYCLE | MANAGEMENT SIGNAL | POSITION RISK | OPPORTUNITY | RED FLAG | CATALYST | COMPETITIVE RISK | MOAT

Rules:
- Be brutally honest — do not be positive just because I hold the stock
- Use actual numbers from the data above
- Each insight must connect at least 2 data points
- No generic statements — every line must be specific to this company`;
  }

  // Parse pasted insights
  function parseInsights(text){
    const lines = text.split('\n').map(l=>l.trim()).filter(Boolean);
    const bullets = lines
      .filter(l=>l.match(/^INSIGHT\s*\d/i))
      .map(l=>{
        const m = l.match(/^INSIGHT\s*\d+\s*[—\-–:]\s*\[?([A-Z\s]+)\]?\s*[—\-–:]\s*(.+)$/i);
        return m ? {cat: m[1].trim(), text: m[2].trim()} : {cat:'INSIGHT', text: l.replace(/^INSIGHT\s*\d+[—\-–:\s]*/i,'').trim()};
      });
    const actionLine = lines.find(l=>l.match(/^ACTION:/i));
    const triggerLine = lines.find(l=>l.match(/^TRIGGER:/i));
    const action  = actionLine?.replace(/^ACTION:\s*/i,'').trim() || null;
    const trigger = triggerLine?.replace(/^TRIGGER:\s*/i,'').trim() || null;
    const headline = bullets[0]?.text?.slice(0,120) || null;
    return { bullets, action, trigger, headline, updated: new Date().toISOString() };
  }

  return `<div style="padding-bottom:80px">

    <!-- Header -->
    <div style="padding:12px 14px 8px;border-bottom:1px solid var(--b1)">
      <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:14px;color:var(--ac)">💡 AI Insights — ${sym}</div>
      <div style="font-size:9px;color:var(--tx3);margin-top:2px">Generated from concall data + your holding + sector context</div>
    </div>

    <!-- Existing insights -->
    ${ins && ins.bullets?.length ? `
      <div style="padding:12px 14px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
          <div style="font-size:9px;color:var(--tx3)">Last updated: ${new Date(ins.updated).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</div>
          <button onclick="document.getElementById('insight-gen').style.display='block';this.style.display='none'"
            style="background:rgba(249,115,22,.1);border:1px solid rgba(249,115,22,.3);border-radius:5px;padding:3px 10px;color:var(--ac);font-size:8px;font-weight:700;cursor:pointer">
            ↺ Refresh
          </button>
        </div>

        <!-- Action Signal -->
        ${ins.action ? `
        <div style="padding:10px 12px;margin-bottom:10px;border-radius:8px;
          background:rgba(${ins.action.match(/BUY/i)?'0,232,150':ins.action.match(/REDUCE|EXIT/i)?'255,107,133':'255,191,71'},.1);
          border:1px solid rgba(${ins.action.match(/BUY/i)?'0,232,150':ins.action.match(/REDUCE|EXIT/i)?'255,107,133':'255,191,71'},.3)">
          <div style="font-size:8px;color:var(--tx3);margin-bottom:4px">RECOMMENDED ACTION</div>
          <div style="font-size:12px;font-weight:800;color:${ins.action.match(/BUY/i)?'#00e896':ins.action.match(/REDUCE|EXIT/i)?'#ff6b85':'#ffbf47'};line-height:1.4">${ins.action}</div>
        </div>` : ''}

        <!-- Insight bullets -->
        <div style="display:flex;flex-direction:column;gap:8px">
          ${(ins.bullets||[]).map((b,i)=>{
            const catCol = b.cat.match(/RED FLAG|RISK|COMPETITIVE/i)?'#ff6b85':
                           b.cat.match(/OPPORTUNITY|CATALYST|GROWTH/i)?'#00e896':
                           b.cat.match(/VALUATION/i)?'#ffbf47':
                           b.cat.match(/MOAT/i)?'#a78bfa':'#64b5f6';
            return `<div style="padding:10px 12px;background:var(--card);border-radius:8px;
              border-left:3px solid ${catCol};border:1px solid var(--b1);border-left:3px solid ${catCol}">
              <div style="font-size:7px;font-weight:800;color:${catCol};letter-spacing:.8px;margin-bottom:5px">${b.cat}</div>
              <div style="font-size:10px;color:var(--tx1);line-height:1.55">${b.text}</div>
            </div>`;
          }).join('')}
        </div>

        <!-- Trigger -->
        ${ins.trigger ? `
        <div style="margin-top:10px;padding:10px 12px;background:rgba(99,102,241,.08);
          border:1px solid rgba(99,102,241,.25);border-radius:8px">
          <div style="font-size:8px;color:#818cf8;font-weight:700;margin-bottom:4px">🎯 WATCH FOR THIS TRIGGER</div>
          <div style="font-size:10px;color:var(--tx1);line-height:1.5">${ins.trigger}</div>
        </div>` : ''}
      </div>` : ''}

    <!-- Generate section -->
    <div id="insight-gen" style="${ins?'display:none':'display:block'};padding:12px 14px">
      <div style="font-size:10px;font-weight:700;color:var(--title);margin-bottom:8px">
        <span style="background:var(--ac);color:#fff;border-radius:50%;width:16px;height:16px;
          display:inline-flex;align-items:center;justify-content:center;font-size:8px;margin-right:6px">1</span>
        Generate Insight Prompt
      </div>
      <div style="font-size:9px;color:var(--tx3);margin-bottom:8px">
        Combines your concall data + holding + quarterly trend → tailored prompt for Claude
      </div>
      <button onclick="generateInsightPrompt('${sym}')"
        style="width:100%;padding:10px;background:rgba(249,115,22,.12);border:1px solid rgba(249,115,22,.4);
        border-radius:8px;color:var(--ac);font-size:11px;font-weight:800;cursor:pointer;font-family:'Syne',sans-serif">
        📋 Copy Prompt &amp; Open Claude.ai ↗
      </button>
      ${!g?`<div style="margin-top:6px;font-size:8px;color:#ffbf47">⚠ Run Analysis tab first to extract concall data for richer insights</div>`:''}

      <div style="margin-top:16px;font-size:10px;font-weight:700;color:var(--title);margin-bottom:8px">
        <span style="background:var(--ac);color:#fff;border-radius:50%;width:16px;height:16px;
          display:inline-flex;align-items:center;justify-content:center;font-size:8px;margin-right:6px">2</span>
        Paste Claude's Response
      </div>
      <textarea id="ta-insights" placeholder="Paste Claude's 5 insights here..."
        style="width:100%;box-sizing:border-box;height:180px;background:var(--s1);
        border:1px solid var(--b1);border-radius:8px;padding:10px;color:var(--tx1);
        font-size:10px;font-family:var(--mono);resize:vertical;outline:none"></textarea>
      <button onclick="saveInsights('${sym}')"
        style="margin-top:8px;width:100%;padding:10px;background:var(--ac);border:none;
        border-radius:8px;color:#fff;font-size:12px;font-weight:800;cursor:pointer;font-family:'Syne',sans-serif">
        💾 Save Insights
      </button>
    </div>

  </div>`;
}

// Build insight prompt combining concall data + holding + peers
function generateInsightPrompt(sym){
  const f  = FUND[sym]||{};
  const g  = GUIDANCE[sym];
  const h  = S.portfolio.find(p=>p.sym===sym);
  const qtrs = (f.quarterly||[]).slice(0,8);
  const yoyRevs = [];
  for(let i=0;i<Math.min(4,qtrs.length-4);i++){
    if(qtrs[i]?.rev&&qtrs[i+4]?.rev)
      yoyRevs.push(+((qtrs[i].rev-qtrs[i+4].rev)/qtrs[i+4].rev*100).toFixed(1));
  }
  const opmR = qtrs.slice(0,4).filter(q=>q.opm>0);
  const opmO = qtrs.slice(4,8).filter(q=>q.opm>0);
  const opmTrend = opmR.length&&opmO.length
    ? +(opmR.reduce((a,q)=>a+q.opm,0)/opmR.length - opmO.reduce((a,q)=>a+q.opm,0)/opmO.length).toFixed(1)
    : null;

  const peers = S.portfolio.map(p=>mergeHolding(p))
    .filter(p=>p.sym!==sym && (FUND[p.sym]?.sector||'')===f.sector)
    .map(p=>p.sym+' PE:'+(FUND[p.sym]?.pe||'?')+'x ROE:'+(FUND[p.sym]?.roe||'?')+'%');

  const gLines = g ? Object.entries(g)
    .filter(([k,v])=>v && typeof v==='string' && !['sym','updated','raw_table','insights'].includes(k))
    .map(([k,v])=>`${k.replace(/_/g,' ')}: ${v}`)
    .slice(0,25).join('\n') : 'No concall data — run Analysis tab first';

  const prompt = `You are a senior portfolio manager. Analyse this stock and generate sharp, actionable insights.

STOCK: ${sym} — ${f.name||sym}
SECTOR: ${f.sector||'Unknown'}

VALUATION:
- Current PE: ${f.pe||'?'}x | Forward PE: ${f.fwd_pe||'?'}x
- ROE: ${f.roe||'?'}% | OPM: ${f.opm_pct||'?'}% | Debt/Equity: ${f.debt_eq||'?'}
- MCap: ₹${f.mcap||'?'}Cr | ATH%: ${f.ath_pct||'?'}%

${h?`MY HOLDING:
- Avg Buy: ₹${h.avgBuy||'?'} | Qty: ${h.qty||'?'} | CMP: ₹${f.ltp||'?'}
- Unrealised P&L: ${f.ltp&&h.avgBuy?((f.ltp-h.avgBuy)/h.avgBuy*100).toFixed(1)+'%':'?'}
- Invested: ₹${h.qty&&h.avgBuy?(h.qty*h.avgBuy/100000).toFixed(2)+'L':'?'}`:'Not held in portfolio'}

REVENUE TREND (YoY last ${yoyRevs.length}Q): ${yoyRevs.map(v=>(v>=0?'+':'')+v+'%').join(', ')||'Insufficient data'}
MARGIN TREND: ${opmTrend!=null?(opmTrend>0?'Expanding +':'Contracting ')+Math.abs(opmTrend)+'%':'Insufficient data'}

SECTOR PEERS IN MY PORTFOLIO: ${peers.length?peers.join(' | '):'None'}

CONCALL DATA EXTRACTED:
${gLines}

---
Generate EXACTLY 6 insights in this format:

INSIGHT 1 — [CATEGORY]: [2-3 sentence insight connecting multiple data points]
INSIGHT 2 — [CATEGORY]: [insight]
INSIGHT 3 — [CATEGORY]: [insight]
INSIGHT 4 — [CATEGORY]: [insight]
INSIGHT 5 — [CATEGORY]: [insight]
INSIGHT 6 — MOAT: [Is the competitive advantage real, widening or narrowing? Rate moat as WIDE/NARROW/NONE. Identify which moat type applies: Switching Cost, Scale Advantage, Intangible Assets, Cost Moat, or Network Effect. Will it protect returns at scale and justify the current valuation?]

ACTION: [BUY MORE / AVERAGE DOWN / HOLD / REDUCE / EXIT] — [specific reason with price or trigger]
TRIGGER: [One specific event or price that would change your view]

CATEGORIES: VALUATION | GROWTH QUALITY | MARGIN RISK | SECTOR CYCLE | MANAGEMENT SIGNAL | POSITION RISK | OPPORTUNITY | RED FLAG | CATALYST | COMPETITIVE RISK | MOAT

Rules:
- Brutally honest — do not be positive just because I hold it
- Use actual numbers from the data
- Each insight must connect at least 2 data points
- Every line must be specific — no generic statements`;

  // Show prompt modal
  showPromptPanel(sym, prompt);
  if(navigator.clipboard && window.isSecureContext){
    navigator.clipboard.writeText(prompt)
      .then(()=>toast('Insight prompt copied — paste in Claude'))
      .catch(()=>toast('Copy prompt from the panel'));
  }
}

// Parse and save AI insights response to GUIDANCE[sym].insights
function saveInsights(sym){
  const ta = document.getElementById('ta-insights');
  if(!ta||!ta.value.trim()){toast('Paste Claude response first');return;}
  const text = ta.value.trim();

  // Parse bullets
  const lines = text.split('\n').map(l=>l.trim()).filter(Boolean);
  const bullets = lines
    .filter(l=>l.match(/^INSIGHT\s*\d/i))
    .map(l=>{
      const m = l.match(/^INSIGHT\s*\d+\s*[—\-–:]\s*\[?([^\]:\-–]+)\]?\s*[—\-–:]\s*(.+)$/i);
      return m?{cat:m[1].trim().toUpperCase(), text:m[2].trim()}:{cat:'INSIGHT',text:l.replace(/^INSIGHT\s*\d+[—\-–:\s]*/i,'').trim()};
    });
  const actionLine  = lines.find(l=>l.match(/^ACTION:/i));
  const triggerLine = lines.find(l=>l.match(/^TRIGGER:/i));

  if(!bullets.length){toast('Could not parse insights — ensure format matches');return;}

  const ins = {
    bullets,
    action:   actionLine?.replace(/^ACTION:\s*/i,'').trim()||null,
    trigger:  triggerLine?.replace(/^TRIGGER:\s*/i,'').trim()||null,
    headline: bullets[0]?.text?.slice(0,150)||null,
    updated:  new Date().toISOString(),
  };

  if(!GUIDANCE[sym]) GUIDANCE[sym]={sym, updated:new Date().toISOString()};
  GUIDANCE[sym].insights = ins;
  saveGuidanceAll();

  toast('Insights saved for '+sym+' ✓');
  ta.value='';
  render();
}

// Toggle collapsible overview card open/closed
function toggleOvCard(cid){
  const body  = document.getElementById(cid+'-body');
  const chev  = document.getElementById(cid+'-chev');
  if(!body) return;
  const open  = body.style.maxHeight !== '0px' && body.style.maxHeight !== '0';
  body.style.maxHeight = open ? '0'     : '600px';
  body.style.padding   = open ? '0 13px': '10px 13px';
  if(chev) chev.style.transform = open ? 'rotate(0deg)' : 'rotate(180deg)';
}

// Overview tab: price strip, metrics chips, position, insights,
// implied growth, concall signal card, collapsible guidance cards
function renderOverview(s){
  const sym = s.symbol;
  const g   = GUIDANCE[sym];
  const ins = g?.insights;
  const f   = FUND[sym]||{};
  const ltp = s.ltp||0;

  // ── helpers ──────────────────────────────────────────────────
  function pill(txt, col){ return `<span style="display:inline-flex;align-items:center;font-size:8px;font-weight:700;padding:2px 8px;border-radius:20px;letter-spacing:.3px;background:${col}18;color:${col};border:1px solid ${col}40">${txt}</span>`; }
  function krow(label, val, col){
    const empty = !val||val==='Not mentioned'||val==='—';
    return `<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.05)">
      <span style="font-size:11px;color:var(--tx3);flex-shrink:0;padding-top:1px;min-width:90px">${label}</span>
      <span style="font-size:11px;font-weight:${empty?'400':'600'};color:${empty?'var(--mu)':(col||'var(--tx1)')};text-align:right;line-height:1.45">${empty?'—':val}</span>
    </div>`;
  }
  function blist(arr, col){
    if(!arr||!arr.length) return '';
    const items = Array.isArray(arr) ? arr : arr.split(/[;,]|\d[.)]\s*/).map(x=>x.trim()).filter(x=>x.length>4);
    return items.map(x=>`<div style="display:flex;gap:8px;padding:5px 0"><span style="color:${col};flex-shrink:0;margin-top:2px;font-size:12px">›</span><span style="font-size:12px;color:var(--tx2);line-height:1.5">${x}</span></div>`).join('');
  }
    function gv(k){ return g ? (g[k]||g[k.replace(/_/g,' ')]||null) : null; }

  // [F] badge — data from fundamentals.json, not concall
  const FB = `<span style="font-size:8px;font-weight:700;padding:1px 5px;border-radius:3px;background:rgba(33,150,243,.15);color:#64b5f6;border:1px solid rgba(33,150,243,.3);margin-left:4px;vertical-align:middle">[F]</span>`;

  // krowF — show concall value first, fall back to FUND value with [F] badge
  function krowF(label, concallVal, fundVal, fundLabel, col){
    if(concallVal && concallVal!=='Not mentioned'){
      return krow(label, concallVal, col);
    } else if(fundVal!=null && fundVal!==''){
      const display = fundLabel ? fundLabel : String(fundVal);
      return krow(label, display+' ${FB}', col||'var(--tx2)');
    }
    return krow(label, null, col); // shows —
  }

  // Web search link — shown when both concall and FUND missing
  function wsLink(label, query){
    const url = 'https://www.google.com/search?q='+encodeURIComponent(query);
    return `<div style="display:flex;justify-content:space-between;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid rgba(255,255,255,.05)">
      <span style="font-size:11px;color:var(--tx3);flex-shrink:0;min-width:90px">${label}</span>
      <a href="${url}" target="_blank" rel="noopener"
        style="font-size:9px;font-weight:700;padding:2px 8px;border-radius:4px;background:rgba(100,181,246,.08);border:1px solid rgba(100,181,246,.2);color:#64b5f6;text-decoration:none;white-space:nowrap">🔍 Search</a>
    </div>`;
  }

  // ── 1. PRICE HEADER STRIP ─────────────────────────────────────
  const candles = s.candles||[];
  const hi  = candles.length ? Math.max(...candles.map(c=>c.h)) : ltp;
  const lo  = candles.length ? Math.min(...candles.map(c=>c.l)) : ltp;
  const vol = candles.length ? candles.reduce((a,c)=>a+c.v,0).toFixed(1) : '—';
  const chgCol = (s.change||0)>=0 ? '#00e896' : '#ff6b85';

  const priceStrip = `
    <div style="background:var(--s1);border-bottom:1px solid var(--b1);padding:10px 13px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start">
        <div>
          <div style="font-size:24px;font-weight:800;color:var(--tx1);font-family:'JetBrains Mono',monospace;line-height:1">₹${fmt(ltp)}</div>
          <div style="font-size:11px;font-weight:700;color:${chgCol};margin-top:3px">${(s.change||0)>=0?'▲':'▼'} ${Math.abs(s.change||0).toFixed(2)}%</div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 14px;text-align:right">
          ${[['Open',fmt(candles[0]?.o||ltp)],['High',fmt(hi)],['Low',fmt(lo)],['Vol',vol+'L']].map(([l,v])=>`
            <div><div style="font-size:7px;color:var(--tx3);text-transform:uppercase;letter-spacing:.4px">${l}</div>
            <div style="font-size:10px;font-weight:600;color:var(--tx2);font-family:var(--mono)">${v}</div></div>`).join('')}
        </div>
      </div>
      ${s.week52H&&s.week52L&&ltp?`
      <div style="margin-top:10px">
        <div style="display:flex;justify-content:space-between;font-size:7px;color:var(--tx3);margin-bottom:4px;text-transform:uppercase;letter-spacing:.4px">
          <span>52W Low ₹${fmt(s.week52L)}</span>
          <span style="color:var(--bl2)">${((ltp-s.week52L)/(s.week52H-s.week52L)*100).toFixed(0)}th percentile</span>
          <span>52W High ₹${fmt(s.week52H)}</span>
        </div>
        <div style="position:relative;height:4px;background:var(--b2);border-radius:2px">
          <div style="position:absolute;top:50%;left:${Math.min(95,Math.max(5,(ltp-s.week52L)/(s.week52H-s.week52L)*100)).toFixed(1)}%;transform:translate(-50%,-50%);width:10px;height:10px;border-radius:50%;background:var(--bl);border:2px solid var(--bg)"></div>
        </div>
      </div>`:''}
    </div>`;

  // ── 2. KEY METRICS ROW (scrollable chips) ─────────────────────
  const metrics = [
    {l:'P/E', v:s.pe?s.pe+'x':null, good:s.pe&&s.pe<18, bad:s.pe&&s.pe>35},
    {l:'P/B', v:s.pb?s.pb+'x':null, good:s.pb&&s.pb<2,  bad:s.pb&&s.pb>5},
    {l:'ROE', v:s.roe?s.roe+'%':null, good:s.roe&&s.roe>15, bad:s.roe&&s.roe<8},
    {l:'ROCE',v:s.roce?s.roce+'%':null, good:s.roce&&s.roce>20, bad:s.roce&&s.roce<10},
    {l:'D/E', v:s.debtEq!=null?s.debtEq+'x':null, good:s.debtEq!=null&&s.debtEq<0.5, bad:s.debtEq!=null&&s.debtEq>1.5},
    {l:'Div', v:s.divYield?s.divYield+'%':null},
    {l:'Prom',v:s.promoter?s.promoter+'%':null, good:s.promoter&&s.promoter>50},
    {l:'Beta',v:s.beta||null, good:s.beta&&s.beta<1, bad:s.beta&&s.beta>1.5},
    {l:'EPS', v:s.eps?'₹'+fmt(s.eps):null},
  ].filter(m=>m.v);

  const metricsRow = metrics.length ? `
    <div style="overflow-x:auto;display:flex;gap:6px;padding:8px 13px;scrollbar-width:none;border-bottom:1px solid var(--b1)">
      ${metrics.map(m=>`
        <div style="flex-shrink:0;background:var(--card);border:1px solid var(--b1);border-radius:8px;padding:8px 11px;text-align:center;min-width:52px;border-top:2px solid ${m.good?'#00d084':m.bad?'#ff3b5c':'var(--b2)'}">
          <div style="font-size:10px;color:var(--tx3);text-transform:uppercase;letter-spacing:.3px;margin-bottom:4px">${m.l}</div>
          <div style="font-size:13px;font-weight:700;color:${m.good?'#00e896':m.bad?'#ff6b85':'var(--tx1)'};font-family:var(--mono)">${m.v}</div>
        </div>`).join('')}
    </div>` : '';

  // ── 3. MY POSITION (if held) ──────────────────────────────────
  const posCard = S.selStock?.qty&&s.avgBuy ? (()=>{
    const pnl    = s.qty*(ltp-s.avgBuy);
    const pnlPct = ((ltp-s.avgBuy)/s.avgBuy*100).toFixed(2);
    const up     = pnl>=0;
    return `<div style="margin:8px 12px;padding:10px 13px;background:var(--card);border-radius:10px;border:1px solid var(--b1);border-left:3px solid ${up?'#00d084':'#ff3b5c'}">
      <div style="font-size:8px;font-weight:700;color:var(--label);text-transform:uppercase;letter-spacing:.6px;margin-bottom:7px">My Position</div>
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px">
        ${[['Qty',s.qty],['Avg Buy','₹'+fmt(s.avgBuy)],['P&L',(up?'+':'')+pnlPct+'%'],['Value','₹'+fmt(s.qty*ltp)]].map(([l,v],i)=>`
          <div><div style="font-size:7px;color:var(--tx3);margin-bottom:2px">${l}</div>
          <div style="font-size:10px;font-weight:700;color:${i===2?(up?'#00e896':'#ff6b85'):'var(--tx1)'};font-family:var(--mono)">${v}</div></div>`).join('')}
      </div>
    </div>`;
  })() : '';

  // ── 4. AI INSIGHTS STRIP ──────────────────────────────────────
  const insStrip = ins ? `
    <div style="margin:0 12px 0;padding:10px 13px;background:rgba(249,115,22,.07);border:1px solid rgba(249,115,22,.2);border-radius:10px;cursor:pointer" onclick="setDrillTab('insights')">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:8px">
        <div style="display:flex;align-items:baseline;gap:6px;flex:1;min-width:0">
          <span style="font-size:11px;font-weight:800;color:var(--ac);flex-shrink:0">💡 Portfolio Signal</span>
          <span style="font-size:11px;color:var(--tx2);line-height:1.45;font-style:italic;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">"${ins.headline||ins.bullets?.[0]||''}"</span>
        </div>
        <span style="font-size:11px;font-weight:700;color:var(--ac);flex-shrink:0">→</span>
      </div>
      ${ins.action?`<div style="margin-top:6px;font-size:9px;font-weight:700;color:${ins.action.match(/BUY/i)?'#00e896':ins.action.match(/REDUCE|EXIT/i)?'#ff6b85':'#ffbf47'}">${ins.action.split('—')[0].trim()}</div>`:''}
    </div>` : `
    <div style="margin:0 12px 0;padding:10px 13px;background:rgba(249,115,22,.03);border:1px dashed rgba(249,115,22,.15);border-radius:10px;cursor:pointer;text-align:center" onclick="setDrillTab('insights')">
      <span style="font-size:12px;color:var(--tx3)">💡 No Portfolio Signal — tap to generate</span>
    </div>`;

  // ── 5. GUIDANCE SECTION (only if g exists) ────────────────────
  if(!g) return `<div>${priceStrip}${metricsRow}${posCard}
    <div style="margin:10px 12px 0">${insStrip}</div>
    <div style="margin:10px 12px;padding:16px;background:var(--card);border-radius:10px;border:1px solid var(--b1);text-align:center">
      <div style="font-size:28px;margin-bottom:8px">📋</div>
      <div style="font-size:12px;font-weight:700;color:var(--tx1);margin-bottom:5px">No analysis yet</div>
      <div style="font-size:9px;color:var(--tx3);margin-bottom:12px;line-height:1.5">Go to Analysis tab → select ${sym} → copy prompt → paste Claude's response</div>
      <button onclick="showTab('analysis',document.querySelector('.nb:last-child'))"
        style="background:var(--ac);color:#fff;border:none;border-radius:8px;padding:9px 20px;font-size:11px;font-weight:700;cursor:pointer">
        Open Analysis Tab
      </button>
    </div>
  </div>`;

  // ── g exists — build full overview ────────────────────────────
  const actionVal  = g.action_signal||g['action signal']||'';
  const actionType = actionVal.match(/BUY MORE/i)?'BUY MORE':actionVal.match(/\bBUY\b/i)?'BUY':actionVal.match(/REDUCE/i)?'REDUCE':actionVal.match(/EXIT/i)?'EXIT':'HOLD';
  const actionCol  = ['BUY MORE','BUY'].includes(actionType)?'#00e896':['REDUCE','EXIT'].includes(actionType)?'#ff6b85':'#ffbf47';
  const actionReason = actionVal.replace(/BUY MORE|BUY|REDUCE|EXIT|HOLD/gi,'').replace(/^[\s\-–:]+/,'').trim();
  const verdict    = g.one_line_verdict||g['one line verdict']||g.summary||'';
  const tone       = g.tone||'Neutral';
  const toneCol    = tone==='Positive'?'#00e896':tone==='Negative'?'#ff6b85':'#ffbf47';
  const conf       = g.confidence||g.confidence_level||'Medium';
  const confCol    = conf==='High'?'#00e896':conf==='Low'?'#ff6b85':'#ffbf47';
  const updated    = g.updated ? new Date(g.updated).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'}) : '';

  // Implied growth
  let igBadge = '';
  if(f.pe>0&&f.fwd_pe>0){
    const ig = +((f.pe/f.fwd_pe-1)*100).toFixed(1);
    igBadge = `<div style="margin:8px 12px 0;padding:9px 12px;background:rgba(${ig>=0?'0,232,150':'255,107,133'},.06);border:1px solid rgba(${ig>=0?'0,232,150':'255,107,133'},.2);border-radius:8px;display:flex;justify-content:space-between;align-items:center">
      <div><div style="font-size:7px;color:var(--tx3);text-transform:uppercase;letter-spacing:.5px">Implied Earnings Growth</div>
      <div style="font-size:18px;font-weight:800;color:${ig>=0?'#00e896':'#ff6b85'};font-family:var(--mono);margin-top:2px">${ig>=0?'+':''}${ig}%</div></div>
      <div style="text-align:right">
        <div style="font-size:8px;color:var(--tx3)">Trailing</div><div style="font-size:11px;font-weight:700;color:var(--tx2);font-family:var(--mono)">${f.pe.toFixed(1)}x</div>
        <div style="font-size:8px;color:var(--tx3);margin-top:3px">Forward</div><div style="font-size:11px;font-weight:700;color:var(--tx2);font-family:var(--mono)">${f.fwd_pe.toFixed(1)}x</div>
      </div>
    </div>`;
  }

  // ── CARD: Action Signal ────────────────────────────────────────
  const signalCard = `
    <div style="margin:10px 12px 0;border-radius:12px;overflow:hidden;border:1px solid ${actionCol}35">
      <div style="padding:12px 14px;background:${actionCol}12">
        <!-- Row 1: label + date -->
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
          <span style="font-size:10px;font-weight:700;color:var(--tx3);text-transform:uppercase;letter-spacing:.8px">📋 Concall Signal</span>
          <span style="font-size:10px;color:var(--tx3)">${updated}</span>
        </div>
        <!-- Row 2: action word + conf pill same line, tone separate -->
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <span style="font-size:16px;font-weight:900;color:${actionCol};font-family:'Syne',sans-serif;letter-spacing:.5px">${actionType}</span>
          ${pill(conf,confCol)}
          ${pill(tone,toneCol)}
        </div>
        <!-- Row 3: reason -->
        ${actionReason?`<div style="font-size:9px;color:${actionCol};opacity:.85;margin-top:5px;line-height:1.45">${actionReason}</div>`:''}
        <!-- Row 4: verdict quote — no italics -->
        ${verdict?`<div style="margin-top:8px;padding:9px 11px;background:rgba(0,0,0,.2);border-radius:8px;font-size:12px;color:var(--tx1);line-height:1.55">"${verdict}"</div>`:''}
      </div>
    </div>`;

  // ── CARDS: Collapsible sections ───────────────────────────────
  const cardId = id => 'ov-'+sym+'-'+id;
  function colCard(id, icon, title, col, isOpen, bodyHtml){
    if(!bodyHtml||!bodyHtml.trim()) return '';
    const cid = cardId(id);
    return `<div style="margin:6px 12px 0;border-radius:10px;overflow:hidden;border:1px solid var(--b1)">
      <div onclick="toggleOvCard('${cid}')" style="display:flex;justify-content:space-between;align-items:center;padding:10px 13px;background:var(--card);cursor:pointer;-webkit-tap-highlight-color:transparent">
        <div style="display:flex;align-items:center;gap:7px">
          <span style="font-size:13px">${icon}</span>
          <span style="font-size:12px;font-weight:700;color:var(--tx1)">${title}</span>
          <div style="width:6px;height:6px;border-radius:50%;background:${col};flex-shrink:0"></div>
        </div>
        <span id="${cid}-chev" style="font-size:9px;color:var(--tx3);display:inline-block;transform:${isOpen?'rotate(180deg)':'rotate(0deg)'};transition:transform .2s">▼</span>
      </div>
      <div id="${cid}-body" style="background:var(--s2);padding:${isOpen?'10px 13px':'0 13px'};max-height:${isOpen?'800px':'0'};overflow:hidden;transition:max-height .28s ease,padding .2s ease">
        ${bodyHtml}
      </div>
    </div>`;
  }

  // Forward Guidance body
  const guidBody = [
    krow('Revenue Target',  gv('revenue_guidance')),
    krow('Growth Guided',   gv('revenue_growth_target')||gv('growth_target')),
    krowF('EBITDA Margin',  gv('ebitda_margin_target')||gv('margin_guidance'), f.opm_pct!=null?f.opm_pct.toFixed(1)+'%':null, null),
    krowF('PAT Margin',     gv('pat_margin_target'), f.npm_pct!=null?f.npm_pct.toFixed(1)+'%':null, null),
    krowF('EPS Estimate',   gv('eps_estimate')||gv('analyst_eps_estimate'), f.eps?'₹'+f.eps.toFixed(1)+' (TTM)':null, null),
    krow('Order Book',      gv('order_book')),
    krow('Pipeline',        gv('pipeline')),
    krow('Deal Wins',       gv('deal_wins')),
  ].join('');

  // Geography body — chips
  const geoRawKey = Object.keys(g).find(k=>k.includes('geographic'));
  const geoRaw    = geoRawKey ? g[geoRawKey] : null;
  let geoBody = '';
  if(!geoRaw||geoRaw==='Not mentioned'){
    geoBody = `<div style="font-size:11px;color:var(--mu);padding:4px 0">— Not mentioned in concall</div>`;
  } else {
    const parts = geoRaw.split(/[;,]/).map(x=>x.trim()).filter(x=>x.length>1);
    const palG  = ['#64b5f6','#4dd0e1','#80cbc4','#81d4fa','#b39ddb','#ef9a9a'];
    geoBody = `<div style="display:flex;flex-wrap:wrap;gap:6px;padding:2px 0">`
      + parts.map((p,i)=>{
          const m   = p.match(/([\d.]+)%/);
          const pct = m?+m[1]:null;
          const loc = p.replace(/[\d.]+%/,'').replace(/[:\-]/g,'').trim();
          const col = palG[i%palG.length];
          return `<div style="background:${col}10;border:1px solid ${col}30;border-radius:8px;padding:6px 10px;text-align:center;min-width:52px">`
            +`<div style="font-size:8px;color:${col};font-weight:700;margin-bottom:1px">${loc}</div>`
            +(pct?`<div style="font-size:12px;font-weight:800;color:var(--tx1);font-family:var(--mono)">${pct}%</div>`:'')+`</div>`;
        }).join('')+'</div>';
  }

  // Products body — bar rows
  const kpRawKey = Object.keys(g).find(k=>k.includes('key_product')||k.includes('product_mix')||k.includes('products_portfolio'));
  const kpRaw    = (kpRawKey?g[kpRawKey]:null)||gv('segment_growth')||gv('key_segments');
  let prodBody = '';
  if(!kpRaw||kpRaw==='Not mentioned'){
    prodBody = `<div style="font-size:11px;color:var(--mu);padding:4px 0">— Not mentioned in concall</div>`;
  } else {
    const parts = kpRaw.split(/[;,]/).map(x=>x.trim()).filter(x=>x.length>2);
    const palP  = ['#f59e0b','#22d3ee','#4ade80','#fb923c','#a78bfa','#f472b6'];
    prodBody = `<div style="display:flex;flex-direction:column;gap:7px;padding:2px 0">`
      + parts.map((p,i)=>{
          const m   = p.match(/([\d.]+)%/);
          const pct = m?+m[1]:null;
          const nm  = p.replace(/[\d.]+%/,'').replace(/[:\-]/g,'').trim();
          const col = palP[i%palP.length];
          return `<div style="display:flex;align-items:center;gap:8px">`
            +`<div style="width:100px;font-size:9px;color:var(--tx2);text-align:right;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${nm}</div>`
            +(pct
              ?`<div style="flex:1;background:var(--b1);border-radius:3px;height:14px;position:relative;overflow:hidden"><div style="position:absolute;left:0;top:0;height:100%;width:${Math.min(100,pct)}%;background:${col};opacity:.7;border-radius:3px"></div></div><div style="font-size:9px;font-weight:700;color:${col};width:32px;text-align:right;flex-shrink:0">${pct}%</div>`
              :`<div style="flex:1;font-size:9px;color:var(--tx2);line-height:1.4">${p}</div>`)
            +'</div>';
        }).join('')+'</div>';
  }

  // Business & Capital body
  const _name = f.name||sym;
  const bizBody = [
    gv('market_share')
      ? krow('Market Share', gv('market_share'))
      : wsLink('Market Share', _name+' market share 2025'),
    krow('New Products',    gv('new_products')),
    gv('capex_plan')
      ? krow('Capex Plan', gv('capex_plan'))
      : wsLink('Capex Plan', _name+' capex plan FY26'),
    krow('Debt Reduction',  gv('debt_reduction_plan')),
    krowF('Dividend',       gv('dividend_guidance'), f.div_yield?f.div_yield.toFixed(2)+'%':null, null),
    krow('M&A / JV',        gv('acquisitions')),
    gv('raw_material_outlook')
      ? krow('Raw Materials', gv('raw_material_outlook'))
      : wsLink('Raw Materials', _name+' raw material cost outlook 2025'),
    gv('headcount_plans')
      ? krow('Headcount', gv('headcount_plans'))
      : wsLink('Headcount', _name+' employee headcount 2025'),
    gv('working_capital')
      ? krow('Working Capital', gv('working_capital'))
      : wsLink('Working Capital', _name+' working capital days FY26'),
    krowF('Sales TTM',      null, f.sales?(f.sales/100).toFixed(0)+'Cr':null, null),
    krowF('CFO TTM',        null, f.cfo?(f.cfo/100).toFixed(0)+'Cr':null, null),
  ].join('');

  // Management & Analyst body
  const mgmtBody = [
    krow('Tone',          tone, toneCol),
    krow('Credibility',   gv('management_credibility'), (gv('management_credibility')||'').match(/Yes/i)?'#00e896':(gv('management_credibility')||'').match(/No/i)?'#ff6b85':'#ffbf47'),
    gv('analyst_consensus')||gv('analyst_rating')
      ? krow('Consensus', gv('analyst_consensus')||gv('analyst_rating'), '#64b5f6')
      : wsLink('Consensus', _name+' analyst consensus rating 2025'),
    gv('price_target')||gv('analyst_price_target')
      ? krow('Price Target', gv('price_target')||gv('analyst_price_target'), '#64b5f6')
      : wsLink('Price Target', _name+' analyst price target 2025'),
    krow('Currency Risk', gv('currency_exposure')),
    krow('Regulatory',    gv('regulatory_impact')),
  ].join('');

  // Commitments & Risks body
  const commitArr = g.specific_commitments||g['specific commitments']||g.key_commitments||[];
  const risksArr  = g.key_risks||g['key risks']||g.risks_flagged||[];
  const riskBody  =
    `<div style="margin-bottom:10px">
      <div style="font-size:10px;font-weight:700;color:#00e896;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px">Commitments</div>
      ${commitArr.length ? blist(commitArr,'#00e896') : '<div style="font-size:11px;color:var(--mu)">— Not mentioned in concall</div>'}
    </div>`
  + `<div>
      <div style="font-size:10px;font-weight:700;color:#ff6b85;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px">Key Risks</div>
      ${risksArr.length ? blist(risksArr,'#ff6b85') : '<div style="font-size:11px;color:var(--mu)">— Not mentioned in concall</div>'}
    </div>`;

  return `<div style="padding-bottom:16px">
    ${priceStrip}
    ${metricsRow}
    ${posCard}
    <div style="padding:8px 12px 0;display:flex;flex-direction:column;gap:0">
      ${insStrip}
      ${igBadge}
      ${signalCard}
      ${colCard('guid', '📈', 'Forward Guidance',    '#64b5f6', false, guidBody)}
      ${colCard('geo',  '🌍', 'Geographic Mix',      '#4dd0e1', false, geoBody)}
      ${colCard('prod', '📦', 'Products & Segments', '#f59e0b', false, prodBody)}
      ${colCard('biz',  '⚙️', 'Business & Capital',  '#a78bfa', false, bizBody)}
      ${colCard('mgmt', '👔', 'Management & Analyst','#8eb0d0', false, mgmtBody)}
      ${colCard('risk', '⚠️', 'Commitments & Risks', '#ff6b85', false, riskBody)}
    </div>
  </div>`;
}

//  FIX #6: PROPER CANDLESTICK CHART
// Technical tab: candlestick chart + MA overlays + signal table
function renderTechnical(s){
  const signals=[
    {n:'RSI (14)',v:s.rsi,sub:'Value: '+s.rsi,sig:s.rsi>70?'Overbought':s.rsi<30?'Oversold':'Neutral',sc:s.rsi>70?'sig-sell':s.rsi<30?'sig-buy':'sig-neutral'},
    {n:'MACD',v:s.macd?.toFixed(1)||'—',sub:'Signal: '+(s.macdSignal?.toFixed(1)||'—'),sig:s.macd>s.macdSignal?'Bullish':'Bearish',sc:s.macd>s.macdSignal?'sig-buy':'sig-sell'},
    {n:'Stoch %K',v:s.stochK||'—',sub:'%D: '+(s.stochD||'—'),sig:s.stochK>80?'Overbought':s.stochK<20?'Oversold':'Neutral',sc:s.stochK>80?'sig-sell':s.stochK<20?'sig-buy':'sig-neutral'},
    {n:'ADX',v:s.adx||'—',sub:s.adx>25?'Strong trend':'Ranging',sig:s.adx>25?'Trending':'No Trend',sc:s.adx>25?'sig-buy':'sig-neutral'},
    {n:'SMA 20',v:'₹'+fmt(s.sma20),sub:s.ltp>s.sma20?'Above':'Below',sig:s.ltp>s.sma20?'Bullish':'Bearish',sc:s.ltp>s.sma20?'sig-buy':'sig-sell'},
    {n:'SMA 50',v:'₹'+fmt(s.sma50),sub:s.ltp>s.sma50?'Above':'Below',sig:s.ltp>s.sma50?'Bullish':'Bearish',sc:s.ltp>s.sma50?'sig-buy':'sig-sell'},
    {n:'EMA 200',v:'₹'+fmt(s.ema200),sub:s.ltp>s.ema200?'Above':'Below',sig:s.ltp>s.ema200?'Bull LT':'Bear LT',sc:s.ltp>s.ema200?'sig-buy':'sig-sell'},
  ];
  const buys=signals.filter(x=>x.sc==='sig-buy').length;
  const sells=signals.filter(x=>x.sc==='sig-sell').length;
  const verdict=buys>=5?'Strong Buy':buys>=4?'Buy':buys>=3?'Weak Buy':sells>=4?'Strong Sell':sells>=3?'Sell':'Neutral';
  const vc=verdict.includes('Buy')?'var(--gr2)':verdict.includes('Sell')?'var(--rd2)':'var(--yw2)';
  const vbg=verdict.includes('Buy')?'rgba(0,208,132,.1)':verdict.includes('Sell')?'rgba(255,59,92,.1)':'rgba(245,166,35,.1)';

  return `<div>
    <!-- Chart controls -->
    <div style="padding:6px 10px;background:var(--s2);border-bottom:1px solid var(--b1);display:flex;justify-content:space-between;align-items:center;gap:8px">
      <div style="font-family:var(--mono);font-size:11px;color:var(--tx2);white-space:nowrap">${s.symbol} · Price Chart</div>
      <div style="display:flex;gap:6px;align-items:center">
        <!-- Interval dropdown -->
        <select onchange="setChartInterval(this.value)" style="background:var(--s1);color:var(--tx1);border:1px solid var(--b1);border-radius:6px;padding:4px 6px;font-size:11px;font-family:var(--mono);cursor:pointer;outline:none">
          <option value="D" ${S.chartInterval==='D'?'selected':''}>Daily</option>
          <option value="W" ${S.chartInterval==='W'?'selected':''}>Weekly</option>
          <option value="M" ${S.chartInterval==='M'?'selected':''}>Monthly</option>
        </select>
        <!-- Range dropdown -->
        <select onchange="setChartRange(this.value)" style="background:var(--s1);color:var(--tx1);border:1px solid var(--b1);border-radius:6px;padding:4px 6px;font-size:11px;font-family:var(--mono);cursor:pointer;outline:none">
          <option value="1M" ${S.chartRange==='1M'?'selected':''}>1 Month</option>
          <option value="3M" ${S.chartRange==='3M'?'selected':''}>3 Months</option>
          <option value="6M" ${S.chartRange==='6M'?'selected':''}>6 Months</option>
          <option value="1Y" ${S.chartRange==='1Y'?'selected':''}>1 Year</option>
          <option value="5Y" ${S.chartRange==='5Y'?'selected':''}>5 Years</option>
        </select>
      </div>
    </div>

    <!-- Unified overlay bar: MAs + KPIs as checkboxes -->
    <div style="padding:5px 10px;background:var(--s2);border-bottom:1px solid var(--b1);display:flex;flex-wrap:wrap;gap:8px;align-items:center">
      <!-- MA overlays -->
      ${[
        {k:'sma20', label:'SMA20',  col:'#f59e0b', type:'ma'},
        {k:'sma50', label:'SMA50',  col:'#3b82f6', type:'ma'},
        {k:'ema200',label:'EMA200', col:'#a855f7', type:'ma'},
        {k:'vol',   label:'Volume', col:'#22c55e', type:'ma'},
      ].map(({k,label,col,type})=>`
        <label style="display:flex;align-items:center;gap:3px;cursor:pointer">
          <input type="checkbox" ${S.maVis[k]?'checked':''}
            onchange="toggleMA('${k}')"
            style="accent-color:${col};width:11px;height:11px;cursor:pointer">
          <span style="font-size:9px;color:${col};font-weight:600">${label}</span>
        </label>`).join('')}
      <span style="width:1px;height:14px;background:var(--b1);margin:0 2px"></span>
      <!-- KPI overlays -->
      ${[
        {k:'pe',  label:'P/E',    col:'#fbbf24', avail:!!(s.pe)},
        {k:'rev', label:'Revenue',col:'#22d3ee', avail:!!(s.sales||(s.quarterly&&s.quarterly.some(q=>q.rev)))},
        {k:'net', label:'Net',    col:'#4ade80', avail:!!(s.npm_pct||(s.quarterly&&s.quarterly.some(q=>q.net)))},
        {k:'cfo', label:'CFO',    col:'#34d399', avail:!!(s.cfo||(s.quarterly&&s.quarterly.some(q=>q.cfo)))},
        {k:'opm', label:'OPM%',   col:'#fb923c', avail:!!(s.opm_pct||(s.quarterly&&s.quarterly.some(q=>q.opm)))},
        {k:'debt',label:'Debt',   col:'#f87171', avail:!!(s.debt_eq||(s.quarterly&&s.quarterly.some(q=>q.debt)))},
      ].map(({k,label,col,avail})=>`
        <label style="display:flex;align-items:center;gap:3px;cursor:pointer;opacity:${avail?1:0.4}" title="${avail?'':'Run Actions to fetch quarterly data'}">
          <input type="checkbox" ${S.kpiVis[k]?'checked':''} ${avail?'':'disabled'}
            onchange="toggleKPI('${k}')"
            style="accent-color:${col};width:11px;height:11px;cursor:pointer">
          <span style="font-size:9px;color:${col};font-weight:600">${label}</span>
        </label>`).join('')}
    </div>

    <!-- MAIN CANDLESTICK CANVAS — KPI overlays drawn here -->
    <div style="position:relative;background:var(--s1);border-bottom:1px solid var(--b1)">
      <div id="chart-wrap" style="position:relative;width:100%;height:240px">
        <canvas id="cv-candle" style="position:absolute;top:0;left:0;width:100%;height:100%"></canvas>
      </div>
      <!-- Volume: bars + optional line trend -->
      ${S.maVis.vol?`<div id="vol-wrap" style="position:relative;width:100%;height:50px;border-top:1px solid var(--b1)">
        <canvas id="cv-vol" style="position:absolute;top:0;left:0;width:100%;height:100%"></canvas>
      </div>`:''}
    </div>

    <div class="chart-stats" style="border-top:1px solid var(--b1);background:var(--s2)">
      <div class="cstat"><div class="cstat-l">Return</div><div class="cstat-v" id="cstat-ret">—</div></div>
      <div class="cstat"><div class="cstat-l">Period High</div><div class="cstat-v" id="cstat-hi">—</div></div>
      <div class="cstat"><div class="cstat-l">Period Low</div><div class="cstat-v" id="cstat-lo">—</div></div>
      <div class="cstat"><div class="cstat-l">Volatility</div><div class="cstat-v" id="cstat-vol">—</div></div>

    </div>

    <!-- Verdict -->
    <div style="margin:10px 12px;padding:14px;border-radius:10px;text-align:center;border:1px solid ${vc}30;background:${vbg}">
      <div style="font-size:9px;font-weight:700;color:var(--label);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Composite Signal</div>
      <div style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;color:${vc}">${verdict}</div>
      <div style="height:5px;background:var(--b1);border-radius:3px;overflow:hidden;margin:8px 0 4px">
        <div style="height:100%;width:${(buys/signals.length*100).toFixed(0)}%;background:${vc};border-radius:3px"></div>
      </div>
      <div style="display:flex;justify-content:space-between;font-size:8px;color:var(--tx3)">
        <span>${buys} Bullish</span><span>${sells} Bearish</span>
      </div>
    </div>

    <!-- Signal rows -->
    <div style="padding:0 12px 14px">
      <div class="sec-lbl">Technical Indicators</div>
      ${signals.map(sg=>`
        <div class="sig-row">
          <div>
            <div class="sig-name">${sg.n}</div>
            <div class="sig-sub">${sg.sub}</div>
          </div>
          <div style="display:flex;align-items:center;gap:8px">
            <span class="sig-pill ${sg.sc}">${sg.sig}</span>
            <span class="sig-val">${sg.v}</span>
          </div>
        </div>`).join('')}

      <!-- S&R levels -->
      <div style="margin-top:10px"><div class="sec-lbl">Support & Resistance</div></div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px">
        ${[
          {l:'Resistance 2',v:s.resist1?fmt(s.resist1*(1.03)):fmt((s.ltp||100)*1.06),c:'var(--rd2)'},
          {l:'Resistance 1',v:s.resist1?fmt(s.resist1):fmt((s.ltp||100)*1.03),c:'var(--rd)'},
          {l:'Support 1',v:s.support1?fmt(s.support1):fmt((s.ltp||100)*0.97),c:'var(--gr)'},
          {l:'Support 2',v:s.support1?fmt(s.support1*(0.97)):fmt((s.ltp||100)*0.94),c:'var(--gr2)'},
        ].map(x=>`
          <div style="background:var(--s2);border:1px solid var(--b1);border-left:3px solid ${x.c};border-radius:8px;padding:9px 11px">
            <div style="font-size:8px;font-weight:700;color:var(--label);text-transform:uppercase;letter-spacing:.5px">${x.l}</div>
            <div style="font-family:var(--mono);font-size:14px;font-weight:700;color:${x.c};margin-top:3px">₹${x.v}</div>
          </div>`).join('')}
      </div>
    </div>
  </div>`;
}

function setChartRange(r){
  S.chartRange=r;
  if(S.drillTab==='technical') scheduleChartRedraw();
}
function setChartInterval(iv){
  S.chartInterval=iv;
  if(S.drillTab==='technical') scheduleChartRedraw();
}
function toggleMA(key){
  S.maVis[key]=!S.maVis[key];
  if(S.drillTab==='technical'){
    // vol toggle needs HTML re-render (shows/hides vol canvas)
    if(key==='vol'){
      const dc=document.getElementById('dc');
      if(dc){ dc.innerHTML=renderDC(S.selStock); }
    }
    scheduleChartRedraw();
  }
}
function toggleKPI(k){
  S.kpiVis[k]=!S.kpiVis[k];
  if(S.drillTab==='technical') scheduleChartRedraw();
}
// Redraw canvases without destroying HTML structure
function scheduleChartRedraw(){
  // Data already in chartCache after first load — just redraw
  if(S.selStock && chartCache[S.selStock.symbol]){
    S.selStock.candles = chartCache[S.selStock.symbol];
  }
  requestAnimationFrame(()=>requestAnimationFrame(()=>scheduleTACharts(S.selStock)));
}

// ── Chart Drawing Engine ──────────────────────────────

// Aggregate daily bars → weekly or monthly OHLCV
function aggregateCandles(daily, interval){
  if(interval === 'D' || !daily.length) return daily;

  const buckets = {};
  daily.forEach(c => {
    const d = new Date(c.d);
    let key;
    if(interval === 'W'){
      // Week key = Monday of that week (ISO)
      const day = d.getDay(); // 0=Sun
      const monday = new Date(d);
      monday.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
      key = monday.toISOString().slice(0,10);
    } else {
      // Month key = YYYY-MM
      key = c.d.slice(0,7);
    }
    if(!buckets[key]){
      buckets[key] = { d: key, o: c.o, h: c.h, l: c.l, c: c.c, v: c.v };
    } else {
      const b = buckets[key];
      b.h = Math.max(b.h, c.h);
      b.l = Math.min(b.l, c.l);
      b.c = c.c;       // last close in period
      b.v += c.v;
    }
  });
  return Object.values(buckets).sort((a,b) => a.d.localeCompare(b.d));
}

// Schedule chart redraws after DOM paint (2x rAF for reliable width)
function scheduleTACharts(s){
  requestAnimationFrame(()=>{
    requestAnimationFrame(()=>{
      drawCandlestick(s);
      if(S.maVis.vol) drawVolume(s);
      updateChartStats(s);
    });
  });
}

// Redraw on resize — canvas width changes when panel opens/rotates
let _chartResizeObs = null;
function attachChartResizeObserver(s){
  if(_chartResizeObs) _chartResizeObs.disconnect();
  const wrap = document.getElementById('chart-wrap');
  if(!wrap || !window.ResizeObserver) return;
  _chartResizeObs = new ResizeObserver(()=>{ scheduleTACharts(s); });
  _chartResizeObs.observe(wrap);
}

function getSlicedCandles(s, canvasWidth){
  const daily = s.candles || [];
  if(!daily.length) return daily;

  // Step 1: Aggregate all daily bars to chosen interval
  const allAgg = aggregateCandles(daily, S.chartInterval);
  if(!allAgg.length) return [];

  // Step 2: Filter by date range (calendar-based)
  const now = new Date();
  const rangeMs = {'1M':30,'3M':91,'6M':182,'1Y':365,'5Y':1825}[S.chartRange] || 91;
  const cutoff = new Date(now - rangeMs*864e5).toISOString().slice(0,10);
  let rangeCandles = allAgg.filter(c => c.d >= cutoff);
  if(!rangeCandles.length) rangeCandles = allAgg.slice(-60);

  // Step 3: Fit to canvas — ideal bar width is 6-8px, minimum 4px
  // This drives HOW MANY bars show, not just caps them
  if(canvasWidth && canvasWidth > 0){
    const PAD_L = 6, PAD_R = 52;
    const chartW = canvasWidth - PAD_L - PAD_R;
    const IDEAL_BAR_W = 7;   // px — comfortable readable width
    const MIN_BAR_W  = 4;    // px — absolute minimum before bars become unreadable
    const maxFit = Math.floor(chartW / MIN_BAR_W);
    const idealFit = Math.floor(chartW / IDEAL_BAR_W);

    if(rangeCandles.length > maxFit){
      // Too many bars — take most recent maxFit
      return rangeCandles.slice(-maxFit);
    }
    // If fewer bars than ideal, that's fine — bars just get wider (up to 10px cap in draw)
  }
  return rangeCandles;
}

// Main candlestick chart with MA overlays and KPI overlays
// KPI overlays use a dedicated Y-axis scale separate from price
function drawCandlestick(s){
  const cv=document.getElementById('cv-candle');
  if(!cv)return;
  const wrap=document.getElementById('chart-wrap');
  // offsetWidth gives the rendered pixel width — reliable after DOM paint
  const W2=Math.max(wrap?wrap.offsetWidth:0, cv.offsetWidth, 280);
  const H2=200;
  const dpr=window.devicePixelRatio||1;
  cv.width=W2*dpr; cv.height=H2*dpr;
  cv.style.width=W2+'px'; cv.style.height=H2+'px';
  const ctx=cv.getContext('2d');
  ctx.scale(dpr,dpr);

  const candles=getSlicedCandles(s, W2);
  if(!candles.length){
    ctx.fillStyle='#060c18'; ctx.fillRect(0,0,W2,H2);
    ctx.textAlign='center';
    if(s._noChartData){
      ctx.fillStyle='rgba(245,166,35,.7)'; ctx.font='bold 11px DM Sans';
      ctx.fillText('No chart data for '+s.symbol, W2/2, H2/2-16);
      ctx.fillStyle='rgba(140,176,208,.5)'; ctx.font='10px DM Sans';
      ctx.fillText('Add to watchlist.txt → run GitHub Actions', W2/2, H2/2+4);
      ctx.fillText('(fetch_type: new_symbol)', W2/2, H2/2+20);
    } else {
      ctx.fillStyle='rgba(120,150,180,.4)'; ctx.font='12px DM Sans';
      ctx.fillText('Loading chart data…', W2/2, H2/2);
    }
    return;
  }

  const W=W2,H=H2;
  const PAD={l:6,r:52,t:8,b:22};
  const cW=W-PAD.l-PAD.r, cH=H-PAD.t-PAD.b;
  const n=candles.length;
  const gap=cW/n;
  const bw=Math.max(2,Math.min(14,gap*0.7));

  // Full history + visible date range — used by both MAs and KPI overlays
  const allCandles = s.candles || candles;
  const visFirst = candles.length ? new Date(candles[0].d).getTime() : 0;
  const visLast  = candles.length ? new Date(candles[candles.length-1].d).getTime() : 1;
  const visRange = visLast - visFirst || 1;

  const allPrices=candles.flatMap(c=>[c.h,c.l]);
  if(s.sma20&&S.maVis.sma20)allPrices.push(s.sma20);
  if(s.sma50&&S.maVis.sma50)allPrices.push(s.sma50);
  if(s.ema200&&S.maVis.ema200)allPrices.push(s.ema200);
  const mn=Math.min(...allPrices), mx=Math.max(...allPrices), rng=mx-mn||1;
  const toY=p=>PAD.t+((mx-p)/rng)*cH;
  const barX=i=>PAD.l+i*gap+gap/2;

  // Background
  ctx.fillStyle='#070c18';
  ctx.fillRect(0,0,W,H);

  // Grid lines
  for(let i=0;i<=4;i++){
    const y=PAD.t+(cH/4)*i;
    ctx.strokeStyle='rgba(255,255,255,.04)';ctx.lineWidth=.5;
    ctx.beginPath();ctx.moveTo(PAD.l,y);ctx.lineTo(PAD.l+cW,y);ctx.stroke();
    // Price label
    const price=mx-(mx-mn)*(i/4);
    ctx.fillStyle='rgba(140,176,208,.65)';
    ctx.font='8px JetBrains Mono,monospace';ctx.textAlign='right';
    ctx.fillText('₹'+Math.round(price).toLocaleString('en-IN'),W-2,y+(i===0?9:-2));
  }

  // Right axis separator
  ctx.fillStyle='rgba(7,12,24,.8)';
  ctx.fillRect(W-PAD.r,0,PAD.r,H);
  ctx.strokeStyle='rgba(30,51,80,.8)';ctx.lineWidth=1;
  ctx.beginPath();ctx.moveTo(W-PAD.r,0);ctx.lineTo(W-PAD.r,H);ctx.stroke();

  // Candles
  candles.forEach((c,i)=>{
    const bull=c.c>=c.o;
    const cx=barX(i);
    const bodyTop=toY(Math.max(c.o,c.c));
    const bodyH=Math.max(1,Math.abs(toY(c.o)-toY(c.c)));

    // Wick
    ctx.strokeStyle=bull?'rgba(0,232,150,.8)':'rgba(255,107,133,.8)';
    ctx.lineWidth=1;
    ctx.beginPath();ctx.moveTo(cx,toY(c.h));ctx.lineTo(cx,toY(c.l));ctx.stroke();

    // Body
    ctx.fillStyle=bull?'#00d084':'#ff3b5c';
    if(ctx.roundRect)ctx.roundRect(cx-bw/2,bodyTop,bw,bodyH,1);
    else ctx.rect(cx-bw/2,bodyTop,bw,bodyH);
    ctx.fill();

    if(!bull){ctx.strokeStyle='rgba(255,59,92,.3)';ctx.lineWidth=.5;ctx.stroke();}
  });

  // ── Moving Average curves computed from candle close prices ──
  function calcSMA(arr, period){
    return arr.map((c,i)=>{
      if(i < period-1) return null;
      const sum = arr.slice(i-period+1, i+1).reduce((a,b)=>a+b.c, 0);
      return sum / period;
    });
  }
  function calcEMA(arr, period){
    const k = 2/(period+1);
    const result = new Array(arr.length).fill(null);
    // Find first valid index
    let first = period-1;
    if(first >= arr.length) return result;
    result[first] = arr.slice(0,period).reduce((a,b)=>a+b.c,0)/period;
    for(let i=first+1; i<arr.length; i++){
      result[i] = arr[i].c * k + result[i-1] * (1-k);
    }
    return result;
  }
  function drawMALine(vals, col, dash, label){
    ctx.strokeStyle=col; ctx.lineWidth=1.2; ctx.setLineDash(dash||[]);
    ctx.beginPath();
    let started=false;
    vals.forEach((v,i)=>{
      if(v===null) return;
      const x=barX(i), y=toY(v);
      if(!started){ ctx.moveTo(x,y); started=true; } else ctx.lineTo(x,y);
    });
    ctx.stroke(); ctx.setLineDash([]);
    // Label at last valid point
    const lastIdx = vals.reduce((best,v,i)=>v!==null?i:best, -1);
    if(lastIdx>=0 && label){
      const lv = vals[lastIdx];
      ctx.fillStyle=col; ctx.font='bold 7px JetBrains Mono,monospace'; ctx.textAlign='right';
      ctx.fillText(label+' ₹'+Math.round(lv).toLocaleString('en-IN'), W-2, toY(lv)-3);
    }
  }
  // MAs computed on allCandles (full history), then only visible portion drawn
  // This ensures EMA200 is correct even on short-range views
  if(S.maVis.sma20 || S.maVis.sma50 || S.maVis.ema200){
    const allC = s.candles || candles;
    const sma20vals  = S.maVis.sma20  ? calcSMA(allC, 20)  : null;
    const sma50vals  = S.maVis.sma50  ? calcSMA(allC, 50)  : null;
    const ema200vals = S.maVis.ema200 ? calcEMA(allC, 200) : null;

    // Map allCandles index → visible x position using date
    function maX(allIdx){
      const t = new Date(allC[allIdx].d).getTime();
      return PAD.l + ((t - visFirst) / visRange) * cW;
    }
    function drawMAFull(vals, col, dash, label){
      if(!vals) return;
      ctx.strokeStyle = col; ctx.lineWidth = 1.2; ctx.setLineDash(dash||[]);
      ctx.beginPath();
      let started = false;
      vals.forEach((v,i)=>{
        if(v === null) return;
        const x = maX(i);
        if(x < PAD.l - 2 || x > PAD.l + cW + 2){ started = false; return; } // off-screen
        const y = toY(v);
        if(!started){ ctx.moveTo(x,y); started=true; } else ctx.lineTo(x,y);
      });
      ctx.stroke(); ctx.setLineDash([]);
      // Label at rightmost visible point
      let lastV = null, lastX = 0;
      vals.forEach((v,i)=>{
        if(v===null) return;
        const x = maX(i);
        if(x >= PAD.l && x <= PAD.l+cW){ lastV=v; lastX=x; }
      });
      if(lastV !== null){
        ctx.fillStyle=col; ctx.font='bold 7px JetBrains Mono,monospace'; ctx.textAlign='right';
        ctx.fillText(label+' ₹'+Math.round(lastV).toLocaleString('en-IN'), W-2, toY(lastV)-3);
      }
    }
    drawMAFull(sma20vals,  '#f59e0b', [],    'SMA20');
    drawMAFull(sma50vals,  '#3b82f6', [],    'SMA50');
    drawMAFull(ema200vals, '#a855f7', [4,3], 'EMA200');
  }

  // Current price dashed line
  if(s.ltp){
    const lastY=toY(s.ltp);
    const bull=s.candles?.length&&s.ltp>=(s.candles[0]?.c||s.ltp);
    ctx.strokeStyle=bull?'rgba(0,208,132,.5)':'rgba(255,59,92,.5)';
    ctx.lineWidth=.6;ctx.setLineDash([3,3]);
    ctx.beginPath();ctx.moveTo(PAD.l,lastY);ctx.lineTo(PAD.l+cW,lastY);ctx.stroke();
    ctx.setLineDash([]);
    // Price badge on right axis
    ctx.fillStyle=bull?'#00d084':'#ff3b5c';
    ctx.font='bold 9px JetBrains Mono,monospace';ctx.textAlign='right';
    ctx.fillText('₹'+Math.round(s.ltp).toLocaleString('en-IN'),W-2,Math.max(lastY+4,PAD.t+10));
  }

  // X-axis date labels — use actual candle.d dates, show ~5 evenly spaced
  const maxLabels = Math.min(6, Math.floor(cW / 40));
  const lblStep = Math.max(1, Math.floor(n / maxLabels));
  ctx.fillStyle='rgba(140,176,208,.55)'; ctx.font='7px JetBrains Mono,monospace';
  candles.forEach((c,i)=>{
    if(i % lblStep !== 0 && i !== n-1) return;
    const d = new Date(c.d);
    let lbl;
    if(S.chartInterval==='M')      lbl = (d.getMonth()+1)+'/'+String(d.getFullYear()).slice(2);
    else if(S.chartRange==='5Y'||S.chartRange==='1Y') lbl = (d.getMonth()+1)+'/'+String(d.getFullYear()).slice(2);
    else                            lbl = d.getDate()+'/'+(d.getMonth()+1);
    const x = barX(i);
    if(x > PAD.l+cW-8) return;
    ctx.textAlign = i===0 ? 'left' : (i===n-1 ? 'right' : 'center');
    ctx.fillText(lbl, x, H-4);
  });

  // ── KPI overlays on price chart ──────────────────────────────────
  const quarterly = s.quarterly || [];

  const KPI_DEFS = [
    {k:'pe',   label:'P/E',     col:'#f59e0b'},
    {k:'rev',  label:'Rev',     col:'#22d3ee'},
    {k:'net',  label:'Net',     col:'#4ade80'},
    {k:'cfo',  label:'CFO',     col:'#34d399'},
    {k:'opm',  label:'OPM%',    col:'#fb923c'},
    {k:'debt', label:'Debt',    col:'#f87171'},
  ];

  // Use FULL candle history for price lookups — not just visible slice
  // (allCandles, visFirst, visRange already defined above)

  function xForDate(dateStr){
    const t = new Date(dateStr).getTime();
    return PAD.l + ((t - visFirst) / visRange) * cW;
  }

  // Search FULL history for price on/before a date
  function priceAt(dateStr){
    for(let i=allCandles.length-1; i>=0; i--){
      if(allCandles[i].d <= dateStr) return allCandles[i].c;
    }
    return allCandles.length ? allCandles[0].c : (s.ltp || 0);
  }

  // Log raw quarterly data once
  if(quarterly.length){
        }

  KPI_DEFS.forEach(({k, label, col})=>{
    if(!S.kpiVis[k]) return;

    let pts = [];
    if(k === 'pe'){
      quarterly.forEach(q=>{
        if(!q.eps || q.eps <= 0) return;
        const annEPS = q.eps * 4;
        const price = priceAt(q.d);
        if(price > 0) pts.push({x: xForDate(q.d), v: price/annEPS, d: q.d});
      });
      // Always add current PE at far right
      if(s.pe > 0 && candles.length > 0){
        const rightX = PAD.l + cW;
        if(!pts.length || pts[pts.length-1].x < rightX - 10)
          pts.push({x: rightX, v: s.pe, d: 'now'});
      }
    } else {
      quarterly.forEach(q=>{
        const v = q[k];
        if(v != null) pts.push({x: xForDate(q.d), v, d: q.d});
      });
      // Add current value as rightmost anchor if available
      const curVal = k==='cfo'?s.cfo : k==='rev'?s.sales : k==='net'?s.npm_pct : k==='opm'?s.opm_pct : k==='debt'?s.debt_eq : null;
      if(curVal != null && pts.length){
        pts.push({x: PAD.l + cW, v: curVal, d: 'now'});
      }
    }

      // Keep points that fall within or near visible chart area
    // Extend margin so points just outside edges still connect to line
    pts = pts.filter(p => p.x >= PAD.l - 20 && p.x <= PAD.l + cW + 20);
    // If nothing visible, show all points spread across full width
    if(!pts.length && (quarterly.length || s.pe)){
      const allPts2 = [];
      if(k==='pe'){
        quarterly.forEach(q=>{
          if(!q.eps||q.eps<=0) return;
          const pr = priceAt(q.d);
          if(pr>0) allPts2.push({x:0, v:pr/(q.eps*4), d:q.d});
        });
        if(s.pe>0) allPts2.push({x:0, v:s.pe, d:'now'});
      } else {
        quarterly.forEach(q=>{ const v=q[k]; if(v!=null) allPts2.push({x:0,v,d:q.d}); });
      }
      if(allPts2.length>=2){
        const t0=new Date(allPts2[0].d==='now'?Date.now():allPts2[0].d).getTime();
        const t1=new Date(allPts2[allPts2.length-1].d==='now'?Date.now():allPts2[allPts2.length-1].d).getTime();
        const tr=t1-t0||1;
        allPts2.forEach(p=>{
          const t=new Date(p.d==='now'?Date.now():p.d).getTime();
          p.x = PAD.l + ((t-t0)/tr)*cW;
        });
        pts = allPts2;
      }
    }
      if(!pts.length) return;

    const drawLine = pts.length >= 2;

    // Map values to Y using a DEDICATED right-side scale for this KPI
    // This avoids the problem of small PE values (eg 18x) mapping to price range (eg 500-800)
    const vals = pts.map(p=>p.v);
    const vMin = Math.min(...vals)*0.92, vMax = Math.max(...vals)*1.08;
    const vRng = vMax - vMin || 1;
    // Use top 80% of chart height, leaving room for x-axis labels at bottom
    const yTop = PAD.t + 4, yBot = H - PAD.b - 16;
    const kpiY = v => yBot - ((v - vMin) / vRng) * (yBot - yTop);

    ctx.save();
    ctx.strokeStyle = col; ctx.lineWidth = 1.5; ctx.globalAlpha = 0.9;

    if(drawLine){
      // Subtle fill under line
      ctx.beginPath();
      pts.forEach((p,j)=>{ j===0 ? ctx.moveTo(p.x, kpiY(p.v)) : ctx.lineTo(p.x, kpiY(p.v)); });
      ctx.lineTo(pts[pts.length-1].x, yBot);
      ctx.lineTo(pts[0].x, yBot);
      ctx.closePath();
      ctx.fillStyle = col;
      ctx.globalAlpha = 0.08;
      ctx.fill();
      // Line
      ctx.globalAlpha = 0.9;
      ctx.beginPath();
      pts.forEach((p,j)=>{ j===0 ? ctx.moveTo(p.x, kpiY(p.v)) : ctx.lineTo(p.x, kpiY(p.v)); });
      ctx.stroke();
    }

    // Dots
    ctx.fillStyle = col; ctx.globalAlpha = 1;
    pts.forEach(p=>{
      ctx.beginPath();
      ctx.arc(p.x, kpiY(p.v), 2.5, 0, Math.PI*2);
      ctx.fill();
    });

    // Value labels above each dot (skip if too crowded)
    const labelEvery = pts.length > 6 ? 2 : 1;
    pts.forEach((p,j)=>{
      if(j % labelEvery !== 0 && j !== pts.length-1) return;
      const dispV = k==='pe'  ? p.v.toFixed(0)+'x' :
                    k==='opm' ? p.v.toFixed(1)+'%' :
                    Math.abs(p.v)>=1000 ? (p.v/1000).toFixed(1)+'K' : p.v.toFixed(0);
      ctx.fillStyle = col; ctx.globalAlpha = 0.85;
      ctx.font = '6px JetBrains Mono,monospace'; ctx.textAlign = 'center';
      ctx.fillText(dispV, p.x, kpiY(p.v) - 4);
    });

    // Label on right axis strip
    const last = pts[pts.length-1];
    const dispVal = k==='pe'  ? last.v.toFixed(0)+'x' :
                    k==='opm' ? last.v.toFixed(1)+'%' :
                    Math.abs(last.v)>=1000 ? (last.v/1000).toFixed(1)+'KCr' : last.v.toFixed(0)+'Cr';
    ctx.fillStyle = col; ctx.globalAlpha = 1;
    ctx.font = 'bold 7px JetBrains Mono,monospace'; ctx.textAlign = 'right';
    ctx.fillText(label+' '+dispVal, W-2, Math.max(kpiY(last.v)-3, PAD.t+8));
    ctx.restore();
  });
}

// Volume bars with 5-period MA trend line
function drawVolume(s){
  const cv=document.getElementById('cv-vol');
  if(!cv)return;
  const wrap=document.getElementById('vol-wrap');
  const W2=Math.max(wrap?wrap.offsetWidth:0, 280);
  const H2=50;
  const dpr=window.devicePixelRatio||1;
  cv.width=W2*dpr;cv.height=H2*dpr;
  cv.style.width=W2+'px';cv.style.height=H2+'px';
  const ctx=cv.getContext('2d');
  ctx.scale(dpr,dpr);

  const candles=getSlicedCandles(s, W2);
  if(!candles.length)return;

  ctx.fillStyle='#070c18';ctx.fillRect(0,0,W2,H2);

  const W=W2,H=H2;
  const PAD={l:6,r:52,t:4,b:4};
  const cW=W-PAD.l-PAD.r,cH=H-PAD.t-PAD.b;
  const n=candles.length,gap=cW/n,bw=Math.max(2,Math.min(14,gap*0.7));
  const mv=Math.max(...candles.map(c=>c.v))||1;

  // Right axis strip
  ctx.fillStyle='rgba(7,12,24,.8)';
  ctx.fillRect(W-PAD.r,0,PAD.r,H);
  ctx.strokeStyle='rgba(30,51,80,.8)';ctx.lineWidth=1;
  ctx.beginPath();ctx.moveTo(W-PAD.r,0);ctx.lineTo(W-PAD.r,H);ctx.stroke();
  ctx.fillStyle='rgba(140,176,208,.5)';ctx.font='7px JetBrains Mono,monospace';ctx.textAlign='right';
  ctx.fillText('Vol',W-2,10);

  candles.forEach((c,i)=>{
    const bh=Math.max(2,(c.v/mv)*cH);
    const x=PAD.l+i*gap+(gap-bw)/2;
    ctx.fillStyle=c.c>=c.o?'rgba(0,208,132,.5)':'rgba(255,59,92,.45)';
    if(ctx.roundRect)ctx.roundRect(x,PAD.t+cH-bh,bw,bh,1);
    else ctx.rect(x,PAD.t+cH-bh,bw,bh);
    ctx.fill();
  });

  // Volume trend line (smoothed MA5)
  const volMA = candles.map((c,i)=>{
    if(i<4) return null;
    return candles.slice(i-4,i+1).reduce((a,b)=>a+b.v,0)/5;
  });
  ctx.strokeStyle='rgba(255,255,255,.4)'; ctx.lineWidth=1; ctx.beginPath();
  let started=false;
  volMA.forEach((v,i)=>{
    if(v===null) return;
    const x=PAD.l+i*gap+gap/2;
    const y=PAD.t+cH-(v/mv)*cH;
    if(!started){ctx.moveTo(x,y);started=true;} else ctx.lineTo(x,y);
  });
  ctx.stroke();
}

// ── Quarterly CFO bar panel ───────────────────────────
// ── Quarterly P/E line panel ──────────────────────────
function updateChartStats(s){
  const candles=getSlicedCandles(s, 0);
  if(!candles.length)return;
  const closes=candles.map(c=>c.c);
  const first=closes[0],last=closes[closes.length-1];
  const ret=((last-first)/first*100).toFixed(2);
  const hi=Math.max(...candles.map(c=>c.h));
  const lo=Math.min(...candles.map(c=>c.l));
  const vol=((hi-lo)/lo*100).toFixed(1);
  const up=last>=first;

  const retEl=document.getElementById('cstat-ret');
  const hiEl=document.getElementById('cstat-hi');
  const loEl=document.getElementById('cstat-lo');
  const volEl=document.getElementById('cstat-vol');
  if(retEl){retEl.textContent=(up?'+':'')+ret+'%';retEl.style.color=up?'var(--gr2)':'var(--rd2)';}
  if(hiEl)hiEl.textContent='₹'+fmt(hi);
  if(loEl)loEl.textContent='₹'+fmt(lo);
  if(volEl)volEl.textContent=vol+'%';
}

// Fundamentals tab
function renderFundamentals(s){
  return `<div style="padding:10px 13px 14px">
    <div class="fund-grid">
      ${[
        {l:'Market Cap',v:s.mcap||'N/A',sub:'',st:'neutral'},
        {l:'P/E Ratio',v:s.pe?s.pe+'x':'—',sub:'Sector ~22x',st:s.pe?(s.pe<18?'good':s.pe<30?'warn':'bad'):'neutral'},
        {l:'P/B Ratio',v:s.pb?s.pb+'x':'—',sub:'Price/Book',st:s.pb?(s.pb<2?'good':s.pb<5?'warn':'bad'):'neutral'},
        {l:'ROE',v:s.roe?s.roe+'%':'—',sub:'>15% strong',st:s.roe?(s.roe>15?'good':s.roe>10?'warn':'bad'):'neutral'},
        {l:'ROCE',v:s.roce?s.roce+'%':'—',sub:'>20% excellent',st:s.roce?(s.roce>20?'good':s.roce>12?'warn':'bad'):'neutral'},
        {l:'EPS TTM',v:s.eps?'₹'+fmt(s.eps):'—',sub:'Earnings/Share',st:'neutral'},
        {l:'Div Yield',v:s.divYield?s.divYield+'%':'—',sub:'Annual',st:'neutral'},
        {l:'Debt/Equity',v:s.debtEq!=null?s.debtEq:'—',sub:'<0.5 safe',st:s.debtEq!=null?(s.debtEq<0.5?'good':s.debtEq<1?'warn':'bad'):'neutral'},
      ].map(({l,v,sub,st})=>`
        <div class="fund-cell ${st}">
          <div class="fc-lbl">${l}</div>
          <div class="fc-val">${v}</div>
          <div class="fc-sub">${sub}</div>
        </div>`).join('')}
    </div>

    <div class="sec-lbl">Shareholding</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px">
      <div class="mbox ${s.promoter>50?'good':'neutral'}">
        <div class="ml">Promoter Holding</div>
        <div class="mv">${s.promoter||'—'}%</div>
        <div class="ms">${s.promoter>50?'Strong':'Below 50%'}</div>
      </div>
      <div class="mbox neutral">
        <div class="ml">Pledging</div>
        <div class="mv">—</div>
        <div class="ms">Not available</div>
      </div>
    </div>
  </div>`;
}

// News tab with RSS
function renderNewsTab(s){
  return `<div>
    <div style="padding:10px 12px 4px">
      <div class="sec-lbl">News Sources</div>
    </div>
    <div id="stock-news-list">
      <div style="padding:14px;text-align:center;font-size:11px;color:var(--mu)">Loading news…</div>
    </div>
    <div style="padding:10px 12px">
      <div class="sec-lbl">Research Links</div>
      <div style="display:flex;flex-direction:column;gap:6px">
        ${[
          {l:'NSE Official',u:`https://www.nseindia.com/get-quotes/equity?symbol=${s.symbol}`,c:'#2196f3',d:'Live quotes & filings'},
          {l:'Screener.in',u:`https://www.screener.in/company/${s.symbol}/`,c:'#a855f7',d:'Annual reports & ratios'},
          {l:'Economic Times',u:`https://economictimes.indiatimes.com/topic/${s.symbol}`,c:'#f97316',d:'Latest news coverage'},
          {l:'Moneycontrol',u:`https://www.moneycontrol.com/india/stockpricequote/${s.symbol}/${s.symbol}`,c:'#00d084',d:'Price & analysis'},
          {l:'TradingView',u:`https://in.tradingview.com/symbols/NSE-${s.symbol}/`,c:'#64b5f6',d:'Advanced charts'},
          {l:'Google News',u:`https://news.google.com/search?q=${encodeURIComponent(s.symbol+' NSE stock India')}`,c:'#4285f4',d:'News aggregator'},
        ].map(lk=>`
          <a href="${lk.u}" target="_blank" rel="noopener"
            style="display:flex;align-items:center;gap:12px;padding:11px 13px;
            background:var(--card);border:1px solid var(--b1);border-radius:9px;
            text-decoration:none;border-left:3px solid ${lk.c}">
            <div style="flex:1">
              <div style="font-size:13px;font-weight:700;color:var(--tx)">${lk.l}</div>
              <div style="font-size:10px;color:var(--tx3);margin-top:2px">${lk.d}</div>
            </div>
            <span style="font-size:11px;color:var(--b3)">↗</span>
          </a>`).join('')}
      </div>
    </div>
  </div>`;
}

// Load news for a stock
async function loadStockNews(sym,name){
  const el=document.getElementById('stock-news-list');
  if(!el)return;
  try{
    const query=encodeURIComponent(sym+' '+name+' NSE India stock');
    const url='https://api.rss2json.com/v1/api.json?rss_url='+encodeURIComponent('https://news.google.com/rss/search?q='+query+'&hl=en-IN&gl=IN&ceid=IN:en')+'&count=8';
    const res=await fetch(url);
    const d=await res.json();
    const items=d.items||[];
    if(!items.length){el.innerHTML=`<div style="padding:14px;text-align:center;font-size:11px;color:var(--mu)">No recent news for ${sym}</div>`;return;}
    el.innerHTML=items.map(item=>{
      const{tag,imp}=classifyNews(item.title);
      const src=item.source?.name||extractDomain(item.link)||'News';
      return `<div class="news-item" style="margin:0;border-radius:0;border-left:none;border-right:none;border-top:none">
        <div class="news-src">
          <span>${src}</span>
          <span class="imp-badge imp-${imp}">${imp==='H'?'HIGH':imp==='M'?'MED':'LOW'}</span>
          <span class="pill pill-bl" style="font-size:7px">${tag}</span>
          <span>${timeAgo(new Date(item.pubDate))}</span>
        </div>
        <div class="news-title">${item.title}</div>
      </div>`;
    }).join('');
  }catch(e){
    el.innerHTML=`<div style="padding:14px;text-align:center;font-size:11px;color:var(--mu)">Could not load news</div>`;
  }
}

function setDrillTab(t){
  S.drillTab=t;
  const dc=document.getElementById('dc');
  if(dc){dc.innerHTML=renderDC(S.selStock);}
  document.querySelectorAll('.dtab').forEach(b=>b.classList.toggle('active',b.dataset.t===t));
  if(t==='technical') loadAndDrawChart(S.selStock);
  if(t==='news'&&S.selStock) loadStockNews(S.selStock.symbol,S.selStock.name);
}

// Central chart loader — fetch OHLC data then draw all panels
// Fetch OHLC data from charts/SYM.json then draw all chart panels
function loadAndDrawChart(s){
  if(!s) return;
  const sym = s.symbol;
  // After 2 rAF the DOM is painted and offsetWidth is correct
  requestAnimationFrame(()=>requestAnimationFrame(()=>{
    if(chartCache[sym]){
      s.candles = chartCache[sym];
      scheduleTACharts(s);
      attachChartResizeObserver(s);
      return;
    }
    fetch('./charts/'+sym+'.json', {cache:'force-cache'})
      .then(r=>r.ok?r.json():null)
      .then(d=>{
        if(d && d.bars && d.bars.length){
          chartCache[sym] = d.bars;
          s.candles = d.bars;
        } else {
          // Mark as no-data so canvas shows helpful message
          s.candles = [];
          s._noChartData = true;
        }
        scheduleTACharts(s);
        attachChartResizeObserver(s);
      })
      .catch(()=>{
        s.candles = [];
        s._noChartData = true;
        scheduleTACharts(s);
      });
  }));
}

//  ANALYSIS TAB
let analysisState = {
  selSym:   null,   // currently selected stock
  filing:   null,   // { url, title, date, quarter }
  loading:  false,
};

// ANALYSIS TAB — concall paste workflow
// User: finds filing → copies prompt → pastes in Claude.ai
//       → pastes response here → saved to GUIDANCE + GitHub
function renderAnalysis(c){
  const pf = S.portfolio.map(h=>mergeHolding(h));

  // Build status per stock from GUIDANCE
  const now = Date.now();
  const stocks = pf.map(h=>{
    const g = GUIDANCE[h.sym];
    let status = 'pending', statusLabel = 'Pending', daysOld = null;
    if(g && g.updated){
      daysOld = Math.floor((now - new Date(g.updated).getTime()) / 86400000);
      if(daysOld > 90){ status='outdated'; statusLabel=daysOld+'d ago'; }
      else { status='done'; statusLabel='Updated '+daysOld+'d ago'; }
    }
    return {...h, g, status, statusLabel};
  });

  const sel = analysisState.selSym;
  const selStock = stocks.find(s=>s.sym===sel);
  const f = FUND[sel]||{};

  c.innerHTML = `<div class="fin" style="padding-bottom:80px">

    <!-- Header -->
    <div style="padding:14px 14px 8px;border-bottom:1px solid var(--b1)">
      <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:15px;color:var(--title)">🔬 Results Analysis</div>
      <div style="font-size:9px;color:var(--tx3);margin-top:2px">Upload BSE/NSE filing → Analyse with Claude.ai → Store guidance</div>
    </div>

    <!-- Stock queue -->
    <div style="padding:10px 12px 6px">
      <div style="font-size:8px;color:var(--tx3);text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Select Stock to Analyse</div>
      <div style="display:flex;flex-direction:column;gap:4px">
        ${stocks.map(s=>{
          const isActive = s.sym===sel;
          const col = s.status==='done'?'#00e896':s.status==='outdated'?'#ffbf47':'#4a6888';
          const dot = s.status==='done'?'🟢':s.status==='outdated'?'🟡':'⚪';
          return `<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
            <div onclick="selectAnalysisStock('${s.sym}')"
              style="flex:1;display:flex;justify-content:space-between;align-items:center;
              padding:8px 10px;border-radius:8px;cursor:pointer;
              background:${isActive?'rgba(249,115,22,.12)':'var(--card)'};
              border:1px solid ${isActive?'var(--ac)':'var(--b1)'}">
              <div>
                <span style="font-size:11px;font-weight:700;color:${isActive?'var(--ac)':'var(--tx1)'};font-family:var(--mono)">${s.sym}</span>
                <span style="font-size:9px;color:var(--tx3);margin-left:6px">${f.name||s.name||''}</span>
              </div>
              <div style="display:flex;align-items:center;gap:5px">
                <span style="font-size:8px;color:${col}">${s.statusLabel}</span>
                <span style="font-size:10px">${dot}</span>
              </div>
            </div>
            ${s.status!=='pending'?`<button onclick="clearStockAnalysis('${s.sym}',event)"
              style="flex-shrink:0;padding:6px 9px;background:rgba(255,59,92,.08);
              border:1px solid rgba(255,59,92,.25);border-radius:7px;color:#ff6b85;
              font-size:11px;cursor:pointer" title="Clear analysis for ${s.sym}">🗑</button>`:''}
          </div>`;
        }).join('')}
      </div>
    </div>

    <!-- Analysis workflow for selected stock -->
    ${sel ? `<div style="margin:10px 12px;background:var(--card);border:1px solid var(--b1);border-radius:12px;overflow:hidden">

      <!-- Stock header -->
      <div style="padding:10px 14px;background:rgba(249,115,22,.08);border-bottom:1px solid var(--b1);display:flex;justify-content:space-between;align-items:center">
        <div>
          <div style="font-weight:800;font-size:13px;color:var(--ac);font-family:var(--mono)">${sel}</div>
          <div style="font-size:9px;color:var(--tx3)">${(FUND[sel]?.name||'')} · ${(FUND[sel]?.sector||'')}</div>
        </div>
        <div style="text-align:right;font-family:var(--mono);font-size:10px">
          <div style="color:var(--tx1)">₹${fmt(FUND[sel]?.ltp||0)}</div>
          <div style="color:var(--tx3)">PE: ${FUND[sel]?.pe||'—'}x</div>
        </div>
      </div>

      <!-- Step 1: Find Filing -->
      <div style="padding:12px 14px;border-bottom:1px solid var(--b1)">
        <div style="font-size:10px;font-weight:700;color:var(--title);margin-bottom:8px">
          <span style="background:var(--ac);color:#fff;border-radius:50%;width:16px;height:16px;display:inline-flex;align-items:center;justify-content:center;font-size:8px;margin-right:6px">1</span>
          Find Latest Results Filing
        </div>
        <button onclick="findFiling('${sel}')" id="btn-find-filing"
          style="background:rgba(99,102,241,.15);border:1px solid rgba(99,102,241,.4);border-radius:8px;padding:8px 16px;color:#818cf8;font-size:11px;font-weight:700;cursor:pointer;width:100%">
          🔍 Search BSE/NSE Filing
        </button>
        <div id="filing-result" style="margin-top:8px"></div>
      </div>

      <!-- Step 2: Generate Prompt -->
      <div style="padding:12px 14px;border-bottom:1px solid var(--b1)">
        <div style="font-size:10px;font-weight:700;color:var(--title);margin-bottom:8px">
          <span style="background:var(--ac);color:#fff;border-radius:50%;width:16px;height:16px;display:inline-flex;align-items:center;justify-content:center;font-size:8px;margin-right:6px">2</span>
          Open Claude.ai with Analysis Prompt
        </div>
        <div style="font-size:9px;color:var(--tx3);margin-bottom:8px">Copies the prompt → opens Claude.ai → attach the PDF from step 1 → paste response below</div>
        <button onclick="openClaudeAnalysis('${sel}')"
          style="background:rgba(0,208,132,.12);border:1px solid rgba(0,208,132,.3);border-radius:8px;padding:8px 16px;color:#00e896;font-size:11px;font-weight:700;cursor:pointer;width:100%">
          📋 Copy Prompt &amp; Open Claude.ai ↗
        </button>
      </div>

      <!-- Step 3: Paste Response -->
      <div style="padding:12px 14px">
        <div style="font-size:10px;font-weight:700;color:var(--title);margin-bottom:8px">
          <span style="background:var(--ac);color:#fff;border-radius:50%;width:16px;height:16px;display:inline-flex;align-items:center;justify-content:center;font-size:8px;margin-right:6px">3</span>
          Paste Claude's Response
        </div>
        <div style="font-size:11px;color:var(--tx3);line-height:1.6;margin-bottom:10px;padding:8px 10px;background:var(--s2);border-radius:7px;border-left:3px solid var(--ac)">
          Everything shown in the stock's <b style="color:var(--tx2)">Overview tab</b> — action signal, guidance, geography, products, risks — comes from this paste. Re-paste a newer quarter anytime to update it.
        </div>
        <textarea id="ta-response" placeholder="Paste Claude's response table here..."
          style="width:100%;box-sizing:border-box;height:160px;background:var(--s1);border:1px solid var(--b1);border-radius:8px;padding:10px;color:var(--tx1);font-size:10px;font-family:var(--mono);resize:vertical;outline:none"></textarea>
        <div style="display:flex;gap:6px;margin-top:8px">
          <button onclick="saveAnalysis('${sel}')"
            style="flex:2;background:var(--ac);border:none;border-radius:8px;padding:10px 0;color:#fff;font-size:12px;font-weight:800;cursor:pointer;font-family:'Syne',sans-serif">
            💾 Save Analysis
          </button>
          <button onclick="debugAnalysis('${sel}')"
            style="flex:1;background:rgba(100,180,255,.12);border:1px solid rgba(100,180,255,.4);border-radius:8px;padding:10px 0;color:#64b5f6;font-size:11px;font-weight:800;cursor:pointer;font-family:'Syne',sans-serif">
            🐛 Debug
          </button>
        </div>
        <div id="debug-panel" style="display:none;margin-top:8px;background:#02040a;border:1px solid #1e3350;border-radius:8px;padding:10px;max-height:320px;overflow-y:auto;font-family:'JetBrains Mono',monospace;font-size:9px;line-height:1.7"></div>

        <!-- Existing guidance preview -->
        ${GUIDANCE[sel] ? `<div style="margin-top:10px;padding:10px;background:rgba(0,0,0,.2);border-radius:8px;border:1px solid var(--b1)">
          <div style="font-size:8px;color:var(--tx3);margin-bottom:5px">EXISTING GUIDANCE · ${new Date(GUIDANCE[sel].updated).toLocaleDateString('en-IN')}</div>
          <div style="font-size:9px;color:var(--tx2);line-height:1.6">${GUIDANCE[sel].summary||'No summary'}</div>
          <div style="margin-top:6px;display:flex;gap:6px">
            <span style="font-size:8px;font-weight:700;color:${GUIDANCE[sel].tone==='Positive'?'#00e896':GUIDANCE[sel].tone==='Negative'?'#ff6b85':'#ffbf47'}">${GUIDANCE[sel].tone||'Neutral'}</span>
            <span style="font-size:8px;color:var(--tx3)">Confidence: ${GUIDANCE[sel].confidence||'—'}</span>
          </div>
        </div>` : ''}
      </div>

    </div>` : `<div style="text-align:center;padding:40px 20px;color:var(--tx3)">
      <div style="font-size:32px;margin-bottom:10px">☝️</div>
      <div style="font-size:12px">Select a stock above to begin analysis</div>
    </div>`}

  </div>`;

  // Restore filing result if exists
  if(sel && analysisState.filing){
    renderFilingResult(analysisState.filing);
  }
}

// Select a stock in the analysis queue
function selectAnalysisStock(sym){
  analysisState.selSym = sym;
  analysisState.filing = null;
  render();
}

// Clear concall + insights for a stock (two-tap confirm)
function clearStockAnalysis(sym, event){
  event.stopPropagation(); // don't trigger selectAnalysisStock
  if(!GUIDANCE[sym]) return;
  // Confirm via toast-style inline — no confirm() on iOS PWA
  const btn = event.target;
  if(btn.dataset.confirm !== '1'){
    btn.dataset.confirm = '1';
    btn.textContent = '✓?';
    btn.style.background = 'rgba(255,59,92,.2)';
    btn.style.borderColor = 'rgba(255,59,92,.5)';
    setTimeout(()=>{
      btn.dataset.confirm = '';
      btn.textContent = '🗑';
      btn.style.background = 'rgba(255,59,92,.08)';
      btn.style.borderColor = 'rgba(255,59,92,.25)';
    }, 2500);
    return;
  }
  // Confirmed — clear
  delete GUIDANCE[sym];
  saveGuidanceAll();
  toast(sym+' analysis cleared');
  render();
}

// Search BSE/NSE/Screener for latest results filing links
async function findFiling(sym){
  const btn = document.getElementById('btn-find-filing');
  const res = document.getElementById('filing-result');
  if(!btn||!res) return;
  btn.textContent = 'Searching...'; btn.disabled = true;

  try{
    const name = FUND[sym]?.name || sym;
    // Search Google News RSS for latest BSE results filing
    const query = encodeURIComponent(`"${name}" quarterly results BSE filing site:bseindia.com OR site:nseindia.com`);
    const rssUrl = `https://news.google.com/rss/search?q=${query}&hl=en-IN&gl=IN&ceid=IN:en`;
    const apiUrl = `https://api.rss2json.com/v1/api.json?rss_url=${encodeURIComponent(rssUrl)}&count=5`;

    const r = await fetch(apiUrl);
    const d = await r.json();
    const items = d.items||[];

    // Screener — works directly with NSE symbol, has concalls + documents
    const screenerUrl  = `https://www.screener.in/company/${sym}/consolidated/`;
    const screenerConc = `https://www.screener.in/company/${sym}/concalls/`;
    // BSE results — search by company name
    const bseResultsUrl = `https://www.bseindia.com/corporates/Comp_Resultsnew.aspx?scripname=${encodeURIComponent(name)}`;
    // NSE — passes symbol directly
    const nseUrl = `https://www.nseindia.com/companies-listing/corporate-filings-financial-results?symbol=${encodeURIComponent(sym)}`;

    const filing = {
      sym, name,
      screenerUrl,
      screenerConc,
      bseUrl:     bseResultsUrl,
      nseUrl:     nseUrl,
      newsItems:  items.slice(0,3),
      quarter:    detectQuarter(),
    };
    analysisState.filing = filing;
    renderFilingResult(filing);
  } catch(e){
    if(res) res.innerHTML = `<div style="color:#ff6b85;font-size:9px;padding:6px">Search failed: ${e.message}</div>`;
  } finally {
    if(btn){ btn.textContent='🔍 Search BSE/NSE Filing'; btn.disabled=false; }
  }
}

function detectQuarter(){
  const m = new Date().getMonth()+1;
  const y = new Date().getFullYear();
  if(m>=4&&m<=6)  return `Q1 FY${y-1999}`;
  if(m>=7&&m<=9)  return `Q2 FY${y-1999}`;
  if(m>=10&&m<=12) return `Q3 FY${y-1999}`;
  return `Q4 FY${y-2000}`;
}

function renderFilingResult(filing){
  const res = document.getElementById('filing-result');
  if(!res) return;
  res.innerHTML = `
    <div style="background:rgba(0,0,0,.2);border-radius:8px;padding:10px;font-size:9px">
      <div style="color:var(--tx3);margin-bottom:6px">📄 Latest filing period: <b style="color:var(--tx1)">${filing.quarter}</b></div>
      <div style="display:flex;flex-direction:column;gap:5px">
        <a href="${filing.screenerUrl}" target="_blank"
          style="display:block;padding:8px 12px;background:rgba(0,208,132,.08);border:1px solid rgba(0,208,132,.3);border-radius:8px;color:#00e896;text-decoration:none;font-weight:700;font-size:10px">
          📊 Screener — ${filing.sym} (Financials + Documents) ↗
        </a>
        <a href="${filing.screenerConc}" target="_blank"
          style="display:block;padding:8px 12px;background:rgba(0,208,132,.08);border:1px solid rgba(0,208,132,.3);border-radius:8px;color:#00e896;text-decoration:none;font-weight:700;font-size:10px">
          🎙 Screener — ${filing.sym} Concall Transcripts ↗
        </a>
        <div style="display:flex;gap:5px">
          <a href="${filing.bseUrl}" target="_blank"
            style="flex:1;display:block;padding:6px 8px;background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.25);border-radius:6px;color:#818cf8;text-decoration:none;font-size:8px;font-weight:700;text-align:center">
            BSE Results ↗
          </a>
          <a href="${filing.nseUrl}" target="_blank"
            style="flex:1;display:block;padding:6px 8px;background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.25);border-radius:6px;color:#818cf8;text-decoration:none;font-size:8px;font-weight:700;text-align:center">
            NSE Results ↗
          </a>
        </div>
      </div>
      <div style="margin-top:6px;color:var(--tx3);font-size:8px">Tap a link → find the results PDF → save it → attach in Claude.ai</div>
    </div>`;
}

// Build analysis prompt from FUND data + concall context,
// copy to clipboard, open Claude.ai
function openClaudeAnalysis(sym){
  const f = FUND[sym]||{};
  const name = f.name || sym;
  const sector = f.sector || '';
  const quarter = detectQuarter();

  // Build quarterly trend from FUND
  const qtrs = (f.quarterly||[]).slice(0,4);
  const qtrText = qtrs.length ? qtrs.map(q=>
    `  ${q.d||'?'}: Rev ₹${q.rev||'—'}Cr | EPS ₹${q.eps||'—'} | Net ₹${q.net||'—'}Cr | OPM ${q.opm||'—'}%`
  ).join('\n') : '  No quarterly data available';

  const prompt = `You are a senior equity research analyst. Analyse the attached ${quarter} results document for ${name} (NSE: ${sym}).

COMPANY CONTEXT:
- Sector: ${sector}
- Current Price: ₹${f.ltp||'—'} | P/E: ${f.pe||'—'}x | Forward P/E: ${f.fwd_pe||'—'}x
- ROE: ${f.roe||'—'}% | OPM: ${f.opm_pct||'—'}% | Debt/Equity: ${f.debt_eq||'—'}
- Promoter: ${f.prom_pct||'—'}% | MCap: ₹${f.mcap||'—'}Cr

LAST 4 QUARTERS TREND:
${qtrText}

TASK: Analyse this earnings concall / results document thoroughly.
Return ONLY in the KEY: VALUE format below — one field per line, no markdown table, no bold, no bullets, no extra text before or after. This format is chosen so it can be easily copied on mobile.

Quarter: Q3 FY26 etc
Action Signal: BUY MORE / HOLD / REDUCE / EXIT with 1-line reason
One Line Verdict: Most important takeaway for investor in 1 sentence
Revenue Guidance: Specific target next quarter and full year
Revenue Growth Target: YoY or QoQ growth % guided
EBITDA Margin Target: Guided range
PAT Margin Target: Guided range
Order Book: Total order book value and execution timeline
Deal Wins: New deals this quarter - size and client type
Pipeline: Sales pipeline or deal pipeline commentary
Customer Changes: New customers added; any major losses
Segment Growth: Which segments growing vs declining
Geographic Mix: Domestic vs export split % e.g. India 60% US 25% Europe 15%
Geographic Presence: Countries/regions actively operating in and expansion plans
Headcount Plans: Hiring / layoff plans; utilisation rate
Raw Material Outlook: Cost pressure or easing expected
Working Capital: Receivables, inventory, cash conversion trend
Debt Reduction Plan: Repayment timeline; net debt target
Capex Plan: Amount, purpose, funding source
Capacity Expansion: New plants or lines with timeline
New Products: Launching products, services or business lines
Key Products Portfolio: Top 3-5 existing products/segments with revenue contribution %
Market Share: Gaining or losing share; pricing strategy
Competition: Key threats or advantages mentioned
Acquisitions: M&A, JVs, partnerships announced
Geographic Expansion: New markets, international plans
Promoter Actions: Insider buying/selling, pledge, buyback
Dividend Guidance: Dividend commitment or payout ratio guided
Regulatory Impact: Policy, export/import, licensing changes
Currency Exposure: FX sensitivity and hedging strategy
Litigation: Ongoing legal or regulatory issues
Management Tone: Positive/Cautious/Negative with specific reason
Management Credibility: Delivered last quarter guidance? Yes/Partially/No
Specific Commitments: Top 3 promises with numbers and timelines
Key Risks: Top 3 risks - rate each High/Medium/Low
Analyst Consensus: Buy/Hold/Sell count and price target range
Confidence Level: High/Medium/Low based on specificity of guidance

RULES:
- Use ONLY information from the attached document
- Write "Not mentioned" if absent - never guess or fabricate
- Be specific - use actual numbers not vague statements
- Action Signal must reflect valuation + guidance quality together
- One Line Verdict must be actionable not descriptive
- Do NOT use markdown table format — plain KEY: VALUE only`;

  showPromptPanel(sym, prompt);
  if(navigator.clipboard && window.isSecureContext){
    navigator.clipboard.writeText(prompt)
      .then(()=> toast("Prompt copied — paste in Claude"))
      .catch(()=> toast("Copy the prompt from the panel below"));
  }
}

// Show full prompt in a modal for copy-paste on mobile
function showPromptPanel(sym, prompt){
  // Show a modal with the prompt + Open Claude button
  const existing = document.getElementById('prompt-modal');
  if(existing) existing.remove();

  const modal = document.createElement('div');
  modal.id = 'prompt-modal';
  modal.style.cssText = `
    position:fixed;inset:0;z-index:500;
    background:rgba(0,0,0,.85);
    display:flex;flex-direction:column;
    padding:0;overflow:hidden;
  `;
  modal.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;
      padding:14px 16px;background:#0d1929;border-bottom:1px solid #1e3350;flex-shrink:0">
      <div>
        <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:13px;color:#f0f6ff">Analysis Prompt — ${sym}</div>
        <div style="font-size:9px;color:#5878a8;margin-top:2px">Copy → Open Claude.ai → Paste → Attach PDF</div>
      </div>
      <button onclick="document.getElementById('prompt-modal').remove()"
        style="background:none;border:1px solid #1e3350;border-radius:6px;padding:4px 10px;color:#8eb0d0;font-size:11px;cursor:pointer">✕ Close</button>
    </div>

    <!-- Open Claude buttons -->
    <div style="display:flex;gap:8px;padding:12px 16px;background:#060c18;border-bottom:1px solid #1e3350;flex-shrink:0">
      <a href="https://claude.ai/new" target="_blank"
        style="flex:1;display:block;text-align:center;padding:10px;
        background:rgba(249,115,22,.15);border:1px solid var(--ac);border-radius:8px;
        color:var(--ac);font-weight:800;font-size:11px;text-decoration:none;font-family:'Syne',sans-serif">
        🤖 Open Claude.ai ↗
      </a>
      <button onclick="
        const ta=document.getElementById('pm-prompt');
        ta.select();document.execCommand('copy');
        toast('Copied!');this.textContent='✓ Copied';"
        style="flex:1;padding:10px;background:rgba(0,208,132,.1);border:1px solid rgba(0,208,132,.3);
        border-radius:8px;color:#00e896;font-weight:800;font-size:11px;cursor:pointer;font-family:'Syne',sans-serif">
        📋 Copy Prompt
      </button>
    </div>

    <!-- Prompt text -->
    <textarea id="pm-prompt" readonly
      style="flex:1;width:100%;box-sizing:border-box;
      background:#02040a;border:none;outline:none;
      padding:14px 16px;color:#8eb0d0;
      font-size:10px;font-family:'JetBrains Mono',monospace;
      line-height:1.6;resize:none;overflow-y:auto"
    >${prompt.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</textarea>

    <div style="padding:10px 16px;background:#060c18;border-top:1px solid #1e3350;
      font-size:8px;color:#4a6888;text-align:center;flex-shrink:0">
      Steps: Copy prompt → Open Claude.ai → Paste prompt → Attach the PDF from BSE/NSE → Come back and paste Claude's response
    </div>
  `;
  document.body.appendChild(modal);
}

// Debug panel: shows parser internals, data{} keys, saved g{} keys
// Re-Save button rebuilds g{} from raw_table using current parser
function debugAnalysis(sym){
  const ta = document.getElementById('ta-response');
  const panel = document.getElementById('debug-panel');
  if(!panel) return;

  const text = (ta && ta.value.trim()) || (GUIDANCE[sym] && GUIDANCE[sym].raw_table) || '';
  if(!text){ panel.style.display='block'; panel.innerHTML='<span style="color:#ff6b85">No text — paste Claude response first (or load existing guidance)</span>'; return; }

  // ── Run parser and expose internals ──
  const data = {};

  // Format 1: table
  const tableLines = text.split('\n').filter(l=>l.includes('|'));
  let fmt1count = 0;
  if(tableLines.length >= 3){
    tableLines.forEach(line=>{
      const cells = line.split('|').map(c=>c.trim()).filter(Boolean);
      if(cells.length >= 2 && !cells[0].match(/^[-:]+$/) && !cells[0].match(/^Field$/i)){
        const key = cells[0].toLowerCase().replace(/[^a-z0-9]/g,'_').replace(/_+/g,'_');
        const val = cells.slice(1).join(' | ').trim();
        if(key && val && val!=='Not mentioned' && val!=='—' && val!=='-'){ data[key]=val; fmt1count++; }
      }
    });
  }

  // Format 2: Key: Value
  let fmt2count = 0;
  text.split('\n').forEach(line=>{
    const clean = line.replace(/\*\*/g,'').replace(/\*/g,'').replace(/^[-•>\s]+/,'').trim();
    const m = clean.match(/^([A-Za-z][A-Za-z\s\/\(\)]+?)[\s]*[:：][\s]*(.+)$/);
    if(m && m[1] && m[2]){
      const key = m[1].trim().toLowerCase().replace(/[^a-z0-9]/g,'_').replace(/_+/g,'_');
      const val = m[2].trim();
      if(key && val && val!=='Not mentioned' && val!=='—' && val!=='-' && !data[key]){ data[key]=val; fmt2count++; }
    }
  });

  // Format 3: numbered
  let fmt3count = 0;
  text.split('\n').forEach(line=>{
    const clean = line.replace(/\*\*/g,'').trim();
    const m = clean.match(/^\d+[\.\)]\s*([A-Za-z][A-Za-z\s\/]+?)\s*[—–-]+\s*(.+)$/);
    if(m && m[1] && m[2]){
      const key = m[1].trim().toLowerCase().replace(/[^a-z0-9]/g,'_').replace(/_+/g,'_');
      const val = m[2].trim();
      if(key && val && !data[key]){ data[key]=val; fmt3count++; }
    }
  });

  const totalKeys = Object.keys(data).length;

  // Check the 2 specific fields we care about
  const geoKey   = Object.keys(data).find(k=>k.includes('geographic'));
  const prodKey  = Object.keys(data).find(k=>k.includes('key_product')||k.includes('product')||k.includes('segment'));

  // Build HTML report
  let html = '';
  html += `<div style="color:#64b5f6;font-weight:700;margin-bottom:6px">━━ PARSE REPORT ━━</div>`;
  html += `<div>Text length: <b style="color:#f0f6ff">${text.length} chars</b> · Lines: <b style="color:#f0f6ff">${text.split('\n').length}</b></div>`;
  html += `<div>Fmt1 (table): <b style="color:${fmt1count?'#00e896':'#ff6b85'}">${fmt1count} keys</b> · Fmt2 (key:val): <b style="color:${fmt2count?'#00e896':'#ff6b85'}">${fmt2count} keys</b> · Fmt3 (numbered): <b style="color:${fmt3count?'#00e896':'#ff6b85'}">${fmt3count} keys</b></div>`;
  html += `<div>Total data{} keys: <b style="color:${totalKeys>3?'#00e896':'#ff6b85'}">${totalKeys}</b></div>`;
  html += `<div style="margin-top:6px;color:#64b5f6;font-weight:700">━━ TARGET FIELDS ━━</div>`;
  // Check with same logic as fixed renderOverview
  const geoKeyFinal  = Object.keys(data).find(k=>k.includes('geographic'));
  const prodKeyFinal = Object.keys(data).find(k=>k.includes('key_product')||k.includes('product_mix')||k.includes('products_portfolio'))
                    || Object.keys(data).find(k=>k==='segment_growth'||k==='key_segments');
  html += `<div>geographic_presence: <b style="color:${geoKeyFinal?'#00e896':'#ff6b85'}">${geoKeyFinal ? 'FOUND as "'+geoKeyFinal+'" → '+data[geoKeyFinal].slice(0,60) : 'NOT FOUND'}</b></div>`;
  html += `<div>key_products_portfolio: <b style="color:${prodKeyFinal?'#00e896':'#ff6b85'}">${prodKeyFinal ? 'FOUND as "'+prodKeyFinal+'" → '+data[prodKeyFinal].slice(0,60) : 'NOT FOUND'}</b></div>`;

  html += `<div style="margin-top:6px;color:#64b5f6;font-weight:700">━━ ALL PARSED KEYS (${totalKeys}) ━━</div>`;
  Object.entries(data).forEach(([k,v])=>{
    const isTarget = k.includes('geographic')||k.includes('product')||k.includes('segment');
    html += `<div style="color:${isTarget?'#ffbf47':'#8eb0d0'}"><b>${k}</b>: ${String(v).slice(0,80)}${v.length>80?'…':''}</div>`;
  });

  if(totalKeys === 0){
    html += `<div style="margin-top:8px;color:#ff6b85;font-weight:700">━━ RAW FIRST 5 LINES ━━</div>`;
    text.split('\n').slice(0,5).forEach((l,i)=>{
      html += `<div style="color:#8eb0d0">${i+1}: ${l.replace(/</g,'&lt;').slice(0,100)}</div>`;
    });
  }

  // Show ALL saved g{} keys so we can see exactly what renderOverview receives
  const saved = GUIDANCE[sym];
  if(saved){
    html += `<div style="margin-top:6px;color:#64b5f6;font-weight:700">━━ SAVED g{} — ALL KEYS (${Object.keys(saved).length}) ━━</div>`;
    html += `<div style="color:#ffbf47;margin-bottom:3px">⚠ If geographic_mix/key_products missing below → tap Re-Save to rebuild from raw_table</div>`;
    Object.keys(saved).filter(k=>!['raw_table','insights'].includes(k)).forEach(k=>{
      const v = saved[k];
      const isTarget = k.includes('geographic')||k.includes('product')||k.includes('segment');
      const hasVal = v && v!==null && v!=='null' && String(v).length>0;
      html += `<div style="color:${isTarget?'#ffbf47':hasVal?'#8eb0d0':'#3a5a72'}"><b>${k}</b>: ${hasVal?String(v).slice(0,80):'❌ empty'}</div>`;
    });
    // Check specifically for the two targets
    const geoInG  = Object.keys(saved).find(k=>k.includes('geographic'));
    const prodInG = Object.keys(saved).find(k=>k.includes('key_product')||k.includes('product_mix')||k==='segment_growth');
    html += `<div style="margin-top:6px;padding:6px;background:rgba(0,0,0,.3);border-radius:4px">`;
    html += `<div>geo in g{}: <b style="color:${geoInG?'#00e896':'#ff6b85'}">${geoInG||'MISSING — re-save needed'}</b></div>`;
    html += `<div>products in g{}: <b style="color:${prodInG?'#00e896':'#ff6b85'}">${prodInG||'MISSING — re-save needed'}</b></div>`;
    html += `</div>`;
  }

  panel.style.display = 'block';
  panel.innerHTML = html;

  // Add Re-Save button if raw_table exists
  if(saved && saved.raw_table){
    const btn = document.createElement('button');
    btn.textContent = '♻ Re-Save from raw_table (rebuilds g{} with new parser)';
    btn.style.cssText = `margin-top:8px;width:100%;padding:8px;background:rgba(0,232,150,.15);border:1px solid rgba(0,232,150,.4);border-radius:6px;color:#00e896;font-size:10px;font-weight:700;cursor:pointer;font-family:'JetBrains Mono',monospace`;
    btn.onclick = () => {
      const rebuilt = parseAnalysisTable(sym, saved.raw_table);
      GUIDANCE[sym] = rebuilt;
      saveGuidanceAll();
      toast('✓ Re-saved with new parser — check Overview now');
      debugAnalysis(sym); // re-run debug to confirm
    };
    panel.appendChild(btn);
  }
}

// Parse pasted Claude response, save to GUIDANCE + GitHub
function saveAnalysis(sym){
  const ta = document.getElementById('ta-response');
  if(!ta || !ta.value.trim()){
    toast('Paste Claude response first'); return;
  }

  const text = ta.value.trim();
  const guidance = parseAnalysisTable(sym, text);

  // Always save — parser has fallback for any format
  GUIDANCE[sym] = guidance;
  saveGuidanceAll();

  toast('Analysis saved for '+sym+' ✓');
  ta.value = '';
  analysisState.filing = null;
  render();
}

// Multi-format parser for Claude concall response:
// Format 1: markdown table | Field | Value |
// Format 2: Key: Value lines (ALL formats run unconditionally)
// Format 3: numbered list  1. Field — Value
function parseAnalysisTable(sym, text){
  const data = {};

  // ── Format 1: Markdown table  | Field | Value |
  const tableLines = text.split('\n').filter(l=>l.includes('|'));
  if(tableLines.length >= 3){
    tableLines.forEach(line=>{
      const cells = line.split('|').map(c=>c.trim()).filter(Boolean);
      if(cells.length >= 2 && !cells[0].match(/^[-:]+$/) && !cells[0].match(/^Field$/i)){
        const key = cells[0].toLowerCase().replace(/[^a-z0-9]/g,'_').replace(/_+/g,'_');
        const val = cells.slice(1).join(' | ').trim();
        if(key && val && val!=='Not mentioned' && val!=='—' && val!=='-')
          data[key] = val;
      }
    });
  }

  // ── Format 2: Key: Value — ALWAYS runs (Claude mixes table + plain lines)
  // Handles **Revenue Guidance**: ₹4200 Cr  OR  Revenue Guidance: ₹4200 Cr
  text.split('\n').forEach(line=>{
    const clean = line.replace(/\*\*/g,'').replace(/\*/g,'').replace(/^[-•>\s]+/,'').trim();
    const m = clean.match(/^([A-Za-z][A-Za-z\s\/\(\)]+?)[\s]*[:：][\s]*(.+)$/);
    if(m && m[1] && m[2]){
      const key = m[1].trim().toLowerCase().replace(/[^a-z0-9]/g,'_').replace(/_+/g,'_');
      const val = m[2].trim();
      // Don't overwrite value already captured from Format 1 table
      if(key && val && val!=='Not mentioned' && val!=='—' && val!=='-' && !data[key])
        data[key] = val;
    }
  });

  // ── Format 3: Numbered list — ALWAYS runs
  text.split('\n').forEach(line=>{
    const clean = line.replace(/\*\*/g,'').trim();
    const m = clean.match(/^\d+[\.\)]\s*([A-Za-z][A-Za-z\s\/]+?)\s*[—–-]+\s*(.+)$/);
    if(m && m[1] && m[2]){
      const key = m[1].trim().toLowerCase().replace(/[^a-z0-9]/g,'_').replace(/_+/g,'_');
      const val = m[2].trim();
      if(key && val && !data[key]) data[key] = val;
    }
  });

  // If still nothing — store raw and let user see it
  if(Object.keys(data).length < 2){
    // Minimal fallback — store raw text as summary
    return {
      sym,
      updated:      new Date().toISOString(),
      quarter:      detectQuarter(),
      summary:      text.slice(0,500),
      tone:         text.match(/positive/i)?'Positive':text.match(/negative|caution|concern/i)?'Negative':'Neutral',
      confidence:   'Low',
      raw_table:    text,
      key_commitments: [],
      risks_flagged:   [],
    };
  }

  // Helper to find value by multiple possible key names
  function get(...keys){
    for(const k of keys){
      const norm = k.toLowerCase().replace(/[^a-z0-9]/g,'_').replace(/_+/g,'_');
      // exact match
      if(data[norm]) return data[norm];
      // partial match
      const found = Object.keys(data).find(dk=>dk.includes(norm)||norm.includes(dk));
      if(found) return data[found];
    }
    return null;
  }

  const toneRaw = get('management_tone','tone','sentiment') || '';
  const tone = toneRaw.match(/positive/i)?'Positive':toneRaw.match(/negative|bearish|caution/i)?'Negative':'Neutral';

  const commitRaw = get('key_commitments','commitments','management_commitments') || '';
  const risksRaw  = get('key_risks','risks','risk_factors') || '';

  const g = {
    sym,
    updated:          new Date().toISOString(),
    quarter:          get('quarter','period','reporting_period') || detectQuarter(),
    revenue_guidance: get('revenue_guidance','revenue_target','revenue'),
    growth_target:    get('revenue_growth_target','growth_target','revenue_growth'),
    margin_guidance:  [get('ebitda_margin_target','ebitda_margin'), get('pat_margin_target','pat_margin')].filter(Boolean).join(' | ') || get('margin_guidance','margin'),
    capex_plan:       get('capex_plan','capex','capital_expenditure'),
    expansion:        [get('capacity_expansion','capacity'), get('new_products_segments','new_products'), get('geographic_expansion','expansion')].filter(Boolean).join('; ') || null,
    ma_plans:         get('acquisitions_partnerships','acquisitions','m_a'),
    // ── Fields that render as standalone visual blocks in Overview ──
    geographic_presence:  get('geographic_presence','geographic_mix','geographic_expansion','geographic','geography'),
    geographic_mix:       get('geographic_mix','geographic_presence','geographic'),
    geographic_expansion: get('geographic_expansion','expansion_plans','new_markets'),
    key_products_portfolio: get('key_products_portfolio','key_products','products_portfolio','product_mix','segments','key_segments','segment_mix'),
    tone,
    tone_detail:      toneRaw || null,
    key_commitments:  commitRaw ? commitRaw.split(/[;,]|\d[\.\)]/).map(s=>s.trim()).filter(s=>s.length>5) : [],
    eps_estimate:     get('analyst_eps_estimate','eps_estimate','forward_eps'),
    price_target:     get('analyst_price_target','price_target','target_price'),
    analyst_rating:   get('analyst_rating','rating','recommendation'),
    risks_flagged:    risksRaw ? risksRaw.split(/[;,]|\d[\.\)]/).map(s=>s.trim()).filter(s=>s.length>5) : [],
    confidence:       get('confidence_level','confidence') || 'Medium',
    summary:          get('summary','overview','outlook'),
    raw_table:        text,
  };

  return g;
}

// ── Boot ──────────────────────────────────────────────

// ── Guidance JSON — strip raw_table to keep file lean ─────────────
// GUIDANCE STORAGE — concall analysis + AI insights
// Persisted to both localStorage AND GitHub (guidance.json)
// raw_table stripped before GitHub commit to keep file lean
function guidanceForStorage(){
  const out = {};
  Object.entries(GUIDANCE).forEach(([sym, g])=>{
    const { raw_table, ...rest } = g;   // drop raw_table — parsed fields only
    out[sym] = rest;
  });
  return out;
}

// Commit guidance.json to GitHub repo (fire-and-forget)
async function saveGuidanceToGitHub(){
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  if(!token || !repo) return;  // silent — not configured

  const json    = JSON.stringify(guidanceForStorage(), null, 2);
  const encoded = btoa(unescape(encodeURIComponent(json)));
  const headers = { 'Authorization':'token '+token, 'Content-Type':'application/json', 'Accept':'application/vnd.github.v3+json' };
  const fileUrl = 'https://api.github.com/repos/'+repo+'/contents/guidance.json';

  try{
    let sha = null;
    const get = await fetch(fileUrl, {headers});
    if(get.ok){ const d = await get.json(); sha = d.sha; }

    const body = { message:'guidance: update '+new Date().toISOString().slice(0,10), content: encoded };
    if(sha) body.sha = sha;
    const put = await fetch(fileUrl, { method:'PUT', headers, body:JSON.stringify(body) });
    if(put.ok){
      console.log('guidance.json saved to GitHub');
    } else {
      console.warn('guidance.json save failed:', await put.json().catch(()=>({})));
    }
  } catch(e){
    console.warn('saveGuidanceToGitHub error:', e.message);
  }
}

// On boot: fetch guidance.json from GitHub Pages CDN,
// merge with localStorage. GitHub wins for parsed fields;
// localStorage retains raw_table and insights.
async function loadGuidanceFromGitHub(){
  const repo  = S.settings.ghRepo?.trim();
  if(!repo) {
    // Fallback to localStorage
    try{ const c = localStorage.getItem('bm_guidance'); if(c) GUIDANCE = JSON.parse(c); }catch(e){}
    return;
  }
  try{
    // Fetch from GitHub Pages (same-origin CDN, no auth needed)
    const r = await fetch('./guidance.json?t='+Date.now(), {cache:'no-store'});
    if(r.ok){
      const d = await r.json();
      // Merge with localStorage — GitHub is authoritative for saved fields,
      // but raw_table only exists in localStorage (never committed)
      const local = {};
      try{ const c = localStorage.getItem('bm_guidance'); if(c) Object.assign(local, JSON.parse(c)); }catch(e){}
      // Merge: GitHub fields + raw_table from localStorage if same stock
      Object.entries(d).forEach(([sym, g])=>{
        GUIDANCE[sym] = { ...g };
        if(local[sym]?.raw_table) GUIDANCE[sym].raw_table = local[sym].raw_table;
        if(local[sym]?.insights)  GUIDANCE[sym].insights  = local[sym].insights;
      });
      // Also keep any local-only stocks not yet pushed
      Object.entries(local).forEach(([sym, g])=>{
        if(!GUIDANCE[sym]) GUIDANCE[sym] = g;
      });
      console.log('guidance.json loaded from GitHub:', Object.keys(GUIDANCE).length, 'stocks');
    } else {
      // guidance.json not yet in repo — use localStorage
      try{ const c = localStorage.getItem('bm_guidance'); if(c) GUIDANCE = JSON.parse(c); }catch(e){}
    }
  } catch(e){
    console.warn('loadGuidanceFromGitHub error:', e.message);
    try{ const c = localStorage.getItem('bm_guidance'); if(c) GUIDANCE = JSON.parse(c); }catch(e2){}
  }
}

// Write GUIDANCE to localStorage only (no GitHub)
function saveGuidanceLocal(){
  try{ localStorage.setItem('bm_guidance', JSON.stringify(GUIDANCE)); }catch(e){}
}

// Primary save: localStorage + GitHub (always call this)
function saveGuidanceAll(){
  saveGuidanceLocal();
  saveGuidanceToGitHub();  // fire-and-forget
}

// BOOT — initialise app on load
// Order: load state → load fundamentals → load guidance → render

// UPLOAD TAB — all data import, sync, and config in one place
function renderUpload(c){
  const ghOk    = !!(S.settings.ghToken && S.settings.ghRepo);
  const ghColor = S.settings._ghStatus==='ok'?'#00e896':S.settings._ghStatus==='fail'?'#ff6b85':'#4a6888';
  const ghDot   = S.settings._ghStatus==='ok'?'#00d084':S.settings._ghStatus==='fail'?'#ff3b5c':'#4a6888';
  const ghLabel = S.settings._ghStatus==='ok'?'Connected':S.settings._ghStatus==='fail'?'Failed':'Not tested';

  c.innerHTML = `<div style="padding:10px 13px 80px;display:flex;flex-direction:column;gap:12px">

    <!-- ── Section: Portfolio Import ── -->
    <div style="background:var(--card);border:1px solid var(--b1);border-radius:12px;overflow:hidden">
      <div style="padding:10px 13px;background:rgba(249,115,22,.08);border-bottom:1px solid var(--b1)">
        <div style="font-size:12px;font-weight:700;color:var(--ac)">📂 Portfolio Import</div>
        <div style="font-size:9px;color:var(--tx3);margin-top:2px">Load your CDSL holdings into the app</div>
      </div>
      <div style="padding:10px 13px;font-size:10px;color:var(--tx3);line-height:1.8;border-bottom:1px solid var(--b1)">
        <b style="color:var(--gr2)">Recommended — CDSL XLS</b><br>
        CDSL Easiest → Portfolio → Equity Summary Details → Download XLS<br>
        Single file: symbol, sector, qty, avg buy — complete import<br><br>
        <b style="color:var(--yw2)">Fallback — CDSL Text or Manual CSV</b><br>
        Copy-paste from CDSL statement · or type <code style="color:#64b5f6">SYMBOL, QTY, AVG</code> manually<br>
        <span style="color:#ffbf47">⚠ Avg buy not available in CDSL text format</span>
      </div>
      <div style="padding:10px 13px">
        <button onclick="openImport()"
          style="width:100%;padding:11px;background:rgba(249,115,22,.12);border:1px solid rgba(249,115,22,.4);border-radius:8px;color:var(--ac);font-size:12px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif">
          📂 Open Import Panel
        </button>
      </div>
    </div>

    <!-- ── Section: GitHub Config ── -->
    <div style="background:var(--card);border:1px solid var(--b1);border-radius:12px;overflow:hidden">
      <div style="padding:10px 13px;background:rgba(99,102,241,.06);border-bottom:1px solid var(--b1)">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <div style="font-size:12px;font-weight:700;color:#818cf8">⚙ GitHub Config</div>
            <div style="font-size:9px;color:var(--tx3);margin-top:2px">Repo + PAT for auto price/fundamentals fetch</div>
          </div>
          <div style="display:flex;align-items:center;gap:5px">
            <div style="width:8px;height:8px;border-radius:50%;background:${ghDot}"></div>
            <span style="font-size:10px;color:${ghColor}">${ghLabel}</span>
          </div>
        </div>
      </div>

      ${S.settings._lastSync?`
      <div style="padding:7px 13px;font-size:10px;border-bottom:1px solid var(--b1);
        color:${S.settings._lastSyncOk?'#00e896':'#ff6b85'}">
        ${S.settings._lastSyncOk?'✅':'❌'} Last sync: ${new Date(S.settings._lastSync).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:false})} — ${S.settings._lastSyncMsg||''}
      </div>`:''}

      <div style="padding:10px 13px;display:flex;flex-direction:column;gap:8px">
        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
            <span style="font-size:10px;color:var(--tx3)">Anthropic API Key</span>
            <div style="display:flex;align-items:center;gap:5px">
              <div style="width:7px;height:7px;border-radius:50%;background:${S.settings.aiKey?'#00d084':'#4a6888'}"></div>
              <a href="https://console.anthropic.com/settings/keys" target="_blank" style="font-size:9px;color:var(--ac);text-decoration:none">Get key ↗</a>
            </div>
          </div>
          <div style="position:relative">
            <input id="ai-key-inp" type="password" autocomplete="off" autocorrect="off" autocapitalize="off"
              value="${S.settings.aiKey||''}" placeholder="sk-ant-xxxxxxxxxxxx"
              oninput="S.settings.aiKey=this.value.trim();saveSettings()"
              style="width:100%;box-sizing:border-box;background:var(--s1);border:1px solid ${S.settings.aiKey?'rgba(0,208,132,.4)':'var(--b1)'};border-radius:7px;padding:7px 36px 7px 10px;color:var(--tx1);font-size:11px;font-family:var(--mono);outline:none"/>
            <span onclick="toggleKeyVis('ai-key-inp')" style="position:absolute;right:10px;top:50%;transform:translateY(-50%);cursor:pointer;color:var(--tx3)">👁</span>
          </div>
          <div style="font-size:8px;color:var(--mu);margin-top:2px">For AI Guidance · stored locally · never leaves device</div>
        </div>
        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
            <span style="font-size:10px;color:var(--tx3)">Repository</span>
            <div style="width:7px;height:7px;border-radius:50%;background:${S.settings.ghRepo?'#00d084':'#4a6888'}"></div>
          </div>
          <input id="gh-repo-inp" value="${S.settings.ghRepo||''}" placeholder="owner/repo  e.g. Murugkan/bharatmarkets"
            oninput="S.settings.ghRepo=this.value;saveSettings()"
            style="width:100%;box-sizing:border-box;background:var(--s1);border:1px solid ${S.settings.ghRepo?'rgba(0,208,132,.4)':'var(--b1)'};border-radius:7px;padding:7px 10px;color:var(--tx1);font-size:11px;font-family:var(--mono);outline:none"/>
        </div>
        <div>
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
            <span style="font-size:10px;color:var(--tx3)">GitHub PAT</span>
            <div style="display:flex;align-items:center;gap:5px">
              <div style="width:7px;height:7px;border-radius:50%;background:${S.settings.ghToken?'#00d084':'#4a6888'}"></div>
              <a href="https://github.com/settings/tokens/new?scopes=repo,workflow&description=BharatMarkets" target="_blank" style="font-size:9px;color:var(--ac);text-decoration:none">Generate ↗</a>
            </div>
          </div>
          <div style="position:relative">
            <input id="gh-token-inp" type="password" autocomplete="off" autocorrect="off" autocapitalize="off"
              value="${S.settings.ghToken||''}" placeholder="ghp_xxxxxxxxxxxx"
              oninput="S.settings.ghToken=this.value.trim();saveSettings()"
              style="width:100%;box-sizing:border-box;background:var(--s1);border:1px solid ${S.settings.ghToken?'rgba(0,208,132,.4)':'var(--b1)'};border-radius:7px;padding:7px 36px 7px 10px;color:var(--tx1);font-size:11px;font-family:var(--mono);outline:none"/>
            <span onclick="toggleKeyVis('gh-token-inp')" style="position:absolute;right:10px;top:50%;transform:translateY(-50%);cursor:pointer;color:var(--tx3)">👁</span>
          </div>
          <div style="font-size:8px;color:var(--mu);margin-top:2px">Needs scopes: <b>repo</b> + <b>workflow</b></div>
        </div>
      </div>
    </div>

    <!-- ── Section: Data Fetch ── -->
    <div style="background:var(--card);border:1px solid var(--b1);border-radius:12px;overflow:hidden">
      <div style="padding:10px 13px;background:rgba(0,188,212,.06);border-bottom:1px solid var(--b1)">
        <div style="font-size:12px;font-weight:700;color:#4dd0e1">⚡ Data Fetch</div>
        <div style="font-size:9px;color:var(--tx3);margin-top:2px">Trigger GitHub Actions to refresh prices & fundamentals</div>
      </div>
      <div style="padding:10px 13px;font-size:10px;color:var(--tx3);line-height:1.8;border-bottom:1px solid var(--b1)">
        <b style="color:var(--tx2)">Prices</b> — Updated every 15 min during NSE hours (9:15–15:35) via scheduled Action<br>
        <b style="color:var(--tx2)">Fundamentals</b> — Updated daily at 6PM IST via scheduled Action<br>
        Use manual triggers below if you need fresh data immediately.
      </div>
      <div style="padding:10px 13px;display:flex;flex-direction:column;gap:7px">
        <button onclick="manualTriggerWorkflow('prices_only')"
          style="width:100%;padding:10px;background:rgba(0,188,212,.08);border:1px solid rgba(0,188,212,.3);border-radius:8px;color:#4dd0e1;font-size:11px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif;text-align:left">
          ▶ Fetch Prices Now &nbsp;<span style="font-size:9px;opacity:.7">updates prices.json (~2 min)</span>
        </button>
        <button onclick="manualTriggerWorkflow('fundamentals_only')"
          style="width:100%;padding:10px;background:rgba(156,39,176,.08);border:1px solid rgba(156,39,176,.3);border-radius:8px;color:#ce93d8;font-size:11px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif;text-align:left">
          ▶ Fetch Fundamentals Now &nbsp;<span style="font-size:9px;opacity:.7">updates fundamentals.json (~5 min)</span>
        </button>
        <button onclick="manualTriggerWorkflow('all')"
          style="width:100%;padding:10px;background:rgba(245,166,35,.08);border:1px solid rgba(245,166,35,.3);border-radius:8px;color:#ffbf47;font-size:11px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif;text-align:left">
          ▶ Fetch Both Now &nbsp;<span style="font-size:9px;opacity:.7">prices + fundamentals</span>
        </button>
      </div>
    </div>

    <!-- ── Section: Diagnostic ── -->
    <div style="background:var(--card);border:1px solid var(--b1);border-radius:12px;overflow:hidden">
      <div style="padding:10px 13px;background:rgba(99,102,241,.06);border-bottom:1px solid var(--b1)">
        <div style="font-size:12px;font-weight:700;color:#818cf8">🔌 Diagnostic</div>
        <div style="font-size:9px;color:var(--tx3);margin-top:2px">Test GitHub connection · verify workflow · check all 3 steps</div>
      </div>
      <div style="padding:10px 13px;display:flex;flex-direction:column;gap:8px">
        <button onclick="testGitHubConnection()"
          style="width:100%;padding:10px;background:rgba(99,102,241,.1);border:1px solid rgba(99,102,241,.4);border-radius:8px;color:#818cf8;font-size:12px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif">
          🔌 Run Full Diagnostic
        </button>
        <div id="gh-diag" style="display:none;background:var(--bg);border:1px solid var(--b1);border-radius:8px;padding:10px;font-family:'JetBrains Mono',monospace;font-size:10px;line-height:1.9"></div>
        <div id="fetch-result" style="display:none;background:var(--bg);border:1px solid var(--b1);border-radius:8px;padding:10px;font-family:'JetBrains Mono',monospace;font-size:10px"></div>
      </div>
    </div>

    <!-- ── Section: Clear Portfolio ── -->
    <div style="background:var(--card);border:1px solid var(--b1);border-radius:12px;overflow:hidden">
      <div style="padding:10px 13px;background:rgba(255,59,92,.06);border-bottom:1px solid var(--b1)">
        <div style="font-size:12px;font-weight:700;color:#ff6b85">🗑 Clear Portfolio</div>
        <div style="font-size:9px;color:var(--tx3);margin-top:2px">Remove all holdings from the app. Analysis data is kept.</div>
      </div>
      <div style="padding:10px 13px">
        <button onclick="clearPortfolio()"
          style="width:100%;padding:10px;background:rgba(255,59,92,.08);border:1px solid rgba(255,59,92,.3);border-radius:8px;color:#ff6b85;font-size:12px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif">
          🗑 Clear All Holdings
        </button>
      </div>
    </div>

    <!-- ── Section: Push App ── -->
    ${ghOk?`
    <div style="background:var(--card);border:1px solid var(--b1);border-radius:12px;overflow:hidden">
      <div style="padding:10px 13px;background:rgba(99,102,241,.06);border-bottom:1px solid var(--b1)">
        <div style="font-size:12px;font-weight:700;color:#818cf8">⬆ Push App to GitHub</div>
        <div style="font-size:9px;color:var(--tx3);margin-top:2px">Save latest index.html to repo — accessible from any device</div>
      </div>
      <div style="padding:10px 13px">
        <button id="push-btn" onclick="pushIndexToGitHub()"
          style="width:100%;padding:10px;background:rgba(99,102,241,.1);border:1px solid rgba(99,102,241,.35);border-radius:8px;color:#818cf8;font-size:12px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif">
          ⬆ Push index.html to GitHub
        </button>
      </div>
    </div>`:''}

  </div>`;
}

// Load static data from JSON files
async function loadStaticData() {
  try {
    const r = await fetch('./nse_db.json?t=' + Date.now(), {cache:'force-cache'});
    if (r.ok) {
      const d = await r.json();
      NSE_DB   = d.stocks || [];
      ISIN_MAP = d.isin   || {};
      console.log('nse_db.json loaded:', NSE_DB.length, 'stocks,', Object.keys(ISIN_MAP).length, 'ISINs');
    }
  } catch(e) { console.warn('nse_db.json load failed:', e.message); }

  try {
    const r = await fetch('./macro_data.json?t=' + Date.now(), {cache:'force-cache'});
    if (r.ok) {
      MACRO_DATA = await r.json();
      console.log('macro_data.json loaded:', MACRO_DATA.length, 'entries');
    }
  } catch(e) { console.warn('macro_data.json load failed:', e.message); }
}

function boot(){
  loadState();
  loadStaticData().then(()=>{ buildTicker(); render(); });
  buildTicker();
  setInterval(updClock,10000);
  updClock();

  // Render immediately with whatever is in localStorage — never block on network
  render();

  // Then load fresh data in background and re-render when ready
  loadFundamentals()
    .catch(e => console.warn('loadFundamentals failed:', e))
    .then(() => { buildTicker(); render(); });

  loadGuidanceFromGitHub()
    .catch(e => console.warn('loadGuidanceFromGitHub failed:', e))
    .then(() => render());
}
boot();