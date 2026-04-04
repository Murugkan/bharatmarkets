// 1. IMMEDIATE HIJACK (Runs the moment the file loads)
(async function hijackSystem() {
    try {
        const r = await fetch('fundamentals.json?nocache=' + Date.now());
        const data = await r.json();
        
        // Force the globals that app-core.js is stuck on
        window.FUND = data;
        window.fundLoaded = true; 
        
        console.log("SYSTEM HIJACKED: fundLoaded is now TRUE");

        // Force a global UI refresh to kill the "Syncing" screen
        if (window.render) window.render();
        else if (window.showTab) window.showTab('portfolio');
    } catch (e) {
        console.error("Hijack failed:", e);
    }
})();

// 2. THE ACTUAL RENDERER
async function renderPortfolio(container) {
    if (!container) return;
    
    // If we get here, the "Syncing" screen is gone.
    const portfolio = (window.S && S.portfolio) ? S.portfolio : [];
    
    container.innerHTML = `
        <div style="padding:20px; background:#02040a; color:#fff; font-family:sans-serif;">
            <div style="padding:15px; background:#111d30; border-radius:12px; border:1px solid #1e3350; margin-bottom:15px;">
                <div style="color:#8b949e; font-size:10px;">LIVE TRACKING</div>
                <div style="font-size:18px; font-weight:bold;">${portfolio.length} Stocks Detected</div>
            </div>
            <div id="pf-list">
                ${portfolio.map(s => {
                    const f = (FUND.stocks && FUND.stocks[s.sym.toUpperCase()]) ? FUND.stocks[s.sym.toUpperCase()] : {};
                    return `
                    <div style="display:flex; justify-content:space-between; padding:12px 0; border-bottom:1px solid #1e3350;">
                        <div>
                            <b>${s.sym}</b><br>
                            <small style="color:#8b949e">ROE: ${f.roe ? f.roe.toFixed(1)+'%' : '--'}</small>
                        </div>
                        <div style="text-align:right;">
                            <b>₹${(s.ltp || f.ltp || 0).toFixed(0)}</b>
                        </div>
                    </div>`;
                }).join('')}
            </div>
        </div>`;
}
