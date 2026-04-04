// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - GLOBAL PROBE EDITION (v3.6)
// ─────────────────────────────────────────────────────────────

function findStockData() {
    // 1. Check common nested paths first
    if (typeof S !== 'undefined') {
        if (S.fundamentals) return S.fundamentals;
        if (S.prices) return S.prices;
        if (S.fund) return S.fund;
    }

    // 2. Scan every single global variable for a large object
    const keys = Object.keys(window);
    for (let key of keys) {
        // Skip system/internal variables
        if (['window', 'document', 'location', 'webkit', 'S'].includes(key)) continue;
        
        try {
            const obj = window[key];
            if (obj && typeof obj === 'object' && !Array.isArray(obj)) {
                const size = Object.keys(obj).length;
                // If it has a lot of keys, it's likely our stock data
                if (size > 100) {
                    logDebug(`PROBE: Found ${size} stocks in window.${key}`, 'info');
                    return obj;
                }
            }
        } catch(e) {}
    }
    return null;
}

function renderPortfolio(container) {
    if (!container) return;

    container.innerHTML = `
    <div id="debug-window" style="position:fixed; top:0; left:0; right:0; height:130px; background:rgba(10,10,10,0.95); z-index:10000; border-bottom:2px solid #333; display:flex; flex-direction:column; backdrop-filter:blur(5px);">
        <div style="background:#222; padding:8px 12px; display:flex; justify-content:space-between; align-items:center;">
            <b style="color:#64b5f6; font-size:11px;">GLOBAL PROBE</b>
            <button onclick="document.getElementById('app-debug-logs').innerHTML=''" style="background:#3a0010; color:#fff; border:none; padding:4px 10px; border-radius:3px; font-size:10px;">Clear</button>
        </div>
        <div id="app-debug-logs" style="flex:1; overflow-y:auto; padding:8px 12px; font-family:monospace; font-size:10px;"></div>
    </div>
    <div id="pf-main-content" style="margin-top:140px; padding:10px;"></div>`;

    const content = document.getElementById('pf-main-content');
    
    let checks = 0;
    const watcher = setInterval(() => {
        checks++;
        const dataObj = findStockData();
        const dataSize = dataObj ? Object.keys(dataObj).length : 0;
        
        logDebug(`Check #${checks}: Found ${dataSize} potential fundamentals.`);

        if (dataSize > 0 || checks > 15) {
            clearInterval(watcher);
            
            const pf = S.portfolio.map(h => {
                const searchSym = h.sym.toUpperCase();
                const f = dataObj ? (dataObj[searchSym] || Object.values(dataObj).find(x => x.sym === searchSym)) : null;
                return { ...h, ...f, ltp: h.liveLtp || f?.ltp || 0 };
            });

            // Summary Header
            const inv = pf.reduce((a, r) => a + (r.qty * r.avgBuy), 0);
            const cur = pf.reduce((a, r) => a + (r.qty * r.ltp), 0);
            const pnlP = (((cur - inv) / inv) * 100) || 0;

            content.innerHTML = `
                <div style="background:#161b22; border:1px solid #30363d; padding:15px; border-radius:8px; margin-bottom:15px; display:flex; justify-content:space-between;">
                    <div><small style="color:#8eb0d0">Invested</small><br><b style="color:#64b5f6">₹${(inv/100000).toFixed(2)}L</b></div>
                    <div style="text-align:right;"><small style="color:#8eb0d0">P&L%</small><br><b style="color:${pnlP >= 0 ? '#00e896' : '#ff6b85'}">${pnlP.toFixed(2)}%</b></div>
                </div>
                <table style="width:100%; border-collapse:collapse; font-size:13px;">
                    <thead><tr style="color:#8eb0d0; text-align:left; border-bottom:1px solid #333;"><th style="padding:10px;">Stock</th><th>ROE</th><th>P/E</th></tr></thead>
                    <tbody>
                        ${pf.map(r => `
                        <tr style="border-bottom:1px solid #21262d;">
                            <td style="padding:12px 10px;"><b>${r.sym}</b></td>
                            <td style="color:${r.roe > 15 ? '#00e896' : '#fff'}">${r.roe ? r.roe.toFixed(1)+'%' : '—'}</td>
                            <td>${r.pe || '—'}</td>
                        </tr>`).join('')}
                    </tbody>
                </table>
            `;
        }
    }, 1000);
}

// Keep the standard logDebug function at the bottom
window.logDebug = (msg, type = 'info') => {
    const logEl = document.getElementById('app-debug-logs');
    if (!logEl) return;
    const time = new Date().toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' });
    const color = type === 'error' ? '#ff6b85' : type === 'warn' ? '#ffb000' : '#00e896';
    logEl.innerHTML = `<div>[${time}] ${msg}</div>` + logEl.innerHTML;
};
