// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - AUTO-RECOVERY EDITION (v7.2)
// ─────────────────────────────────────────────────────────────

/** 1. DATA LOADER: Fetches the file if window.FUND is missing **/
async function getFundData() {
    // If FUND is already there, just return the stocks
    if (window.FUND && window.FUND.stocks) return window.FUND.stocks;

    try {
        console.log("FUND missing. Fetching from server...");
        const response = await fetch('fundamentals.json?t=' + Date.now());
        if (!response.ok) throw new Error("File not found");
        const data = await response.json();
        
        // Save it globally so other parts of the app can use it
        window.FUND = data;
        return data.stocks || {};
    } catch (e) {
        console.error("Manual fetch failed:", e);
        return {};
    }
}

/** 2. THE RENDERER: The main entry point **/
async function renderPortfolio(container) {
    if (!container) return;

    // Show a quick "Loading" message while we fetch the file
    container.innerHTML = `<div style="padding:100px 20px; text-align:center; color:#8b949e; font-family:sans-serif;">
        <div style="color:#58a6ff; font-weight:bold; margin-bottom:10px;">BHARATMARKETS PRO</div>
        <div>Syncing Fundamentals...</div>
    </div>`;

    // Wait for the data fetch to finish
    const stocksData = await getFundData();
    
    // Draw the table
    drawPortfolioUI(container, stocksData);
}

/** 3. THE UI: Builds the actual table **/
function drawPortfolioUI(container, fundStocks) {
    const pf = S.portfolio.map(h => {
        const sym = h.sym.toUpperCase();
        // Handle Ticker Mismatch (AFCONSINFRAS -> AFCONS)
        const targetSym = sym === "AFCONSINFRAS" ? "AFCONS" : sym;
        const f = fundStocks[targetSym] || {};
        
        const ltp = h.ltp || f.ltp || 0;
        const avg = h.avgBuy || 0;
        const pnlP = avg > 0 ? ((ltp - avg) / avg) * 100 : 0;
        
        return { ...h, ...f, ltp, pnlP, sym };
    });

    const totalInv = pf.reduce((a, r) => a + (r.qty * r.avgBuy), 0);
    const totalCur = pf.reduce((a, r) => a + (r.qty * r.ltp), 0);
    const netPnlP = totalInv > 0 ? ((totalCur - totalInv) / totalInv) * 100 : 0;

    container.innerHTML = `
    <div style="padding:12px; background:#02040a; min-height:100vh; font-family:sans-serif; color:#fff;">
        
        <div style="background:#111d30; padding:20px; border-radius:12px; border:1px solid #1e3350; display:flex; justify-content:space-between; margin-bottom:16px;">
            <div>
                <div style="color:#8b949e; font-size:11px;">INVESTED</div>
                <div style="font-size:20px; font-weight:bold; margin-top:4px;">₹${(totalInv/100000).toFixed(2)}L</div>
            </div>
            <div style="text-align:right;">
                <div style="color:#8b949e; font-size:11px;">NET P&L</div>
                <div style="font-size:20px; font-weight:bold; margin-top:4px; color:${netPnlP >= 0 ? '#3fb950' : '#f85149'}">${netPnlP.toFixed(2)}%</div>
            </div>
        </div>

        <div style="background:#0d1525; border-radius:12px; border:1px solid #1e3350; overflow:hidden;">
            <table style="width:100%; border-collapse:collapse; font-size:14px;">
                <tbody>
                    ${pf.map(r => `
                    <tr onclick="openStockDetail('${r.sym}')" style="border-bottom:1px solid #1e3350;">
                        <td style="padding:14px 12px;">
                            <div style="font-weight:bold;">${r.sym}</div>
                            <div style="font-size:10px; color:${r.signal==='BUY'?'#3fb950':'#8b949e'}">${r.signal || 'HOLD'}</div>
                        </td>
                        <td style="text-align:center;">
                            <div style="color:#8b949e; font-size:10px;">ROE</div>
                            <div style="color:${r.roe > 15 ? '#3fb950' : '#fff'}">${r.roe ? r.roe.toFixed(1)+'%' : '—'}</div>
                        </td>
                        <td style="padding:14px 12px; text-align:right;">
                            <div style="color:${r.pnlP >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">${r.pnlP.toFixed(1)}%</div>
                            <div style="font-size:10px; color:#484f58">₹${r.ltp.toFixed(0)}</div>
                        </td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>
        <div style="height:80px;"></div>
    </div>`;
}

/** 4. NAVIGATION: Links back to app-core.js functionality **/
window.openStockDetail = (sym) => {
    const s = sym.toUpperCase();
    const h = S.portfolio.find(p => p.sym === s) || {};
    const f = (window.FUND && FUND.stocks && FUND.stocks[s]) ? FUND.stocks[s] : {};
    
    S.selStock = { ...h, ...f, sym: s };
    S.drillTab = 'overview';
    
    // Call the global render function from app-core.js
    if (typeof render === 'function') render();
};
