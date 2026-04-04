// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - AUTO-SYNC RECOVERY (v4.2)
// ─────────────────────────────────────────────────────────────

const initDebug = () => {
    if (document.getElementById('emergency-debug')) return;
    const div = document.createElement('div');
    div.id = 'emergency-debug';
    div.style.cssText = "position:fixed;top:0;left:0;right:0;height:100px;background:#000;color:#0f0;z-index:99999;font-size:10px;overflow-y:auto;padding:10px;border-bottom:1px solid #333;font-family:monospace;pointer-events:none;";
    document.body.appendChild(div);
};

window.logMsg = (msg, isError = false) => {
    initDebug();
    const el = document.getElementById('emergency-debug');
    el.innerHTML = `[${new Date().toLocaleTimeString()}] ${isError ? 'ERR: ' : 'OK: '} ${msg}<br>` + el.innerHTML;
};

// THE MAIN RENDERER
function renderPortfolio(container) {
    if (!container) return;
    initDebug();

    // 1. CLEAR PREVIOUS WATCHERS
    if (window.pfSyncTimer) clearInterval(window.pfSyncTimer);

    // 2. START THE SYNC WATCHER
    window.pfSyncTimer = setInterval(() => {
        const count = (window.S && S.portfolio) ? S.portfolio.length : 0;
        
        logMsg(`Checking... Portfolio Count: ${count}`);

        if (count > 0) {
            clearInterval(window.pfSyncTimer);
            logMsg(`Sync Complete! Rendering ${count} stocks.`);
            drawTable(container);
        }
    }, 1000); // Check every 1 second
}

// THE DRAWING FUNCTION
function drawTable(container) {
    try {
        const pf = S.portfolio.map(h => {
            const sym = h.sym ? h.sym.toUpperCase() : '';
            // Match with global stock data
            const f = window[sym] || {};
            const ltp = h.liveLtp || f.ltp || 0;
            const avg = h.avgBuy || 0;
            return { ...h, ...f, ltp, pnlP: (((ltp - avg) / avg) * 100) || 0 };
        });

        container.innerHTML = `
        <div style="margin-top:110px; padding:15px; color:#fff;">
            <div style="background:#161b22; padding:15px; border-radius:10px; margin-bottom:20px; border:1px solid #30363d; display:flex; justify-content:space-between;">
                <div><small style="color:#8eb0d0">HOLDINGS</small><br><b style="font-size:20px;">${pf.length}</b></div>
                <div style="text-align:right;"><small style="color:#8eb0d0">STATUS</small><br><b style="color:#00e896">Synced</b></div>
            </div>
            
            <table style="width:100%; border-collapse:collapse; font-size:14px;">
                <tr style="color:#8eb0d0; border-bottom:1px solid #333; text-align:left;">
                    <th style="padding:10px 0;">Stock</th>
                    <th>ROE%</th>
                    <th style="text-align:right;">P&L%</th>
                </tr>
                ${pf.map(r => `
                    <tr onclick="window.openPortfolioStock('${r.sym}')" style="border-bottom:1px solid #222;">
                        <td style="padding:15px 0;"><b>${r.sym}</b><br><small style="color:#4a6888">${(r.name||'').slice(0,10)}</small></td>
                        <td style="color:${r.roe > 15 ? '#00e896' : '#fff'}">${r.roe ? r.roe.toFixed(1) : '—'}</td>
                        <td style="text-align:right; color:${r.pnlP >= 0 ? '#00e896' : '#ff6b85'}">${r.pnlP.toFixed(1)}%</td>
                    </tr>
                `).join('')}
            </table>
        </div>`;
    } catch (e) {
        logMsg("Draw Error: " + e.message, true);
    }
}

// DRILL DOWN TRIGGER
window.openPortfolioStock = (sym) => {
    const h = S.portfolio.find(p => p.sym === sym);
    const f = window[sym.toUpperCase()] || {};
    S.selStock = { ...h, ...f, sym };
    S.drillTab = 'overview';
    if (typeof showTab === 'function') showTab('drill');
};
