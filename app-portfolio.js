// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - ACTIVE RECOVERY (v6.1)
// ─────────────────────────────────────────────────────────────

async function renderPortfolio(container) {
    if (!container) return;

    // 1. SHOW THE "ACTIVE RECOVERY" STATUS
    container.innerHTML = `
        <div id="pf-loader" style="padding:60px 20px; text-align:center; font-family:sans-serif; background:#0d1117; min-height:100vh; color:#8b949e;">
            <div style="color:#58a6ff; font-size:18px; font-weight:bold; margin-bottom:15px;">BharatMarkets Pro</div>
            <div id="step-fund">📡 Fetching fundamentals.json...</div>
            <div id="step-broker" style="margin-top:10px; opacity:0.5;">⌛ Waiting for Broker Data (S.portfolio)...</div>
        </div>`;

    // 2. FETCH FUNDAMENTALS MANUALLY (Since window.FUND is missing)
    let fundStocks = {};
    try {
        const response = await fetch('fundamentals.json');
        if (!response.ok) throw new Error("HTTP " + response.status);
        const data = await response.json();
        fundStocks = data.stocks || {};
        window._LOCAL_FUND = fundStocks; // Store for navigation
        
        const fEl = document.getElementById('step-fund');
        fEl.innerHTML = "✅ Fundamentals Loaded";
        fEl.style.color = "#3fb950";
    } catch (e) {
        document.getElementById('step-fund').innerHTML = "❌ Fundamentals Fetch Failed: " + e.message;
        return;
    }

    // 3. POLL FOR BROKER DATA
    if (window.pfTimer) clearInterval(window.pfTimer);
    
    window.pfTimer = setInterval(() => {
        // If S.portfolio is still missing, we look for ANY array that looks like your stocks
        const hasPF = (window.S && S.portfolio && S.portfolio.length > 0);
        const bEl = document.getElementById('step-broker');

        if (hasPF) {
            clearInterval(window.pfTimer);
            bEl.innerHTML = "✅ Broker Synced";
            bEl.style.color = "#3fb950";
            
            // Render the table using the data we just fetched
            setTimeout(() => drawFinalTable(container, fundStocks), 300);
        } else {
            bEl.style.opacity = "1";
        }
    }, 1000);
}

// 4. DATA-MAPPED TABLE
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
                        </td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>
    </div>`;
}

window.openStockDetail = (sym) => {
    const h = S.portfolio.find(p => p.sym === sym) || {};
    const f = (window._LOCAL_FUND && _LOCAL_FUND[sym.toUpperCase()]) ? _LOCAL_FUND[sym.toUpperCase()] : {};
    S.selStock = { ...h, ...f, sym };
    S.drillTab = 'overview';
    if (typeof showTab === 'function') showTab('drill');
};
