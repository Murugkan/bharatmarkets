// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE (STANDARDIZED & TUNED)
// ─────────────────────────────────────────────────────────────

// ── 1. Style Constants (Consolidated for Size) ───────────────
const CSS = Object.freeze({
  GRN:    'background:#003a20;color:#fff',
  GRN_B:  'background:#003a20;color:#fff;font-weight:600',
  GRN_BD: 'background:#003a20;color:#fff;font-weight:700',
  RED:    'background:#3a0010;color:#fff',
  RED_B:  'background:#3a0010;color:#fff;font-weight:600',
  RED_BD: 'background:#3a0010;color:#fff;font-weight:700',
  AMB:    'background:#3a1a00;color:#fff;font-weight:600',
  NEU:    'color:#c8dff5',
  DIM:    'color:#4a6888',
  MUTE:   'color:#8eb0d0',
});

// ── 2. Column Definitions (Single Source of Truth) ────────────
const TH_COLS = [
  ['sym',    'Ticker'], ['sector', 'Sector'], ['pos', 'Pos', 'Bullish'],
  ['neg',    'Neg', 'Bearish'], ['ath', 'ATH%'], ['w52', '52W%'],
  ['prom',   'Prom%'], ['pledge', 'Pl%'], ['pub', 'Pub%'],
  ['pb',     'P/B'], ['eps', 'EPS'], ['sales', 'Sales'],
  ['cfo',    'CFO'], ['roe', 'ROE%'], ['pe', 'P/E'],
  ['name',   'Name'], ['opm', 'OPM%'], ['ebi', 'EBI'],
  ['npm',    'NPM%'], ['mcap', 'MCAP'], ['chg1d', '%1D'],
  ['chg5d',  '%5D'], ['ltp', 'LTP'], ['qty', 'Qty'],
  ['avg',    'Avg'], ['pnl', 'P&L'], ['pnlpct', 'P&L%'],
  ['wt',     'Wt%'], ['sig', 'Sig']
];

const FIX_COLS = new Set(['sym', 'sector']);
const STR_COLS = new Set(['sym', 'sector', 'name', 'sig']);

// ── 3. Sector Mapping (Static Allocation) ────────────────────
const SECTOR_MAP = Object.freeze({
  'Auto Ancillaries':'Auto','Automobiles':'Auto','Banks':'Banking','Bank':'Banking',
  'Pharmaceutical':'Pharma','Pharmaceuticals':'Pharma','IT - Software':'IT',
  'Information Technology':'IT','Telecom Services':'Telecom','Utilities':'Power',
  'POWER':'Power','Industrials':'Capital Goods','Basic Materials':'Metals',
  'Consumer Cyclical':'Consumer','Consumer Defensive':'FMCG','Tobacco Products':'FMCG',
  'Refineries':'Energy','Financial Services':'Finance','Health Care':'Pharma',
  'Technology':'IT','Real Estate':'Real Estate' // Add others as needed
});

// ── 4. Pure Utility Functions ────────────────────────────────
const round2 = (n) => Math.round(n * 100) / 100;

const normSector = (raw) => (!raw || raw === '—') ? '—' : (SECTOR_MAP[raw] || raw);

const getStatusStyle = (val, g, r) => {
  if (val == null || isNaN(val)) return '';
  if (val >= g) return CSS.GRN_B;
  if (val <= r) return CSS.RED_B;
  return CSS.NEU;
};

const fn = (v, dp = 1, pre = '', suf = '') => {
  if (v == null || isNaN(v)) return `<span class="u-dark">—</span>`;
  return pre + Number(v).toFixed(dp) + suf;
};

const fnCr = (v) => {
  if (v == null || isNaN(v)) return `<span class="u-dark">—</span>`;
  if (v >= 100000) return (v / 100000).toFixed(1) + 'LCr';
  if (v >= 1000) return (v / 1000).toFixed(1) + 'KCr';
  return v.toFixed(0) + 'Cr';
};

