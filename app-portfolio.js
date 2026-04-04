// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - BHARATMARKETS PRO (v5.1)
// ─────────────────────────────────────────────────────────────

// 1. DATA MAPPING (Matches fundamentals.json 'stocks' key)
const getStockDetails = (ticker) => {
    if (!ticker) return {};
    const sym = ticker.toUpperCase();
    
    // Check for the 'stocks' object inside your FUND variable
    const base = (typeof FUND !== 'undefined' && FUND.stocks) ? FUND.stocks : {};
    
    // Ticker Mappings (For symbols that differ between broker and data)
    const aliases = {
        "AFCONSINFRAS": "AFCONS",
        "TATA MOTORS": "TATAMOTORS",
        "M&M": "M&M"
    };
    
    const targetSym = aliases[sym] || sym;
    return base[targetSym] || window[targetSym] || {};
};

// 2. NAVIGATION
window.openPortfolioStock = (sym) => {
    try {
        const h = S.portfolio.find(p => p.sym === sym) || {};
        const f = getStockDetails(sym);
        
        // Prepare global state for Detail Page
        S.selStock = { ...h, ...f, sym };
        S.drillTab = 'overview';
        
        // Execute Navigation
        const nav = window.showTab || window.setTab || window.router;
        if (typeof nav === 'function') nav('drill');
    } catch (e) {
        console.error("Navigation Error:", e);
    }
};

// 3. RENDERER (The Main Entry Point)
function renderPortfolio(container) {
    if (!container) return;

    // Show initial loading state
    container.innerHTML = `
        <div style="padding:50px 20px; text-align:center; font-family:sans-serif; color:#8eb0d0;">
            <div style="font-size:14px; margin-bottom:8px;">⚡ Syncing Portfolio Data...</div>
            <div id="pf-sync-msg" style="font-size:10px; color:#484f58;">Waiting for S.portfolio</div>
        </div>`;

    if (window.pfTimer) clearInterval(window.pfTimer);
    
    window.pfTimer = setInterval(() => {
        // Based on your logs, we know the data lives in S.portfolio
        const dataReady = (window.S && S.portfolio && S.portfolio.length > 0);
        
        if (dataReady) {
            clearInterval(window.pfTimer);
            drawPortfolioTable(container);
        }
    }, 800);
}

// 4. UI GENERATOR
function drawPortfolioTable(container) {
    const pf = S.portfolio.map(h => {
        const f = getStockDetails(h.sym);
        const ltp = h.liveLtp || f.ltp || 0;
        const avg = h.avgBuy || 0;
        const pnlP = avg > 0 ? ((ltp - avg) / avg) * 100 : 0;
        return { ...h, ...f, ltp, pnlP };
    });

    const totalInv = pf.reduce((a, r) => a + (r.qty * r.avgBuy), 0);
    const totalCur = pf.reduce((a, r) => a + (r.qty * r.ltp), 0);
    const netPnlP = totalInv > 0 ? ((totalCur - totalInv) / totalInv) * 100 : 0;

    container.innerHTML = `
    <div style="padding:12px; background:#0d1117; min-height:100vh; font-family:-apple-system, sans-serif; color:#fff;">
        
        <div style="background:#161b22; padding:18px; border-radius:12px; border:1px solid #30363d; display:flex; justify-content:space-between; margin-bottom:16px;">
            <div>
                <div style="color:#8b949e; font-size:11px; text-transform:uppercase;">Invested</div>
                <div style="font-size:20px; font-weight:bold; margin-top:4px;">₹${(totalInv/100000).toFixed(2)}L</div>
            </div>
            <div style="text-align:right;">
                <div style="color:#8b949e; font-size:11px; text-transform:uppercase;">Net P&L</div>
                <div style="font-size:20px; font-weight:bold; margin-top:4px; color:${netPnlP >= 0 ? '#3fb950' : '#f85149'}">${netPnlP.toFixed(2)}%</div>
            </div>
        </div>

        <div style="background:#161b22; border-radius:12px; border:1px solid #30363d; overflow:hidden;">
            <table style="width:100%; border-collapse:collapse; font-size:14px;">
                <thead style="background:#1c2128; color:#8b949e; font-size:11px;">
                    <tr>
                        <th style="padding:12px; text-align:left;">STOCK</th>
                        <th style="text-align:center;">ROE%</th>
                        <th style="padding:12px; text-align:right;">P&L%</th>
                    </tr>
                </thead>
                <tbody>
                    ${pf.map(r => `
                    <tr onclick="openPortfolioStock('${r.sym}')" style="border-bottom:1px solid #30363d;">
                        <td style="padding:14px 12px;">
                            <div style="font-weight:bold;">${r.sym}</div>
                            <div style="font-size:10px; color:${r.signal === 'BUY' ? '#3fb950' : '#8b949e'}">${r.signal || 'HOLD'}</div>
                        </td>
                        <td style="text-align:center;">
                            <div style="color:${r.roe > 15 ? '#3fb950' : '#fff'}">${r.roe ? r.roe.toFixed(1)+'%' : '—'}</div>
                        </td>
                        <td style="padding:14px 12px; text-align:right;">
                            <div style="color:${r.pnlP >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">${r.pnlP.toFixed(1)}%</div>
                            <div style="font-size:10px; color:#484f58">₹${r.ltp.toFixed(0)}</div>
                        </td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>
        <div style="height:100px;"></div>
    </div>`;
}
