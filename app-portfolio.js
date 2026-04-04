// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - FULL PATHFINDER EDITION (v4.5)
// ─────────────────────────────────────────────────────────────

/** 1. FAIL-SAFE DEBUGGER & UTILS **/
const PF_CONFIG = {
    initDebug: () => {
        if (document.getElementById('emergency-debug')) return;
        const div = document.createElement('div');
        div.id = 'emergency-debug';
        div.style.cssText = "position:fixed;top:0;left:0;right:0;height:100px;background:rgba(0,0,0,0.9);color:#0f0;z-index:99999;font-size:10px;overflow-y:auto;padding:10px;border-bottom:1px solid #333;font-family:monospace;backdrop-filter:blur(4px);";
        div.innerHTML = `<div style="display:flex;justify-content:space-between;"><b>SYSTEM MONITOR</b> <span onclick="location.reload()" style="color:#fff;text-decoration:underline;">Reload App</span></div><div id="debug-content"></div>`;
        document.body.appendChild(div);
    },
    log: (msg, type = 'info') => {
        PF_CONFIG.initDebug();
        const el = document.getElementById('debug-content');
        const color = type === 'err' ? '#f85149' : '#0f0';
        if (el) el.innerHTML = `<div style="color:${color}">[${new Date().toLocaleTimeString([],{hour12:false})}] ${msg}</div>` + el.innerHTML;
    }
};

/** 2. THE PATHFINDER (Finds the 92 stocks) **/
function findPortfolioData() {
    // Priority 1: Standard paths
    if (window.S && S.portfolio && S.portfolio.length > 0) return S.portfolio;
    if (window.S && S.holdings && S.holdings.length > 0) return S.holdings;
    
    // Priority 2: Scan memory for any array with 50-200 items (your 92 stocks)
    for (let key in window) {
        if (['window', 'document', 'S'].includes(key)) continue;
        try {
            const val = window[key];
            if (Array.isArray(val) && val.length > 50 && val.length < 500) {
                PF_CONFIG.log(`Pathfinder: Found data in window.${key}`);
                return val;
            }
        } catch(e) {}
    }
    return null;
}

/** 3. DRILL DOWN HANDLER **/
window.openPortfolioStock = (sym) => {
    try {
        const ticker = sym.toUpperCase();
        PF_CONFIG.log(`Opening Detail: ${ticker}`);
        
        // Find the specific stock in the detected portfolio
        const portfolio = findPortfolioData() || [];
        const h = portfolio.find(p => (p.sym || p.symbol || '').toUpperCase() === ticker) || {};
        
        // Find fundamental data (Global variables)
        const f = window[ticker] || {};
        
        // Set global state for the Drill/Overview page
        if (!window.S) window.S = {};
        S.selStock = { ...h, ...f, sym: ticker };
        S.drillTab = 'overview';
        
        // Trigger Navigation
        const router = window.showTab || window.setTab || window.router;
        if (typeof router === 'function') router('drill');
        else PF_CONFIG.log("Router not found", "err");
        
    } catch (e) {
        PF_CONFIG.log("Drill Error: " + e.message, "err");
    }
};

/** 4. MAIN RENDERER (The Entry Point) **/
function renderPortfolio(container) {
    if (!container) return;
    PF_CONFIG.initDebug();
    if (window.pfSyncTimer) clearInterval(window.pfSyncTimer);

    PF_CONFIG.log("Searching for Portfolio data...");

    window.pfSyncTimer = setInterval(() => {
        const data = findPortfolioData();
        if (data && data.length > 0) {
            clearInterval(window.pfSyncTimer);
            PF_CONFIG.log(`Success! Rendering ${data.length} stocks.`);
            drawTable(container, data);
        } else {
            PF_CONFIG.log("Syncing... (No data found yet)");
        }
    }, 1000);
}

/** 5. THE TABLE DRAWING ENGINE **/
function drawTable(container, rawData) {
    try {
        const pf = rawData.map(h => {
            const sym = (h.sym || h.symbol || '').toUpperCase();
            const f = window[sym] || {}; // Matches loose global stock variables
            const ltp = h.liveLtp || f.ltp || 0;
            const avg = h.avgBuy || h.averagePrice || 0;
            const pnlP = avg > 0 ? (((ltp - avg) / avg) * 100) : 0;
            return { ...h, ...f, ltp, pnlP, sym };
        });

        const totalInv = pf.reduce((a, r) => a + (r.qty * (r.avgBuy || r.averagePrice || 0)), 0);
        const totalCur = pf.reduce((a, r) => a + (r.qty * r.ltp), 0);
        const totalPnl = totalInv > 0 ? (((totalCur - totalInv) / totalInv) * 100) : 0;

        container.innerHTML = `
        <div style="margin-top:110px; padding:12px; background:#0d1117; min-height:100vh; font-family:-apple-system, sans-serif;">
            
            <div style="background:#161b22; padding:16px; border-radius:12px; border:1px solid #30363d; display:flex; justify-content:space-between; margin-bottom:16px;">
                <div>
                    <div style="color:#8b949e; font-size:11px;">INVESTED</div>
                    <div style="color:#fff; font-size:18px; font-weight:bold;">₹${(totalInv/100000).toFixed(2)}L</div>
                </div>
                <div style="text-align:right;">
                    <div style="color:#8b949e; font-size:11px;">P&L %</div>
                    <div style="color:${totalPnl >= 0 ? '#3fb950' : '#f85149'}; font-size:18px; font-weight:bold;">${totalPnl.toFixed(2)}%</div>
                </div>
            </div>

            <div style="background:#161b22; border-radius:12px; border:1px solid #30363d; overflow:hidden;">
                <table style="width:100%; border-collapse:collapse; font-size:14px;">
                    <tbody>
                        ${pf.map(r => `
                            <tr onclick="openPortfolioStock('${r.sym}')" style="border-bottom:1px solid #30363d;">
                                <td style="padding:14px 12px;">
                                    <div style="color:#fff; font-weight:bold;">${r.sym}</div>
                                    <div style="color:#484f58; font-size:10px;">${(r.name||'').slice(0,15)}</div>
                                </td>
                                <td style="padding:14px 12px; text-align:center;">
                                    <div style="color:#8b949e; font-size:10px;">ROE</div>
                                    <div style="color:${r.roe > 15 ? '#3fb950' : '#fff'}">${r.roe ? r.roe.toFixed(1)+'%' : '—'}</div>
                                </td>
                                <td style="padding:14px 12px; text-align:right;">
                                    <div style="color:${r.pnlP >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">${r.pnlP.toFixed(1)}%</div>
                                    <div style="color:#484f58; font-size:10px;">₹${r.ltp}</div>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
            <div style="height:80px;"></div>
        </div>`;
    } catch (e) {
        PF_CONFIG.log("Draw Error: " + e.message, "err");
    }
}
