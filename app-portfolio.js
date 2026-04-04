async function loadFundamentals() {
  if (window.pfRefreshing) return;
  window.pfRefreshing = true;

  try {
    // 1. Fetch Master Symbol List first (The Anchor)
    const symRes = await fetch(`./symbols.json?v=${Date.now()}`);
    const symbolsData = await symRes.json();
    
    // 2. Fetch Fundamental Data
    const fundRes = await fetch(`./fundamentals.json?v=${Date.now()}`);
    const fundData = await fundRes.json();

    // 3. Map Symbols to S.portfolio so the table has rows to draw
    window.S = window.S || {};
    window.S.portfolio = symbolsData.map(item => ({
      sym: item.sym,
      isin: item.isin,
      sector: item.sector
    }));

    // 4. Map Fundamental Data to global FUND object
    window.FUND = fundData.stocks || fundData;
    
    // 5. Build ISIN Map for the 37-column logic
    window.ISIN_MAP = {};
    Object.keys(window.FUND).forEach(s => {
      if (window.FUND[s].isin) window.ISIN_MAP[window.FUND[s].isin] = s;
    });

    window.fundLoaded = true;
    console.log(`✅ Step 1: ${window.S.portfolio.length} Symbols loaded as Master List.`);
    return true;
  } catch (e) {
    console.error("❌ Step 1 Loader Error:", e.message);
    return false;
  } finally {
    window.pfRefreshing = false;
  }
}

async function renderPortfolio(container) {
  if (!container) return;

  const overlay = document.querySelector('.loading, #sync-overlay');
  if (overlay) overlay.style.display = 'none';

  if (!window.fundLoaded) {
    container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> LOADING SYMBOLS MASTER...</div>`;
    await loadFundamentals();
  }

  // Double Check
  if (!window.S?.portfolio?.length) {
    container.innerHTML = `<div style="padding:40px;color:#f85149;">❌ Error: Master Symbols List Empty.</div>`;
    return;
  }

  // --- START ORIGINAL 37-COLUMN RENDER ---
  console.log("🚀 Rendering 37 columns for " + S.portfolio.length + " stocks.");
  
  // (Paste your original table drawing code here)
}
