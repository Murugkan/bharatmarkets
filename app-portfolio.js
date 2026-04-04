// 1. Internal State Safety Net
if (typeof pfRefreshing === 'undefined') window.pfRefreshing = false;
if (typeof fundLoaded === 'undefined') window.fundLoaded = false;

async function loadFundamentals() {
  if (window.pfRefreshing) return;
  window.pfRefreshing = true;

  try {
    const ts = Date.now();
    // Fetch both files
    const [sRes, fRes] = await Promise.all([
      fetch(`./symbols.json?v=${ts}`),
      fetch(`./fundamentals.json?v=${ts}`)
    ]);

    const sData = await sRes.json();
    const fData = await fRes.json();

    // MAP MASTER SYMBOLS (The Array)
    window.S = window.S || {};
    window.S.portfolio = sData.map(item => ({
      sym: item.sym,
      isin: item.isin || '',
      sector: item.sector || 'N/A'
    }));

    // MAP FUNDAMENTALS (The Object)
    window.FUND = fData.stocks || fData;
    
    // BUILD ISIN LOOKUP
    window.ISIN_MAP = {};
    Object.keys(window.FUND).forEach(key => {
      const stock = window.FUND[key];
      if (stock && stock.isin) window.ISIN_MAP[stock.isin] = key;
    });

    window.fundLoaded = true;
    return true;
  } catch (e) {
    console.error("Engine Crash:", e);
    return false;
  } finally {
    window.pfRefreshing = false;
  }
}

async function renderPortfolio(container) {
  if (!container) return;

  // Kill any stuck app overlays
  const overlay = document.querySelector('.loading, #sync-overlay');
  if (overlay) overlay.style.display = 'none';

  // Boot Engine if needed
  if (!window.fundLoaded) {
    container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> BOOTING...</div>`;
    await loadFundamentals();
  }

  // Final check before drawing
  if (!window.S?.portfolio?.length) {
    container.innerHTML = `<div style="padding:40px;color:#f85149;">ERROR: SYMBOLS_EMPTY</div>`;
    return;
  }

  // --- START 37-COLUMN TABLE DRAWING ---
  console.log("🚀 DRAWING TABLE");
  
  // Create the table container
  let html = `<div style="padding:10px; background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif;">`;
  html += `<h2 style="margin-bottom:15px; font-size:18px;">${window.S.portfolio.length} STOCKS</h2>`;
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

  // Body Rows
  window.S.portfolio.forEach(h => {
    const f = window.FUND[h.sym] || (h.isin ? window.FUND[window.ISIN_MAP[h.isin]] : null) || {};
    
    html += `<tr style="border-bottom:1px solid #1e3350;">
              <td style="padding:12px; font-weight:bold; color:#58a6ff; position:sticky; left:0; background:#02040a;">${h.sym}</td>
              <td style="padding:12px; color:#8b949e;">${h.sector || f.sector || '—'}</td>
              <td style="padding:12px; text-align:center; color:${f.roe > 15 ? '#3fb950' : '#fff'}">${f.roe ? f.roe + '%' : '—'}</td>
              <td style="padding:12px; text-align:center;">${f.opm || '—'}</td>
              <td style="padding:12px; text-align:right; font-weight:bold;">₹${(f.ltp || 0).toFixed(0)}</td>
            </tr>`;
  });

  html += `</table></div></div>`;
  container.innerHTML = html;
}
