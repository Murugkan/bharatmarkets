// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - BHARATMARKETS PRO (v7.0 - FINAL)
// ─────────────────────────────────────────────────────────────

/** 1. DATA RECOVERY ENGINE **/
async function ensureFundamentals() {
    // If FUND is already populated, skip
    if (window.FUND && window.FUND.stocks && Object.keys(window.FUND.stocks).length > 0) return true;

    try {
        console.log("Empty FUND detected. Attempting direct recovery...");
        const response = await fetch('fundamentals.json?t=' + Date.now());
        if (!response.ok) throw new Error("File not found");
        const data = await response.json();
        
        // Assign to the global variable expected by app-core.js
        window.FUND = data; 
        console.log("Recovery Successful:", Object.keys(data.stocks).length, "stocks loaded.");
        return true;
    } catch (e) {
        console.error("Recovery Failed:", e);
        return false;
    }
}

/** 2. NAVIGATION **/
window.openStock = (sym) => {
    const s = sym.toUpperCase();
    const h = (S.portfolio || []).find(p => p.sym === s) || {};
    // Extract from .stocks sub-object per your JSON structure
    const f = (FUND && FUND.stocks && FUND.stocks[s]) ? FUND.stocks[s] : {};
    
    S.selStock = { ...h, ...f, sym: s };
    S.drillTab = 'overview';
    if (typeof render === 'function') render(); // Uses app-core's render
};

/** 3. THE RENDERER **/
async function renderPortfolio(container) {
    if (!container) return;

    // Show Loading Checklist
    container.innerHTML = `
        <div style="padding:60px 20px; text-align:center; font-family:sans-serif; background:#04060d; min-height:100vh; color:#8b949e;">
            <div style="color:#58a6ff; font-size:18px; font-weight:bold; margin-bottom:15px; font-family:Syne;">BHARATMARKETS PRO</div>
            <div id="check-f" style="margin-bottom:8px;">📡 Loading Fundamentals...</div>
            <div id="check-p" style="opacity:0.5;">⌛ Waiting for Broker Sync...</div>
        </div>`;

    const fundReady = await ensureFundamentals();
    if (fundReady) {
        const fEl = document.getElementById('check-f');
        if (fEl) { fEl.innerText = "✅ Fundamentals Ready"; fEl.style.color = "#3fb950"; }
    }

    // Polling for Portfolio (92 stocks)
    if (window.pfTimer) clearInterval(window.pfTimer);
    window.pfTimer = setInterval(() => {
        const hasPF = (window.S && S.portfolio && S.portfolio.length > 0);
        const pEl = document.getElementById('check-p');
        
        if (hasPF) {
            clearInterval(window.pfTimer);
            drawUI(container);
        } else if (pEl) {
            pEl.style.opacity = "1";
        }
    }, 1000);
}

/** 4. THE UI **/
function drawUI(container) {
    const pfData = S.portfolio.map(h => {
        const s = h.sym.toUpperCase();
        // Handle the specific "stocks" nesting in your fundamentals.json
        const f = (FUND && FUND.stocks && FUND.stocks[s]) ? FUND.stocks[s] : {};
        const ltp = h.ltp || f.ltp || 0;
        const avg = h.avgBuy || 0;
        const pnlP = avg > 0 ? ((ltp - avg) / avg) * 100 : 0;
        return { ...h, ...f, ltp, pnlP, sym: s };
    });

    const totalInv = pfData.reduce((a, r) => a + (r.qty * r.avgBuy), 0);
    const totalCur = pfData.reduce((a, r) => a + (r.qty * r.ltp), 0);
    const netPnlP = totalInv > 0 ? ((totalCur - totalInv) / totalInv) * 100 : 0;

    container.innerHTML = `
    <div style="padding:12px; background:#02040a; min-height:100vh; font-family:'DM Sans', sans-serif; color:#fff;">
        <div style="background:#111d30; padding:20px; border-radius:16px; border:1px solid #1e3350; display:flex; justify-content:space-between; margin-bottom:20px; box-shadow:0 4px 20px rgba(0,0,0,0.5);">
            <div><small style="color:#8b949e; font-size:11px;">INVESTED</small><br><b style="font-size:22px;">₹${(totalInv/100000).toFixed(2)}L</b></div>
            <div style="text-align:right;"><small style="color:#8b949e; font-size:11px;">NET P&L</small><br><b style="font-size:22px; color:${netPnlP >= 0 ? '#3fb950' : '#f85149'}">${netPnlP.toFixed(2)}%</b></div>
        </div>

        <div style="background:#0d1525; border-radius:16px; border:1px solid #1e3350; overflow:hidden;">
            <table style="width:100%; border-collapse:collapse; font-size:14px;">
                <tbody>
                    ${pfData.map(r => `
                    <tr onclick="openStock('${r.sym}')" style="border-bottom:1px solid #1e3350;">
                        <td style="padding:16px 12px;"><b>${r.sym}</b><br><small style="color:#8b949e">${r.sector || 'General'}</small></td>
                        <td style="text-align:center;"><small style="color:#8b949e">ROE</small><br><span style="color:${r.roe > 15 ? '#3fb950' : '#fff'}">${r.roe ? r.roe.toFixed(1)+'%' : '—'}</span></td>
                        <td style="padding:16px 12px; text-align:right;"><span style="color:${r.pnlP >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">${r.pnlP.toFixed(1)}%</span><br><small style="color:#484f58">₹${r.ltp.toFixed(0)}</small></td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>
        <div style="height:100px;"></div>
    </div>`;
}
