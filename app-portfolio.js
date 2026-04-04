// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - FULL RESTORATION (FIXED)
// ─────────────────────────────────────────────────────────────

// ── 1. Style Constants ────────────────────────────────────────
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

// ── 2. Column Definitions ─────────────────────────────────────
const TH_COLS = [
  ['sym','Ticker'],['sector','Sector'],['pos','Pos'],['neg','Neg'],['ath','ATH%'],['w52','52W%'],
  ['prom','Prom%'],['pledge','Pl%'],['pub','Pub%'],['pb','P/B'],['eps','EPS'],['sales','Sales'],
  ['cfo','CFO'],['roe','ROE%'],['pe','P/E'],['name','Name'],['opm','OPM%'],['ebi','EBI'],
  ['npm','NPM%'],['mcap','MCAP'],['chg1d','%1D'],['chg5d','%5D'],['ltp','LTP'],['qty','Qty'],
  ['avg','Avg'],['pnl','P&L'],['pnlpct','P&L%'],['wt','Wt%'],['sig','Sig']
];

// ── 3. Utilities & Data Merging ───────────────────────────────
const fn = (v, dp=1, pre='', suf='') => (v==null || isNaN(v)) ? '<span class="u-dark">—</span>' : pre+Number(v).toFixed(dp)+suf;
const fnCr = (v) => (v==null || isNaN(v)) ? '<span class="u-dark">—</span>' : (v>=100000 ? (v/100000).toFixed(1)+'LCr' : (v>=1000 ? (v/1000).toFixed(1)+'KCr' : v.toFixed(0)+'Cr'));
const cc = (v, g, r) => (v==null || isNaN(v)) ? '' : (v >= g ? CSS.GRN_B : v <= r ? CSS.RED_B : CSS.NEU);

function mergeHolding(h) {
  const f = FUND[h.sym] || {};
  const ltp = h.liveLtp || f.ltp || 0;
  let pos = f.pos || 0, neg = f.neg || 0;
  
  // Fallback signal logic if fundamental data is missing
  if(!f.pos) {
    const roe = f.roe || h.roe || 0, pe = f.pe || h.pe || 0;
    if(roe > 15) pos++; else if(roe < 8 && roe > 0) neg++;
    if(pe > 0 && pe < 18) pos++; else if(pe > 35) neg++;
  }

  return {
    ...h, ...f, ltp, pos, neg,
    sector: SECTOR_MAP[f.sector || h.sector] || f.sector || h.sector || '—',
    sig: f.signal || (pos - neg >= 2 ? 'BUY' : pos - neg <= -2 ? 'SELL' : 'HOLD'),
    w52_pct: (ltp && f.w52h) ? ((ltp / f.w52h - 1) * 100) : (f.w52_pct || null)
  };
}

// ── 4. UI Components ──────────────────────────────────────────
function renderKpiStrip(t, pf) {
  const pCol = t.totalPnL >= 0 ? '#00e896' : '#ff6b85';
  return `
    <div class="kpi-strip">
      <div class="kpi"><div class="kpi-l">Invested</div><div class="kpi-v" style="color:#64b5f6">₹${(t.totalInv/100000).toFixed(2)}L</div><div class="kpi-s">${pf.length} stocks</div></div>
      <div class="kpi"><div class="kpi-l">Mkt Value</div><div class="kpi-v">₹${(t.totalCur/100000).toFixed(2)}L</div><div class="kpi-s">${t.priced} priced</div></div>
      <div class="kpi"><div class="kpi-l">Total P&L</div><div class="kpi-v" style="color:${pCol}">₹${(Math.abs(t.totalPnL)/100000).toFixed(2)}L</div><div class="kpi-s" style="color:${pCol}">${t.pnlPct.toFixed(2)}%</div></div>
    </div>`;
}

function renderSectorBars(pf) {
  const sMap = {};
  pf.forEach(h => { const s = h.sector || 'Other'; sMap[s] = (sMap[s] || 0) + (h.qty * (h.ltp || h.avgBuy)); });
  const total = Object.values(sMap).reduce((a, b) => a + b, 0) || 1;
  const sorted = Object.entries(sMap).sort((a, b) => b[1] - a[1]).slice(0, 5);

  return `
    <div class="sector-bars" style="padding:10px 12px; display:flex; gap:12px; overflow-x:auto;">
      ${sorted.map(([n, v]) => `
        <div style="flex:1; min-width:80px;">
          <div style="font-size:9px; color:#8eb0d0; margin-bottom:4px; white-space:nowrap;">${n}</div>
          <div style="height:4px; background:#1e3350; border-radius:2px;"><div style="height:100%; width:${(v/total*100)}%; background:#64b5f6; border-radius:2px;"></div></div>
        </div>`).join('')}
    </div>`;
}

