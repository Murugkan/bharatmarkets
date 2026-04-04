// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - FULL PRODUCTION RECOVERY
// ─────────────────────────────────────────────────────────────

// 1. HELPERS: Formatting & Debug
window.logDebug = (msg, type = 'info') => {
    const logEl = document.getElementById('app-debug-logs');
    if (!logEl) return;
    const time = new Date().toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' });
    const color = type === 'error' ? '#ff6b85' : type === 'warn' ? '#ffb000' : '#00e896';
    const div = document.createElement('div');
    div.style.cssText = `color:${color}; border-bottom:1px dotted #333; padding:4px 0; font-size:10px;`;
    div.innerHTML = `[${time}] ${msg}`;
    logEl.prepend(div);
};

const fn = (v, dp = 1, pre = '', suf = '') => (v == null || isNaN(v)) ? '—' : pre + Number(v).toFixed(dp) + suf;

// 2. DATA ENGINE: Deep-Lookup Strategy
function getMergedData() {
    if (!S.portfolio) return [];
    
    return S.portfolio.map(h => {
        const searchSym = h.sym.toUpperCase();
        // Look in FUND (Try key first, then search within values for symbol/isin)
        let f = (typeof FUND !== 'undefined') ? FUND[searchSym] : null;
        if (!f && typeof FUND !== 'undefined') {
            f = Object.values(FUND).find(x => 
                (x.sym?.toUpperCase() === searchSym) || 
                (x.symbol?.toUpperCase() === searchSym) ||
                (x.isin && h.isin && x.isin === h.isin)
            );
        }
        
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

// 3. DRILL-DOWN: Selection & Tab Switch
window.openPortfolioStock = (sym) => {
    logDebug(`Opening: ${sym}`);
    try {
        const allData = getMergedData();
        const selected = allData.find(p => p.sym === sym);
        
        if (selected) {
            S.selStock = selected;
            S.drillTab = 'overview';
            
            // Standard Tab Switching Logic
            if (typeof showTab === 'function') showTab('drill');
            else if (typeof setTab === 'function') setTab('drill');
            else if (typeof router === 'function') router('drill');
            
            logDebug(`SUCCESS: ${sym} details loaded.`);
        }
    } catch (e) {
        logDebug(`Drill Error: ${e.message}`, 'error');
    }
};

// 4. MAIN RENDERER: The "Data-First" Loop
function renderPortfolio(container) {
    if (!container) return;

    // A. Setup Fixed Debug UI at Top
    container.innerHTML = `
    <div id="debug-window" style="position:fixed; top:0; left:0; right:0; height:110px; background:rgba(10,10,10,0.95); z-index:10000; border-bottom:2px solid #333; display:flex; flex-direction:column; backdrop-filter:blur(5px);">
        <div style="background:#222; padding:5px 12px; display:flex; justify-content:space-between; align-items:center;">
            <b style="color:#64b5f6; font-size:11px;">SYNC MONITOR</b>
            <button onclick="document.getElementById('app-debug-logs').innerHTML=''" style="background:#3a0010; color:#fff; border:none; padding:2px 8px; border-radius:3px; font-size:10px;">Clear</button>
        </div>
        <div id="app-debug-logs" style="flex:1; overflow-y:auto; padding:5px 12px; font-family:monospace;"></div>
    </div>
    <div id="pf-main-content" style="margin-top:120px; padding:10px;"></div>`;

    const content = document.getElementById('pf-main-content');
    logDebug('Initializing Watcher...');

    // B. The Data Watcher: Polls every 800ms until FUND is populated
    let checks = 0;
    const watcher = setInterval(() => {
        checks++;
        const fundSize = (typeof FUND !== 'undefined') ? Object.keys(FUND).length : 0;
        
        logDebug(`Check #${checks}: FUND has ${fundSize} stocks.`);

        if (fundSize > 0 || checks > 12) {
            clearInterval(watcher);
            if (fundSize === 0) logDebug("TIMEOUT: Rendering with empty data.", "warn");
            
            const pf = getMergedData();
            const inv = pf.reduce((a, r) => a + (r.qty * r.avgBuy), 0);
            const cur = pf.reduce((a, r) => a + (r.qty * r.ltp), 0);
            const pnl = cur - inv;

            content.innerHTML = `
                <div style="display:flex; justify-content:space-between; padding:15px; background:#161b22; border-radius:8px; margin-bottom:15px; border:1px solid #30363d;">
                    <div><small style="color:#8eb0d0">Invested</small><br><b style="color:#64b5f6">₹${(inv/100000).toFixed(2)}L</b></div>
                    <div style="text-align:right;"><small style="color:#8eb0d0">Mkt Value</small><br><b style="color:${pnl >= 0 ? '#00e896' : '#ff6b85'}">₹${(cur/100000).toFixed(2)}L</b></div>
                </div>

                <div style="overflow-x:auto;">
                    <table style="width:100%; border-collapse:collapse; font-size:13px; white-space:nowrap;">
                        <thead>
                            <tr style="color:#8eb0d0; border-bottom:1px solid #30363d; text-align:left;">
                                <th style="padding:12px 10px;">Ticker</th>
                                <th>ROE%</th>
                                <th>P/E</th>
                                <th>P&L%</th>
                                <th>Signal</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${pf.map(r => `
                                <tr onclick="openPortfolioStock('${r.sym}')" style="border-bottom:1px solid #21262d;">
                                    <td style="padding:12px 10px;"><b>${r.sym}</b></td>
                                    <td style="color:${r.roe > 15 ? '#00e896' : '#fff'}">${fn(r.roe, 1, '', '%')}</td>
                                    <td>${fn(r.pe, 1)}</td>
                                    <td style="color:${r.pnl >= 0 ? '#00e896' : '#ff6b85'}">${r.pnlP.toFixed(1)}%</td>
                                    <td><span style="font-size:10px; padding:2px 5px; border-radius:3px; border:1px solid; color:${r.signal==='BUY'?'#00e896':'#888'}">${r.signal || 'HOLD'}</span></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
                <div style="height:100px;"></div>
            `;
        }
    }, 800);
}
