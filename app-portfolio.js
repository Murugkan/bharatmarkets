/**
 * 1. FORCE THE BRIDGE
 * This part ensures that even if app-core.js is "empty", 
 * this module fills it immediately upon loading.
 */
(async function initializeDataBridge() {
    try {
        const r = await fetch('fundamentals.json?v=' + Date.now());
        const data = await r.json();
        // Force-populate the global variable app-core.js is looking for
        window.FUND = data;
        window.fundLoaded = true;
        console.log("🚀 Data Bridge Active:", Object.keys(data.stocks).length, "stocks linked.");
    } catch (e) {
        console.error("Data Bridge Failed:", e);
    }
})();

/**
 * 2. THE RENDERER
 * Optimized to handle the 92 stocks found in your diagnostics.
 */
async function renderPortfolio(container) {
    if (!container) return;

    // Fast-path: if data is already there, don't show "Syncing"
    if (window.FUND && window.FUND.stocks && window.S && S.portfolio.length > 0) {
        return drawPortfolioFinal(container);
    }

    container.innerHTML = `<div style="padding:60px; text-align:center; color:#58a6ff; font-family:Syne;">
        <div style="margin-bottom:15px; font-size:18px;">BHARATMARKETS PRO</div>
        <div style="color:#8b949e; font-size:12px; font-family:monospace;">CONNECTING DATA NODES...</div>
    </div>`;

    // Polling logic for the 92 stocks
    const syncInterval = setInterval(() => {
        const isReady = (window.FUND && FUND.stocks && window.S && S.portfolio.length > 0);
        if (isReady) {
            clearInterval(syncInterval);
            drawPortfolioFinal(container);
        }
    }, 500);
}

/**
 * 3. THE UI GENERATOR
 */
function drawPortfolioFinal(container) {
    const portfolio = S.portfolio.map(holding => {
        const sym = holding.sym.toUpperCase();
        // JSON uses .stocks[SYMBOL]
        const fundamental = (FUND.stocks && FUND.stocks[sym]) ? FUND.stocks[sym] : {};
        
        const ltp = holding.ltp || fundamental.ltp || 0;
        const avg = holding.avgBuy || 0;
        const pnl = avg > 0 ? ((ltp - avg) / avg) * 100 : 0;
        
        return { ...holding, ...fundamental, ltp, pnl, sym };
    });

    // Summary Calculations
    const totalInv = portfolio.reduce((a, b) => a + (b.qty * b.avgBuy), 0);
    const totalCur = portfolio.reduce((a, b) => a + (b.qty * b.ltp), 0);
    const netPnl = totalInv > 0 ? ((totalCur - totalInv) / totalInv) * 100 : 0;

    container.innerHTML = `
    <div style="padding:15px; background:#02040a; min-height:100vh; font-family:'DM Sans', sans-serif; color:#fff;">
        
        <div style="background:#111d30; padding:20px; border-radius:16px; border:1px solid #1e3350; display:flex; justify-content:space-between; margin-bottom:20px; box-shadow:0 10px 30px rgba(0,0,0,0.5);">
            <div><small style="color:#8b949e; font-size:10px; text-transform:uppercase;">Invested Value</small><br><b style="font-size:22px;">₹${(totalInv/100000).toFixed(2)}L</b></div>
            <div style="text-align:right;"><small style="color:#8b949e; font-size:10px; text-transform:uppercase;">Overall P&L</small><br><b style="font-size:22px; color:${netPnl >= 0 ? '#3fb950' : '#f85149'}">${netPnl.toFixed(2)}%</b></div>
        </div>

        <div style="background:#0d1525; border-radius:16px; border:1px solid #1e3350; overflow:hidden;">
            <table style="width:100%; border-collapse:collapse;">
                <tbody>
                    ${portfolio.map(s => `
                    <tr onclick="openStockDetail('${s.sym}')" style="border-bottom:1px solid #1e3350;">
                        <td style="padding:16px 12px;">
                            <div style="font-weight:600; font-family:Syne;">${s.sym}</div>
                            <div style="font-size:10px; color:#8b949e;">${s.sector || 'PORTFOLIO'}</div>
                        </td>
                        <td style="text-align:center;">
                            <div style="color:#8b949e; font-size:10px;">ROE</div>
                            <div style="font-weight:500; color:${s.roe > 15 ? '#3fb950' : '#fff'}">${s.roe ? s.roe.toFixed(1)+'%' : '—'}</div>
                        </td>
                        <td style="padding:16px 12px; text-align:right;">
                            <div style="color:${s.pnl >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">${s.pnl.toFixed(1)}%</div>
                            <div style="font-size:10px; color:#484f58">₹${s.ltp.toFixed(0)}</div>
                        </td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>
        <div style="height:100px;"></div>
    </div>`;
}

/**
 * 4. NAVIGATION
 */
window.openStockDetail = (sym) => {
    const s = sym.toUpperCase();
    const h = (S.portfolio || []).find(p => p.sym === s) || {};
    const f = (FUND.stocks && FUND.stocks[s]) ? FUND.stocks[s] : {};
    S.selStock = { ...h, ...f, sym: s };
    S.drillTab = 'overview';
    if (typeof render === 'function') render();
};
