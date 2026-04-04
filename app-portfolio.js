// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE
//  Data sources:
//    prices.json       → LTP, %1D, %5D, P/E, P/B, EPS, MCAP, 52Wk
//    fundamentals.json → ATH%, Prom%, Pledge%, OPM%, NPM%, ROE,
//                        Sales, CFO, EBITDA, Signal, Pos, Neg
//
//  Globals declared in app-core.js:
//    FUND, fundLoaded, pfRefreshing, pfLastRefresh, S, ISIN_MAP
// ─────────────────────────────────────────────────────────────

// ── Style constants ───────────────────────────────────────────
const CSS = {
  GRN:    'background:#003a20;color:#fff',
  GRN_B:  'background:#003a20;color:#fff;font-weight:600',
  GRN_BD: 'background:#003a20;color:#fff;font-weight:700',
  RED:    'background:#3a0010;color:#fff',
  RED_B:  'background:#3a0010;color:#fff;font-weight:600',
  RED_BD: 'background:#3a0010;color:#fff;font-weight:700',
  AMB:    'background:#3a1a00;color:#fff;font-weight:600',
  NEU:    'color:#c8dff5',
  DIM:    'color:#4a6888',
};

// ── Column definitions ────────────────────────────────────────
const TH_COLS = [
  ['sym',    'Ticker'],
  ['sector', 'Sector'],
  ['pos',    'Pos',   'Bullish signals'],
  ['neg',    'Neg',   'Bearish signals'],
  ['ath',    'ATH%'],
  ['w52',    '52W%'],
  ['prom',   'Prom%'],
  ['pledge', 'Pl%',  'Pledge %'],
  ['pub',    'Pub%', 'Public holding %'],
  ['pb',     'P/B'],
  ['eps',    'EPS'],
  ['sales',  'Sales'],
  ['cfo',    'CFO'],
  ['roe',    'ROE%'],
  ['pe',     'P/E'],
  ['name',   'Name'],
  ['opm',    'OPM%'],
  ['ebi',    'EBI'],
  ['npm',    'NPM%'],
  ['mcap',   'MCAP'],
  ['chg1d',  '%1D'],
  ['chg5d',  '%5D'],
  ['ltp',    'LTP'],
  ['qty',    'Qty'],
  ['avg',    'Avg'],
  ['pnl',    'P&L'],
  ['pnlpct', 'P&L%'],
  ['wt',     'Wt%'],
  ['sig',    'Sig'],
];

const FIX_COLS = new Set(['sym','sector']);
const STR_COLS = new Set(['sym','sector','name','sig']);

const SECTOR_MAP = {
  'Auto Ancillaries':'Auto','Automobiles':'Auto',
  'Banks':'Banking','Bank':'Banking',
  'Pharmaceutical':'Pharma','Pharmaceuticals':'Pharma',
  'IT - Software':'IT','Information Technology':'IT',
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
  'Other':'Diversified','Services':'Diversified','Trading':'Diversified',
  'Refineries':'Energy','Crude Oil & Natural Gas':'Energy',
  'Financial Services':'Finance',
  'Health Care':'Pharma','Healthcare':'Pharma',
  'Shipping':'Infrastructure','Steel':'Metals',
  'Construction':'Infrastructure',
  'Technology':'IT','Real Estate':'Real Estate','Energy':'Energy',
  'Dry cells':'Capital Goods','Cables':'Capital Goods',
  'Alcoholic Beverages':'Consumer',
  'ETF':'Diversified','Finance':'Finance',
  'Insurance':'Finance','Entertainment':'Consumer','Retail':'Consumer',
};

// ─────────────────────────────────────────────────────────────
//  SECTION 1 — Pure utility functions
// ─────────────────────────────────────────────────────────────

function cellColor(val, goodAbove, badBelow) {
  if(val==null||isNaN(val)) return 'color:var(--tx3)';
  if(val>=goodAbove) return 'color:var(--gr2)';
  if(val<=badBelow)  return 'color:var(--rd2)';
  return 'color:var(--yw2)';
}

function round2(n){ return Math.round(n*100)/100; }

function normSector(raw){
  if(!raw || raw==='—') return '—';
  return SECTOR_MAP[raw] || raw;
}

function cc(val, greenAbove, redBelow){
  if(val===null||val===undefined||isNaN(val)) return '';
  if(val>=greenAbove) return CSS.GRN_B;
  if(val<=redBelow)   return CSS.RED_B;
  return CSS.NEU;
}

function rowBg(sig){
  if(sig==='BUY')  return 'background:rgba(0,160,80,.13)';
  if(sig==='SELL') return 'background:rgba(200,30,50,.13)';
  return '';
}

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

function computePos(h, f){
  let pos=0;
  const roe=f.roe||h.roe||0, pe=f.pe||h.pe||0, opm=f.opm_pct||0;
  const prom=f.prom_pct||h.promoter||0, chg=f.chg1d||h.change||0;
  const ath=f.ath_pct??null, debt=f.debt_eq??null;
  if(roe>15) pos++;
  if(roe>20) pos++;
  if(pe>0&&pe<18) pos++;
  if(opm>15) pos++;
  if(prom>50) pos++;
  if(chg>1)  pos++;
  if(ath!==null&&ath>-10) pos++;
  if(debt!==null&&debt<0.5) pos++;
  return pos;
}

