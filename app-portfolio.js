/**
 * BHARATMARKETS PRO - RAW PROBE (v15.0)
 * Objective: Fetch the file and display the FIRST available stock data.
 */
async function renderPortfolio(container) {
    if (!container) return;

    container.innerHTML = `
        <div style="padding:40px; background:#02040a; min-height:100vh; font-family:monospace; color:#58a6ff;">
            > CONNECTING TO fundamentals.json...
        </div>`;

    try {
        const response = await fetch('fundamentals.json?v=' + Date.now());
        const data = await response.json();
        
        // 1. Identify the first stock in the list
        // Most BharatMarkets JSONs use the "stocks" key
        const stockList = data.stocks || data; 
        const symbols = Object.keys(stockList);
        
        if (symbols.length > 0) {
            const firstSym = symbols[0];
            const stockDetails = stockList[firstSym];

            // 2. DISPLAY RAW DATA FOR THE FIRST STOCK
            container.innerHTML = `
                <div style="padding:25px; background:#111d30; border:2px solid #58a6ff; border-radius:16px; color:#fff; font-family:sans-serif;">
                    <div style="color:#58a6ff; font-weight:bold; font-size:12px; margin-bottom:10px; letter-spacing:1px;">PROBE SUCCESSFUL</div>
                    
                    <div style="font-size:32px; font-weight:bold; margin-bottom:5px;">${firstSym}</div>
                    <div style="color:#8b949e; font-size:14px; margin-bottom:20px;">Raw Fundamental Data Row</div>
                    
                    <div style="background:#0d1117; padding:15px; border-radius:8px; font-family:monospace; font-size:16px; line-height:1.8;">
                        <span style="color:#8b949e">ROE:</span> <b style="color:#3fb950">${stockDetails.roe || stockDetails.ROE || 'Missing'}%</b><br>
                        <span style="color:#8b949e">LTP:</span> <b style="color:#3fb950">₹${stockDetails.ltp || stockDetails.LTP || 'Missing'}</b><br>
                        <span style="color:#8b949e">Sector:</span> <b style="color:#fff">${stockDetails.sector || 'Missing'}</b>
                    </div>

                    <div style="margin-top:20px; font-size:11px; color:#484f58; border-top:1px solid #1e3350; padding-top:15px;">
                        Total stocks identified in file: <b>${symbols.length}</b>
                    </div>
                </div>
            `;
        } else {
            container.innerHTML = `<div style="color:#f85149; padding:40px;">❌ JSON found, but it is empty.</div>`;
        }
    } catch (e) {
        container.innerHTML = `
            <div style="padding:40px; background:#02040a; color:#f85149; font-family:monospace;">
                <b>❌ PROBE FAILED</b><br><br>
                ERROR: ${e.message}<br><br>
                Check if fundamentals.json exists in your GitHub root.
            </div>`;
    }
}
