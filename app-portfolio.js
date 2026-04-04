async function renderPortfolio(container) {
  if (!container) return;

  // 1. Hide any stuck app overlays
  var overlay = document.querySelector('.loading, #sync-overlay');
  if (overlay) overlay.style.display = 'none';

  // 2. Boot Engine
  if (!window.fundLoaded) {
    container.innerHTML = '<div style="padding:40px;color:#58a6ff;font-family:monospace;">> SYNCING...</div>';
    await loadFundamentals();
  }

  // 3. Safety Check
  if (!window.S || !window.S.portfolio || window.S.portfolio.length === 0) {
    container.innerHTML = '<div style="padding:40px;color:#f85149;">❌ MASTER LIST EMPTY</div>';
    return;
  }

  // 4. PRE-CALCULATE MATCHES (For Debugging)
  var matchedCount = 0;
  var portfolio = window.S.portfolio;
  var fund = window.FUND || {};
  var isinMap = window.ISIN_MAP || {};

  // 5. DRAW THE TABLE
  var html = '<div style="padding:10px; background:#02040a; color:#fff; font-family:sans-serif; font-size:12px;">';
  
  // Header Info
  html += '<div style="margin-bottom:10px; padding:10px; background:#111d30; border-radius:8px; border:1px solid #1e3350;">';
  html += '<div style="color:#8b949e; font-size:10px;">MASTER SYMBOLS: ' + portfolio.length + '</div>';
  html += '</div>';

  html += '<div style="overflow-x:auto;"><table style="width:100%; border-collapse:collapse;">';
  html += '<tr style="background:#0d1117; border-bottom:2px solid #1e3350; color:#8b949e; font-size:10px;">';
  html += '<th style="padding:10px; text-align:left;">SYMBOL</th>';
  html += '<th style="padding:10px; text-align:left;">SECTOR</th>';
  html += '<th style="padding:10px; text-align:right;">ROE%</th>';
  html += '</tr>';

  for (var i = 0; i < portfolio.length; i++) {
    var stock = portfolio[i];
    var symbol = stock.sym || '—';
    var isin = stock.isin || '';
    
    // THE HYBRID MATCHING LOGIC
    var f = fund[symbol]; // Match 1: Direct Symbol
    if (!f && isin && isinMap[isin]) {
        f = fund[isinMap[isin]]; // Match 2: via ISIN
    }
    if (!f) f = {}; // Final Fallback
    
    // Count matches for the debug header
    if (f.roe !== undefined) matchedCount++;

    // Row Styling
    var rowBg = (i % 2 === 0) ? 'transparent' : '#0d1117';
    var sectorText = stock.sector || f.sector || '—';
    var roeVal = f.roe !== undefined ? f.roe : '—';
    var roeColor = (parseFloat(roeVal) > 15) ? '#3fb950' : '#fff';

    html += '<tr style="background:' + rowBg + '; border-bottom:1px solid #1e3350;">';
    html += '<td style="padding:12px; font-weight:bold; color:#58a6ff;">' + symbol + '</td>';
    html += '<td style="padding:12px; color:#8b949e;">' + sectorText + '</td>';
    html += '<td style="padding:12px; text-align:right; font-weight:bold; color:' + roeColor + ';">' + roeVal + (roeVal !== '—' ? '%' : '') + '</td>';
    html += '</tr>';
  }

  html += '</table></div></div>';
  
  // Update the matched count in the header
  html = html.replace('MASTER SYMBOLS: ' + portfolio.length, 'MASTER SYMBOLS: ' + portfolio.length + ' | DATA HITS: ' + matchedCount);
  
  container.innerHTML = html;
}