function computeNeg(h, f){
  let neg=0;
  const roe=f.roe||h.roe||0, pe=f.pe||h.pe||0, opm=f.opm_pct||0;
  const prom=f.prom_pct||h.promoter||0, chg=f.chg1d||h.change||0;
  const ath=f.ath_pct??null, debt=f.debt_eq??null;
  if(roe>0&&roe<8) neg++;
  if(pe>35) neg++;
  if(opm>0&&opm<8) neg++;
  if(prom>0&&prom<35) neg++;
  if(chg<-1) neg++;
  if(ath!==null&&ath<-30) neg++;
  if(debt!==null&&debt>1.5) neg++;
  return neg;
}

function calcSignalLocal(h, f){
  let pos=0, neg=0;
  const roe=h.roe||f.roe||0, pe=h.pe||f.pe||0;
  const chg=h.change||0, prom=h.promoter||f.prom_pct||0;
  if(roe>15) pos++; else if(roe<8) neg++;
  if(pe>0&&pe<18) pos++; else if(pe>35) neg++;
  if(chg>1) pos++; else if(chg<-1) neg++;
  if(prom>50) pos++; else if(prom&&prom<35) neg++;
  const net=pos-neg;
  return net>=2?'BUY':net<=-2?'SELL':'HOLD';
}

function mergeHolding(h){
  const f=FUND[h.sym]||{};
  const liveLtp=h.liveLtp||f.ltp||0;
  return {
    sym:        h.sym,
    isin:       h.isin||'',
    name:       f.name||h.name||h.sym,
    sector:     normSector(f.sector||h.sector||'—'),
    qty:        h.qty||0,
    avgBuy:     h.avgBuy||0,
    ltp:        liveLtp,
    chg1d:      h.change||f.chg1d||0,
    chg5d:      f.chg5d||0,
    pe:         h.pe??f.pe??null,
    pb:         h.pb??f.pb??null,
    eps:        h.eps??f.eps??null,
    roe:        h.roe??f.roe??null,
    roce:       h.roce??f.roce??null,
    mcap:       h.mcapRaw ? h.mcapRaw/1e7 : (f.mcap??null),
    w52h:       h.week52H??f.w52h??null,
    w52l:       h.week52L??f.w52l??null,
    w52_pct:    (liveLtp&&(h.week52H??f.w52h))
                  ? round2((liveLtp/(h.week52H??f.w52h)-1)*100)
                  : (f.w52_pct??null),
    ath:        f.ath??null,
    ath_pct:    f.ath_pct??null,
    prom_pct:   f.prom_pct??h.promoter??null,
    public_pct: f.public_pct??null,
    opm_pct:    f.opm_pct??h.ebitdaMargin??null,
    npm_pct:    f.npm_pct??h.netMargin??null,
    ebitda:     f.ebitda??null,
    sales:      f.sales??null,
    cfo:        f.cfo??null,
    signal:     f.signal||calcSignalLocal(h,f),
    pos:        f.pos||computePos(h,f),
    neg:        f.neg||computeNeg(h,f),
  };
}

function calcPortfolioTotals(pf){
  const priced   = pf.filter(h=>h.ltp>0);
  const totalInv = pf.reduce((a,h)=>a+h.qty*(h.avgBuy||0), 0);
  const totalCur = priced.reduce((a,h)=>a+h.qty*h.ltp, 0);
  const invPriced= priced.reduce((a,h)=>a+h.qty*(h.avgBuy||0), 0);
  const totalPnL = totalCur-invPriced;
  const pnlPct   = invPriced>0 ? totalPnL/invPriced*100 : 0;
  const dayPnL   = priced.reduce((a,h)=>{ const c=h.chg1d||0; return a+h.qty*h.ltp*c/(100+c); },0);
  return {
    priced, totalInv, totalCur, invPriced, totalPnL, pnlPct, dayPnL,
    gainers: pf.filter(h=>h.chg1d>0).length,
    losers:  pf.filter(h=>h.chg1d<0).length,
    buys:    pf.filter(h=>h.signal==='BUY').length,
    sells:   pf.filter(h=>h.signal==='SELL').length,
  };
}

function calcSectorMap(pf){
  const sMap={};
  pf.forEach(h=>{
    const s=h.sector||'Other';
    sMap[s]=(sMap[s]||0)+h.qty*(h.ltp||h.avgBuy||0);
  });
  const sTotal=Object.values(sMap).reduce((a,b)=>a+b,0)||1;
  const sectors=Object.entries(sMap).sort((a,b)=>b[1]-a[1]).slice(0,10);
  return {sMap, sTotal, sectors};
}

