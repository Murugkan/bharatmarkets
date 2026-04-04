// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - VARIABLE HUNTER EDITION (v3.5)
// ─────────────────────────────────────────────────────────────

// 1. THE HUNTER: Finds where your ROE/PE data is hiding
function findFundamentalVariable() {
    // List of common names your app might be using
    const candidates = ['FUND', 'fundamentals', 'prices', 'F', 'stockData', 'DATA', 'MARKET'];
    for (let name of candidates) {
        if (window[name] && Object.keys(window[name]).length > 10) {
            logDebug(`FOUND DATA! It is hidden in window.${name}`, 'info');
            return window[name];
        }
    }
    // If not in the list, look for any large object
    for (let key in window) {
        if (key.length < 20 && window[key] && typeof window[key] === 'object' && Object.keys(window[key]).length > 500) {
           logDebug(`POSSIBLE DATA FOUND: window.${key}`, 'warn');
           return window[key];
        }
    }
    return null;
}

// 2. UPDATED DATA ENGINE
function getMergedData() {
    if (!S.portfolio) return [];
    
    // Use the Hunter to get the data object
    const DataSource = findFundamentalVariable() || {};
    
    return S.portfolio.map(h => {
        const searchSym = h.sym.toUpperCase();
        let f = DataSource[searchSym] || Object.values(DataSource).find(x => x.sym === searchSym || x.isin === h.isin);
        
        const ltp = h.liveLtp || f?.ltp || 0;
        const avg = h.avgBuy || 0;
        const qty = h.qty || 0;
        
        return { 
            ...h, ...f, ltp, 
            pnl: (ltp - avg) * qty,
            pnlP: (((ltp - avg) / avg) * 100) || 0
        };
    });
}

// 3. MAIN RENDERER
function renderPortfolio(container) {
    if (!container) return;

    container.innerHTML = `
    <div id="debug-window" style="position:fixed; top:0; left:0; right:0; height:120px; background:rgba(0,0,0,0.95); z-index:10000; border-bottom:2px solid #333; display:flex; flex-direction:column;">
        <div style="background:#222; padding:5px 12px; display:flex; justify-content:space-between;">
            <b style="color:#64b5f6">DATA HUNTER</b>
            <button onclick="document.getElementById('app-debug-logs').innerHTML=''" style="background:#3a0010; color:#fff; border:none; padding:2px 8px; border-radius:3px;">Clear</button>
        </div>
        <div id="app-debug-logs" style="flex:1; overflow-y:auto; padding:5px 12px; font-family:monospace; font-size:10px;"></div>
    </div>
    <div id="pf-main-content" style="margin-top:130px; padding:10px;"></div>`;

    const content = document.getElementById('pf-main-content');
    
    let checks = 0;
    const watcher = setInterval(() => {
        checks++;
        const dataObj = findFundamentalVariable();
        const dataSize = dataObj ? Object.keys(dataObj).length : 0;
        
        logDebug(`Check #${checks}: Found data object with ${dataSize} stocks.`);

        if (dataSize > 0 || checks > 10) {
            clearInterval(watcher);
            const pf = getMergedData();
            
            // Calculate Totals
            const inv = pf.reduce((a, r) => a + (r.qty * r.avgBuy), 0);
            const cur = pf.reduce((a, r) => a + (r.qty * r.ltp), 0);
            const pnl = cur - inv;

            content.innerHTML = `
                <div style="background:#161b22; padding:15px; border-radius:8px; margin-bottom:15px; border:1px solid #30363d; display:flex; justify-content:space-between;">
                    <div><small style="color:#8eb0d0">Invested</small><br><b>₹${(inv/100000).toFixed(2)}L</b></div>
                    <div style="text-align:right;"><small style="color:#8eb0d0">P&L%</small><br><b style="color:${pnl >= 0 ? '#00e896' : '#ff6b85'}">${((pnl/inv)*100).toFixed(2)}%</b></div>
                </div>
                <table style="width:100%; border-collapse:collapse; font-size:13px;">
                    <thead style="color:#8eb0d0; border-bottom:1px solid #30363d;">
                        <tr><th style="padding:10px; text-align:left;">Ticker</th><th>ROE</th><th>Sig</th></tr>
                    </thead>
                    <tbody>
                        ${pf.map(r => `
                            <tr onclick="openPortfolioStock('${r.sym}')" style="border-bottom:1px solid #21262d;">
                                <td style="padding:12px 10px;"><b>${r.sym}</b></td>
                                <td style="color:${r.roe > 15 ? '#00e896' : '#fff'}">${r.roe ? r.roe.toFixed(1)+'%' : '—'}</td>
                                <td><span style="border:1px solid; padding:2px 5px; border-radius:3px; font-size:10px; color:${r.signal==='BUY'?'#00e896':'#888'}">${r.signal || 'HOLD'}</span></td>
                            </tr>`).join('')}
                    </tbody>
                </table>`;
        }
    }, 1000);
}

// Global logger helper (Keep this)
window.logDebug = (msg, type = 'info') => {
    const logEl = document.getElementById('app-debug-logs');
    if (!logEl) return;
    const time = new Date().toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' });
    const color = type === 'error' ? '#ff6b85' : type === 'warn' ? '#ffb000' : '#00e896';
    logEl.innerHTML = `<div>[${time}] ${msg}</div>` + logEl.innerHTML;
};
