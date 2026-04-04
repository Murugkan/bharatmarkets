// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - IPHONE TOP-DEBUG EDITION
// ─────────────────────────────────────────────────────────────

// 1. IMPROVED LOGGER WITH CLIPBOARD SUPPORT
window.logDebug = (msg, type = 'info') => {
    const logEl = document.getElementById('app-debug-logs');
    if (!logEl) return;
    const time = new Date().toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' });
    const color = type === 'error' ? '#ff6b85' : type === 'warn' ? '#ffb000' : '#00e896';
    
    const newLog = document.createElement('div');
    newLog.style.cssText = `color:${color}; border-bottom:1px dotted #333; padding:4px 0; white-space:pre-wrap;`;
    newLog.innerHTML = `[${time}] ${msg}`;
    logEl.prepend(newLog);
};

window.copyDebugLogs = () => {
    const text = document.getElementById('app-debug-logs').innerText;
    navigator.clipboard.writeText(text).then(() => alert('Logs copied to clipboard!'));
};

// 2. UI: TOP-MOUNTED DEBUG WINDOW (Prevents iPhone Notch/Menu overlap)
function renderDebugWindow() {
    return `
    <div id="debug-window" style="position:fixed; top:0; left:0; right:0; height:180px; background:rgba(10,10,10,0.95); border-bottom:2px solid #333; z-index:10000; font-family:monospace; font-size:11px; display:flex; flex-direction:column; backdrop-filter:blur(5px);">
        <div style="background:#222; padding:8px 12px; display:flex; justify-content:space-between; align-items:center;">
            <span style="color:#64b5f6; font-weight:bold;">S-CONSOLE v2.0</span>
            <div style="display:flex; gap:10px;">
                <button onclick="copyDebugLogs()" style="background:#003a20; border:none; color:#fff; font-size:10px; padding:4px 8px; border-radius:3px;">Copy All</button>
                <button onclick="document.getElementById('app-debug-logs').innerHTML=''" style="background:#3a0010; border:none; color:#fff; font-size:10px; padding:4px 8px; border-radius:3px;">Clear</button>
            </div>
        </div>
        <div id="app-debug-logs" style="flex:1; overflow-y:auto; padding:8px 12px; color:#ccc;">
            <div style="color:#888;">--- Console Initialized ---</div>
        </div>
    </div>`;
}

// 3. MAIN RENDERER
function renderPortfolio(container) {
    if (!container) return;
    
    // Initializing Debug
    container.innerHTML = renderDebugWindow() + `<div id="pf-content" style="margin-top:190px; padding:10px;"></div>`;
    const content = document.getElementById('pf-content');

    logDebug('Checking Globals...');
    if (typeof S === 'undefined') { logDebug('S is UNDEFINED', 'error'); return; }
    if (typeof FUND === 'undefined') { logDebug('FUND is UNDEFINED', 'error'); }
    
    const pfSize = S.portfolio ? S.portfolio.length : 0;
    logDebug(`Portfolio Size: ${pfSize}`);

    if (pfSize === 0) {
        content.innerHTML = `<div style="text-align:center; padding:50px; color:#4a6888;">No holdings found in S.portfolio</div>`;
        return;
    }

    // Process Table
    let html = `
    <div class="kpi-strip" style="display:flex; justify-content:space-between; padding:15px; background:#161b22; border-radius:8px; margin-bottom:15px;">
        <div><small style="color:#8eb0d0">Invested</small><br><b style="color:#64b5f6">₹${pfSize > 0 ? 'Calculated' : '0'}</b></div>
        <div style="text-align:right;"><small style="color:#8eb0d0">Count</small><br><b>${pfSize}</b></div>
    </div>
    
    <div style="overflow-x:auto;">
        <table style="width:100%; border-collapse:collapse; font-size:13px;">
            <thead>
                <tr style="color:#8eb0d0; border-bottom:1px solid #30363d; text-align:left;">
                    <th style="padding:10px;">Ticker</th>
                    <th>ROE%</th>
                    <th>Sig</th>
                </tr>
            </thead>
            <tbody>
                ${S.portfolio.map(h => {
                    const f = (typeof FUND !== 'undefined') ? FUND[h.sym] : null;
                    if (!f) logDebug(`No fundamental data for ${h.sym}`, 'warn');
                    return `
                    <tr onclick="openPortfolioStock('${h.sym}')" style="border-bottom:1px solid #21262d;">
                        <td style="padding:12px 10px;"><b>${h.sym}</b></td>
                        <td>${f ? f.roe + '%' : '—'}</td>
                        <td><span style="color:${f?.signal==='BUY'?'#00e896':'#888'}">${f?.signal || 'HOLD'}</span></td>
                    </tr>`;
                }).join('')}
            </tbody>
        </table>
    </div>`;

    content.innerHTML = html;
}

// 4. DRILL DOWN LOGIC
window.openPortfolioStock = (sym) => {
    logDebug(`Opening Stock: ${sym}`);
    try {
        if (!FUND[sym]) throw new Error(`No data in FUND for ${sym}`);
        S.selStock = { ...FUND[sym], sym };
        logDebug(`Success: ${sym} selected.`, 'info');
        // If your app uses a specific function to switch tabs, call it here
        if (typeof showDrill === 'function') showDrill();
    } catch (e) {
        logDebug(`Error: ${e.message}`, 'error');
    }
};