function filterRows(pf, filt, secFilt, srch){
  let rows = filt==='All' ? [...pf] : pf.filter(h=>h.signal===filt);
  if(secFilt) rows=rows.filter(h=>h.sector===secFilt);
  if(srch)    rows=rows.filter(h=>h.sym.includes(srch)||(h.name||'').toUpperCase().includes(srch));
  return rows;
}

function sortRows(rows, skey, sdir){
  rows.sort((a,b)=>{
    let av,bv;
    switch(skey){
      case 'sym':    av=a.sym;       bv=b.sym;       break;
      case 'sector': av=a.sector||'—'; bv=b.sector||'—'; break;
      case 'pos':    av=a.pos||0;    bv=b.pos||0;    break;
      case 'neg':    av=a.neg||0;    bv=b.neg||0;    break;
      case 'pub':    av=a.public_pct||0; bv=b.public_pct||0; break;
      case 'name':   av=a.name||'';  bv=b.name||'';  break;
      case 'chg1d':  av=a.chg1d||0; bv=b.chg1d||0;  break;
      case 'pe':     av=a.pe||999;   bv=b.pe||999;   break;
      case 'roe':    av=a.roe||0;    bv=b.roe||0;    break;
      case 'mcap':   av=a.mcap||0;   bv=b.mcap||0;   break;
      case 'ltp':    av=a.ltp||0;    bv=b.ltp||0;    break;
      case 'qty':    av=a.qty||0;    bv=b.qty||0;    break;
      case 'pnl':    av=a.ltp>0?a.qty*a.ltp-a.qty*a.avgBuy:-Infinity;
                     bv=b.ltp>0?b.qty*b.ltp-b.qty*b.avgBuy:-Infinity; break;
      case 'wt':     av=a.ltp>0?a.qty*a.ltp:0; bv=b.ltp>0?b.qty*b.ltp:0; break;
      case 'ath':    av=a.ath_pct??-9999; bv=b.ath_pct??-9999; break;
      default:       av=a.qty*(a.ltp||0); bv=b.qty*(b.ltp||0);
    }
    if(typeof av==='string') return sdir==='asc'?av.localeCompare(bv):bv.localeCompare(av);
    return sdir==='asc'?av-bv:bv-av;
  });
}

// ─────────────────────────────────────────────────────────────
//  SECTION 2 — HTML fragment builders
// ─────────────────────────────────────────────────────────────

function sigBadge(sig){
  const c={BUY:{bg:'#00a050',bd:'#00d084'},SELL:{bg:'#c01e32',bd:'#ff3b5c'},HOLD:{bg:'#7a6010',bd:'#f5a623'}}[sig]
    ||{bg:'#1a3050',bd:'#4a6888'};
  return `<span style="display:inline-block;font-size:8px;font-weight:800;padding:2px 7px;border-radius:3px;letter-spacing:.6px;background:${c.bg};border:1px solid ${c.bd};color:#fff">${sig}</span>`;
}

function pfSortArrow(k){
  if(S.pfSort!==k) return '';
  return S.pfSortDir==='asc'
    ? '<span style="color:#64b5f6;margin-right:2px">↑</span>'
    : '<span style="color:#64b5f6;margin-right:2px">↓</span>';
}

function renderTableHead(){
  const ths=TH_COLS.map(([k,label,title])=>{
    const fix  = FIX_COLS.has(k) ? (k==='sym'?'th-l th-fix th-fix1':'th-l th-fix th-fix2') : '';
    const sort = S.pfSort===k ? 'sorted' : '';
    const ttl  = title ? `title="${title}"` : '';
    return `<th class="${fix} ${sort}" ${ttl} onclick="togglePfSort('${k}')">${pfSortArrow(k)}${label}</th>`;
  }).join('');
  return `<thead><tr>${ths}</tr></thead>`;
}
function renderKpiStrip(t, pf){
  const pnlUp=t.totalPnL>=0, dayUp=t.dayPnL>=0;
  const pCol=pnlUp?'#00e896':'#ff6b85', dCol=dayUp?'#00e896':'#ff6b85';
  const ps=S.settings._pricesStatus, fs=S.settings._fundStatus;
  const pDot=ps==='ok'?'#00d084':ps==='fail'?'#ff3b5c':'#4a6888';
  const fDot=fs==='ok'?'#00d084':fs==='stale'?'#ffbf47':'#4a6888';
  const pTxt=ps==='ok'?'#00e896':ps==='fail'?'#ff6b85':'#4a6888';
  const fTxt=fs==='ok'?'#00e896':fs==='stale'?'#ffbf47':'#4a6888';
  const fmtTs=(ts)=>ts?new Date(ts).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:false}):'—';
  return `<div class="kpi-strip" id="kpi-strip-el">
  <div class="kpi"><div class="kpi-l">Invested</div>
    <div class="kpi-v" style="color:#64b5f6">₹${(t.totalInv/100000).toFixed(2)}L</div>
    <div class="kpi-s">${pf.length} stocks</div></div>
  <div class="kpi"><div class="kpi-l">Mkt Value</div>
    <div class="kpi-v">₹${(t.totalCur/100000).toFixed(2)}L</div>
    <div class="kpi-s">${t.priced.length}/${pf.length} priced</div></div>
  <div class="kpi"><div class="kpi-l">Total P&L</div>
    <div class="kpi-v" style="color:${pCol}">₹${(Math.abs(t.totalPnL)/100000).toFixed(2)}L</div>
    <div class="kpi-s" style="color:${pnlUp?'#00d084':'#ff3b5c'}">${t.pnlPct.toFixed(2)}%</div></div>
  <div class="kpi"><div class="kpi-l">Day P&L</div>
    <div class="kpi-v" style="color:${dCol}">${dayUp?'+':''}₹${(Math.abs(t.dayPnL)/100000).toFixed(2)}L</div>
    <div class="kpi-s">${t.gainers}▲ ${t.losers}▼</div></div>
  <div class="kpi-status">
    <div class="kpi-srow" onclick="headerPricesTap()">
      <span class="kpi-sdot" style="background:${pDot}"></span>
      <span class="kpi-slbl" style="color:${pTxt}">prices ${fmtTs(S.settings._pricesUpdated)}</span>
      <span class="kpi-sico" id="hdr-prices-spin">↻</span></div>
    <div class="kpi-srow" onclick="headerFundTap()">
      <span class="kpi-sdot" style="background:${fDot}"></span>
      <span class="kpi-slbl" style="color:${fTxt}">fund ${fmtTs(S.settings._fundUpdated)}</span>
      <span class="kpi-sico" id="hdr-fund-spin">↻</span></div>
  </div></div>`;
}

