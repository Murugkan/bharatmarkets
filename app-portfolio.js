// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - DATA-MATCHED EDITION (v5.0)
// ─────────────────────────────────────────────────────────────

// 1. DATA MAPPING ENGINE
const getStockDetails = (ticker) => {
    if (!ticker) return {};
    const sym = ticker.toUpperCase();
    
    // Check if FUND variable exists (from fundamentals.json)
    const base = (typeof FUND !== 'undefined' && FUND.stocks) ? FUND.stocks : {};
    
    // Handle Mismatches (Add more here if needed)
    const aliases = {
        "AFCONSINFRAS": "AFCONS",
        "TATA MOTORS": "TATAMOTORS",
        "M&M": "M&M"
    };
    
    const targetSym = aliases[sym] || sym;
    
    // Look in FUND.stocks first, then check global window for loose variables
    return base[targetSym] || window[targetSym] || {};
};

// 2. DRILL-DOWN HANDLER
window.openPortfolioStock = (sym) => {
    try {
        console.log(`[Drill] Opening ${sym}`);
        const h = S.portfolio.find(p => p.sym === sym) || {};
        const f = getStockDetails(sym);
        
        // Populate Global Selection
        S.selStock = { ...h, ...f, sym };
        S.drillTab = 'overview';
        
        // Navigation (Tries all common app router names)
        const nav = window.showTab || window.setTab || window.router;
        if (typeof nav === 'function') nav('drill');
        
    } catch (e) {
        console.error("Drill Error:", e);
    }
};

// 3. THE RENDERER
function renderPortfolio(container) {
    if (!container) return;

    // Reset UI and show loading state
    container.innerHTML = `<div style="padding:40px; text-align:center; color:#8eb0d0; font-family:sans-serif;">
        <div style="margin-bottom:10px;">⚡ Connecting to Market Data...</div>
        <small id="sync-status">Checking Portfolio...</small>
    </div>`;

    // Polling Watcher: Waits for S.portfolio to arrive
    if (window.pfTimer) clearInterval(window.pfTimer);
    
    window.pfTimer = setInterval(() => {
        const hasPortfolio = (window.S && S.portfolio && S.portfolio.length > 0);
        const hasFundamentals = (typeof FUND !== 'undefined' && FUND.stocks);
        
        const statusEl = document.getElementById('sync-status');
        if (statusEl) {
            statusEl.innerText = `Portfolio: ${hasPortfolio ? 'READY' : 'WAITING'} | Data: ${hasFundamentals ? 'READY' : 'WAITING'}`;
        }

        if (hasPortfolio) {
            clearInterval(window.pfTimer);
            drawPortfolioUI(container);
        }
    }, 1000);
}

// 4. THE UI GENERATOR
function drawPortfolioUI(container) {
    const pf = S.portfolio.map(h => {
        const f = getStockDetails(h.sym);
        const ltp = h.liveLtp || f.ltp || 0;
        const avg = h.avgBuy || 0;
        const pnl = (ltp - avg) * h.qty;
        const pnlP = avg > 0 ? ((ltp - avg) / avg) * 100 : 0;
        return { ...h, ...f, ltp, pnl, pnlP };
    });

    // Calc Totals
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
                <div style="color:#8b949e; font-size:11px; text-transform:uppercase;">Returns</div>
                <div style="font-size:20px; font-weight:bold; margin-top:4px; color:${netPnlP >= 0 ? '#3fb950' : '#f85149'}">${netPnlP.toFixed(2)}%</div>
            </div>
        </div>

        <div style="background:#161b22; border-radius:12px; border:1px solid #30363d; overflow:hidden;">
            <table style="width:100%; border-collapse:collapse; font-size:14px;">
                <thead>
                    <tr style="border-bottom:1px solid #30363d; color:#8b949e; font-size:11px;">
                        <th style="padding:12px; text-align:left;">STOCK</th>
                        <th style="text-align:center;">ROE%</th>
                        <th style="padding:12px; text-align:right;">P&L%</th>
                    </tr>
                </thead>
                <tbody>
                    ${pf.map(r => `
                    <tr onclick="openPortfolioStock('${r.sym}')" style="border-bottom:1px solid #21262d;">
                        <td style="padding:14px 12px;">
                            <div style="font-weight:bold;">${r.sym}</div>
                            <div style="font-size:10px; color:${r.signal === 'BUY' ? '#3fb950' : '#8b949e'}">${r.signal || 'HOLD'}</div>
                        </td>
                        <td style="text-align:center;">
                            <div style="color:${r.roe > 15 ? '#3fb950' : '#fff'}">${r.roe ? r.roe.toFixed(1)+'%' : '—'}</div>
                            <div style="font-size:10px; color:#484f58">PE: ${r.pe ? r.pe.toFixed(0) : '—'}</div>
                        </td>
                        <td style="padding:14px 12px; text-align:right;">
                            <div style="color:${r.pnlP >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">${r.pnlP.toFixed(1)}%</div>
                            <div style="font-size:10px; color:#484f58">₹${r.ltp.toFixed(0)}</div>
                        </td>
                    </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        
        <div style="padding:20px; text-align:center;">
            <small style="color:#484f58;">Last Updated: ${typeof FUND !== 'undefined' ? (FUND.updated || 'Recent') : 'Syncing...'}</small>
        </div>
    </div>`;
}
