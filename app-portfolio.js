/**
 * BHARATMARKETS PRO - RAW DATA TEST (v14.0)
 * Goal: Read just ONE sample row.
 */
async function renderPortfolio(container) {
    if (!container) return;

    container.innerHTML = `<div style="padding:40px; color:#58a6ff; font-family:monospace; background:#02040a; min-height:100vh;">
        📡 ATTEMPTING RAW READ...
    </div>`;

    try {
        const response = await fetch('fundamentals.json?nocache=' + Date.now());
        const data = await response.json();
        
        // Your JSON structure has a "stocks" object
        const stockKeys = Object.keys(data.stocks || {});
        
        if (stockKeys.length > 0) {
            const firstSymbol = stockKeys[0];
            const stockData = data.stocks[firstSymbol];

            // RENDER ONLY THE FIRST ROW FOUND
            container.innerHTML = `
                <div style="padding:20px; background:#111d30; border:2px solid #3fb950; border-radius:12px; font-family:sans-serif; color:#fff;">
                    <h2 style="margin:0; color:#3fb950;">✅ DATA FOUND</h2>
                    <hr style="border:0; border-top:1px solid #1e3350; margin:15px 0;">
                    
                    <div style="font-size:24px; font-weight:bold;">${firstSymbol}</div>
                    <div style="margin-top:10px; font-size:18px;">
                        ROE: <span style="color:#58a6ff">${stockData.roe || 'N/A'}%</span><br>
                        LTP: <span style="color:#58a6ff">₹${stockData.ltp || 'N/A'}</span><br>
                        Sector: <span style="color:#8b949e">${stockData.sector || 'Unknown'}</span>
                    </div>
                    
                    <div style="margin-top:20px; font-size:10px; color:#484f58;">
                        Total Stocks in File: ${stockKeys.length}
                    </div>
                </div>
            `;
        } else {
            container.innerHTML = `<div style="color:#f85149;">❌ File loaded, but "stocks" object is empty.</div>`;
        }
    } catch (e) {
        container.innerHTML = `
            <div style="color:#f85149; padding:20px; border:1px solid #f85149; border-radius:8px;">
                <b>❌ RAW READ FAILED</b><br>
                Error: ${e.message}
            </div>
        `;
    }
}