function renderSectorBar(sectors, sTotal){
  const segs=sectors.map(([s,v])=>
    `<div class="sec-bar-seg" style="width:${(v/sTotal*100).toFixed(1)}%;background:${sectorColor(s)}" title="${s} ${(v/sTotal*100).toFixed(1)}%"></div>`
  ).join('');
  const allActive=!S.pfSector;
  const items=sectors.map(([s,v])=>{
    const on=S.pfSector===s;
    const col=sectorColor(s);
    return `<div class="sec-leg-item ${on?'sec-leg-active':''}" onclick="setSectorFilter('${s}')"
      style="cursor:pointer;border:1px solid ${on?col:'transparent'};border-radius:4px;padding:1px 5px;color:${on?col:'#5878a8'}">
      <div class="sec-leg-dot" style="background:${col}"></div>${s} ${(v/sTotal*100).toFixed(0)}%</div>`;
  }).join('');
  return `<div class="sec-bar">${segs}</div>
<div class="sec-legend">
  <div class="sec-leg-item ${allActive?'sec-leg-active':''}" onclick="setSectorFilter('')"
    style="cursor:pointer;border:1px solid ${allActive?'#4a6888':'transparent'};border-radius:4px;padding:1px 5px">All</div>
  ${items}</div>`;
}

function renderToolbar(){
  const chips=['All','BUY','SELL','HOLD'].map(f=>
    `<div class="tb-chip ${(S.pfFilter||'All')===f?'on':''}" onclick="setPfFilter('${f}')">${f}</div>`
  ).join('');
  const s1d=S.pfSort==='chg1d', dir=S.pfSortDir==='desc'?'↓':'↑';
  return `<div class="bls-tb" style="gap:6px;flex-wrap:nowrap">
  <input id="pf-search" type="text" value="${S.pfSearch||''}" placeholder="Search…"
    autocorrect="off" autocapitalize="characters" autocomplete="off" spellcheck="false"
    oninput="pfSearchUpdate(this.value)"
    style="width:72px;flex-shrink:0;background:#0d1525;border:1px solid #182840;border-radius:4px;
    padding:4px 6px;color:#f0f6ff;font-size:11px;font-family:'JetBrains Mono',monospace;
    outline:none;text-transform:uppercase"/>
  <div class="tb-chips">${chips}
    <div class="tb-chip ${s1d?'on':''}" onclick="togglePfSort('chg1d')">%1D ${s1d?dir:''}</div></div>
  <button onclick="showPfDebug()" style="flex-shrink:0;background:rgba(100,181,246,.1);border:1px solid rgba(100,181,246,.3);border-radius:4px;padding:4px 8px;color:#64b5f6;font-size:9px;font-weight:700;cursor:pointer;font-family:'JetBrains Mono',monospace">DBG</button>
</div>`;
}

function renderTableFoot(rows){
  const priced=rows.filter(h=>h.ltp>0);
  const totCur=priced.reduce((a,h)=>a+h.qty*h.ltp,0);
  const totInv=priced.reduce((a,h)=>a+h.qty*(h.avgBuy||0),0);
  const totPnL=totCur-totInv;
  const totPct=totInv>0?totPnL/totInv*100:0;
  const up=totPnL>=0, col=up?'#00e896':'#ff6b85';
  const cells=Array(29).fill('<td></td>');
  cells[0] ='<td class="td-l td-fix td-fix1" style="color:#8eb0d0;font-size:9px;letter-spacing:.5px;text-transform:uppercase">TOTAL</td>';
  cells[25]=`<td style="color:${col}">${up?'+':''}₹${(Math.abs(totPnL)/100000).toFixed(2)}L</td>`;
  cells[26]=`<td style="color:${col}">${totPct>=0?'+':''}${totPct.toFixed(2)}%</td>`;
  return `<tfoot id="bls-tfoot"><tr>${cells.join('')}</tr></tfoot>`;
}

