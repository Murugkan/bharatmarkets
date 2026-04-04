// 1. GLOBAL STATE - Persistent across renders
if (typeof window.pfRefreshing === 'undefined') window.pfRefreshing = false;
if (typeof window.fundLoaded === 'undefined') window.fundLoaded = false;

/**
 * STEP 1: THE DATA ENGINE
 * Fetches Master Symbols and Fundamental Data with Cache Busting
 */
async function loadFundamentals() {
  if (window.pfRefreshing) return;
  window.pfRefreshing = true;

  try {
    const ts = Date.now();
    
    // Fetch both JSON files simultaneously
    const [sRes, fRes] = await Promise.all([
      fetch(`./symbols.json?v=${ts}`),
      fetch(`./fundamentals.json?v=${ts}`)
    ]);

    const sData = await sRes.json();
    const fData = await fRes.json();

    // MAP MASTER SYMBOLS (From symbols.json Array)
    window.S = window.S || {};
    window.S.portfolio = sData.map(item => ({
      sym: item.sym || '?',
      isin: item.isin || '',
      sector: item.sector || 'N/A'
    }));

    // MAP FUNDAMENTAL DATA (From fundamentals.json Object)
    window.FUND = fData.stocks || fData;
    
    // BUILD ISIN LOOKUP BRIDGE
    window.ISIN_MAP = {};
    Object.keys(window.FUND).forEach(key => {
      const stock = window.FUND[key];
      if (stock && stock.isin) {
        window.ISIN_MAP[stock.isin] = key;
      }
    });

    window.fundLoaded = true;
    console.log("✅ Engine Ready: " + window.S.portfolio.length + " Symbols Synced.");
    return true;
  } catch (e) {
    console.error("❌ Engine Error:", e);
    return false;
  } finally {
    window.pfRefreshing = false;
  }
}

/**
 * STEP 2: THE RENDERER
 * Draws the table with mapped OPM% and LTP
 */
async function renderPortfolio(container) {
  if (!container) return;

  // Clear any existing app-level loading overlays
  const overlay = document.querySelector('.loading, #sync-overlay');
  if (overlay) overlay.style.display = 'none';

  // Boot the engine if data isn't ready
  if (!window.fundLoaded) {
    container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> BOOTING ENGINE...</div>`;
    const success = await loadFundamentals();
    if (!success) {
      container.innerHTML = `<div style="padding:40px;color:#f85149;">❌ ENGINE_LOAD_FAILURE</div>`;
      return;
    }
  }

  // Calculate Data Hits for the Diagnostic Header
  let dataHits = 0;
  window.S.portfolio.forEach(h => {
    if (window.FUND[h.sym] || (h.isin && window.FUND[window.ISIN_MAP[h.isin]])) {
      dataHits++;
    }
  });

  // Start Building HTML String
  let html = `<div style="padding:10px; background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif;">`;
  
  // DIAGNOSTIC STATUS BAR
  html += `<div style="margin-bottom:15px; padding:10px; background:#0d1117; border:1px solid #1e3350; border-radius:4px; font-size:11px; font-family:monospace;">
            <span style="color:#3fb950;">● ENGINE: READY</span> | 
            <span style="color:#58a6ff;">STOCKS: ${window.S.portfolio.length}</span> | 
            <span style="color:#d29922;">DATA HITS: ${dataHits}</span>
           </div>`;

  // TABLE CONTAINER
  html += `<div style="overflow-x:auto; border:1px solid #1e3350; border-radius:8px;">`;
  html += `<table style="width:100%; border-collapse:collapse; white-space:nowrap; font-size:12px;">`;
  
  // HEADER ROW
  html += `<tr style="background:#0d1117; border-bottom:2px solid #1e3350; color:#8b949e; text-transform:uppercase; font-size:10px;">
            <th style="padding:12px; text-align:left; position:sticky; left:0; background:#0d1117; z-index:2;">Symbol</th>
            <th style="padding:12px; text-align:left;">Sector</th>
            <th style="padding:12px; text-align:center;">ROE %</th>
            <th style="padding:12px; text-align:center;">OPM %</th>
            <th style="padding:12px; text-align:right;">Price (LTP)</th>
          </tr>`;

  // DATA ROWS
  window.S.portfolio.forEach((h, index) => {
    // Attempt match via Symbol or ISIN
    const f = window.FUND[h.sym] || (h.isin ? window.FUND[window.ISIN_MAP[h.isin]] : null) || {};
    
    // Field Extraction based on fundamentals.json structure
    const roe = f.roe !== undefined ? f.roe : '—';
    const opm = f.opm_pct !== undefined ? f.opm_pct : '—';
    const ltp = f.ltp || 0;
    
    // Dynamic Styling
    const rowBg = index % 2 === 0 ? 'transparent' : '#0d1117';
    const roeColor = (parseFloat(roe) > 15) ? '#3fb950' : (parseFloat(roe) < 0 ? '#f85149' : '#fff');
    const opmColor = (parseFloat(opm) > 20) ? '#d29922' : '#fff';

    html += `<tr style="background:${rowBg}; border-bottom:1px solid #1e3350;">
              <td style="padding:12px; font-weight:bold; color:#58a6ff; position:sticky; left:0; background:${index % 2 === 0 ? '#02040a' : '#0d1117'}; z-index:1;">${h.sym}</td>
              <td style="padding:12px; color:#8b949e;">${h.sector || f.sector || '—'}</td>
              <td style="padding:12px; text-align:center; font-weight:bold; color:${roeColor}">${roe !== '—' ? roe + '%' : '—'}</td>
              <td style="padding:12px; text-align:center; color:${opmColor}">${opm !== '—' ? opm + '%' : '—'}</td>
              <td style="padding:12px; text-align:right; font-weight:bold; color:#fff;">₹${Number(ltp).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
            </tr>`;
  });

  html += `</table></div></div>`;
  
  // Inject into the DOM
  container.innerHTML = html;
}
