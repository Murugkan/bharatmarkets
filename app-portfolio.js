async function renderPortfolio(container) {
  if (!container) return;
  const overlay = document.querySelector('.loading, #sync-overlay');
  if (overlay) overlay.style.display = 'none';

  if (!window.fundLoaded) {
    container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> BOOTING ENGINE...</div>`;
    await loadFundamentals();
  }

  // Engine Hit Counter
  let dataHits = 0;
  window.S.portfolio.forEach(h => {
    if (window.FUND[h.sym] || (h.isin && window.FUND[window.ISIN_MAP[h.isin]])) dataHits++;
  });

  let html = `<div style="padding:10px; background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif;">`;
  
  // Status Bar
  html += `<div style="margin-bottom:15px; padding:10px; background:#0d1117; border:1px solid #1e3350; border-radius:4px; font-size:11px; font-family:monospace;">
            <span style="color:#3fb950;">● ENGINE: READY</span> | 
            <span style="color:#58a6ff;">STOCKS: ${window.S.portfolio.length}</span> | 
            <span style="color:#d29922;">DATA HITS: ${dataHits}</span>
           </div>`;

  html += `<div style="overflow-x:auto; border:1px solid #1e3350; border-radius:8px;">`;
  html += `<table style="width:100%; border-collapse:collapse; white-space:nowrap; font-size:12px;">`;
  
  // Header Row
  html += `<tr style="background:#0d1117; border-bottom:2px solid #1e3350;">
            <th style="padding:12px; text-align:left; position:sticky; left:0; background:#0d1117;">SYMBOL</th>
            <th style="padding:12px;">SECTOR</th>
            <th style="padding:12px;">ROE%</th>
            <th style="padding:12px;">OPM%</th>
            <th style="padding:12px; text-align:right;">LTP</th>
          </tr>`;

  window.S.portfolio.forEach(h => {
    // Advanced Matcher
    const f = window.FUND[h.sym] || (h.isin ? window.FUND[window.ISIN_MAP[h.isin]] : null) || {};
    
    // Data Extraction for Step 2
    const roe = f.roe !== undefined ? f.roe : '—';
    const opm = f.opm !== undefined ? f.opm : '—';
    const ltp = f.ltp || f.price || 0; // Check both 'ltp' and 'price' keys
    
    // Colors
    const roeColor = (parseFloat(roe) > 15) ? '#3fb950' : (parseFloat(roe) < 0 ? '#f85149' : '#fff');
    const opmColor = (parseFloat(opm) > 20) ? '#d29922' : '#fff'; // Gold for high margin

    html += `<tr style="border-bottom:1px solid #1e3350;">
              <td style="padding:12px; font-weight:bold; color:#58a6ff; position:sticky; left:0; background:#02040a;">${h.sym}</td>
              <td style="padding:12px; color:#8b949e;">${h.sector || f.sector || '—'}</td>
              <td style="padding:12px; text-align:center; color:${roeColor}">${roe !== '—' ? roe + '%' : '—'}</td>
              <td style="padding:12px; text-align:center; color:${opmColor}">${opm !== '—' ? opm + '%' : '—'}</td>
              <td style="padding:12px; text-align:right; font-weight:bold;">₹${Number(ltp).toLocaleString('en-IN')}</td>
            </tr>`;
  });

  html += `</table></div></div>`;
  container.innerHTML = html;
}