function renderFundBanner(){
  if(fundLoaded) return '';
  const cfg=S.settings.ghToken&&S.settings.ghRepo;
  const steps=cfg
    ? `<div style="color:#4a6888">Auto-sync configured. If this persists after import:</div>
       <div><span class="u-cyn">1</span> — Re-import portfolio (triggers auto-sync)</div>
       <div><span class="u-cyn">2</span> — Wait ~5 min → tap ↻ Refresh</div>
       <div><span class="u-cyn">3</span> — Run diagnostic in Watchlist → GitHub Sync</div>`
    : `<div><span class="u-cyn">1</span> — Configure GitHub in <b style="color:#fff">Watchlist → GitHub Sync</b></div>
       <div><span class="u-cyn">2</span> — Run diagnostic to verify connection</div>
       <div><span class="u-cyn">3</span> — Re-import portfolio → data auto-fetches (~5 min)</div>`;
  return `<div style="margin:10px 12px;padding:12px;background:rgba(245,166,35,.06);border:1px solid rgba(245,166,35,.25);border-radius:8px;font-size:10px;color:#8eb0d0;font-family:'JetBrains Mono',monospace;line-height:2">
  <div style="color:#ffbf47;font-weight:700;margin-bottom:6px">⚠ Fundamentals not loaded — ATH%, Prom%, OPM%, ROE, Signal all show —</div>
  ${steps}
  <div style="margin-top:4px;color:#4a6888;font-size:9px">Once configured, every import auto-syncs symbols and triggers data fetch.</div>
  <button onclick="exportPortfolioSymbols()" style="margin-top:8px;width:100%;padding:7px;background:rgba(100,181,246,.06);border:1px solid rgba(100,181,246,.2);border-radius:6px;color:#64b5f6;font-size:10px;font-weight:600;cursor:pointer;font-family:'JetBrains Mono',monospace;">
    📤 Manual fallback — export portfolio_symbols.txt</button>
</div>`;
}

function renderBLSRows(rows, totalCur){
  return rows.map(h=>{
    const ltp=h.ltp||0;
    const inv=h.qty*(h.avgBuy||0);
    const cur=ltp>0?h.qty*ltp:null;
    const pnl=cur!==null?cur-inv:null;
    const pnlP=cur!==null&&inv>0?pnl/inv*100:null;
    const wt=cur!==null&&totalCur>0?cur/totalCur*100:0;
    const sig=h.signal||'HOLD';

    const c1d  = h.chg1d>=0  ? CSS.GRN_BD : CSS.RED_BD;
    const c5d  = h.chg5d>=0  ? CSS.GRN    : CSS.RED;
    const cROE = cc(h.roe, 15, 8);
    const cPE  = h.pe==null ? '' : h.pe<18 ? CSS.GRN_B : h.pe>35 ? CSS.RED_B : CSS.NEU;
    const cOPM = cc(h.opm_pct, 15, 8);
    const cNPM = cc(h.npm_pct, 10, 5);
    const cATH = h.ath_pct==null ? '' : h.ath_pct>-10 ? CSS.GRN_B : h.ath_pct<-20 ? CSS.RED_B : CSS.NEU;
    const cW52 = h.w52_pct==null ? '' : h.w52_pct>-10 ? CSS.GRN_B : h.w52_pct<-20 ? CSS.RED_B : CSS.NEU;
    const cPR  = h.prom_pct==null ? '' : h.prom_pct>50 ? CSS.GRN_B : h.prom_pct<35 ? CSS.RED_B : CSS.NEU;
    const cPnL = pnl==null||pnl>=0 ? CSS.GRN_BD : CSS.RED_BD;
    const cCFO = h.cfo>0 ? CSS.GRN : CSS.RED;
    const cAvg = h.avgBuy>0 ? CSS.AMB : CSS.DIM;
    const cLtp = ltp>0 ? (h.chg1d>0?CSS.GRN:h.chg1d<0?CSS.RED:'color:#f0f6ff') : CSS.DIM;
    const fixBg= sig==='BUY'?'background:#030e07':sig==='SELL'?'background:#0e0306':'background:#03060f';
    const ltpHtml=ltp>0
      ? `₹${ltp.toFixed(1)}`
      : `<span style="font-size:7px;background:rgba(245,166,35,.15);border:1px solid rgba(245,166,35,.3);color:#ffbf47;padding:1px 4px;border-radius:3px">NO PRICE</span>`;

    return `<tr style="${rowBg(sig)}" onclick="openPortfolioStock('${h.sym}')">
      <td class="td-l td-fix td-fix1" style="${fixBg}">
        <div class="sym-main">${h.sym}</div>
        <div class="sym-name">${trunc(h.name,14)}</div></td>
      <td class="td-l td-fix td-fix2" style="${fixBg};color:#7a9ab8;font-size:8px;max-width:70px;overflow:hidden;text-overflow:ellipsis">${trunc(h.sector||'—',10)}</td>
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
      <td style="${cCFO}">${fnCr(h.cfo)}</td>
      <td style="${cROE}">${fn(h.roe,1,'','%')}</td>
      <td style="${cPE}">${fn(h.pe,1,'','x')}</td>
      <td style="color:#8eb0d0;font-size:8px;max-width:90px;text-align:left;overflow:hidden;text-overflow:ellipsis">${trunc(h.name,12)}</td>
      <td style="${cOPM}">${fn(h.opm_pct,1,'','%')}</td>
      <td>${fnCr(h.ebitda)}</td>
      <td style="${cNPM}">${fn(h.npm_pct,1,'','%')}</td>
      <td class="u-muted">${fnCr(h.mcap)}</td>
      <td style="${c1d}">${h.chg1d>=0?'+':''}${fn(h.chg1d,2,'','%')}</td>
      <td style="${c5d}">${h.chg5d>=0?'+':''}${fn(h.chg5d,2,'','%')}</td>
      <td style="${cLtp};font-weight:${ltp>0?'600':'400'}">${ltpHtml}</td>
      <td class="u-muted">${h.qty.toLocaleString('en-IN')}</td>
      <td style="${cAvg}">${h.avgBuy>0?'₹'+h.avgBuy.toFixed(1):'—'}</td>
      <td style="${ltp>0?cPnL:CSS.DIM}">${ltp>0?(pnl>=0?'+':'')+pnl.toFixed(0):'—'}</td>
      <td style="${ltp>0?cPnL:CSS.DIM}">${ltp>0&&pnlP!=null?(pnlP>=0?'+':'')+pnlP.toFixed(1)+'%':'—'}</td>
      <td class="u-muted">${wt.toFixed(1)}%</td>
      <td>${sigBadge(sig)}</td></tr>`;
  }).join('');
}

