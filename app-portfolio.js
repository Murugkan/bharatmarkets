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
// FUND, GUIDANCE, fundLoaded, pfRefreshing, pfLastRefresh declared in app-core.js

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
      // Restore timestamp from cache so KPI strip shows it on boot
      if(d.updated && !S.settings._fundUpdated){
        S.settings._fundUpdated = d.updated;
        S.settings._fundStatus  = 'ok';
        saveSettings();
      }
      return;
    }

    // Cache miss or stale — fetch fresh from raw.githubusercontent.com (no Pages lag)
    const repo = S.settings.ghRepo?.trim();
    const fundUrl = repo
      ? `https://raw.githubusercontent.com/${repo}/main/fundamentals.json?t=${Date.now()}`
      : `./fundamentals.json?t=${Date.now()}`;
    const r = await fetch(fundUrl, {cache:'no-store'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const d = await r.json();
    FUND = d.stocks || {};
    fundLoaded = true;

    // Save to cache
    try{
      localStorage.setItem('fund_cache', JSON.stringify(d));
      localStorage.setItem('fund_cache_ts', Date.now().toString());
    } catch(_){ /* storage full — skip cache */ }
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

function computePos(h, f){
  let pos = 0;
  const roe  = f.roe  || h.roe  || 0;
  const pe   = f.pe   || h.pe   || 0;
  const opm  = f.opm_pct || 0;
  const prom = f.prom_pct || h.promoter || 0;
  const chg  = f.chg1d || h.change || 0;
  const ath  = f.ath_pct != null ? f.ath_pct : null;
  const debt = f.debt_eq != null ? f.debt_eq : null;
  if(roe > 15)  pos++;
  if(roe > 20)  pos++;
  if(pe > 0 && pe < 18) pos++;
  if(opm > 15)  pos++;
  if(prom > 50) pos++;
  if(chg > 1)   pos++;
  if(ath !== null && ath > -10) pos++;
  if(debt !== null && debt < 0.5) pos++;
  return pos;
}

function computeNeg(h, f){
  let neg = 0;
  const roe  = f.roe  || h.roe  || 0;
  const pe   = f.pe   || h.pe   || 0;
  const opm  = f.opm_pct || 0;
  const prom = f.prom_pct || h.promoter || 0;
  const chg  = f.chg1d || h.change || 0;
  const ath  = f.ath_pct != null ? f.ath_pct : null;
  const debt = f.debt_eq != null ? f.debt_eq : null;
  if(roe > 0 && roe < 8)  neg++;
  if(pe > 35)  neg++;
  if(opm > 0 && opm < 8)  neg++;
  if(prom > 0 && prom < 35) neg++;
  if(chg < -1) neg++;
  if(ath !== null && ath < -30) neg++;
  if(debt !== null && debt > 1.5) neg++;
  return neg;
}

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
    pos:       f.pos || computePos(h, f),
    neg:       f.neg || computeNeg(h, f),
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
  if(v===null||v===undefined||isNaN(v)) return '<span class="u-dark">—</span>';
  return prefix+Number(v).toFixed(dp)+suffix;
}
function fnCr(v){
  if(v===null||v===undefined||isNaN(v)) return '<span class="u-dark">—</span>';
  if(v>=100000) return (v/100000).toFixed(1)+'LCr';
  if(v>=1000)   return (v/1000).toFixed(1)+'KCr';
  return v.toFixed(0)+'Cr';
}

// ── MAIN RENDER ────────────────────────────────────────
// PORTFOLIO TAB — Bloomberg-style 29-column screener
// Data: portfolio holdings (CDSL import) + fundamentals.json


function normSector(raw){
  const map={
    'Auto Ancillaries':'Auto','Automobiles':'Auto',
    'Banks':'Banking','Bank':'Banking',
    'Pharmaceutical':'Pharma','Pharmaceuticals':'Pharma',
    'IT - Software':'IT','Information Technology':'IT','Technology':'IT',
    'Telecomm Equipment & Infra Services':'Telecom',
    'Telecom Services':'Telecom','Communication Services':'Telecom',
    'Power Generation & Distribution':'Power',
    'Utilities':'Power','POWER':'Power',
    'Capital Goods-Non Electrical Equipment':'Capital Goods',
    'Capital Goods - Electrical Equipment':'Capital Goods',
    'Industrials':'Capital Goods',
    'Infrastructure Developers & Operators':'Infrastructure',
    'Ship Building':'Defence',
    'Non Ferrous Metals':'Metals','Basic Materials':'Metals',
    'Mining & Mineral products':'Mining',
    'Consumer Durables':'Consumer','Consumer Cyclical':'Consumer',
    'Consumer Defensive':'FMCG','Tobacco Products':'FMCG',
    'Miscellaneous':'Diversified','Others':'Diversified',
    'Other':'Diversified','Services':'Diversified',
    'Refineries':'Energy','Crude Oil & Natural Gas':'Energy',
    'Financial Services':'Finance',
    'Health Care':'Pharma','Healthcare':'Pharma',
    'Shipping':'Infrastructure','Steel':'Metals',
    'Construction':'Infrastructure','Trading':'Diversified',
  };
  return map[raw]||raw;
}

function sortRows(rows, skey, sdir) {
  rows.sort((a,b) => {
    let av, bv;
    switch(skey) {
      case 'sym':    av=a.sym; bv=b.sym; break;
      case 'sector': av=normSector(a.sector||''); bv=normSector(b.sector||''); break;
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
      case 'ath':    av=a.ath_pct!=null?a.ath_pct:-9999; bv=b.ath_pct!=null?b.ath_pct:-9999; break;
      case 'w52':    av=a.w52_pct!=null?a.w52_pct:-9999; bv=b.w52_pct!=null?b.w52_pct:-9999; break;
      default:       av=a.qty*(a.ltp||0); bv=b.qty*(b.ltp||0);
    }
    if(typeof av==='string') return sdir==='asc'?av.localeCompare(bv):bv.localeCompare(av);
    return sdir==='asc'?av-bv:bv-av;
  });
}

function renderPortfolio(c){
  // Don't nuke DOM if user is actively typing in search — just update tbody
  const activeEl = document.activeElement;
  if(activeEl && activeEl.id === 'pf-search'){
    const tbody = document.getElementById('bls-tbody');
    if(tbody){
      const pf2 = S.portfolio.map(mergeHolding);
      const filt2 = S.pfFilter||'All';
      const srch2 = S.pfSearch.trim();
      const sec2  = S.pfSector||'';
      let rows2 = filt2==='All' ? [...pf2] : pf2.filter(h=>h.signal===filt2);
      if(srch2) rows2 = rows2.filter(h=>h.sym.includes(srch2)||(h.name||'').toUpperCase().includes(srch2));
      if(sec2)  rows2 = rows2.filter(h=>(h.sector||'').includes(sec2));
      sortRows(rows2, S.pfSort||'wt', S.pfSortDir||'desc');
      const totalCur2 = pf2.filter(h=>h.ltp>0).reduce((a,h)=>a+h.qty*h.ltp,0);
      tbody.innerHTML = renderBLSRows(rows2, totalCur2);
      return;
    }
  }
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
    <div class="kpi-v" class="u-dim">₹${(totalCur/100000).toFixed(2)}L</div>
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
  <input id="pf-search" type="text" value="${S.pfSearch||''}"
    placeholder="Search…"
    autocorrect="off" autocapitalize="characters" autocomplete="off" spellcheck="false"
    oninput="pfSearchUpdate(this.value)"
    style="width:72px;flex-shrink:0;background:#0d1525;border:1px solid #182840;border-radius:4px;
    padding:4px 6px;color:#f0f6ff;font-size:11px;font-family:'JetBrains Mono',monospace;
    outline:none;text-transform:uppercase"/>
  <div class="tb-chips">
    ${['All','BUY','SELL','HOLD'].map(f=>`<div class="tb-chip ${(S.pfFilter||'All')===f?'on':''}" onclick="setPfFilter('${f}')">${f}</div>`).join('')}
    <div class="tb-chip ${S.pfSort==='chg1d'?'on':''}" onclick="togglePfSort('chg1d')">%1D ${S.pfSort==='chg1d'?(S.pfSortDir==='desc'?'↓':'↑'):''}</div>
  </div>
  <button onclick="showPfDebug()" style="flex-shrink:0;background:rgba(100,181,246,.1);border:1px solid rgba(100,181,246,.3);border-radius:4px;padding:4px 8px;color:#64b5f6;font-size:9px;font-weight:700;cursor:pointer;font-family:'JetBrains Mono',monospace">DBG</button>
</div>

<!-- ── 37-Column Bloomberg Screener Table ── -->
<div class="bls-table-outer">
<table class="bls-t" id="bls-tbl">
<thead><tr>
  <th class="th-l th-fix th-fix1" onclick="togglePfSort('sym')">${pfSortArrow('sym')}Ticker</th>
  <th class="th-l th-fix th-fix2" onclick="togglePfSort('sector')" class="u-ptr">${pfSortArrow('sector')}Sector</th>
  <th title="Bullish signals" onclick="togglePfSort('pos')" class="u-ptr">${pfSortArrow('pos')}Pos</th>
  <th title="Bearish signals" onclick="togglePfSort('neg')" class="u-ptr">${pfSortArrow('neg')}Neg</th>
  <th onclick="togglePfSort('ath')"  class="${S.pfSort==='ath'?'sorted':''}">${pfSortArrow('ath')}ATH%</th>
  <th onclick="togglePfSort('w52')"  class="${S.pfSort==='w52'?'sorted':''}">${pfSortArrow('w52')}52W%</th>
  <th onclick="togglePfSort('prom')" class="${S.pfSort==='prom'?'sorted':''}">${pfSortArrow('prom')}Prom%</th>
  <th title="Pledge %" onclick="togglePfSort('pledge')" class="u-ptr">${pfSortArrow('pledge')}Pl%</th>
  <th title="Public holding %" onclick="togglePfSort('pub')" class="u-ptr">${pfSortArrow('pub')}Pub%</th>
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
  // Use filtered rows so grand total matches visible rows
  const totCur   = rows.filter(h=>h.ltp>0).reduce((a,h)=>a+h.qty*h.ltp, 0);
  const totInvPr = rows.filter(h=>h.ltp>0).reduce((a,h)=>a+h.qty*(h.avgBuy||0), 0);
  const totPnL   = totCur - totInvPr;
  const totPnLPct= totInvPr>0 ? (totPnL/totInvPr*100) : 0;
  const pnlUp    = totPnL >= 0;
  const pnlCol   = pnlUp ? '#00e896' : '#ff6b85';
  const cells = Array(29).fill('<td></td>');
  cells[0]  = '<td class="td-l td-fix td-fix1" style="color:#8eb0d0;font-size:9px;letter-spacing:.5px;text-transform:uppercase">TOTAL</td>';
  cells[25] = '<td style="color:'+pnlCol+'">'+(pnlUp?'+':'')+'₹'+(Math.abs(totPnL)/100000).toFixed(2)+'L</td>';
  cells[26] = '<td style="color:'+pnlCol+'">'+(totPnLPct>=0?'+':'')+totPnLPct.toFixed(2)+'%</td>';
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
  <div><span class="u-cyn">1</span> — Re-import your portfolio (triggers auto-sync)</div>
  <div><span class="u-cyn">2</span> — Wait ~5 min → tap ↻ Refresh</div>
  <div><span class="u-cyn">3</span> — If still empty → run diagnostic in Watchlist → GitHub Sync</div>
  ` : `
  <div><span class="u-cyn">1</span> — Configure GitHub in <b style="color:#fff">Watchlist → GitHub Sync</b> (repo + PAT)</div>
  <div><span class="u-cyn">2</span> — Run diagnostic to verify connection</div>
  <div><span class="u-cyn">3</span> — Re-import portfolio → data auto-fetches (~5 min)</div>
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
      <td class="u-dark">—</td>
      <td>${fn(h.public_pct,1,'','%')}</td>
      <td>${fn(h.pb,1,'','x')}</td>
      <td class="u-dim">${fn(h.eps,1,'₹')}</td>
      <td>${fnCr(h.sales)}</td>
      <td style="${h.cfo>0?'background:#003a20;color:#fff':'background:#3a0010;color:#fff'}">${fnCr(h.cfo)}</td>
      <td style="${cROE}">${fn(h.roe,1,'','%')}</td>
      <td style="${cPE}">${fn(h.pe,1,'','x')}</td>
      <td style="color:#8eb0d0;font-size:8px;max-width:90px;text-align:left;overflow:hidden;text-overflow:ellipsis">${trunc(h.name,12)}</td>
      <td style="${cOPM}">${fn(h.opm_pct,1,'','%')}</td>
      <td>${fnCr(h.ebitda)}</td>
      <td style="${cNPM}">${fn(h.npm_pct,1,'','%')}</td>
      <td class="u-muted">${fnCr(h.mcap)}</td>
      <td style="${c1d}">${h.chg1d>=0?'+':''}${fn(h.chg1d,2,'','%')}</td>
      <td style="${c5d}">${h.chg5d>=0?'+':''}${fn(h.chg5d,2,'','%')}</td>
      <td style="${ltp>0?(h.chg1d>0?'background:#003a20;color:#fff':h.chg1d<0?'background:#3a0010;color:#fff':'color:#f0f6ff'):'color:#4a6888'};font-weight:${ltp>0?'600':'400'}">
        ${ltp>0?'₹'+ltp.toFixed(1):'<span style="font-size:7px;background:rgba(245,166,35,.15);border:1px solid rgba(245,166,35,.3);color:#ffbf47;padding:1px 4px;border-radius:3px">NO PRICE</span>'}
      </td>
      <td class="u-muted">${h.qty.toLocaleString('en-IN')}</td>
      <td style="${h.avgBuy>0?'background:#3a1a00;color:#fff;font-weight:600':'color:#3a5a72'}">${h.avgBuy>0?'₹'+h.avgBuy.toFixed(1):'—'}</td>
      <td style="${ltp>0?cPnL:'color:#3a5a72'}">${ltp>0?(pnl>=0?'+':'')+pnl.toFixed(0):'—'}</td>
      <td style="${ltp>0?cPnL:'color:#3a5a72'}">${ltp>0&&pnlP!=null?(pnlP>=0?'+':'')+pnlP.toFixed(1)+'%':'—'}</td>
      <td class="u-muted">${wt.toFixed(1)}%</td>
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
  const strCols = new Set(['sym','sector','name','sig']);
  if(S.pfSort===k) S.pfSortDir=S.pfSortDir==='desc'?'asc':'desc';
  else{ S.pfSort=k; S.pfSortDir=strCols.has(k)?'asc':'desc'; }
  render();
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
    // Fetch from raw.githubusercontent.com — bypasses GitHub Pages CDN lag (~5min)
    // Pages serves cached files; raw always reflects latest commit immediately
    const repo = S.settings.ghRepo?.trim();
    const url = repo
      ? `https://raw.githubusercontent.com/${repo}/main/prices.json?t=${Date.now()}`
      : `./prices.json?t=${Date.now()}`;
    const r = await fetch(url, {cache:'no-store'});
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
        // Also update FUND cache with fresh prices.json fields
        // This bypasses the 1-hour fundamentals cache for price-derived fields
        if(FUND[h.sym]){
          if(q.changePct != null) FUND[h.sym].chg1d  = q.changePct;
          if(q.pe        != null) FUND[h.sym].pe      = q.pe;
          if(q.pb        != null) FUND[h.sym].pb      = q.pb;
          if(q.eps       != null) FUND[h.sym].eps     = q.eps;
          if(q.roe       != null) FUND[h.sym].roe     = q.roe;
          if(q.w52h      != null) FUND[h.sym].w52h    = q.w52h;
          if(q.w52l      != null) FUND[h.sym].w52l    = q.w52l;
          if(q.opm       != null) FUND[h.sym].opm_pct = q.opm;
          if(q.npm       != null) FUND[h.sym].npm_pct = q.npm;
          if(q.ltp       != null) FUND[h.sym].ltp     = q.ltp;
        }
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
  const info=FUND[sym]||{name:sym,sector:'Diversified'};
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
        autoSyncPortfolioSymbols();
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

function showPfDebug(){
  const out = [];
  const pfSyms = S.portfolio.map(h=>h.sym);

  out.push('=== PORTFOLIO DEBUG ===');
  out.push('Total stocks: ' + pfSyms.length);
  out.push('');

  out.push('=== FUND keys in memory: ' + Object.keys(FUND).length + ' ===');
  out.push(Object.keys(FUND).join(', ') || '(none)');
  out.push('');

  out.push('=== Per stock: sym | resolved | ltp | has FUND ===');
  S.portfolio.forEach(h => {
    const f = FUND[h.sym] || null;
    const hasFund = !!f;
    const hasLtp  = f && f.ltp > 0;
    out.push(
      h.sym.padEnd(16) +
      ' ltp='    + (h.ltp||h.liveLtp||0) +
      ' FUND='   + (hasFund ? 'YES' : 'NO') +
      (hasFund ? ' f.ltp='+f.ltp+' f.pe='+f.pe+' f.roe='+f.roe : '')
    );
  });
  out.push('');

  out.push('=== ISIN_MAP: ' + Object.keys(ISIN_MAP).length + ' entries ===');
  out.push('');

  out.push('=== Stocks NOT in FUND ===');
  S.portfolio.forEach(h => {
    if(!FUND[h.sym]) out.push('  ' + h.sym.padEnd(16) + ' isin=' + (h.isin||'—') + ' ISIN_MAP=' + (ISIN_MAP[h.isin]||'—'));
  });

  // Show modal
  const modal = document.createElement('div');
  modal.style.cssText = 'position:fixed;inset:0;z-index:999;background:rgba(0,0,0,.85);display:flex;flex-direction:column;padding:16px;';
  modal.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <span style="font-family:'Syne',sans-serif;font-size:14px;font-weight:700;color:#64b5f6">Portfolio Debug</span>
      <button onclick="this.closest('div[style]').remove()" style="background:none;border:1px solid #4a6888;border-radius:6px;color:#8eb0d0;padding:4px 10px;cursor:pointer;font-size:11px">✕ Close</button>
    </div>
    <pre style="flex:1;overflow-y:auto;font-family:'JetBrains Mono',monospace;font-size:9px;color:#c8dff5;background:#02040a;border:1px solid #1e3350;border-radius:8px;padding:10px;white-space:pre-wrap;word-break:break-all">${out.join('\n')}</pre>`;
  document.body.appendChild(modal);
}
