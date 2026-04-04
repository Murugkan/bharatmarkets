// =============================================================
// STEP 1: RELIABLE DATA LOADER (INTEGRATED VERSION)
// =============================================================

/**
 * Replaces the old 1-hour localStorage logic with a 
 * Fail-Safe Direct Fetch for fundamentals.json.
 */
async function loadFundamentals(forceRefresh) {
  if (window.pfRefreshing) return;
  window.pfRefreshing = true;

  try {
    console.log("📡 [Step 1] Requesting fresh fundamentals...");
    
    // Force browser to ignore cache and get the latest Python-generated data
    const response = await fetch(`./fundamentals.json?v=${Date.now()}`, { 
      cache: "no-store" 
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    const stockData = data.stocks || data;

    // 1. Update Global Fund Object
    window.FUND = stockData;
    
    // 2. Re-build the ISIN Map used by the table logic
    window.ISIN_MAP = {};
    Object.keys(stockData).forEach(sym => {
      const s = stockData[sym];
      if (s && s.isin) window.ISIN_MAP[s.isin] = sym;
    });

    window.fundLoaded = true;
    window.pfLastRefresh = Date.now();
    
    console.log(`✅ [Step 1] Sync Success: ${Object.keys(stockData).length} stocks ready.`);
    return true;

  } catch (e) {
    console.error("❌ [Step 1] Load Failed:", e.message);
    window.fundLoaded = false;
    return false;
  } finally {
    window.pfRefreshing = false;
  }
}

/**
 * Enhanced renderPortfolio that ensures Step 1 is successful 
 * before trying to draw the 37-column table.
 */
async function renderPortfolio(container) {
  if (!container) return;

  // Kill any existing "Syncing" overlays from the core app
  const overlay = document.querySelector('.loading, #sync-overlay');
  if (overlay) overlay.style.display = 'none';

  // If fundamentals aren't loaded yet, trigger the Step 1 loader
  if (!window.fundLoaded) {
    container.innerHTML = `<div style="padding:40px;color:var(--bl2);font-family:monospace;">> BOOTING DATA ENGINE...</div>`;
    const success = await loadFundamentals();
    if (!success) {
      container.innerHTML = `<div style="padding:40px;color:var(--rd2);">❌ Step 1 Failure: Could not reach fundamentals.json</div>`;
      return;
    }
  }

  // NOW CALL YOUR ORIGINAL TABLE LOGIC
  // (The rest of this function is your original code from app-portfolio-Nkl.js)
  
  if (!S.portfolio || S.portfolio.length === 0) {
    container.innerHTML = `<div style="padding:40px;text-align:center;color:var(--tx3);">0 Stocks Detected in S.portfolio</div>`;
    return;
  }

  // ... [YOUR ORIGINAL TABLE RENDERING LOGIC STARTS HERE] ...
  // (Paste the rest of your original renderPortfolio function here)
  // Ensure you include your cellColor, getSignalColor, etc. functions below.
}

/* NOTE: For this test, ensure you have pasted all your original 
  helper functions (cellColor, getSignalColor, openStatsModal, etc.) 
  below this line so the table can render properly.
*/
