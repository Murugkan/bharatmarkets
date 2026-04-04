// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - ACTIVE LOADER (v6.0)
// ─────────────────────────────────────────────────────────────

async function renderPortfolio(container) {
    if (!container) return;

    // 1. UI SETUP
    container.innerHTML = `
        <div id="pf-loader" style="padding:60px 20px; text-align:center; font-family:sans-serif; background:#0d1117; min-height:100vh; color:#8b949e;">
            <div style="color:#58a6ff; font-size:18px; font-weight:bold; margin-bottom:10px;">BharatMarkets Pro</div>
            <div id="pf-step-1">📡 Connecting to Fundamentals...</div>
            <div id="pf-step-2" style="margin-top:8px; opacity:0.5;">⌛ Waiting for Broker Sync...</div>
        </div>`;

    // 2. FETCH FUNDAMENTALS DIRECTLY (Since Global FUND is missing)
    try {
        const response = await fetch('fundamentals.json');
        if (!response.ok) throw new Error("HTTP " + response.status);
        window._FUND = await response.json(); 
        document.getElementById('pf-step-1').innerHTML = "✅ Fundamentals Loaded";
        document.getElementById('pf-step-1').style.color = "#3fb950";
    } catch (e) {
        document.getElementById('pf-step-1').innerHTML = "❌ Fundamentals Failed: " + e.message;
        return;
    }

    // 3. POLL FOR BROKER DATA (Since S.portfolio is missing initially)
    if (window.pfTimer) clearInterval(window.pfTimer);
    
    window.pfTimer = setInterval(() => {
        // We look for S.portfolio OR any array that looks like your 92 stocks
        const hasPF = (window.S && S.portfolio && S.portfolio.length > 0);
        
        if (hasPF) {
            clearInterval(window.pfTimer);
            drawFinalTable(container);
        } else {
            document.getElementById('pf-step-2').style.opacity = "1";
        }
    }, 1000);
}

function drawFinalTable(container) {
    // Map data using the _FUND variable we just fetched
    const pf = S.portfolio.map(h => {
        const sym = h.sym.toUpperCase();
        // Handle your specific JSON 'stocks' structure
        const f = (_FUND.stocks && _FUND.stocks[sym]) ? _FUND.stocks[sym] : {};
        
        // Calculation Logic
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
        <div style="background:#161b22; padding:20px; border-radius:12px; border:1px solid #30363d; display:flex; justify-content:space-between; margin-bottom:16px;">
            <div><small style="color:#8b949e; font-size:11px;">INVESTED</small><br><b style="font-size:22px;">₹${(totalInv/100000).toFixed(2)}L</b></div>
            <div style="text-align:right;"><small style="color:#8b949e; font-size:11px;">RETURNS</small><br><b style="font-size:22px; color:${netPnlP >= 0 ? '#3fb950' : '#f85149'}">${netPnlP.toFixed(2)}%</b></div>
        </div>

        <div style="background:#161b22; border-radius:12px; border:1px solid #30363d; overflow:hidden;">
            <table style="width:100%; border-collapse:collapse; font-size:14px;">
                <tbody>
                    ${pf.map(r => `
                    <tr onclick="openStock('${r.sym}')" style="border-bottom:1px solid #30363d;">
                        <td style="padding:14px 12px;"><b>${r.sym}</b><br><small style="color:#8b949e">${r.signal || 'HOLD'}</small></td>
                        <td style="text-align:center;"><small style="color:#8b949e">ROE</small><br><span style="color:${r.roe > 15 ? '#3fb950' : '#fff'}">${r.roe ? r.roe.toFixed(1)+'%' : '—'}</span></td>
                        <td style="padding:14px 12px; text-align:right;"><span style="color:${r.pnlP >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">${r.pnlP.toFixed(1)}%</span></td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>
    </div>`;
}

window.openStock = (sym) => {
    const h = S.portfolio.find(p => p.sym === sym) || {};
    const f = (_FUND.stocks && _FUND.stocks[sym.toUpperCase()]) ? _FUND.stocks[sym.toUpperCase()] : {};
    S.selStock = { ...h, ...f, sym };
    S.drillTab = 'overview';
    if (typeof showTab === 'function') showTab('drill');
};
