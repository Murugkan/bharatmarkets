// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - FULL FUNCTIONALITY RESTORED
// ─────────────────────────────────────────────────────────────

const CSS = {
  GRN_B: 'background:#003a20;color:#fff;font-weight:600',
  RED_B: 'background:#3a0010;color:#fff;font-weight:600',
  NEU: 'color:#c8dff5'
};

// 1. KPI STRIP RESTORATION
function renderKpiStrip(t, pf) {
  const pnlUp = t.totalPnL >= 0;
  return `
    <div class="kpi-strip">
      <div class="kpi">
        <div class="kpi-l">Invested</div>
        <div class="kpi-v" style="color:#64b5f6">₹${(t.totalInv/100000).toFixed(2)}L</div>
        <div class="kpi-s">${pf.length} stocks</div>
      </div>
      <div class="kpi">
        <div class="kpi-l">Total P&L</div>
        <div class="kpi-v" style="color:${pnlUp?'#00e896':'#ff6b85'}">₹${(Math.abs(t.totalPnL)/100000).toFixed(2)}L</div>
        <div class="kpi-s" style="color:${pnlUp?'#00d084':'#ff3b5c'}">${t.pnlPct.toFixed(2)}%</div>
      </div>
      <div class="kpi">
        <div class="kpi-l">Signals</div>
        <div class="kpi-v" style="color:#00e896">${t.buys} BUY</div>
        <div class="kpi-s" style="color:#ff6b85">${t.sells} SELL</div>
      </div>
    </div>`;
}

// 2. SECTOR BAR RESTORATION
function renderSectorBars(pf) {
  const sMap = {};
  pf.forEach(h => {
    const s = h.sector || 'Other';
    sMap[s] = (sMap[s] || 0) + (h.qty * (h.ltp || h.avgBuy || 0));
  });
  const total = Object.values(sMap).reduce((a, b) => a + b, 0) || 1;
  const topSectors = Object.entries(sMap).sort((a, b) => b[1] - a[1]).slice(0, 5);

  return `
    <div class="sector-bars">
      ${topSectors.map(([name, val]) => `
        <div class="s-bar-item">
          <div class="s-bar-label"><span>${name}</span><span>${(val/total*100).toFixed(1)}%</span></div>
          <div class="s-bar-bg"><div class="s-bar-fill" style="width:${(val/total*100)}%"></div></div>
        </div>`).join('')}
    </div>`;
}

// 3. SIGNAL LOGIC RESTORATION
function computeSignals(h, f) {
  let pos = 0, neg = 0;
  const roe = f.roe || h.roe || 0, pe = f.pe || h.pe || 0;
  const prom = f.prom_pct || h.promoter || 0;
  
  if (roe > 15) pos++; else if (roe < 8 && roe > 0) neg++;
  if (pe > 0 && pe < 18) pos++; else if (pe > 35) neg++;
  if (prom > 50) pos++; else if (prom > 0 && prom < 35) neg++;
  
  const net = pos - neg;
  return { pos, neg, sig: net >= 2 ? 'BUY' : net <= -2 ? 'SELL' : 'HOLD' };
}

// 4. MAIN CONTROLLER
function renderPortfolio(container) {
  if (!S.portfolio || !S.portfolio.length) {
    container.innerHTML = '<div class="u-dark" style="padding:20px">No Holdings Found</div>';
    return;
  }

  // Merge and Calculate Totals
  const merged = S.portfolio.map(h => {
    const f = FUND[h.sym] || {};
    const signals = computeSignals(h, f);
    return { ...h, ...f, ...signals, ltp: h.liveLtp || f.ltp || 0 };
  });

  const totals = {
    totalInv: merged.reduce((a, h) => a + (h.qty * h.avgBuy), 0),
    totalCur: merged.reduce((a, h) => a + (h.qty * h.ltp), 0),
    get totalPnL() { return this.totalCur - this.totalInv },
    get pnlPct() { return (this.totalPnL / this.totalInv) * 100 || 0 },
    buys: merged.filter(h => h.sig === 'BUY').length,
    sells: merged.filter(h => h.sig === 'SELL').length
  };

  // Build Layout
  container.innerHTML = `
    <div class="portfolio-module">
      ${renderKpiStrip(totals, merged)}
      ${renderSectorBars(merged)}
      <div class="table-scroll">
        <table class="bls-t">
          <thead>
            <tr>
              <th class="th-fix th-fix1">Ticker</th>
              <th>ROE%</th>
              <th>P/E</th>
              <th>P&L</th>
              <th>Sig</th>
            </tr>
          </thead>
          <tbody>
            ${merged.map(h => `
              <tr style="background:${h.sig==='BUY'?'rgba(0,160,80,.1)':h.sig==='SELL'?'rgba(200,30,50,.1)':'transparent'}">
                <td class="td-fix td-fix1">${h.sym}</td>
                <td style="${h.roe > 15 ? CSS.GRN_B : CSS.NEU}">${h.roe || '—'}%</td>
                <td>${h.pe || '—'}</td>
                <td style="color:${(h.ltp-h.avgBuy)>=0?'#00e896':'#ff6b85'}">₹${((h.ltp-h.avgBuy)*h.qty).toFixed(0)}</td>
                <td><span class="badge-${h.sig.toLowerCase()}">${h.sig}</span></td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>
    </div>`;
}
