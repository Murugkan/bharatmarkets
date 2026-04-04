/**
 * APP-PORTFOLIO.JS - THE COMPLETE MASTER MODULE (STAGES 1, 2, & 3)
 * Full Parity with Old Table: 33+ Fields, Split Pos/Neg, Sorting, Colors, & Totals.
 */

// --- 1. GLOBAL STATE & CONFIG ---
window.currentSort = { key: 'mcap', dir: 'desc' };
window.fundLoaded = false;
window.pfRefreshing = false;

/**
 * STAGE 1: THE DATA ENGINE
 * Simultaneous Fetching & ISIN Bridging
 */
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

        // Map Symbols
        window.S = { portfolio: sData.map(item => ({
            sym: item.sym || '?',
            isin: item.isin || '',
            sector: item.sector || 'N/A'
        }))};

        // Map Fundamentals
        window.FUND = fData.stocks || fData;
        window.ISIN_MAP = {};
        Object.keys(window.FUND).forEach(key => {
            const stock = window.FUND[key];
            if (stock && stock.isin) window.ISIN_MAP[stock.isin] = key;
        });

        window.fundLoaded = true;
        return true;
    } catch (e) {
        console.error("Engine Sync Error:", e);
        window.fundLoaded = true; 
        return false;
    } finally {
        window.pfRefreshing = false;
    }
}

/**
 * STAGE 3: THE STYLE & COLOR ENGINE
 * Benchmarks for Industry-Standard Fundamental Analysis
 */
function getCellStyle(key, val, sector = "") {
    const n = parseFloat(val);
    if (isNaN(n) || val === null) return { text: '—', color: '#8b949e' };

    let color = '#fff';
    const isFin = /Bank|NBFC|Finance|Insurance/i.test(sector);

    // Color Logic
    if (['roe', 'roce'].includes(key)) color = n > 18 ? '#3fb950' : (n < 10 ? '#f85149' : '#d29922');
    if (key === 'debt_eq') color = isFin ? '#8b949e' : (n < 0.5 ? '#3fb950' : (n > 1.5 ? '#f85149' : '#d29922'));
    if (['chg1d', 'chg5d'].includes(key)) color = n > 0 ? '#3fb950' : (n < 0 ? '#f85149' : '#fff');
    if (key === 'pe') color = n < 18 ? '#3fb950' : (n > 55 ? '#f85149' : '#fff');
    if (['ath_pct', 'w52_pct'].includes(key)) color = n > -10 ? '#3fb950' : (n < -35 ? '#f85149' : '#d29922');
    if (key === 'pos') color = n >= 4 ? '#3fb950' : '#fff';
    if (key === 'neg') color = n > 0 ? '#f85149' : '#8b949e';

    // Formatting Logic
    let display = n.toFixed(1);
    if (['ltp', 'mcap', 'sales', 'cfo', 'ebitda', 'bv', 'ath'].includes(key)) {
        display = Math.round(n).toLocaleString('en-IN');
    } else if (['roe', 'roce', 'opm_pct', 'npm_pct', 'chg1d', 'ath_pct', 'prom_pct'].includes(key)) {
        display += '%';
    } else if (key === 'pos' || key === 'neg') {
        display = Math.round(n);
    }

    return { text: display, color };
}

/**
 * STAGE 3: INTERACTIVE SORTING
 */
function handleSort(key) {
    const dir = (window.currentSort.key === key && window.currentSort.dir === 'desc') ? 'asc' : 'desc';
    window.currentSort = { key, dir };
    
    window.S.portfolio.sort((a, b) => {
        const dA = window.FUND[a.sym] || window.FUND[window.ISIN_MAP[a.isin]] || {};
        const dB = window.FUND[b.sym] || window.FUND[window.ISIN_MAP[b.isin]] || {};
        const vA = dA[key] ?? -999999;
        const vB = dB[key] ?? -999999;
        return dir === 'desc' ? vB - vA : vA - vB;
    });
    renderPortfolio(document.getElementById('portfolio-container'));
}

/**
 * STAGE 2 & 3: THE MAIN RENDER ENGINE
 */
