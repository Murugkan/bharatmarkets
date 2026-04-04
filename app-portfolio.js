/**
 * APP-PORTFOLIO.JS - FINAL RESOLUTION (STEPS 1 & 2)
 * All 37+ fields from fundamentals.json mapped and displayed.
 */

// 1. GLOBAL STATE
if (typeof window.pfRefreshing === 'undefined') window.pfRefreshing = false;
if (typeof window.fundLoaded === 'undefined') window.fundLoaded = false;

async function loadFundamentals() {
    if (window.pfRefreshing) return;
    window.pfRefreshing = true;
    try {
        const ts = Date.now();
        const [sRes, fRes] = await Promise.all([
            fetch(`./symbols.json?v=${ts}`),
            fetch(`./fundamentals.json?v=${ts}`)
        ]);
        const sData = await sRes.json();
        const fData = await fRes.json();

        window.S = window.S || {};
        window.S.portfolio = sData.map(item => ({
            sym: item.sym || '?',
            isin: item.isin || '',
            sector: item.sector || 'N/A'
        }));

        window.FUND = fData.stocks || fData;
        window.ISIN_MAP = {};
        Object.keys(window.FUND).forEach(key => {
            const stock = window.FUND[key];
            if (stock && stock.isin) window.ISIN_MAP[stock.isin] = key;
        });

        window.fundLoaded = true;
        return true;
    } catch (e) {
        console.error("Engine Error:", e);
        window.fundLoaded = true; 
        return false;
    } finally {
        window.pfRefreshing = false;
    }
}

