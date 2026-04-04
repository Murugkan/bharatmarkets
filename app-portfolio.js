// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - FINAL PRODUCTION BUILD (v4.3)
// ─────────────────────────────────────────────────────────────

// 1. FAIL-SAFE DEBUGGER
const initDebug = () => {
    if (document.getElementById('emergency-debug')) return;
    const div = document.createElement('div');
    div.id = 'emergency-debug';
    div.style.cssText = "position:fixed;top:0;left:0;right:0;height:80px;background:rgba(0,0,0,0.85);color:#0f0;z-index:99999;font-size:10px;overflow-y:auto;padding:8px;border-bottom:1px solid #333;font-family:monospace;pointer-events:none;backdrop-filter:blur(4px);";
    document.body.appendChild(div);
};

window.logMsg = (msg, isError = false) => {
    initDebug();
    const el = document.getElementById('emergency-debug');
    if (el) el.innerHTML = `[${new Date().toLocaleTimeString([], {hour12:false})}] ${isError ? 'ERR' : 'OK'}: ${msg}<br>` + el.innerHTML;
};

// 2. DRILL DOWN HANDLER
window.openPortfolioStock = (sym) => {
    try {
        logMsg(`Drilling into: ${sym}`);
        const h = S.portfolio.find(p => p.sym === sym) || {};
        const f = window[sym.toUpperCase()] || {};
        
        // Critical: Set the global selection for the Drill page
        S.selStock = { ...h, ...f, sym };
        S.drillTab = 'overview';
        
        // Route to the drill page
        const router = window.showTab || window.setTab || window.router;
        if (typeof router === 'function') {
            router('drill');
        } else {
            logMsg("Navigation function not found", true);
        }
    } catch (e) {
        logMsg(`Drill Error: ${e.message}`, true);
    }
};

// 3. THE MAIN RENDERER
function renderPortfolio(container) {
    if (!container) return;
    initDebug();

    // Reset any existing timers
    if (window.pfSyncTimer) clearInterval(window.pfSyncTimer);

    logMsg("Waiting for Portfolio data...");

    window.pfSyncTimer = setInterval(() => {
        const hasData = (window.S && S.portfolio && S.portfolio.length > 0);
        
        if (hasData) {
            clearInterval(window.pfSyncTimer);
            logMsg(`Sync Success: ${S.portfolio.length} stocks found.`);
            drawTable(container);
        } else {
            // Optional: Log every 5th check to keep console clean
            if (Math.random() > 0.8) logMsg("Syncing..."); 
        }
    }, 800);
}

// 4. THE TABLE DRAWING ENGINE
function drawTable(container) {
    try {
        const pf = S.portfolio.map(h => {
            const sym = (h.sym || '').toUpperCase();
            const f = window[sym] || {};
            const ltp = h.liveLtp || f.ltp || 0;
            const avg = h.avgBuy || 0;
            const pnlP = avg > 0 ? (((ltp - avg) / avg) * 100) : 0;
            return { ...h, ...f, ltp, pnlP, sym };
        });

        // Totals for Header
        const totalInv = pf.reduce((a, r) => a + (r.qty * r.avgBuy), 0);
        const totalCur = pf.reduce((a, r) => a + (r.qty * r.ltp), 0);
        const totalPnlP = totalInv > 0 ? (((totalCur - totalInv) / totalInv) * 100) : 0;

        container.innerHTML = `
        <div style="margin-top:90px; padding:12px; background:#0d1117; min-height:100vh; font-family:-apple-system, system-ui, sans-serif;">
            
            <div style="background:#161b22; padding:16px; border-radius:12px; border:1px solid #30363d; display:flex; justify-content:space-between; margin-bottom:16px;">
                <div>
                    <div style="color:#8b949e; font-size:11px; text-transform:uppercase; margin-bottom:4px;">Invested</div>
                    <div style="color:#fff; font-size:18px; font-weight:bold;">₹${(totalInv/100000).toFixed(2)}L</div>
                </div>
                <div style="text-align:right;">
                    <div style="color:#8b949e; font-size:11px; text-transform:uppercase; margin-bottom:4px;">Net P&L</div>
                    <div style="color:${totalPnlP >= 0 ? '#3fb950' : '#f85149'}; font-size:18px; font-weight:bold;">${totalPnlP.toFixed(2)}%</div>
                </div>
            </div>

            <div style="color:#8b949e; font-size:12px; margin-bottom:8px; padding-left:4px;">ALL HOLDINGS (${pf.length})</div>
            <div style="background:#161b22; border-radius:12px; border:1px solid #30363d; overflow:hidden;">
                <table style="width:100%; border-collapse:collapse; font-size:14px;">
                    <tbody>
                        ${pf.map(r => `
                            <tr onclick="openPortfolioStock('${r.sym}')" style="border-bottom:1px solid #30363d; -webkit-tap-highlight-color:transparent;">
                                <td style="padding:14px 12px;">
                                    <div style="color:#fff; font-weight:bold;">${r.sym}</div>
                                    <div style="color:#484f58; font-size:11px;">${(r.name||'').slice(0,12)}</div>
                                </td>
                                <td style="padding:14px 12px; text-align:center;">
                                    <div style="color:#8b949e; font-size:10px;">ROE</div>
                                    <div style="color:${r.roe > 15 ? '#3fb950' : '#fff'}">${r.roe ? r.roe.toFixed(1)+'%' : '—'}</div>
                                </td>
                                <td style="padding:14px 12px; text-align:right;">
                                    <div style="color:${r.pnlP >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">${r.pnlP.toFixed(1)}%</div>
                                    <div style="color:#484f58; font-size:10px;">₹${r.ltp.toLocaleString()}</div>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
            <div style="height:100px;"></div>
        </div>`;
    } catch (e) {
        logMsg("Draw Error: " + e.message, true);
    }
}
