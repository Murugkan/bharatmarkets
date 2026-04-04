/**
 * BHARATMARKETS PRO - RAW PROBE (v18.0)
 * Goal: Read ONLY the first entry from fundamentals.json
 */
async function renderPortfolio(container) {
    if (!container) return;

    // Force clear the "Syncing" screen manually
    const overlay = document.querySelector('.loading, #sync-overlay');
    if (overlay) overlay.style.display = 'none';

    container.innerHTML = `<div style="padding:40px; color:#58a6ff; font-family:monospace;">> ACCESSING FILE...</div>`;

    try {
        const response = await fetch('fundamentals.json?v=' + Date.now());
        const data = await response.json();
        
        // Target the 'stocks' object from your JSON structure
        const stocks = data.stocks || data;
        const symbols = Object.keys(stocks);
        
        if (symbols.length > 0) {
            const firstSym = symbols[0];
            const stock = stocks[firstSym];

            // RENDER ONLY THE FIRST ROW
            container.innerHTML = `
                <div style="padding:20px; background:#111d30; border:2px solid #3fb950; border-radius:12px; color:#fff; font-family:sans-serif;">
                    <div style="color:#3fb950; font-weight:bold; font-size:12px; margin-bottom:10px;">✅ SINGLE LINE READ</div>
                    <div style="font-size:24px; font-weight:bold;">${firstSym}</div>
                    <hr style="border:0; border-top:1px solid #1e3350; margin:12px 0;">
                    <div style="font-size:18px;">
                        ROE: <span style="color:#58a6ff">${stock.roe || 'N/A'}%</span><br>
                        LTP: <span style="color:#58a6ff">₹${stock.ltp || 'N/A'}</span><br>
                        SEC: <span style="color:#8b949e">${stock.sector || 'N/A'}</span>
                    </div>
                </div>
            `;
        } else {
            container.innerHTML = `<div style="color:#f85149;">❌ File is empty.</div>`;
        }
    } catch (e) {
        container.innerHTML = `<div style="color:#f85149; padding:20px;">❌ FAILED: ${e.message}</div>`;
    }
}
