// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - BHARATMARKETS PRO (v6.0)
// ─────────────────────────────────────────────────────────────

async function renderPortfolio(container) {
    if (!container) return;

    // 1. INITIAL UI & CHECKLIST
    container.innerHTML = `
        <div id="pf-loader" style="padding:60px 20px; text-align:center; font-family:sans-serif; background:#0d1117; min-height:100vh; color:#8b949e;">
            <div style="color:#58a6ff; font-size:18px; font-weight:bold; margin-bottom:15px;">BharatMarkets Pro</div>
            <div id="step-fund" style="margin-bottom:8px;">📡 Connecting to Fundamentals...</div>
            <div id="step-broker" style="opacity:0.5;">⌛ Waiting for Broker Sync...</div>
        </div>`;

    // 2. ACTIVE FETCH (Bypasses the missing 'FUND' variable)
    let fundData = null;
    try {
        const response = await fetch('fundamentals.json');
        if (!response.ok) throw new Error("HTTP " + response.status);
        const json = await response.json();
        fundData = json.stocks; // Extract the stocks object
        window._FUND_CACHE = fundData; // Store globally for drill-down
        
        const fEl = document.getElementById('step-fund');
        if (fEl) {
            fEl.innerHTML = "✅ Fundamentals Loaded";
            fEl.style.color = "#3fb950";
        }
    } catch (e) {
        document.getElementById('step-fund').innerHTML = "❌ Fundamentals Fail: " + e.message;
        return;
    }

    // 3. POLLING FOR BROKER DATA (S.portfolio)
    if (window.pfTimer) clearInterval(window.pfTimer);
    
    window.pfTimer = setInterval(() => {
        const hasPF = (window.S && S.portfolio && S.portfolio.length > 0);
        const bEl = document.getElementById('step-broker');
        
        if (hasPF) {
            clearInterval(window.pfTimer);
            bEl.innerHTML = "✅ Broker Synced";
            bEl.style.color = "#3fb950";
            
            // Short delay so you can see the checklist complete
            setTimeout(() => drawFinalTable(container, fundData), 300);
        } else {
            if (bEl) bEl.style.opacity = "1";
        }
    }, 1000);
}

// 4. TABLE GENERATOR
function drawFinalTable(container, fundData) {
    const pf = S.portfolio.map(h => {
        const sym = h.sym.toUpperCase();
        // Handle Ticker Mismatch (AFCONSINFRAS -> AFCONS)
        const targetSym = sym === "AFCONSINFRAS" ? "AFCONS" : sym;
        const f = fundData[targetSym] || {};
        
        const ltp = h.liveLtp || f.ltp || 0;
        const avg = h.avgBuy || 0;
        const pnlP = avg > 0 ? ((ltp - avg) / avg) * 100 : 0;
        
        return { ...h, ...f, ltp, pnlP, sym };
    });

    const totalInv = pf.reduce((a, r) => a + (r.qty * r.avgBuy), 0);
    const totalCur = pf.reduce((a, r) => a + (r.qty * r.ltp), 0);
    const netPnlP = totalInv > 0 ? ((totalCur - totalInv) / totalInv) * 100 : 0;

    container.innerHTML = `
    <div style="padding:12px; background:#0d1117; min-height:100vh; font-family:-apple-system, sans-serif; color:#fff;">
        
        <div style="background:#161b22; padding:20px; border-radius:12px; border:1px solid #30363d; display:flex; justify-content:space-between; margin-bottom:16px;">
            <div>
                <div style="color:#8b949e; font-size:11px;">INVESTED</div>
                <div style="font-size:22px; font-weight:bold; margin-top:4px;">₹${(totalInv/100000).toFixed(2)}L</div>
            </div>
            <div style="text-align:right;">
                <div style="color:#8b949e; font-size:11px;">NET P&L</div>
                <div style="font-size:22px; font-weight:bold; margin-top:4px; color:${netPnlP >= 0 ? '#3fb950' : '#f85149'}">${netPnlP.toFixed(2)}%</div>
            </div>
        </div>

        <div style="background:#161b22; border-radius:12px; border:1px solid #30363d; overflow:hidden;">
            <table style="width:100%; border-collapse:collapse; font-size:14px;">
                <tbody>
                    ${pf.map(r => `
                    <tr onclick="openStockDetail('${r.sym}')" style="border-bottom:1px solid #30363d;">
                        <td style="padding:14px 12px;">
                            <div style="font-weight:bold;">${r.sym}</div>
                            <div style="font-size:10px; color:#8b949e">${r.signal || 'HOLD'}</div>
                        </td>
                        <td style="text-align:center;">
                            <div style="color:#8b949e; font-size:10px;">ROE</div>
                            <div style="color:${r.roe > 15 ? '#3fb950' : '#fff'}">${r.roe ? r.roe.toFixed(1)+'%' : '—'}</div>
                        </td>
                        <td style="padding:14px 12px; text-align:right;">
                            <div style="color:${r.pnlP >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">${r.pnlP.toFixed(1)}%</div>
                            <div style="font-size:10px; color:#484f58">₹${(r.ltp||0).toFixed(0)}</div>
                        </td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>
        <div style="height:80px;"></div>
    </div>`;
}

// 5. DETAIL NAVIGATION
window.openStockDetail = (sym) => {
    const h = S.portfolio.find(p => p.sym === sym) || {};
    const f = (window._FUND_CACHE && _FUND_CACHE[sym]) ? _FUND_CACHE[sym] : {};
    S.selStock = { ...h, ...f, sym };
    S.drillTab = 'overview';
    const nav = window.showTab || window.setTab || window.router;
    if (nav) nav('drill');
};