// ─────────────────────────────────────────────────────────────
//  SECTION 3 — DOM-writing renderers
// ─────────────────────────────────────────────────────────────

function renderPortfolio(c){
  const activeEl=document.activeElement;
  if(activeEl&&activeEl.id==='pf-search'){
    const tbody=document.getElementById('bls-tbody');
    if(tbody){
      const pf2=S.portfolio.map(mergeHolding);
      const rows2=filterRows(pf2, S.pfFilter||'All', S.pfSector||'', (S.pfSearch||'').trim());
      sortRows(rows2, S.pfSort||'wt', S.pfSortDir||'desc');
      const tc2=pf2.filter(h=>h.ltp>0).reduce((a,h)=>a+h.qty*h.ltp,0);
      tbody.innerHTML=renderBLSRows(rows2,tc2);
      return;
    }
  }

  if(!S.portfolio.length){
    c.innerHTML=`<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;padding:50px 24px;text-align:center">
      <div style="font-size:42px;margin-bottom:14px;opacity:.6">💼</div>
      <div style="font-family:'Syne',sans-serif;font-size:16px;font-weight:700;color:#fff;margin-bottom:6px">No Portfolio Yet</div>
      <div style="font-size:12px;color:#8eb0d0;line-height:1.7;margin-bottom:18px">Import your holdings from CDSL statement,<br>CSV, or type manually</div>
      <button onclick="openImport()" style="background:#f97316;border:none;border-radius:10px;padding:12px 28px;color:#fff;font-size:14px;font-weight:700;font-family:'Syne',sans-serif;cursor:pointer;">📂 Import Holdings</button>
    </div>`;
    return;
  }

  const pf      = S.portfolio.map(mergeHolding);
  const totals  = calcPortfolioTotals(pf);
  const {sectors, sTotal} = calcSectorMap(pf);
  const rows    = filterRows(pf, S.pfFilter||'All', S.pfSector||'', (S.pfSearch||'').toUpperCase().trim());
  sortRows(rows, S.pfSort||'wt', S.pfSortDir||'desc');

  c.innerHTML=`<div class="bls">
<div id="pf-status-strip"></div>
${renderKpiStrip(totals, pf)}
${renderSectorBar(sectors, sTotal)}
${renderToolbar()}
<div class="bls-table-outer">
<table class="bls-t" id="bls-tbl">
${renderTableHead()}
<tbody id="bls-tbody">${renderBLSRows(rows, totals.totalCur)}</tbody>
${renderTableFoot(rows)}
</table></div>
${renderFundBanner()}
</div>`;

  requestAnimationFrame(()=>{
    const strip=document.getElementById('pf-status-strip');
    if(strip&&S._importStatus){
      const st=S._importStatus;
      const col=st.state==='ok'?'#00e896':st.state==='error'?'#ff6b85':'#ffbf47';
      const icon=st.state==='ok'?'✅':st.state==='error'?'❌':'⏳';
      strip.style.cssText=`padding:8px 13px;font-size:11px;font-family:JetBrains Mono,monospace;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid ${col}40;color:${col};background:${col}0a`;
      strip.innerHTML=icon+' '+st.msg;
    }
  });
}

