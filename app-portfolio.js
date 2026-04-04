// ─────────────────────────────────────────────────────────────
//  APP-PORTFOLIO.JS - FINAL ARCHITECTURE MERGE (v13.0)
// ─────────────────────────────────────────────────────────────

async function renderPortfolio(container) {
    if (!container) return;

    container.innerHTML = `
        <div style="padding:60px 20px; text-align:center; background:#02040a; min-height:100vh; font-family:sans-serif;">
            <div style="color:#58a6ff; font-weight:bold; font-size:18px; margin-bottom:10px;">BHARATMARKETS PRO</div>
            <div id="pf-status" style="color:#8b949e; font-size:12px;">🔗 SYNCING WITH GATEKEEPER...</div>
        </div>`;

    try {
        // 1. Fetch Fundamentals (The reliable source)
        const fRes = await fetch('fundamentals.json?v=' + Date.now());
        if (!fRes.ok) throw new Error("Fundamentals sync failed");
        const fData = await fRes.json();
        
        // 2. Map to Global Gatekeeper
        window.FUND = fData;
        window.fundLoaded = true;

        // 3. Check for Portfolio Data (S.portfolio)
        // We poll for 3 seconds to let the Orchestrator finish
        let attempts = 0;
        const checkS = setInterval(() => {
            const hasPortfolio = (window.S && S.portfolio && S.portfolio.length > 0);
            attempts++;

            if (hasPortfolio) {
                clearInterval(checkS);
                drawPortfolioFinal(container);
            } else if (attempts > 6) { // If S.portfolio is still empty after 3 seconds
                clearInterval(checkS);
                // Fallback: If S is empty, try to use the 'stocks' list from Fundamentals
                if (fData.stocks) {
                    window.S = window.S || {};
                    window.S.portfolio = Object.keys(fData.stocks).map(sym => ({ sym, qty: 0 }));
                    drawPortfolioFinal(container);
                } else {
                    document.getElementById('pf-status').innerHTML = "❌ NO PORTFOLIO DATA FOUND IN S or JSON";
                }
            }
        }, 500);

    } catch (e) {
        container.innerHTML = `<div style="color:#f85149; padding:40px; text-align:center;">Sync Error: ${e.message}</div>`;
    }
}

function drawPortfolioFinal(container) {
    const portfolio = S.portfolio.map(h => {
        const sym = h.sym.toUpperCase();
        const f = (FUND.stocks && FUND.stocks[sym]) ? FUND.stocks[sym] : {};
        const ltp = h.ltp || f.ltp || 0;
        const pnl = h.avgBuy > 0 ? ((ltp - h.avgBuy) / h.avgBuy) * 100 : 0;
        return { ...h, ...f, ltp, pnl, sym };
    });

    container.innerHTML = `
    <div style="padding:16px; background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif;">
        <div style="background:#111d30; padding:15px; border-radius:12px; border:1px solid #1e3350; margin-bottom:15px;">
            <div style="color:#8b949e; font-size:10px;">PORTFOLIO ASSETS</div>
            <div style="font-size:22px; font-weight:bold;">${portfolio.length} Stocks</div>
        </div>
        <div style="background:#0d1525; border-radius:12px; border:1px solid #1e3350; overflow:hidden;">
            <table style="width:100%; border-collapse:collapse;">
                ${portfolio.map(s => `
                <tr style="border-bottom:1px solid #1e3350;">
                    <td style="padding:12px;">
                        <b>${s.sym}</b><br>
                        <small style="color:#8b949e">ROE: ${s.roe ? s.roe.toFixed(1)+'%' : '--'}</small>
                    </td>
                    <td style="text-align:right; padding:12px;">
                        <b style="color:${s.pnl >= 0 ? '#3fb950' : '#f85149'}">${s.pnl.toFixed(1)}%</b><br>
                        <small style="color:#484f58">₹${(s.ltp||0).toFixed(0)}</small>
                    </td>
                </tr>`).join('')}
            </table>
        </div>
    </div>`;
}
