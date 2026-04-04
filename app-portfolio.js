// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - GITHUB PRODUCTION (v5.5)
// ─────────────────────────────────────────────────────────────

const BHARAT_CONFIG = {
    // Exact mapping for your fundamentals.json 'stocks' key
    getData: (ticker) => {
        if (!ticker) return {};
        const s = ticker.toUpperCase();
        const aliases = { "AFCONSINFRAS": "AFCONS", "TATA MOTORS": "TATAMOTORS" };
        const target = aliases[s] || s;
        
        // Prioritize the freshly fetched _FUND object
        const source = (window._FUND && _FUND.stocks) ? _FUND.stocks : {};
        return source[target] || {};
    }
};

// 1. THE LOADER (Fetches the JSON file directly)
async function loadBharatData() {
    try {
        // Fetching directly from your GitHub path to bypass global variable issues
        const response = await fetch('fundamentals.json');
        if (!response.ok) throw new Error('Network response was not ok');
        window._FUND = await response.json();
        console.log("Fundamentals Loaded:", _FUND.count, "stocks");
        return true;
    } catch (e) {
        console.error("Failed to load fundamentals.json:", e);
        return false;
    }
}

// 2. THE RENDERER
async function renderPortfolio(container) {
    if (!container) return;

    // Loading Screen
    container.innerHTML = `
        <div style="padding:60px 20px; text-align:center; font-family:sans-serif; background:#0d1117; min-height:100vh;">
            <div style="color:#58a6ff; font-size:18px; font-weight:bold; margin-bottom:10px;">BharatMarkets Pro</div>
            <div id="pf-status" style="color:#8b949e; font-size:12px;">Initializing Market Data...</div>
        </div>`;

    // Step 1: Load Fundamentals
    const fundLoaded = await loadBharatData();
    
    // Step 2: Wait for Portfolio State (S.portfolio)
    if (window.pfTimer) clearInterval(window.pfTimer);
    
    window.pfTimer = setInterval(() => {
        const hasPF = (window.S && S.portfolio && S.portfolio.length > 0);
        const statusEl = document.getElementById('pf-status');
        
        if (statusEl) {
            statusEl.innerText = `Portfolio: ${hasPF?'Ready':'Waiting'} | Data: ${fundLoaded?'Ready':'Error'}`;
        }

        if (hasPF) {
            clearInterval(window.pfTimer);
            renderFinalUI(container);
        }
    }, 800);
}

// 3. THE UI
function renderFinalUI(container) {
    const pf = S.portfolio.map(h => {
        const f = BHARAT_CONFIG.getData(h.sym);
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
            <div>
                <div style="color:#8b949e; font-size:11px; text-transform:uppercase;">Invested</div>
                <div style="font-size:22px; font-weight:bold; margin-top:4px;">₹${(totalInv/100000).toFixed(2)}L</div>
            </div>
            <div style="text-align:right;">
                <div style="color:#8b949e; font-size:11px; text-transform:uppercase;">Returns</div>
                <div style="font-size:22px; font-weight:bold; margin-top:4px; color:${netPnlP >= 0 ? '#3fb950' : '#f85149'}">${netPnlP.toFixed(2)}%</div>
            </div>
        </div>

        <div style="background:#161b22; border-radius:12px; border:1px solid #30363d; overflow:hidden;">
            <table style="width:100%; border-collapse:collapse; font-size:14px;">
                <tbody>
                    ${pf.map(r => `
                    <tr onclick="openPortfolioStock('${r.sym}')" style="border-bottom:1px solid #30363d;">
                        <td style="padding:14px 12px;">
                            <div style="font-weight:bold;">${r.sym}</div>
                            <div style="font-size:10px; color:${r.signal === 'BUY' ? '#3fb950' : '#8b949e'}">${r.signal || 'HOLD'}</div>
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
        <div style="text-align:center; padding:20px; color:#484f58; font-size:10px;">
            Updated: ${window._FUND ? _FUND.updated.split('T')[0] : '--'}
        </div>
        <div style="height:80px;"></div>
    </div>`;
}

// 4. NAVIGATION
window.openPortfolioStock = (sym) => {
    const h = (S.portfolio || []).find(p => p.sym === sym) || {};
    const f = BHARAT_CONFIG.getData(sym);
    S.selStock = { ...h, ...f, sym };
    S.drillTab = 'overview';
    if (typeof showTab === 'function') showTab('drill');
};
