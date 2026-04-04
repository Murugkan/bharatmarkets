/**
 * Enhanced renderPortfolio (Step 1 COMPLETE)
 * Now waits for BOTH the Data Engine AND the Portfolio Sync.
 */
async function renderPortfolio(container) {
  if (!container) return;

  // 1. Kill any "Syncing" overlays from the core app
  const overlay = document.querySelector('.loading, #sync-overlay');
  if (overlay) overlay.style.display = 'none';

  // 2. BOOT DATA ENGINE (Fundamentals)
  if (!window.fundLoaded) {
    container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> BOOTING DATA ENGINE...</div>`;
    const success = await loadFundamentals();
    if (!success) {
      container.innerHTML = `<div style="padding:40px;color:#f85149;">❌ Step 1 Failure: Fundamentals 404</div>`;
      return;
    }
  }

  // 3. WAIT FOR S.PORTFOLIO (Broker/Core Sync)
  // We will give the system 5 seconds to populate S.portfolio before failing.
  let attempts = 0;
  while ((!window.S || !S.portfolio || S.portfolio.length === 0) && attempts < 10) {
    container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> SYNCING BROKER NODES (${attempts + 1}/10)...</div>`;
    await new Promise(r => setTimeout(r, 500)); // Wait 500ms
    attempts++;
  }

  // 4. FINAL CHECK
  if (!window.S || !S.portfolio || S.portfolio.length === 0) {
    container.innerHTML = `
      <div style="padding:40px;text-align:center;color:#8b949e;font-family:sans-serif;">
        <div style="font-size:20px;margin-bottom:10px;">0 Stocks Detected</div>
        <div style="font-size:12px;">Broker sync timeout. Please check app-core.js or login status.</div>
      </div>`;
    return;
  }

  // 5. CALL ORIGINAL RENDER LOGIC
  console.log("🚀 Both engines ready. Drawing 37-column table.");
  
  /* PASTE THE REST OF YOUR ORIGINAL RENDER LOGIC HERE 
     (Everything from "const out = [];" down to the end of the function)
  */
}