async function renderPortfolio(container) {
    if (!container) return;
    if (!window.fundLoaded) {
        container.innerHTML = `<div style="padding:60px; color:#58a6ff; font-family:monospace; text-align:center;">[ BOOTING_ENGINE ]</div>`;
        await loadFundamentals();
    }

    // 1. Calculate Grand Totals
    let totalMcap = 0, totalCfo = 0;
    window.S.portfolio.forEach(s => {
        const f = window.FUND[s.sym] || window.FUND[window.ISIN_MAP[s.isin]] || {};
        totalMcap += parseFloat(f.mcap || 0);
        totalCfo += parseFloat(f.cfo || 0);
    });

    let html = `<div style="background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif; padding:10px;">`;
    
    // 2. Main Table
    html += `<div style="overflow-x:auto; border:1px solid #30363d; border-radius:8px; background:#0d1117; margin-bottom:70px;">`;
    html += `<table style="width:100%; border-collapse:collapse; white-space:nowrap; font-size:11px;">`;
    
    // --- FULL 33-COLUMN DEFINITION ---
    const cols = [
        { l: 'Symbol', k: 'sym', a: 'left', s: true },
        { l: 'Price', k: 'ltp', a: 'right' },
        { l: '1D%', k: 'chg1d', a: 'center' },
        { l: '5D%', k: 'chg5d', a: 'center' },
        { l: 'Pos', k: 'pos', a: 'center' }, // Split Column 1
        { l: 'Neg', k: 'neg', a: 'center' }, // Split Column 2
        { l: 'ROE%', k: 'roe', a: 'center' },
        { l: 'ROCE%', k: 'roce', a: 'center' },
        { l: 'OPM%', k: 'opm_pct', a: 'center' },
        { l: 'NPM%', k: 'npm_pct', a: 'center' },
        { l: 'P/E', k: 'pe', a: 'center' },
        { l: 'F-PE', k: 'fwd_pe', a: 'center' },
        { l: 'P/B', k: 'pb', a: 'center' },
        { l: 'D/E', k: 'debt_eq', a: 'center' },
        { l: 'MCAP', k: 'mcap', a: 'center' },
        { l: 'Sales', k: 'sales', a: 'center' },
        { l: 'CFO', k: 'cfo', a: 'center' },
        { l: 'EPS', k: 'eps', a: 'center' },
        { l: 'BV', k: 'bv', a: 'center' },
        { l: 'FII%', k: 'fii_pct', a: 'center' },
        { l: 'DII%', k: 'dii_pct', a: 'center' },
        { l: 'PROM%', k: 'prom_pct', a: 'center' },
        { l: 'ATH%', k: 'ath_pct', a: 'center' },
        { l: 'Signal', k: 'signal', a: 'center' }
    ];

    // Header Generator (with sorting on ALL fields)
    html += `<tr style="background:#161b22; border-bottom:2px solid #30363d;">`;
    cols.forEach(c => {
        const arrow = window.currentSort.key === c.k ? (window.currentSort.dir === 'desc' ? ' ↓' : ' ↑') : '';
        html += `<th onclick="handleSort('${c.k}')" style="padding:14px 12px; text-align:${c.a}; color:#8b949e; cursor:pointer; font-size:9px; text-transform:uppercase; ${c.s ? 'position:sticky; left:0; background:#161b22; z-index:10;' : ''}">
                    ${c.l}${arrow}
                 </th>`;
    });
    html += `</tr>`;

    // Data Row Generator
    window.S.portfolio.forEach((stock, idx) => {
        const f = window.FUND[stock.sym] || window.FUND[window.ISIN_MAP[stock.isin]] || {};
        const bg = idx % 2 === 0 ? '#0d1117' : '#161b22';
        
        html += `<tr style="background:${bg}; border-bottom:1px solid #21262d;" onclick="window.location.href='stock.html?s=${stock.sym}'">`;
        cols.forEach(c => {
            const fm = getCellStyle(c.k, f[c.k], f.sector);
            const isSym = c.k === 'sym';
            html += `<td style="padding:14px 12px; text-align:${c.a}; color:${fm.color}; ${isSym ? 'font-weight:bold; color:#58a6ff; position:sticky; left:0; background:'+bg+';' : ''}">
                        ${isSym ? stock.sym : (c.k === 'signal' ? (f.signal || '—') : fm.text)}
                    </td>`;
        });
        html += `</tr>`;
    });

    html += `</table></div>`;

    // 3. Floating Grand Total Footer (Fixed to Bottom)
    html += `<div style="position:fixed; bottom:0; left:0; right:0; background:#0d1117; border-top:2px solid #30363d; padding:15px; display:flex; justify-content:space-around; font-size:11px; z-index:100; box-shadow: 0 -5px 15px rgba(0,0,0,0.5);">
                <div><span style="color:#8b949e;">MCAP TOTAL:</span> <span style="color:#58a6ff; font-weight:bold;">₹${Math.round(totalMcap).toLocaleString('en-IN')} Cr</span></div>
                <div><span style="color:#8b949e;">CFO TOTAL:</span> <span style="color:#3fb950; font-weight:bold;">₹${Math.round(totalCfo).toLocaleString('en-IN')} Cr</span></div>
             </div>`;

    html += `</div>`;
    container.innerHTML = html;
}
