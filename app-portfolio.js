// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - WITH INTEGRATED DEBUG & SAFETY GUARDS
// ─────────────────────────────────────────────────────────────

const CSS = {
  GRN_B: 'background:#003a20;color:#fff;font-weight:600',
  RED_B: 'background:#3a0010;color:#fff;font-weight:600',
  NEU: 'color:#c8dff5',
  DIM: 'color:#4a6888'
};

// ── 1. HELPERS ────────────────────────────────────────────────
const fn = (v, dp = 1, pre = '', suf = '') => (v == null || isNaN(v)) ? '—' : pre + Number(v).toFixed(dp) + suf;

function getRowSignals(h, f) {
  let p = f?.pos || 0, n = f?.neg || 0;
  const roe = f?.roe || h?.roe || 0;
  const pe = f?.pe || h?.pe || 0;
  if (!f?.pos) {
    if (roe > 15) p++; else if (roe > 0 && roe < 8) n++;
    if (pe > 0 && pe < 18) p++; else if (pe > 35) n++;
  }
  const net = p - n;
  return { pos: p, neg: n, sig: f?.signal || (net >= 2 ? 'BUY' : net <= -2 ? 'SELL' : 'HOLD') };
}

// ── 2. DEBUG COMPONENT ────────────────────────────────────────
function renderInlineDebug() {
  const reports = [
    `Global S: ${typeof S !== 'undefined' ? 'READY' : 'MISSING'}`,
    `Portfolio Size: ${window.S?.portfolio?.length || 0}`,
    `FUND Data: ${typeof FUND !== 'undefined' ? Object.keys(FUND).length + ' keys' : 'MISSING'}`,
    `ISIN Map: ${typeof ISIN_MAP !== 'undefined' ? 'READY' : 'MISSING'}`
  ];
  
  return `
    <div style="margin-top:20px; padding:10px; background:#1a0000; border:1px solid #330000; border-radius:4px; font-family:monospace; font-size:10px; color:#ffbaba;">
      <div style="font-weight:bold; margin-bottom:5px; color:#ff6b85;">[SYSTEM DEBUG LOG]</div>
      ${reports.map(r => `<div>• ${r}</div>`).join('')}
    </div>`;
}

// ── 3. MAIN RENDERER ──────────────────────────────────────────
function renderPortfolio(container) {
  // Guard Clause: Prevent Crash if globals aren't ready
  if (typeof S === 'undefined' || !S.portfolio) {
    container.innerHTML = `<div style="padding:40px; color:#ff6b85;">Critical Error: Global State (S) not found.${renderInlineDebug()}</div>`;
    return;
  }

  const pf = S.portfolio.map(h => {
    const f = (typeof FUND !== 'undefined') ? FUND[h.sym] : null;
    const ltp = h.liveLtp || f?.ltp || 0;
    return { ...h, ...f, ltp, ...getRowSignals(h, f) };
  });

  const t = {
    inv: pf.reduce((a, r) => a + (r.qty * r.avgBuy), 0),
    cur: pf.reduce((a, r) => a + (r.qty * r.ltp), 0),
    get pnl() { return this.cur - this.inv },
    get pnlP() { return (this.pnl / this.inv * 100) || 0 }
  };

  // UI Construction
  let html = `
    <div class="bls">
      <div class="kpi-strip" style="display:flex; justify-content:space-between; padding:15px; background:#0d1525; border-radius:8px; margin-bottom:10px;">
        <div><small style="color:#8eb0d0">Invested</small><br><b style="color:#64b5f6">₹${(t.inv/100000).toFixed(2)}L</b></div>
        <div><small style="color:#8eb0d0">Total P&L</small><br><b style="color:${t.pnl>=0?'#00e896':'#ff6b85'}">${t.pnlP.toFixed(2)}%</b></div>
      </div>

      <div class="bls-table-outer" style="overflow-x:auto;">
        <table class="bls-t" style="width:100%; border-collapse:collapse; font-size:12px;">
          <thead>
            <tr style="text-align:left; color:#8eb0d0; border-bottom:1px solid #1e3350;">
              <th style="padding:10px;">Ticker</th>
              <th>ROE%</th>
              <th>P/L</th>
              <th>Sig</th>
            </tr>
          </thead>
          <tbody>
            ${pf.map(r => {
              const rPnl = (r.ltp - r.avgBuy) * r.qty;
              return `
                <tr style="border-bottom:1px solid #0d1525; background:${r.sig==='BUY'?'rgba(0,160,80,.05)':''}">
                  <td style="padding:10px;"><b>${r.sym}</b><br><small style="color:#4a6888">${(r.name||'').slice(0,10)}</small></td>
                  <td>${fn(r.roe, 1, '', '%')}</td>
                  <td style="color:${rPnl>=0?'#00e896':'#ff6b85'}">${rPnl.toFixed(0)}</td>
                  <td><span class="badge-${r.sig.toLowerCase()}">${r.sig}</span></td>
                </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>
      
      ${renderInlineDebug()}
    </div>`;

  container.innerHTML = html;
}
