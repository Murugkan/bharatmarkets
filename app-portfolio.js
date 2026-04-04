// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - TUNED & FULLY FUNCTIONAL
// ─────────────────────────────────────────────────────────────

const CSS = {
  GRN: 'background:#003a20;color:#fff', GRN_B: 'background:#003a20;color:#fff;font-weight:600',
  GRN_BD: 'background:#003a20;color:#fff;font-weight:700', RED: 'background:#3a0010;color:#fff',
  RED_B: 'background:#3a0010;color:#fff;font-weight:600', RED_BD: 'background:#3a0010;color:#fff;font-weight:700',
  AMB: 'background:#3a1a00;color:#fff;font-weight:600', NEU: 'color:#c8dff5', DIM: 'color:#4a6888'
};

const TH_COLS = [
  ['sym','Ticker'],['sector','Sector'],['pos','Pos'],['neg','Neg'],['ath','ATH%'],['w52','52W%'],
  ['prom','Prom%'],['pledge','Pl%'],['pub','Pub%'],['pb','P/B'],['eps','EPS'],['sales','Sales'],
  ['cfo','CFO'],['roe','ROE%'],['pe','P/E'],['name','Name'],['opm','OPM%'],['ebi','EBI'],
  ['npm','NPM%'],['mcap','MCAP'],['chg1d','%1D'],['chg5d','%5D'],['ltp','LTP'],['qty','Qty'],
  ['avg','Avg'],['pnl','P&L'],['pnlpct','P&L%'],['wt','Wt%'],['sig','Sig']
];

// ── UTILITIES ────────────────────────────────────────────────
const fn = (v, dp=1, pre='', suf='') => (v==null || isNaN(v)) ? '<span class="u-dark">—</span>' : pre+Number(v).toFixed(dp)+suf;
const fnCr = (v) => (v==null || isNaN(v)) ? '<span class="u-dark">—</span>' : (v>=100000 ? (v/100000).toFixed(1)+'LCr' : (v>=1000 ? (v/1000).toFixed(1)+'KCr' : v.toFixed(0)+'Cr'));
const getCC = (v, g, r) => (v==null || isNaN(v)) ? '' : (v >= g ? CSS.GRN_B : v <= r ? CSS.RED_B : CSS.NEU);

// ── DATA LOGIC ───────────────────────────────────────────────
function mergeHolding(h) {
  const f = FUND[h.sym] || {};
  const ltp = h.liveLtp || f.ltp || 0;
  let pos=0, neg=0;
  if(f.roe > 15) pos++; else if(f.roe < 8) neg++;
  if(f.pe > 0 && f.pe < 18) pos++; else if(f.pe > 35) neg++;
  
  return {
    ...h, ...f, ltp, pos, neg,
    sector: SECTOR_MAP[f.sector||h.sector] || f.sector || h.sector || '—',
    sig: f.signal || (pos-neg >= 2 ? 'BUY' : pos-neg <= -2 ? 'SELL' : 'HOLD'),
    w52_pct: (ltp && f.w52h) ? ((ltp/f.w52h - 1)*100) : null
  };
}

// ── UI COMPONENTS ────────────────────────────────────────────
function renderKpiStrip(t, pf) {
  return `<div class="kpi-strip">
    <div class="kpi"><div class="kpi-l">Invested</div><div class="kpi-v" style="color:#64b5f6">₹${(t.totalInv/100000).toFixed(2)}L</div></div>
    <div class="kpi"><div class="kpi-l">Mkt Value</div><div class="kpi-v">₹${(t.totalCur/100000).toFixed(2)}L</div></div>
    <div class="kpi"><div class="kpi-l">Total P&L</div><div class="kpi-v" style="color:${t.totalPnL>=0?'#00e896':'#ff6b85'}">${t.pnlPct.toFixed(2)}%</div></div>
  </div>`;
}

function renderToolbar() {
  return `<div class="bls-tb">
    <input id="pf-search" type="text" placeholder="Search..." value="${S.pfSearch||''}" oninput="S.pfSearch=this.value.toUpperCase();renderPortfolio(document.getElementById('pf-container'))">
    <div class="tb-chips">
      ${['All','BUY','SELL','HOLD'].map(f => `<div class="tb-chip ${S.pfFilter===f?'on':''}" onclick="S.pfFilter='${f}';renderPortfolio(document.getElementById('pf-container'))">${f}</div>`).join('')}
    </div>
  </div>`;
}

