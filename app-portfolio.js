/**
 * BHARATMARKETS PRO - ARCHITECTURE BYPASS (v16.0)
 * Force-clears the "Syncing" screen to show one data row.
 */
async function renderPortfolio(container) {
    if (!container) return;

    // 1. FORCE THE UI OPEN (Remove any "Syncing" overlays manually)
    const overlays = document.querySelectorAll('.loading, #sync-overlay, [style*="z-index: 9999"]');
    overlays.forEach(el => el.style.display = 'none');

    container.innerHTML = `<div style="padding:40px; color:#58a6ff; font-family:monospace;">> ACCESSING FUNDAMENTALS...</div>`;

    try {
        const r = await fetch('fundamentals.json?v=' + Date.now());
        const data = await r.json();
        
        // 2. Locate the first available stock
        const stocksObj = data.stocks || data;
        const firstSymbol = Object.keys(stocksObj)[0];
        const s = stocksObj[firstSymbol];

        // 3. RENDER ONE RAW ROW
        container.innerHTML = `
            <div style="padding:25px; background:#111d30; border:2px solid #58a6ff; border-radius:12px; color:#fff; font-family:sans-serif;">
                <div style="color:#58a6ff; font-weight:bold; font-size:10px; margin-bottom:8px;">DATA PROBE SUCCESSFUL</div>
                <div style="font-size:28px; font-weight:bold;">${firstSymbol}</div>
                <hr style="border:0; border-top:1px solid #1e3350; margin:12px 0;">
                <div style="font-size:18px; line-height:1.6;">
                    ROE: <span style="color:#3fb950">${s.roe || s.ROE || 'N/A'}%</span><br>
                    LTP: <span style="color:#3fb950">₹${s.ltp || s.LTP || 'N/A'}</span><br>
                    SEC: <span style="color:#8b949e">${s.sector || 'N/A'}</span>
                </div>
                <div style="margin-top:15px; font-size:10px; color:#484f58;">
                    Total nodes in file: ${Object.keys(stocksObj).length}
                </div>
            </div>`;

    } catch (e) {
        container.innerHTML = `<div style="padding:20px; color:#f85149; font-family:monospace;">
            ❌ PROBE ERROR: ${e.message}<br>
            Ensure fundamentals.json is in the root folder.
        </div>`;
    }
}

// 4. ARCHITECTURE OVERRIDE
// This forces the render even if the boot sequence is stuck.
setTimeout(() => {
    const mainBox = document.getElementById('main-content') || document.body;
    if (mainBox.innerHTML.includes('Syncing')) {
        renderPortfolio(mainBox);
    }
}, 2000);
