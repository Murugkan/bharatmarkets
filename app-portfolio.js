// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - MOBILE DEBUG EDITION (v5.6)
// ─────────────────────────────────────────────────────────────

const PF_UTILS = {
    // Corrects for GitHub Pages subfolder issues
    getCorrectPath: (file) => {
        const isGH = window.location.hostname.includes('github.io');
        if (isGH) {
            const repo = window.location.pathname.split('/')[1];
            return `/${repo}/${file}`;
        }
        return file;
    },
    
    // Exact mapping for your fundamentals.json 'stocks' key
    getFundData: (ticker) => {
        if (!ticker) return {};
        const s = ticker.toUpperCase();
        const aliases = { "AFCONSINFRAS": "AFCONS", "TATA MOTORS": "TATAMOTORS" };
        const target = aliases[s] || s;
        const source = (window._FUND && _FUND.stocks) ? _FUND.stocks : {};
        return source[target] || {};
    }
};

// 1. THE DATA LOADER (With explicit error reporting for iPhone)
async function fetchFundamentals() {
    const logEl = document.getElementById('pf-status');
    const path = PF_UTILS.getCorrectPath('fundamentals.json');
    
    try {
        if (logEl) logEl.innerText = `Fetching: ${path}...`;
        
        const response = await fetch(path);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        window._FUND = await response.json();
        return true;
    } catch (e) {
        if (logEl) {
            logEl.style.color = '#ff6b85';
            logEl.innerText = `Data Error: ${e.message}\nPath: ${path}`;
        }
        console.error("Load failed:", e);
        return false;
    }
}

// 2. THE RENDERER
async function renderPortfolio(container) {
    if (!container) return;

    // Loading State with visible logs for you to read on phone
    container.innerHTML = `
        <div style="padding:60px 20px; text-align:center; font-family:monospace; background:#0d1117; min-height:100vh; color:#8b949e;">
            <div style="color:#58a6ff; font-size:16px; margin-bottom:15px;">BHARATMARKETS CORE</div>
            <div id="pf-status" style="font-size:12px; line-height:1.6;">Starting sync...</div>
            <div id="pf-portfolio-status" style="font-size:10px; margin-top:10px;">Checking Portfolio Array...</div>
        </div>`;

    const fundSuccess = await fetchFundamentals();
    
    if (window.pfTimer) clearInterval(window.pfTimer);
    
    window.pfTimer = setInterval(() => {
        const hasPF = (window.S && S.portfolio && S.portfolio.length > 0);
        const pStat = document.getElementById('pf-portfolio-status');
        
        if (pStat) {
            pStat.innerText = hasPF ? `Portfolio found: ${S.portfolio.length} items` : "Still waiting for broker data (S.portfolio)...";
        }

        if (hasPF && fundSuccess) {
            clearInterval(window.pfTimer);
            renderTableUI(container);
        }
    }, 1000);
}

// 3. THE UI
function renderTableUI(container) {
    const pf = S.portfolio.map(h => {
        const f = PF_UTILS.getFundData(h.sym);
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
                    <tr onclick="openPortfolioStock('${r.sym}')" style="border-bottom:1px solid #30363d;">
                        <td style="padding:14px 12px;"><b>${r.sym}</b><br><small style="color:${r.signal==='BUY'?'#3fb950':'#8b949e'}">${r.signal||'HOLD'}</small></td>
                        <td style="text-align:center;"><small style="color:#8b949e">ROE</small><br><span style="color:${r.roe > 15 ? '#3fb950' : '#fff'}">${r.roe ? r.roe.toFixed(1)+'%' : '—'}</span></td>
                        <td style="padding:14px 12px; text-align:right;"><span style="color:${r.pnlP >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">${r.pnlP.toFixed(1)}%</span><br><small style="color:#484f58">₹${(r.ltp||0).toFixed(0)}</small></td>
                    </tr>`).join('')}
                </tbody>
            </table>
        </div>
    </div>`;
}

window.openPortfolioStock = (sym) => {
    const h = (S.portfolio || []).find(p => p.sym === sym) || {};
    const f = PF_UTILS.getFundData(sym);
    S.selStock = { ...h, ...f, sym };
    S.drillTab = 'overview';
    if (typeof showTab === 'function') showTab('drill');
};
