// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - IPHONE DEBUG EDITION
// ─────────────────────────────────────────────────────────────

// 1. GLOBAL DEBUG LOGGER
window.logDebug = (msg, type = 'info') => {
    const logEl = document.getElementById('app-debug-logs');
    if (!logEl) return;
    const time = new Date().toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' });
    const color = type === 'error' ? '#ff6b85' : type === 'warn' ? '#ffb000' : '#8eb0d0';
    logEl.innerHTML = `<div style="color:${color}; border-bottom:1px solid #222; padding:2px 0;">[${time}] ${msg}</div>` + logEl.innerHTML;
};

// 2. DATA MERGE ENGINE (With ISIN/Symbol Protection)
function mergeHolding(h) {
    // 1. Try direct Ticker match
    let f = (typeof FUND !== 'undefined') ? FUND[h.sym] : null;
    
    // 2. Fallback: Try ISIN match if Symbol fails
    if (!f && h.isin && typeof FUND !== 'undefined') {
        const found = Object.values(FUND).find(x => x.isin === h.isin);
        if (found) { f = found; logDebug(`Matched ${h.sym} via ISIN`, 'info'); }
    }

    if (!f) logDebug(`Missing Fundamentals for: ${h.sym}`, 'warn');

    const ltp = h.liveLtp || f?.ltp || 0;
    const roe = f?.roe || 0;
    const pe = f?.pe || 0;

    return {
        ...h, ...f, ltp, roe, pe,
        sig: f?.signal || (roe > 15 && pe < 18 ? 'BUY' : 'HOLD')
    };
}

// 3. UI: PERMANENT DEBUG WINDOW
function renderDebugWindow() {
    return `
    <div id="debug-window" style="position:fixed; bottom:0; left:0; right:0; height:120px; background:#0a0a0a; border-top:2px solid #333; z-index:9999; font-family:monospace; font-size:10px; display:flex; flex-direction:column;">
        <div style="background:#222; padding:4px 10px; display:flex; justify-content:space-between; align-items:center;">
            <span style="color:#64b5f6; font-weight:bold;">SYSTEM CONSOLE (iPhone)</span>
            <button onclick="document.getElementById('app-debug-logs').innerHTML=''" style="background:none; border:1px solid #444; color:#fff; font-size:9px; padding:2px 5px;">Clear</button>
        </div>
        <div id="app-debug-logs" style="flex:1; overflow-y:auto; padding:5px 10px; color:#ccc;">
            <div>Waiting for activity...</div>
        </div>
    </div>`;
}

// 4. MAIN RENDERER
function renderPortfolio(container) {
    logDebug('Initializing Portfolio Render...');

    if (typeof S === 'undefined' || !S.portfolio) {
        logDebug('CRITICAL: Global state S.portfolio is missing!', 'error');
        container.innerHTML = `<div style="padding:40px; color:#ff6b85;">State Error. Check Console Below.</div>${renderDebugWindow()}`;
        return;
    }

    const pf = S.portfolio.map(mergeHolding);
    logDebug(`Merged ${pf.length} stocks successfully.`);

    container.innerHTML = `
    <div class="bls" style="padding-bottom:130px;"> <div class="kpi-strip" style="display:flex; justify-content:space-between; padding:15px; background:#0d1525; border-radius:8px; margin-bottom:15px;">
            <div><small style="color:#8eb0d0">Mkt Value</small><br><b style="color:#64b5f6">₹${(pf.reduce((a,r)=>a+(r.qty*r.ltp),0)/100000).toFixed(2)}L</b></div>
            <div style="text-align:right;"><small style="color:#8eb0d0">Stocks</small><br><b>${pf.length}</b></div>
        </div>

        <div class="table-outer" style="overflow-x:auto;">
            <table class="bls-t" style="width:100%; border-collapse:collapse;">
                <thead>
                    <tr style="color:#8eb0d0; border-bottom:1px solid #1e3350; font-size:11px;">
                        <th style="padding:10px; text-align:left;">Ticker</th>
                        <th>ROE%</th>
                        <th>P/E</th>
                        <th>Sig</th>
                    </tr>
                </thead>
                <tbody>
                    ${pf.map(r => `
                        <tr onclick="logDebug('Clicked ${r.sym}'); openPortfolioStock('${r.sym}')" style="border-bottom:1px solid #0d1525;">
                            <td style="padding:10px;"><b>${r.sym}</b><br><small style="color:#4a6888">${r.name?.slice(0,10) || '—'}</small></td>
                            <td style="color:${r.roe > 15 ? '#00e896' : '#fff'}">${r.roe || '—'}%</td>
                            <td>${r.pe || '—'}</td>
                            <td><span class="badge-${r.sig.toLowerCase()}">${r.sig}</span></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>

        ${renderDebugWindow()}
    </div>`;
}

// 5. DRILL DOWN WRAPPER
window.openPortfolioStock = (sym) => {
    logDebug(`Attempting Drill-down: ${sym}`);
    try {
        const f = FUND[sym] || {};
        S.selStock = { ...f, sym };
        S.drillTab = 'overview';
        logDebug(`Selection Success: ${sym}. Routing to Overview...`);
        // Force refresh of the app view if needed
        if (typeof router !== 'undefined') router('drill'); 
    } catch (e) {
        logDebug(`Drill-down Failed: ${e.message}`, 'error');
    }
};
