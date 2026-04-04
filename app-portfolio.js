// ─────────────────────────────────────────────────────────────
//  APP-PORTFOLIO.JS - ORCHESTRATOR BYPASS (v12.0)
// ─────────────────────────────────────────────────────────────

async function renderPortfolio(container) {
    if (!container) return;

    // 1. Show immediate status
    container.innerHTML = `<div style="padding:60px; text-align:center; background:#02040a; color:#58a6ff; font-family:sans-serif;">
        <div style="margin-bottom:10px;">📡 FORCING DATA MERGE...</div>
        <small style="color:#8b949e;">Bypassing Orchestrator Lock</small>
    </div>`;

    try {
        // 2. FORCE FETCH BOTH (The "Architecture" way to fix the lock)
        const [fRes, pRes] = await Promise.all([
            fetch('fundamentals.json?v=' + Date.now()),
            fetch('portfolio.json?v=' + Date.now()) // Explicitly fetching the source
        ]);

        const fData = await fRes.json();
        const pData = await pRes.json();

        // 3. REPAIR THE GATEKEEPER (Populate S and FUND manually)
        window.FUND = fData;
        if (!window.S) window.S = {};
        
        // If your portfolio.json has a 'stocks' or 'holdings' key, map it here:
        window.S.portfolio = pData.stocks || pData.holdings || pData; 
        window.fundLoaded = true;

        // 4. VERIFY AND DRAW
        if (S.portfolio && S.portfolio.length > 0) {
            drawFinalUI(container);
        } else {
            throw new Error("Portfolio file is empty");
        }

    } catch (e) {
        container.innerHTML = `
            <div style="padding:40px; text-align:center; color:#f85149;">
                <b>❌ BYPASS FAILED</b><br>
                <small>${e.message}</small><br>
                <button onclick="location.reload()" style="margin-top:15px; background:#1f6feb; color:#fff; border:none; padding:8px 16px; border-radius:6px;">Retry System Boot</button>
            </div>`;
    }
}

function drawFinalUI(container) {
    const pf = S.portfolio.map(h => {
        const sym = h.sym.toUpperCase();
        const f = (FUND.stocks && FUND.stocks[sym]) ? FUND.stocks[sym] : {};
        const ltp = h.ltp || f.ltp || 0;
        const pnl = h.avgBuy > 0 ? ((ltp - h.avgBuy) / h.avgBuy) * 100 : 0;
        return { ...h, ...f, ltp, pnl, sym };
    });

    container.innerHTML = `
    <div style="padding:16px; background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif;">
        <div style="background:#111d30; padding:15px; border-radius:12px; border:1px solid #1e3350; margin-bottom:15px;">
            <small style="color:#8b949e;">SYNCED ASSETS</small>
            <div style="font-size:22px; font-weight:bold;">${pf.length} Holdings</div>
        </div>
        ${pf.map(s => `
            <div style="display:flex; justify-content:space-between; padding:12px 0; border-bottom:1px solid #1e3350;">
                <div><b>${s.sym}</b><br><small style="color:#8b949e">ROE: ${s.roe ? s.roe.toFixed(1)+'%' : '--'}</small></div>
                <div style="text-align:right;">
                    <b style="color:${s.pnl >= 0 ? '#3fb950' : '#f85149'}">${s.pnl.toFixed(1)}%</b><br>
                    <small style="color:#484f58">₹${s.ltp.toFixed(0)}</small>
                </div>
            </div>
        `).join('')}
    </div>`;
}