// ── 5. Data Processing Logic ─────────────────────────────────
function mergeHolding(h) {
  const f = FUND[h.sym] || {};
  const liveLtp = h.liveLtp || f.ltp || 0;
  return {
    ...h,
    name: f.name || h.name || h.sym,
    sector: normSector(f.sector || h.sector || '—'),
    ltp: liveLtp,
    chg1d: h.change || f.chg1d || 0,
    ath_pct: f.ath_pct ?? null,
    prom_pct: f.prom_pct ?? h.promoter ?? null,
    signal: f.signal || 'HOLD',
    pos: f.pos || 0,
    neg: f.neg || 0,
    wt: 0 // Calculated later
  };
}

function sortRows(rows, skey, sdir) {
  rows.sort((a, b) => {
    let av = a[skey], bv = b[skey];
    if (skey === 'pnl') {
        av = a.ltp > 0 ? (a.qty * a.ltp) - (a.qty * a.avgBuy) : -Infinity;
        bv = b.ltp > 0 ? (b.qty * b.ltp) - (b.qty * b.avgBuy) : -Infinity;
    }
    if (typeof av === 'string') return sdir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av);
    return sdir === 'asc' ? (av || 0) - (bv || 0) : (bv || 0) - (av || 0);
  });
}

// ── 6. UI Fragment Builders ──────────────────────────────────
function renderBLSRows(rows, totalCur) {
  return rows.map(h => {
    const pnl = h.ltp > 0 ? (h.qty * h.ltp) - (h.qty * h.avgBuy) : null;
    const pnlP = (pnl !== null && h.avgBuy > 0) ? (pnl / (h.qty * h.avgBuy)) * 100 : null;
    const wt = (h.ltp > 0 && totalCur > 0) ? (h.qty * h.ltp / totalCur) * 100 : 0;

    const cPnL = pnl == null || pnl >= 0 ? CSS.GRN_BD : CSS.RED_BD;
    const cLtp = h.ltp > 0 ? (h.chg1d >= 0 ? CSS.GRN : CSS.RED) : CSS.DIM;

    return `<tr style="background:${h.signal === 'BUY' ? 'rgba(0,160,80,.1)' : 'transparent'}" onclick="openPortfolioStock('${h.sym}')">
      <td class="td-l td-fix td-fix1">${h.sym}</td>
      <td class="td-l td-fix td-fix2">${h.sector}</td>
      <td>${h.pos}</td>
      <td>${h.neg}</td>
      <td style="${getStatusStyle(h.ath_pct, -5, -20)}">${fn(h.ath_pct, 1, '', '%')}</td>
      <td style="${getStatusStyle(h.prom_pct, 50, 35)}">${fn(h.prom_pct, 1, '', '%')}</td>
      <td style="${cLtp}">${fn(h.ltp, 1, '₹')}</td>
      <td style="${cPnL}">${fn(pnl, 0, '₹')}</td>
      <td style="${cPnL}">${fn(pnlP, 1, '', '%')}</td>
      <td class="u-muted">${wt.toFixed(1)}%</td>
      <td>${h.signal}</td>
    </tr>`;
  }).join('');
}

// ── 7. Main Controller ───────────────────────────────────────
function renderPortfolio(container) {
  if (!S.portfolio.length) {
    container.innerHTML = `<div class="empty-state">No Holdings Found</div>`;
    return;
  }

  const pf = S.portfolio.map(mergeHolding);
  const totalCur = pf.reduce((a, h) => a + (h.qty * h.ltp), 0);

  // Apply filters and sort
  let rows = pf.filter(h => !S.pfSearch || h.sym.includes(S.pfSearch));
  sortRows(rows, S.pfSort || 'wt', S.pfSortDir || 'desc');

  container.innerHTML = `
    <div class="bls">
      <div class="toolbar">
        <input type="text" placeholder="Search..." oninput="debounce(() => { S.pfSearch=this.value.toUpperCase(); renderPortfolio(container); }, 150)()">
      </div>
      <table class="bls-t">
        <thead>
          <tr>${TH_COLS.map(([k, l]) => `<th onclick="toggleSort('${k}')">${l}</th>`).join('')}</tr>
        </thead>
        <tbody>${renderBLSRows(rows, totalCur)}</tbody>
      </table>
    </div>`;
}
