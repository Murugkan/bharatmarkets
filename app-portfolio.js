// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE
//  Data sources: prices.json, fundamentals.json
//  Globals: FUND, fundLoaded, pfRefreshing, pfLastRefresh, S, ISIN_MAP
// ─────────────────────────────────────────────────────────────

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

const TH_COLS = [
  ['sym',    'Ticker'], ['sector', 'Sector'], ['pos',    'Pos'], ['neg',    'Neg'],
  ['ath',    'ATH%'],   ['w52',    '52W%'],   ['prom',   'Prom%'],['pledge', 'Pl%'],
  ['pub',    'Pub%'],   ['pb',     'P/B'],    ['eps',    'EPS'],  ['sales',  'Sales'],
  ['cfo',    'CFO'],    ['roe',    'ROE%'],   ['pe',     'P/E'],  ['name',   'Name'],
  ['opm',    'OPM%'],   ['ebi',    'EBI'],    ['npm',    'NPM%'], ['mcap',   'MCAP'],
  ['chg1d',  '%1D'],    ['chg5d',  '%5D'],    ['ltp',    'LTP'],  ['qty',    'Qty'],
  ['avg',    'Avg'],    ['pnl',    'P&L'],    ['pnlpct', 'P&L%'], ['wt',     'Wt%'],
  ['sig',    'Sig']
];

const FIX_COLS = new Set(['sym','sector']);
const STR_COLS = new Set(['sym','sector','name','sig']);

const SECTOR_MAP = {
  'Banks':'Banking','Bank':'Banking','Pharmaceuticals':'Pharma','Information Technology':'IT',
  'Technology':'IT','Financial Services':'Finance','Insurance':'Finance','Auto Ancillaries':'Auto'
};

// ── SECTION 1 — Utilities ─────────────────────────────────────
function round2(n){ return Math.round(n*100)/100; }
function normSector(raw){ if(!raw || raw==='—') return '—'; return SECTOR_MAP[raw] || raw; }
function cc(v, gA, rB){ if(v==null||isNaN(v)) return ''; if(v>=gA) return CSS.GRN_B; if(v<=rB) return CSS.RED_B; return CSS.NEU; }
function rowBg(sig){ if(sig==='BUY') return 'background:rgba(0,160,80,.13)'; if(sig==='SELL') return 'background:rgba(200,30,50,.13)'; return ''; }
function fn(v, dp=1, pre='', suf=''){ if(v==null||isNaN(v)) return '<span class="u-dark">—</span>'; return pre+Number(v).toFixed(dp)+suf; }
function fnCr(v){ if(v==null||isNaN(v)) return '<span class="u-dark">—</span>'; if(v>=100000) return (v/100000).toFixed(1)+'LCr'; if(v>=1000) return (v/1000).toFixed(1)+'KCr'; return v.toFixed(0)+'Cr'; }

function mergeHolding(h){
  const f=FUND[h.sym]||{};
  const liveLtp=h.liveLtp||f.ltp||0;
  return {
    sym: h.sym, name: f.name||h.name||h.sym, sector: normSector(f.sector||h.sector),
    qty: h.qty||0, avgBuy: h.avgBuy||0, ltp: liveLtp, chg1d: h.change||f.chg1d||0,
    pe: f.pe??null, pb: f.pb??null, roe: f.roe??null, mcap: f.mcap??null,
    ath_pct: f.ath_pct??null, signal: f.signal||'HOLD', pos: f.pos||0, neg: f.neg||0
  };
}

// ── SECTION 2 — Render Helpers ────────────────────────────────
function sigBadge(sig){
  const c={BUY:{bg:'#00a050',bd:'#00d084'},SELL:{bg:'#c01e32',bd:'#ff3b5c'},HOLD:{bg:'#7a6010',bd:'#f5a623'}}[sig]||{bg:'#1a3050',bd:'#4a6888'};
  return `<span style="display:inline-block;font-size:8px;font-weight:800;padding:2px 7px;border-radius:3px;background:${c.bg};border:1px solid ${c.bd};color:#fff">${sig}</span>`;
}

function renderBLSRows(rows, totalCur){
  return rows.map(h=>{
    const ltp=h.ltp||0;
    const inv=h.qty*h.avgBuy;
    const cur=ltp>0?h.qty*ltp:null;
    const pnl=cur!==null?cur-inv:null;
    const wt=cur!==null&&totalCur>0?cur/totalCur*100:0;
    const sig=h.signal||'HOLD';

    return `<tr style="${rowBg(sig)}" onclick="openPortfolioStock('${h.sym}')">
      <td class="td-l td-fix td-fix1"><b>${h.sym}</b></td>
      <td class="td-l td-fix td-fix2">${h.sector}</td>
      <td>${h.pos}</td><td>${h.neg}</td>
      <td>${fn(h.ath_pct,1,'','%')}</td>
      <td colspan="9"></td> <td style="text-align:left">${h.name}</td>
      <td colspan="4"></td>
      <td style="${h.chg1d>=0?CSS.GRN_BD:CSS.RED_BD}">${fn(h.chg1d,2,'','%')}</td>
      <td>${fn(h.chg5d,2)}</td>
      <td style="font-weight:600">${ltp>0?'₹'+ltp.toFixed(1):'—'}</td>
      <td>${h.qty}</td>
      <td>${fn(h.avgBuy)}</td>
      <td style="${pnl>=0?CSS.GRN_BD:CSS.RED_BD}">${fn(pnl,0)}</td>
      <td style="${pnl>=0?CSS.GRN_BD:CSS.RED_BD}">${fn(pnl/inv*100,1,'','%')}</td>
      <td>${wt.toFixed(1)}%</td>
      <td>${sigBadge(sig)}</td>
    </tr>`;
  }).join('');
}

// ── SECTION 3 — Main Rendering ────────────────────────────────
function renderPortfolio(c){
  if(!S.portfolio.length){
    c.innerHTML=`<div style="padding:50px;text-align:center"><button onclick="openImport()">Import Holdings</button></div>`;
    return;
  }

  const pf = S.portfolio.map(mergeHolding);
  const totalCur = pf.reduce((a,h)=>a+(h.qty*h.ltp),0);
  
  c.innerHTML = `
    <div class="bls">
      <div class="bls-table-outer">
        <table class="bls-t">
          <thead><tr>${TH_COLS.map(col=>`<th>${col[1]}</th>`).join('')}</tr></thead>
          <tbody id="bls-tbody">${renderBLSRows(pf, totalCur)}</tbody>
        </table>
      </div>
    </div>`;
}

// ── SECTION 8 — Debug ─────────────────────────────────────────
function showPfDebug(){
  const out = ['=== PORTFOLIO DEBUG ===', 'Total: ' + S.portfolio.length];
  S.portfolio.forEach(h => {
    out.push(`${h.sym.padEnd(10)} ltp=${h.ltp || 0}`);
  });

  const modal = document.createElement('div');
  modal.style.cssText = 'position:fixed;inset:0;z-index:999;background:rgba(0,0,0,.85);display:flex;flex-direction:column;padding:16px;';
  modal.innerHTML = `
    <div style="display:flex;justify-content:space-between;color:#64b5f6;margin-bottom:8px">
      <b>Debug Console</b>
      <button onclick="this.closest('div[style]').parentElement.remove()">✕ Close</button>
    </div>
    <pre style="flex:1;overflow:auto;font-size:10px;color:#c8dff5;background:#000;padding:10px">${out.join('\n')}</pre>`;
  document.body.appendChild(modal);
}
