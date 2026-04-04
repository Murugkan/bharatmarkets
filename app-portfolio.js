async function renderPortfolio(container) {
  if (!container) return;

  // 1. Clear Overlays
  const overlay = document.querySelector('.loading, #sync-overlay');
  if (overlay) overlay.style.display = 'none';

  // 2. Load Fundamentals
  if (!window.fundLoaded) {
    container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> BOOTING DATA ENGINE...</div>`;
    await loadFundamentals();
  }

  // 3. Wait for Portfolio (with 3-second timeout)
  let attempts = 0;
  while ((!window.S?.portfolio?.length) && attempts < 6) {
    container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> SYNCING BROKER NODES (${attempts + 1}/6)...</div>`;
    await new Promise(r => setTimeout(r, 500));
    attempts++;
  }

  // 4. Emergency Fallback (For Testing Only)
  // If S.portfolio is still empty, let's fill it with keys from FUND 
  // so we can actually see the 37 columns render.
  if (!window.S?.portfolio?.length && window.FUND) {
    console.warn("⚠️ Broker sync empty. Using Fundamentals as fallback for UI test.");
    window.S.portfolio = Object.keys(window.FUND).map(sym => ({
        sym: sym,
        isin: window.FUND[sym].isin || ''
    }));
  }

  // 5. Render your original 37-column logic
  // (Paste your original table drawing code here)
  console.log("🚀 Rendering 37-column table...");
  drawTable(container); 
}

function drawTable(container) {
    // YOUR ORIGINAL 37-COLUMN TABLE CODE GOES HERE
}
