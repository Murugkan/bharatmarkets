// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - FULL PRODUCTION BUILD (v3.0 STABLE)
// ─────────────────────────────────────────────────────────────

// 1. STYLES & CONSTANTS
const CSS = {
    GRN: 'color:#00e896', RED: 'color:#ff6b85', DIM: 'color:#4a6888',
    BG_BUY: 'rgba(0,160,80,.1)', BG_SELL: 'rgba(200,30,50,.1)'
};

// 2. IPHONE DEBUG LOGGER
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

// 3. DATA ENGINE: ROBUST MAPPING
function mergeHolding(h) {
    if (typeof FUND === 'undefined') return h;
    
    // Attempt mapping via Symbol, then Case-Insensitive, then ISIN
    let f = FUND[h.sym];
    if (!f) {
        const s = h.sym.toUpperCase();
        f = Object.values(FUND).find(x => x.sym?.toUpperCase() === s || x.symbol?.toUpperCase() === s || x.isin === h.isin);
    }

    if (!f) {
        logDebug(`No data found for ${h.sym}`, 'warn');
        return { ...h, ltp: h.liveLtp || 0, roe: 0, pe: 0, sig: 'HOLD' };
    }

    const ltp = h.liveLtp || f.ltp || 0;
    return {
        ...h, ...f, ltp,
        sig: f.signal || (f.roe > 15 ? 'BUY' : 'HOLD')
    };
}

// 4. DRILL-DOWN LOGIC
window.openPortfolioStock = (sym) => {
    logDebug(`Opening: ${sym}`);
    try {
        const h = S.portfolio.find(p => p.sym === sym);
        const merged = mergeHolding(h);
        S.selStock = merged; 
        S.drillTab = 'overview';
        
        // Trigger App Navigation
        if (typeof showTab === 'function') showTab('drill');
        else if (typeof setTab === 'function') setTab('drill');
        else if (typeof router === 'function') router('drill');
        
        logDebug(`Success: ${sym} loaded.`);
    } catch (e) {
        logDebug(`Drill Error: ${e.message}`, 'error');
    }
};

// 5. UI COMPONENTS
function renderKpiHeader(pf) {
    const inv = pf.reduce((a, r) => a + (r.qty * r.avgBuy), 0);
    const cur = pf.reduce((a, r) => a + (r.qty * r.ltp), 0);
    const pnl = cur - inv;
    const pnlP = (pnl / inv * 100) || 0;

    return `
    <div style="display:flex; justify-content:space-between; padding:15px; background:#161b22; border-radius:8px; margin-bottom:15px; border:1px solid #30363d;">
        <div><small style="color:#8eb0d0">Invested</small><br><b style="color:#64b5f6">₹${(inv/100000).toFixed(2)}L</b></div>
        <div style="text-align:right;"><small style="color:#8eb0d0">Total P&L</small><br><b style="${pnl >= 0 ? CSS.GRN : CSS.RED}">${pnlP.toFixed(2)}%</b></div>
    </div>`;
}

// 6. MAIN RENDERER
function renderPortfolio(container) {
    if (!container) return;

    // A. Setup Top Debug Window & Content Area
    container.innerHTML = `
    <div id="debug-window" style="position:fixed; top:0; left:0; right:0; height:150px; background:rgba(10,10,10,0.9); z-index:1000; border-bottom:2px solid #333; display:flex; flex-direction:column; backdrop-filter:blur(4px);">
        <div style="background:#222; padding:5px 12px; display:flex; justify-content:space-between; align-items:center; font-size:11px;">
            <b style="color:#64b5f6">DEBUG LOGS (iPhone)</b>
            <button onclick="document.getElementById('app-debug-logs').innerHTML=''" style="background:#3a0010; color:#fff; border:none; padding:2px 8px; border-radius:3px;">Clear</button>
        </div>
        <div id="app-debug-logs" style="flex:1; overflow-y:auto; padding:5px 12px; font-family:monospace;"></div>
    </div>
    <div id="pf-main-content" style="margin-top:160px; padding:10px;"></div>`;

    const content = document.getElementById('pf-main-content');
    logDebug('Initializing...');

    if (typeof S === 'undefined' || !S.portfolio) {
        logDebug('Global S.portfolio missing!', 'error');
        return;
    }

    const pf = S.portfolio.map(mergeHolding);
    logDebug(`Found ${pf.length} stocks.`);

    // B. Render UI
    content.innerHTML = `
        ${renderKpiHeader(pf)}
        
        <div style="overflow-x:auto;">
            <table style="width:100%; border-collapse:collapse; font-size:13px; white-space:nowrap;">
                <thead>
                    <tr style="color:#8eb0d0; border-bottom:1px solid #30363d; text-align:left;">
                        <th style="padding:12px 10px;">Ticker</th>
                        <th>ROE%</th>
                        <th>P/E</th>
                        <th>P&L%</th>
                        <th>Sig</th>
                    </tr>
                </thead>
                <tbody>
                    ${pf.map(r => {
                        const pnlP = ((r.ltp - r.avgBuy) / r.avgBuy * 100) || 0;
                        const bg = r.sig === 'BUY' ? CSS.BG_BUY : r.sig === 'SELL' ? CSS.BG_SELL : 'transparent';
                        return `
                        <tr onclick="openPortfolioStock('${r.sym}')" style="border-bottom:1px solid #21262d; background:${bg}">
                            <td style="padding:12px 10px;"><b>${r.sym}</b><br><small style="${CSS.DIM}">${(r.name || '').slice(0, 10)}</small></td>
                            <td style="${r.roe > 15 ? CSS.GRN : ''}">${r.roe ? r.roe.toFixed(1) + '%' : '—'}</td>
                            <td>${r.pe ? r.pe.toFixed(1) : '—'}</td>
                            <td style="${pnlP >= 0 ? CSS.GRN : CSS.RED}">${pnlP.toFixed(1)}%</td>
                            <td><span style="font-size:10px; padding:2px 5px; border-radius:3px; border:1px solid; color:${r.sig==='BUY'?'#00e896':'#888'}">${r.sig}</span></td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>
        </div>
        <div style="height:100px;"></div> `;
}