// ─────────────────────────────────────────────────────────────
//  SECTION 4 — Sort / filter controls
// ─────────────────────────────────────────────────────────────

function setPfFilter(f){S.pfFilter=f;if(S.curTab==='portfolio')render();}

function pfSearchUpdate(val){
  S.pfSearch=val.toUpperCase();
  const tbody=document.getElementById('bls-tbody');
  if(!tbody){render();return;}
  const pf=S.portfolio.map(mergeHolding);
  const rows=filterRows(pf, S.pfFilter||'All', S.pfSector||'', S.pfSearch.trim());
  sortRows(rows, S.pfSort||'wt', S.pfSortDir||'desc');
  const tc=pf.filter(h=>h.ltp>0).reduce((a,h)=>a+h.qty*h.ltp,0);
  tbody.innerHTML=renderBLSRows(rows,tc);
}

function setSectorFilter(s){
  S.pfSector=S.pfSector===s?'':s;
  if(S.curTab==='portfolio')render();
}

function togglePfSort(k){
  if(S.pfSort===k) S.pfSortDir=S.pfSortDir==='desc'?'asc':'desc';
  else{ S.pfSort=k; S.pfSortDir=STR_COLS.has(k)?'asc':'desc'; }
  render();
}

// ─────────────────────────────────────────────────────────────
//  SECTION 5 — Data loading & refresh
// ─────────────────────────────────────────────────────────────

const FUND_CACHE_TTL=60*60*1000;

async function loadFundamentals(forceRefresh){
  try{
    const cached=localStorage.getItem('fund_cache');
    const cacheTs=parseInt(localStorage.getItem('fund_cache_ts')||'0');
    if(!forceRefresh&&cached&&(Date.now()-cacheTs)<FUND_CACHE_TTL){
      const d=JSON.parse(cached);
      FUND=d.stocks||{}; fundLoaded=true;
      if(d.updated&&!S.settings._fundUpdated){
        S.settings._fundUpdated=d.updated;
        S.settings._fundStatus='ok';
        saveSettings();
      }
      return;
    }
    const repo=S.settings.ghRepo?.trim();
    const url=repo
      ?`https://raw.githubusercontent.com/${repo}/main/fundamentals.json?t=${Date.now()}`
      :`./fundamentals.json?t=${Date.now()}`;
    const r=await fetch(url,{cache:'no-store'});
    if(!r.ok) throw new Error('HTTP '+r.status);
    const d=await r.json();
    FUND=d.stocks||{}; fundLoaded=true;
    try{
      localStorage.setItem('fund_cache',JSON.stringify(d));
      localStorage.setItem('fund_cache_ts',Date.now().toString());
    }catch(_){}
    if(d.updated){S.settings._fundUpdated=d.updated;S.settings._fundStatus='ok';}
    saveSettings();
  }catch(e){
    try{
      const cached=localStorage.getItem('fund_cache');
      if(cached){
        const cd=JSON.parse(cached);
        FUND=cd.stocks||{}; fundLoaded=true;
        if(cd.updated){S.settings._fundUpdated=cd.updated;S.settings._fundStatus='stale';saveSettings();}
        return;
      }
    }catch(_){}
    console.warn('fundamentals.json not found');
  }
}

async function refreshPortfolioData(){
  if(pfRefreshing||!S.portfolio.length)return;
  pfRefreshing=true;
  const ico=document.getElementById('rf-icon');
  if(ico)ico.classList.add('spin');
  let updated=0,d=null;
  try{
    const repo=S.settings.ghRepo?.trim();
    const url=repo
      ?`https://raw.githubusercontent.com/${repo}/main/prices.json?t=${Date.now()}`
      :`./prices.json?t=${Date.now()}`;
    const r=await fetch(url,{cache:'no-store'});
    if(r.ok){
      d=await r.json();
      const quotes=d.quotes||d;
      S.portfolio.forEach(h=>{
        const q=quotes[h.sym]; if(!q)return;
        if(q.ltp){h.ltp=q.ltp;h.liveLtp=q.ltp;updated++;}
        if(q.changePct){h.change=q.changePct;}
        if(q.chg5d){h.chg5d=q.chg5d;}
      });
      S.watchlist.forEach(w=>{
        const q=quotes[w.symbol]; if(!q)return;
        if(q.ltp){w.ltp=q.ltp;}
        if(q.changePct){w.change=q.changePct;}
      });
    }
  }catch(e){console.warn('prices.json fetch failed:',e);}
  finally{
    pfLastRefresh=Date.now(); pfRefreshing=false;
    if(ico)ico.classList.remove('spin');
    savePF();
    if(d&&d.updated)S.settings._pricesUpdated=d.updated;
    S.settings._pricesStatus=updated>0?'ok':'fail';
    saveSettings(); render();
  }
}

// ─────────────────────────────────────────────────────────────
//  SECTION 6 — Market hours & timers
// ─────────────────────────────────────────────────────────────

