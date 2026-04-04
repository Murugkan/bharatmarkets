// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - DEEP SCAN EDITION (v3.1)
// ─────────────────────────────────────────────────────────────

// 1. DATA ENGINE: DEEP SCAN MAPPING
function mergeHolding(h) {
    if (typeof FUND === 'undefined') return h;
    
    let f = null;
    const searchSym = h.sym.toUpperCase();

    // STEP 1: Direct Key Match
    if (FUND[searchSym]) {
        f = FUND[searchSym];
    } 
    // STEP 2: Deep Value Search (Scanning all objects in FUND)
    else {
        f = Object.values(FUND).find(x => 
            (x.sym && x.sym.toUpperCase() === searchSym) || 
            (x.symbol && x.symbol.toUpperCase() === searchSym) ||
            (x.isin && h.isin && x.isin === h.isin) ||
            (x.ticker && x.ticker.toUpperCase() === searchSym)
        );
    }

    if (!f) {
        // Log the first 2 keys of FUND to debug what the keys actually look like
        const sampleKeys = Object.keys(FUND).slice(0, 2).join(', ');
        logDebug(`Map Fail: ${searchSym}. FUND keys look like: [${sampleKeys}]`, 'warn');
        return { ...h, ltp: h.liveLtp || 0, roe: 0, pe: 0, sig: 'HOLD' };
    }

    logDebug(`SUCCESS: Mapped ${searchSym}`, 'info');
    const ltp = h.liveLtp || f.ltp || 0;
    return {
        ...h, ...f, ltp,
        sig: f.signal || (f.roe > 15 ? 'BUY' : 'HOLD')
    };
}

// 2. DRILL-DOWN LOGIC (Updated for Deep Scan)
window.openPortfolioStock = (sym) => {
    logDebug(`Requesting Drill: ${sym}`);
    try {
        const h = S.portfolio.find(p => p.sym === sym);
        const merged = mergeHolding(h);
        
        // Critical: Set the global selection
        S.selStock = merged; 
        S.drillTab = 'overview';
        
        logDebug(`State Set. Navigating to Drill...`);
        
        // Attempt to trigger the app's navigation
        const navActions = ['showTab', 'setTab', 'router', 'changeView'];
        let triggered = false;
        navActions.forEach(action => {
            if (typeof window[action] === 'function') {
                window[action]('drill');
                triggered = true;
            }
        });
        
        if (!triggered) logDebug('Manual navigation failed. Need app router name.', 'warn');
        
    } catch (e) {
        logDebug(`Drill Error: ${e.message}`, 'error');
    }
};

// 3. MAIN RENDERER (Clean & Standardized)
function renderPortfolio(container) {
    if (!container) return;

    container.innerHTML = `
    <div id="debug-window" style="position:fixed; top:0; left:0; right:0; height:140px; background:rgba(10,10,10,0.95); z-index:10000; border-bottom:2px solid #333; display:flex; flex-direction:column; backdrop-filter:blur(5px);">
        <div style="background:#222; padding:5px 12px; display:flex; justify-content:space-between; align-items:center;">
            <b style="color:#64b5f6; font-size:11px;">DEBUG CONSOLE</b>
            <button onclick="document.getElementById('app-debug-logs').innerHTML=''" style="background:#3a0010; color:#fff; border:none; padding:3px 10px; border-radius:3px; font-size:10px;">Clear</button>
        </div>
        <div id="app-debug-logs" style="flex:1; overflow-y:auto; padding:5px 12px; font-family:monospace; font-size:10px;"></div>
    </div>
    <div id="pf-main-content" style="margin-top:150px; padding:10px;"></div>`;

    const content = document.getElementById('pf-main-content');
    if (typeof S === 'undefined' || !S.portfolio) {
        logDebug('S.portfolio not found', 'error');
        return;
    }

    const pf = S.portfolio.map(mergeHolding);
    
    const inv = pf.reduce((a, r) => a + (r.qty * r.avgBuy), 0);
    const cur = pf.reduce((a, r) => a + (r.qty * r.ltp), 0);
    const pnlP = ((cur - inv) / inv * 100) || 0;

    content.innerHTML = `
        <div style="display:flex; justify-content:space-between; padding:15px; background:#161b22; border-radius:8px; margin-bottom:15px; border:1px solid #30363d;">
            <div><small style="color:#8eb0d0">Invested</small><br><b style="color:#64b5f6">₹${(inv/100000).toFixed(2)}L</b></div>
            <div style="text-align:right;"><small style="color:#8eb0d0">P&L</small><br><b style="color:${pnlP >= 0 ? '#00e896' : '#ff6b85'}">${pnlP.toFixed(2)}%</b></div>
        </div>
        
        <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:13px; white-space:nowrap;">
                <thead>
                    <tr style="color:#8eb0d0; border-bottom:1px solid #30363d; text-align:left;">
                        <th style="padding:12px 10px;">Ticker</th>
                        <th>ROE%</th>
                        <th>P/E</th>
                        <th>Sig</th>
                    </tr>
                </thead>
                <tbody>
                    ${pf.map(r => `
                        <tr onclick="openPortfolioStock('${r.sym}')" style="border-bottom:1px solid #21262d;">
                            <td style="padding:12px 10px;"><b>${r.sym}</b><br><small style="color:#4a6888">${(r.name || '').slice(0, 10)}</small></td>
                            <td style="color:${r.roe > 15 ? '#00e896' : '#fff'}">${r.roe ? r.roe.toFixed(1) + '%' : '—'}</td>
                            <td>${r.pe ? r.pe.toFixed(1) : '—'}</td>
                            <td><span style="font-size:10px; padding:2px 5px; border-radius:3px; border:1px solid; color:${r.sig==='BUY'?'#00e896':'#888'}">${r.sig}</span></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        <div style="height:80px;"></div>
    `;
}

// Global logger helper
window.logDebug = (msg, type = 'info') => {
    const logEl = document.getElementById('app-debug-logs');
    if (!logEl) return;
    const time = new Date().toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' });
    const color = type === 'error' ? '#ff6b85' : type === 'warn' ? '#ffb000' : '#00e896';
    logEl.innerHTML = `<div style="color:${color}; border-bottom:1px dotted #333; padding:4px 0;">[${time}] ${msg}</div>` + logEl.innerHTML;
};
