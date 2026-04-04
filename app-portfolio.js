/**
 * BHARATMARKETS PRO - RAW FUNDAMENTALS PROBE
 * Goal: Read ONLY the first line from fundamentals.json.
 */
async function renderPortfolio(container) {
    if (!container) return;

    // 1. Force-hide the "Syncing" overlay immediately
    const overlay = document.querySelector('.loading, #sync-overlay');
    if (overlay) overlay.style.display = 'none';

    container.innerHTML = `<div style="padding:40px; color:#58a6ff; font-family:monospace;">> ACCESSING FUNDAMENTALS...</div>`;

    try {
        // 2. Direct Fetch with cache-busting
        const response = await fetch('fundamentals.json?v=' + Date.now());
        const data = await response.json();
        
        // 3. Identify the first stock entry
        const stocks = data.stocks || data;
        const firstSymbol = Object.keys(stocks)[0];
        const details = stocks[firstSymbol];

        // 4. DISPLAY ONLY THIS ONE ROW
        container.innerHTML = `
            <div style="padding:25px; background:#111d30; border:2px solid #3fb950; border-radius:12px; color:#fff; font-family:sans-serif;">
                <div style="color:#3fb950; font-weight:bold; font-size:10px; margin-bottom:8px;">✅ FUNDAMENTALS READ SUCCESS</div>
                <div style="font-size:28px; font-weight:bold;">${firstSymbol}</div>
                <hr style="border:0; border-top:1px solid #1e3350; margin:12px 0;">
                <div style="font-size:18px; line-height:1.6;">
                    ROE: <span style="color:#58a6ff">${details.roe || details.ROE || 'N/A'}%</span><br>
                    SEC: <span style="color:#8b949e">${details.sector || 'N/A'}</span><br>
                    LTP: <span style="color:#58a6ff">₹${details.ltp || 'N/A'}</span>
                </div>
            </div>`;

    } catch (e) {
        container.innerHTML = `<div style="padding:20px; color:#f85149; font-family:monospace;">
            ❌ ERROR: ${e.message}
        </div>`;
    }
}