function isMarketHours(){
  const ist=new Date(Date.now()+5.5*60*60*1000);
  const day=ist.getUTCDay();
  if(day===0||day===6)return false;
  const min=ist.getUTCHours()*60+ist.getUTCMinutes();
  return min>=555&&min<=935;
}

setTimeout(()=>{ if(S.portfolio.length)refreshPortfolioData(); },1500);

setInterval(()=>{
  if(!pfRefreshing&&S.portfolio.length){
    if(isMarketHours()) refreshPortfolioData();
    else if((Date.now()-pfLastRefresh)>30*60*1000) refreshPortfolioData();
  }
},5*60*1000);

// ─────────────────────────────────────────────────────────────
//  SECTION 7 — Drill-down
// ─────────────────────────────────────────────────────────────

function openPortfolioStock(sym){
  const h=S.portfolio.find(p=>p.sym===sym); if(!h)return;
  const f=FUND[sym]||{};
  const liveLtp=h.liveLtp||f.ltp||0;
  S.selStock={
    symbol:sym, name:f.name||h.name||sym,
    sector:f.sector||h.sector||'Diversified',
    ltp:liveLtp, prev:f.prev||null,
    change:h.change||f.chg1d||0,
    qty:h.qty, avgBuy:h.avgBuy,
    holdingValue:liveLtp>0?h.qty*liveLtp:null,
    pe:h.pe||f.pe||null, pb:h.pb||f.pb||null,
    roe:h.roe||f.roe||null,
    mcap:f.mcap?f.mcap+'Cr':null,
    week52H:h.week52H||f.w52h||null,
    week52L:h.week52L||f.w52l||null,
    cfo:f.cfo||null,
    sales:f.sales||null, opm_pct:f.opm_pct||null,
  };
  S.drillTab='overview'; render();
}

function clearPortfolio(){
  const ov=document.getElementById('ov');
  const panel=document.getElementById('import-panel');
  const body=document.getElementById('import-panel-body');
  body.innerHTML=`<div style="text-align:center;padding:20px 0 10px">
    <div style="font-size:36px;margin-bottom:12px">🗑</div>
    <div style="font-family:'Syne',sans-serif;font-size:16px;font-weight:700;color:var(--tx);margin-bottom:8px">Clear Portfolio?</div>
    <div style="font-size:12px;color:var(--tx3);margin-bottom:24px">This cannot be undone.</div>
    <button onclick="S.portfolio=[];savePF();render();document.getElementById('ov').classList.remove('on');document.getElementById('import-panel').classList.remove('on');"
      style="width:100%;padding:14px;background:rgba(255,59,92,.15);border:1px solid var(--rd);border-radius:10px;color:var(--rd2);font-size:14px;font-weight:700;cursor:pointer;margin-bottom:10px;">
      Yes, Clear All</button>
    <button onclick="document.getElementById('ov').classList.remove('on');document.getElementById('import-panel').classList.remove('on');"
      style="width:100%;padding:14px;background:var(--s2);border:1px solid var(--b2);border-radius:10px;color:var(--tx3);font-size:14px;font-weight:700;cursor:pointer;">
      Cancel</button></div>`;
  ov.classList.add('on'); panel.classList.add('on');
}

// ─────────────────────────────────────────────────────────────
//  SECTION 8 — Debug panel
// ─────────────────────────────────────────────────────────────

function showPfDebug(){
  const out=['=== PORTFOLIO DEBUG ===','Total stocks: '+S.portfolio.length,'',
    '=== FUND keys: '+Object.keys(FUND).length+' ===',
    Object.keys(FUND).join(', ')||'(none)','',
    '=== Per stock ==='];
  S.portfolio.forEach(h=>{
    const f=FUND[h.sym]||null;
    out.push(h.sym.padEnd(16)+' ltp='+(h.ltp||h.liveLtp||0)
      +' FUND='+(f?'YES':'NO')+(f?' f.ltp='+f.ltp+' f.pe='+f.pe+' f.roe='+f.roe:''));
  });
  out.push('','=== ISIN_MAP: '+Object.keys(ISIN_MAP).length+' entries ===');
  
  const modal=document.createElement('div');
  modal.style.cssText='position:fixed;inset:0;z-index:999;background:rgba(0,0,0,.85);display:flex;flex-direction:column;padding:16px;';
  modal.innerHTML=`<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
    <span style="font-family:'Syne',sans-serif;font-size:14px;font-weight:700;color:#64b5f6">Portfolio Debug</span>
    <button onclick="this.parentElement.parentElement.remove()" style="background:none;border:1px solid #4a6888;border-radius:6px;color:#8eb0d0;padding:4px 10px;cursor:pointer;font-size:11px">✕ Close</button></div>
  <pre style="flex:1;overflow-y:auto;font-family:'JetBrains Mono',monospace;font-size:9px;color:#c8dff5;background:#02040a;border:1px solid #1e3350;border-radius:8px;padding:10px;white-space:pre-wrap;word-break:break-all">${out.join('\n')}</pre>`;
  document.body.appendChild(modal);
}