// ── 5. Main Renderer ──────────────────────────────────────────
function renderPortfolio(c) {
  if (!S.portfolio || !S.portfolio.length) {
    c.innerHTML = '<div class="empty-state" style="padding:40px; text-align:center; color:#4a6888;">No Holdings Found</div>';
    return;
  }

  const pf = S.portfolio.map(mergeHolding);
  const t = {
    totalInv: pf.reduce((a, h) => a + (h.qty * h.avgBuy), 0),
    totalCur: pf.reduce((a, h) => a + (h.qty * h.ltp), 0),
    priced: pf.filter(h => h.ltp > 0).length,
    get totalPnL() { return this.totalCur - this.totalInv },
    get pnlPct() { return (this.totalPnL / this.totalInv * 100) || 0 }
  };

  let rows = pf.filter(h => (!S.pfSearch || h.sym.includes(S.pfSearch.toUpperCase())) && (S.pfFilter === 'All' || h.sig === S.pfFilter));
  
  // Sorting logic logic
  rows.sort((a, b) => {
    const av = a[S.pfSort], bv = b[S.pfSort];
    return S.pfSortDir === 'asc' ? (av > bv ? 1 : -1) : (bv > av ? 1 : -1);
  });

  c.innerHTML = `
    <div class="bls">
      ${renderKpiStrip(t, pf)}
      ${renderSectorBars(pf)}
      <div class="bls-tb" style="padding:10px 12px; display:flex; gap:8px;">
        <input type="text" placeholder="Search..." value="${S.pfSearch || ''}" oninput="S.pfSearch=this.value.toUpperCase();renderPortfolio(c)" style="flex:1; background:#0d1525; border:1px solid #1e3350; color:#fff; padding:6px; border-radius:4px; outline:none;">
        <div class="tb-chips" style="display:flex; gap:4px;">
          ${['All', 'BUY', 'SELL', 'HOLD'].map(f => `<div class="tb-chip ${S.pfFilter === f ? 'on' : ''}" onclick="S.pfFilter='${f}';renderPortfolio(c)" style="padding:4px 8px; font-size:10px; cursor:pointer; background:${S.pfFilter === f ? '#1e3350' : '#0d1525'}; border-radius:4px; color:${S.pfFilter === f ? '#64b5f6' : '#8eb0d0'}; border:1px solid #1e3350;">${f}</div>`).join('')}
        </div>
      </div>
      <div class="bls-table-outer">
        <table class="bls-t">
          <thead><tr>${TH_COLS.map(([k, l]) => `<th onclick="S.pfSort='${k}'; S.pfSortDir=(S.pfSortDir==='asc'?'desc':'asc'); renderPortfolio(c)" style="cursor:pointer;">${l}${S.pfSort === k ? (S.pfSortDir === 'asc' ? '↑' : '↓') : ''}</th>`).join('')}</tr></thead>
          <tbody>
            ${rows.map(h => `
              <tr style="background:${h.sig === 'BUY' ? 'rgba(0,160,80,.08)' : h.sig === 'SELL' ? 'rgba(200,30,50,.08)' : 'transparent'}" onclick="openPortfolioStock('${h.sym}')">
                <td class="td-fix td-fix1">${h.sym}<br><small style="color:#4a6888">${(h.name || '').slice(0, 10)}</small></td>
                <td class="td-fix td-fix2" style="color:#4a6888">${h.sector}</td>
                <td><span class="pn-p">${h.pos}</span></td><td><span class="pn-n">${h.neg}</span></td>
                <td style="${cc(h.ath_pct, -5, -25)}">${fn(h.ath_pct, 1, '', '%')}</td>
                <td style="${cc(h.w52_pct, -5, -25)}">${fn(h.w52_pct, 1, '', '%')}</td>
                <td style="${cc(h.prom_pct, 50, 35)}">${fn(h.prom_pct, 1, '', '%')}</td>
                <td class="u-dark">—</td><td>${fn(h.public_pct)}</td>
                <td>${fn(h.pb)}</td><td>${fn(h.eps, 1, '₹')}</td>
                <td>${fnCr(h.sales)}</td><td>${fnCr(h.cfo)}</td>
                <td style="${cc(h.roe, 15, 8)}">${fn(h.roe, 1, '', '%')}</td>
                <td style="${h.pe < 18 ? CSS.GRN_B : h.pe > 35 ? CSS.RED_B : ''}">${fn(h.pe)}</td>
                <td style="color:#4a6888; font-size:9px;">${(h.name || '').slice(0, 12)}</td>
                <td>${fn(h.opm_pct)}</td><td>${fnCr(h.ebitda)}</td>
                <td>${fn(h.npm_pct)}</td><td>${fnCr(h.mcap)}</td>
                <td style="${h.chg1d >= 0 ? CSS.GRN_BD : CSS.RED_BD}">${fn(h.chg1d, 2, '', '%')}</td>
                <td style="color:#4a6888">${fn(h.chg5d)}</td>
                <td style="${h.ltp > 0 ? CSS.GRN_B : CSS.DIM}">${h.ltp > 0 ? '₹' + h.ltp.toFixed(1) : '—'}</td>
                <td>${h.qty}</td><td>${fn(h.avgBuy)}</td>
                <td style="${(h.ltp - h.avgBuy) >= 0 ? CSS.GRN_BD : CSS.RED_BD}">${((h.ltp - h.avgBuy) * h.qty).toFixed(0)}</td>
                <td style="${(h.ltp - h.avgBuy) >= 0 ? CSS.GRN_BD : CSS.RED_BD}">${fn(((h.ltp - h.avgBuy) / (h.avgBuy || 1) * 100), 1, '', '%')}</td>
                <td style="color:#4a6888">${((h.ltp * h.qty) / t.totalCur * 100).toFixed(1)}%</td>
                <td><span class="badge-${h.sig.toLowerCase()}" style="font-size:8px; padding:2px 4px; border-radius:3px; border:1px solid; color:#fff;">${h.sig}</span></td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>`;
}