function renderBLSRows(rows, totalCur) {
  return rows.map(h => {
    const pnl = h.ltp > 0 ? (h.qty * (h.ltp - h.avgBuy)) : 0;
    const wt = (h.ltp > 0 && totalCur > 0) ? (h.qty * h.ltp / totalCur * 100) : 0;
    const c1d = h.chg1d >= 0 ? CSS.GRN_BD : CSS.RED_BD;
    
    return `<tr style="background:${h.sig==='BUY'?'rgba(0,160,80,.1)':h.sig==='SELL'?'rgba(200,30,50,.1)':'transparent'}" onclick="openPortfolioStock('${h.sym}')">
      <td class="td-l td-fix td-fix1">${h.sym}<br><small>${h.name?.slice(0,12)}</small></td>
      <td class="td-l td-fix td-fix2">${h.sector}</td>
      <td><span class="pn-p">${h.pos}</span></td><td><span class="pn-n">${h.neg}</span></td>
      <td style="${getCC(h.ath_pct, -5, -25)}">${fn(h.ath_pct,1,'','%')}</td>
      <td style="${getCC(h.w52_pct, -5, -25)}">${fn(h.w52_pct,1,'','%')}</td>
      <td style="${getCC(h.prom_pct, 50, 35)}">${fn(h.prom_pct,1,'','%')}</td>
      <td class="u-dark">—</td><td>${fn(h.public_pct)}</td>
      <td>${fn(h.pb)}</td><td>${fn(h.eps,1,'₹')}</td>
      <td>${fnCr(h.sales)}</td><td>${fnCr(h.cfo)}</td>
      <td style="${getCC(h.roe, 15, 8)}">${fn(h.roe,1,'','%')}</td>
      <td style="${h.pe<18?CSS.GRN_B:h.pe>35?CSS.RED_B:''}">${fn(h.pe)}</td>
      <td class="u-dim">${h.name?.slice(0,10)}</td>
      <td>${fn(h.opm_pct)}</td><td>${fnCr(h.ebitda)}</td>
      <td>${fn(h.npm_pct)}</td><td>${fnCr(h.mcap)}</td>
      <td style="${c1d}">${fn(h.chg1d,2,'','%')}</td>
      <td class="u-muted">${fn(h.chg5d)}</td>
      <td style="${h.ltp>0?CSS.GRN:CSS.DIM}">${h.ltp>0?'₹'+h.ltp.toFixed(1):'—'}</td>
      <td>${h.qty}</td><td>${fn(h.avgBuy)}</td>
      <td style="${pnl>=0?CSS.GRN_BD:CSS.RED_BD}">${pnl.toFixed(0)}</td>
      <td style="${pnl>=0?CSS.GRN_BD:CSS.RED_BD}">${fn((pnl/(h.qty*h.avgBuy||1)*100),1,'','%')}</td>
      <td>${wt.toFixed(1)}%</td>
      <td><span class="badge-${h.sig.toLowerCase()}">${h.sig}</span></td>
    </tr>`;
  }).join('');
}

// ── MAIN RENDERER ────────────────────────────────────────────
function renderPortfolio(c) {
  if (!S.portfolio.length) { c.innerHTML = '<div class="empty">No Data</div>'; return; }

  const pf = S.portfolio.map(mergeHolding);
  const t = {
    totalInv: pf.reduce((a,h)=>a+(h.qty*h.avgBuy), 0),
    totalCur: pf.reduce((a,h)=>a+(h.qty*h.ltp), 0),
    get totalPnL() { return this.totalCur - this.totalInv },
    get pnlPct() { return (this.totalPnL/this.totalInv*100) || 0 }
  };

  let rows = pf.filter(h => (!S.pfSearch || h.sym.includes(S.pfSearch)) && (S.pfFilter === 'All' || h.sig === S.pfFilter));
  rows.sort((a,b) => S.pfSortDir === 'asc' ? (a[S.pfSort] - b[S.pfSort]) : (b[S.pfSort] - a[S.pfSort]));

  c.innerHTML = `
    <div class="bls">
      ${renderKpiStrip(t, pf)}
      ${renderToolbar()}
      <div class="bls-table-outer">
        <table class="bls-t">
          <thead><tr>${TH_COLS.map(([k,l]) => `<th onclick="S.pfSort='${k}';S.pfSortDir=(S.pfSortDir==='asc'?'desc':'asc');renderPortfolio(c)">${l}</th>`).join('')}</tr></thead>
          <tbody>${renderBLSRows(rows, t.totalCur)}</tbody>
        </table>
      </div>
    </div>`;
}
