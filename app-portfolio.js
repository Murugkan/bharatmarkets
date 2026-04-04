async function renderPortfolio(container) {
  if (!container) return;
  const overlay = document.querySelector('.loading, #sync-overlay');
  if (overlay) overlay.style.display = 'none';

  if (!window.fundLoaded) {
    container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> BOOTING ENGINE...</div>`;
    await loadFundamentals();
  }

  let dataHits = 0;
  window.S.portfolio.forEach(h => {
    if (window.FUND[h.sym] || (h.isin && window.FUND[window.ISIN_MAP[h.isin]])) dataHits++;
  });

  let html = `<div style="padding:10px; background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif;">`;
  
  html += `<div style="margin-bottom:15px; padding:10px; background:#0d1117; border:1px solid #1e3350; border-radius:4px; font-size:11px; font-family:monospace;">
            <span style="color:#3fb950;">● ENGINE: READY</span> | <span style="color:#58a6ff;">STOCKS: ${window.S.portfolio.length}</span> | <span style="color:#d29922;">DATA HITS: ${dataHits}</span>
           </div>`;

  html += `<div style="overflow-x:auto; border:1px solid #1e3350; border-radius:8px;">`;
  html += `<table style="width:100%; border-collapse:collapse; white-space:nowrap; font-size:12px;">`;
  
  // HEADER - Expanded with efficiency and risk metrics
  html += `<tr style="background:#0d1117; border-bottom:2px solid #1e3350; color:#8b949e; text-transform:uppercase; font-size:10px;">
            <th style="padding:12px; text-align:left; position:sticky; left:0; background:#0d1117; z-index:2;">Symbol</th>
            <th style="padding:12px; text-align:center;">ROE%</th>
            <th style="padding:12px; text-align:center;">ROCE%</th>
            <th style="padding:12px; text-align:center;">OPM%</th>
            <th style="padding:12px; text-align:center;">NPM%</th>
            <th style="padding:12px; text-align:center;">P/E</th>
            <th style="padding:12px; text-align:center;">D/E</th>
            <th style="padding:12px; text-align:center;">PROM%</th>
            <th style="padding:12px; text-align:right;">Price (LTP)</th>
          </tr>`;

  window.S.portfolio.forEach((h, index) => {
    const f = window.FUND[h.sym] || (h.isin ? window.FUND[window.ISIN_MAP[h.isin]] : null) || {};
    
    // --- STEP 2: FULL DATA MAP ---
    const ltp = f.ltp || 0;
    const roe = f.roe ?? '—';
    const roce = f.roce ?? '—';
    const opm = f.opm_pct ?? '—';
    const npm = f.npm_pct ?? '—';
    const pe = f.pe ?? '—';
    const debtEq = f.debt_eq ?? '—';
    const prom = f.prom_pct ?? '—';
    
    // Hidden variables (Ready for Step 3 formatting)
    const mcap = f.mcap ?? '—';
    const fii = f.fii_pct ?? '—';
    const dii = f.dii_pct ?? '—';
    const sales = f.sales ?? '—';
    const divYield = f.div_yield ?? '—';
    const beta = f.beta ?? '—';

    const rowBg = index % 2 === 0 ? 'transparent' : '#0d1117';
    
    // Logic Colors
    const roeColor = (parseFloat(roe) > 15) ? '#3fb950' : (parseFloat(roe) < 0 ? '#f85149' : '#fff');
    const deColor = (parseFloat(debtEq) > 1.5) ? '#f85149' : '#fff';

    html += `<tr style="background:${rowBg}; border-bottom:1px solid #1e3350;">
              <td style="padding:12px; font-weight:bold; color:#58a6ff; position:sticky; left:0; background:${index % 2 === 0 ? '#02040a' : '#0d1117'}; z-index:1;">${h.sym}</td>
              <td style="padding:12px; text-align:center; color:${roeColor}">${roe !== '—' ? roe + '%' : '—'}</td>
              <td style="padding:12px; text-align:center;">${roce !== '—' ? roce + '%' : '—'}</td>
              <td style="padding:12px; text-align:center; color:#d29922;">${opm !== '—' ? opm + '%' : '—'}</td>
              <td style="padding:12px; text-align:center;">${npm !== '—' ? npm + '%' : '—'}</td>
              <td style="padding:12px; text-align:center;">${pe !== '—' ? Number(pe).toFixed(1) : '—'}</td>
              <td style="padding:12px; text-align:center; color:${deColor}">${debtEq}</td>
              <td style="padding:12px; text-align:center;">${prom !== '—' ? prom + '%' : '—'}</td>
              <td style="padding:12px; text-align:right; font-weight:bold;">₹${Number(ltp).toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
            </tr>`;
  });

  html += `</table></div></div>`;
  container.innerHTML = html;
}
