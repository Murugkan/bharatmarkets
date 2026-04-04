async function loadFundamentals() {
  if (window.pfRefreshing) return;
  window.pfRefreshing = true;

  try {
    // 1. Fetch Symbols (The Array: [{}, {}, ...])
    const symRes = await fetch(`./symbols.json?v=${Date.now()}`);
    const symbolsData = await symRes.json();
    
    // 2. Fetch Fundamentals (The Object: {stocks: {...}})
    const fundRes = await fetch(`./fundamentals.json?v=${Date.now()}`);
    const fundData = await fundRes.json();

    // 3. Populate S.portfolio correctly from the Array
    window.S = window.S || {};
    if (Array.isArray(symbolsData)) {
      window.S.portfolio = symbolsData.map(item => ({
        sym: item.sym,
        isin: item.isin || '',
        sector: item.sector || 'N/A'
      }));
    } else {
      throw new Error("symbols.json is not an Array");
    }

    // 4. Map Fundamentals
    window.FUND = fundData.stocks || fundData;
    
    // 5. Build ISIN Map for the 37-column lookup
    window.ISIN_MAP = {};
    Object.keys(window.FUND).forEach(s => {
      const f = window.FUND[s];
      if (f && f.isin) window.ISIN_MAP[f.isin] = s;
    });

    window.fundLoaded = true;
    console.log(`✅ Step 1: ${window.S.portfolio.length} Symbols Loaded.`);
    return true;

  } catch (e) {
    console.error("❌ Step 1 Error:", e.message);
    return false;
  } finally {
    window.pfRefreshing = false;
  }
}