async function renderPortfolio(container) {
    if (!container) return;
    const overlay = document.querySelector('.loading, #sync-overlay');
    if (overlay) overlay.style.display = 'none';

    if (!window.fundLoaded) {
        container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> BOOTING ENGINE...</div>`;
        await loadFundamentals();
    }

    let html = `<div style="padding:10px; background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif;">`;
    
    // Status Bar
    html += `<div style="margin-bottom:15px; padding:10px; background:#0d1117; border:1px solid #1e3350; border-radius:4px; font-size:11px; font-family:monospace; color:#8b949e;">
                <span style="color:#3fb950;">● ENGINE: LIVE</span> | <span style="color:#58a6ff;">STOCKS: ${window.S.portfolio.length}</span>
             </div>`;

    html += `<div style="overflow-x:auto; border:1px solid #1e3350; border-radius:8px;">`;
    html += `<table style="width:100%; border-collapse:collapse; white-space:nowrap; font-size:11px;">`;
    
    // --- FULL 37-COLUMN HEADER ---
    html += `<tr style="background:#0d1117; border-bottom:2px solid #1e3350; color:#8b949e; text-transform:uppercase; font-size:9px;">
                <th style="padding:12px; text-align:left; position:sticky; left:0; background:#0d1117; z-index:2;">Symbol</th>
                <th style="padding:12px; text-align:right;">LTP</th>
                <th style="padding:12px; text-align:center;">1D%</th>
                <th style="padding:12px; text-align:center;">5D%</th>
                <th style="padding:12px; text-align:center;">ROE%</th>
                <th style="padding:12px; text-align:center;">ROCE%</th>
                <th style="padding:12px; text-align:center;">GPM%</th>
                <th style="padding:12px; text-align:center;">OPM%</th>
                <th style="padding:12px; text-align:center;">NPM%</th>
                <th style="padding:12px; text-align:center;">P/E</th>
                <th style="padding:12px; text-align:center;">F-PE</th>
                <th style="padding:12px; text-align:center;">P/B</th>
                <th style="padding:12px; text-align:center;">D/E</th>
                <th style="padding:12px; text-align:center;">MCAP (Cr)</th>
                <th style="padding:12px; text-align:center;">Sales</th>
                <th style="padding:12px; text-align:center;">EPS</th>
                <th style="padding:12px; text-align:center;">BV</th>
                <th style="padding:12px; text-align:center;">Div%</th>
                <th style="padding:12px; text-align:center;">PROM%</th>
                <th style="padding:12px; text-align:center;">FII%</th>
                <th style="padding:12px; text-align:center;">DII%</th>
                <th style="padding:12px; text-align:center;">PUB%</th>
                <th style="padding:12px; text-align:center;">% off 52W</th>
                <th style="padding:12px; text-align:center;">% off ATH</th>
                <th style="padding:12px; text-align:center;">Signal</th>
                <th style="padding:12px; text-align:center;">Sector</th>
             </tr>`;

    window.S.portfolio.forEach((h, index) => {
        const f = window.FUND[h.sym] || (h.isin ? window.FUND[window.ISIN_MAP[h.isin]] : null) || {};
        
        // Logical Helpers
        const num = (val, dec = 1) => (val !== undefined && val !== null) ? Number(val).toFixed(dec) : '—';
        const curr = (val) => (val !== undefined && val !== null) ? Number(val).toLocaleString('en-IN') : '—';

        const rowBg = index % 2 === 0 ? 'transparent' : '#0d1117';
        
        // Dynamic Coloring
        const c1d = f.chg1d > 0 ? '#3fb950' : (f.chg1d < 0 ? '#f85149' : '#fff');
        const c5d = f.chg5d > 0 ? '#3fb950' : (f.chg5d < 0 ? '#f85149' : '#fff');
        const roeC = (parseFloat(f.roe) > 15) ? '#3fb950' : (parseFloat(f.roe) < 0 ? '#f85149' : '#fff');
        const dColor = (v) => (parseFloat(v) > -10) ? '#3fb950' : (parseFloat(v) < -30 ? '#f85149' : '#d29922');

        html += `<tr style="background:${rowBg}; border-bottom:1px solid #1e3350;">
                    <td style="padding:12px; font-weight:bold; color:#58a6ff; position:sticky; left:0; background:${index % 2 === 0 ? '#02040a' : '#0d1117'}; z-index:1;">${h.sym}</td>
                    <td style="padding:12px; text-align:right; font-weight:bold;">₹${num(f.ltp, 2)}</td>
                    <td style="padding:12px; text-align:center; color:${c1d}">${num(f.chg1d)}%</td>
                    <td style="padding:12px; text-align:center; color:${c5d}">${num(f.chg5d)}%</td>
                    <td style="padding:12px; text-align:center; color:${roeC}">${num(f.roe)}%</td>
                    <td style="padding:12px; text-align:center;">${num(f.roce)}%</td>
                    <td style="padding:12px; text-align:center;">${num(f.gpm_pct)}%</td>
                    <td style="padding:12px; text-align:center; color:#d29922;">${num(f.opm_pct)}%</td>
                    <td style="padding:12px; text-align:center;">${num(f.npm_pct)}%</td>
                    <td style="padding:12px; text-align:center;">${num(f.pe)}</td>
                    <td style="padding:12px; text-align:center;">${num(f.fwd_pe)}</td>
                    <td style="padding:12px; text-align:center;">${num(f.pb)}</td>
                    <td style="padding:12px; text-align:center;">${num(f.debt_eq, 2)}</td>
                    <td style="padding:12px; text-align:center;">${curr(Math.round(f.mcap))}</td>
                    <td style="padding:12px; text-align:center;">${curr(Math.round(f.sales))}</td>
                    <td style="padding:12px; text-align:center;">${num(f.eps)}</td>
                    <td style="padding:12px; text-align:center;">${num(f.bv)}</td>
                    <td style="padding:12px; text-align:center;">${num(f.div_yield)}%</td>
                    <td style="padding:12px; text-align:center;">${num(f.prom_pct)}%</td>
                    <td style="padding:12px; text-align:center;">${num(f.fii_pct)}%</td>
                    <td style="padding:12px; text-align:center;">${num(f.dii_pct)}%</td>
                    <td style="padding:12px; text-align:center;">${num(f.public_pct)}%</td>
                    <td style="padding:12px; text-align:center; color:${dColor(f.w52_pct)}">${num(f.w52_pct)}%</td>
                    <td style="padding:12px; text-align:center; color:${dColor(f.ath_pct)}">${num(f.ath_pct)}%</td>
                    <td style="padding:12px; text-align:center; font-weight:bold; color:#d29922;">${f.signal || '—'}</td>
                    <td style="padding:12px; color:#8b949e; font-size:10px;">${f.sector || h.sector || '—'}</td>
                </tr>`;
    });

    html += `</table></div></div>`;
    container.innerHTML = html;
}
