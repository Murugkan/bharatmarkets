/**
 * STEP 1: SYMBOLS-FIRST DATA ENGINE
 * Uses your Master Symbol list to map all fundamental data.
 */
async function loadFundamentals() {
  if (window.pfRefreshing) return;
  window.pfRefreshing = true;

  try {
    // 1. Direct Fetch with Timestamp to bypass iPhone cache
    const r = await fetch(`./fundamentals.json?v=${Date.now()}`);
    if (!r.ok) throw new Error("Fundamentals file missing on server");
    
    const data = await r.json();
    
    // 2. Map data to the "stocks" object
    window.FUND = data.stocks || data;
    
    // 3. Build ISIN Map for the 37-column logic
    window.ISIN_MAP = {};
    const keys = Object.keys(window.FUND);
    keys.forEach(sym => {
      const s = window.FUND[sym];
      if (s && s.isin) window.ISIN_MAP[s.isin] = sym;
    });

    console.log(`✅ Engine Linked: ${keys.length} data nodes found.`);
    window.fundLoaded = true;
    return true;
  } catch (e) {
    console.error("❌ Engine Boot Error:", e.message);
    return false;
  } finally {
    window.pfRefreshing = false;
  }
}

async function renderPortfolio(container) {
  if (!container) return;

  // Kill the "Syncing" overlay immediately
  const overlay = document.querySelector('.loading, #sync-overlay');
  if (overlay) overlay.style.display = 'none';

  // 1. Ensure Fundamentals are ready
  if (!window.fundLoaded) {
    container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> BOOTING DATA ENGINE...</div>`;
    await loadFundamentals();
  }

  // 2. Verify Symbols/Portfolio List
  // S.portfolio is your master list of Symbols
  if (!window.S || !S.portfolio || S.portfolio.length === 0) {
    container.innerHTML = `
      <div style="padding:40px;color:#8b949e;text-align:center;">
        <b>0 Symbols Detected</b><br>
        <small>Waiting for Broker/Core Sync...</small>
      </div>`;
    return;
  }

  // 3. START 37-COLUMN RENDER
  // Now that the engine is loaded, we call your original drawing logic
  console.log(`🚀 Rendering ${S.portfolio.length} Symbols...`);
  
  // --- [PASTE YOUR ORIGINAL drawTable OR render logic HERE] ---
}
