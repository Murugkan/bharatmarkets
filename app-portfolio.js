/**
 * STEP 1: FINAL INTEGRATED TEST (v21.0)
 * Bypasses empty states to force-render the 37-column table.
 */
async function loadFundamentals() {
  if (window.pfRefreshing) return;
  window.pfRefreshing = true;

  try {
    const r = await fetch(`./fundamentals.json?v=${Date.now()}`);
    if (!r.ok) throw new Error("File Not Found");
    
    const data = await r.json();
    
    // Explicitly target the "stocks" wrapper from your JSON
    window.FUND = data.stocks || data;
    
    window.ISIN_MAP = {};
    Object.keys(window.FUND).forEach(sym => {
      const s = window.FUND[sym];
      if (s && s.isin) window.ISIN_MAP[s.isin] = sym;
    });

    window.fundLoaded = true;
    return true;
  } catch (e) {
    console.error("Step 1 Load Error:", e.message);
    return false;
  } finally {
    window.pfRefreshing = false;
  }
}

async function renderPortfolio(container) {
  if (!container) return;

  // 1. Clear UI
  const overlay = document.querySelector('.loading, #sync-overlay');
  if (overlay) overlay.style.display = 'none';

  // 2. Ensure Engine is Booted
  if (!window.fundLoaded) {
    container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> BOOTING DATA ENGINE...</div>`;
    await loadFundamentals();
  }

  // 3. DATA INTEGRITY CHECK & DUMMY FALLBACK
  // If no portfolio is found, we inject OLECTRA and others to test the 37 columns
  if (!window.S || !S.portfolio || S.portfolio.length === 0) {
    console.warn("⚠️ Injecting Test Data to verify 37-column UI...");
    window.S = window.S || { portfolio: [] };
    
    // Use first 5 stocks from FUND, or hardcoded samples if FUND is empty
    const samples = (window.FUND && Object.keys(window.FUND).length > 0) 
      ? Object.keys(window.FUND).slice(0, 5) 
      : ["OLECTRA", "RELIANCE", "TCS", "INFY", "HDFCBANK"];

    window.S.portfolio = samples.map(sym => ({
      sym: sym,
      isin: (window.FUND && window.FUND[sym]) ? window.FUND[sym].isin : '',
      qty: 10,
      avg: 100
    }));
  }

  // 4. DRAW THE TABLE
  // This calls the original drawing logic from your app-portfolio-Nkl.js file
  console.log("🚀 Rendering 37-column table with " + S.portfolio.length + " stocks.");
  
  // --- PASTE YOUR ORIGINAL TABLE DRAWING LOGIC BELOW ---
  // (Start from: const out = []; ... all the way to the end of your original file)
}
