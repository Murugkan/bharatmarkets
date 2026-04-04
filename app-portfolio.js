/**
 * APP-PORTFOLIO.JS - THE FINAL RESOLUTION (STAGES 1, 2, & 3)
 * Logic: Multi-source Sync, 38-Field Mapping, Dynamic Scoring, & Interactive Sorting
 */

// 1. GLOBAL STATE & CONFIG
window.pfRefreshing = false;
window.fundLoaded = false;
window.currentSort = { key: 'mcap', dir: 'desc' }; // Default: Biggest companies first

/**
 * STAGE 1: THE ENGINE
 * Fetches and bridges Symbols + Fundamentals
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
        
        if (!sRes.ok || !fRes.ok) throw new Error("Sync Failed");
        
        const sData = await sRes.json();
        const fData = await fRes.json();

        window.S = { portfolio: sData.map(item => ({
            sym: item.sym || '?',
            isin: item.isin || '',
            sector: item.sector || 'N/A'
        }))};

        window.FUND = fData.stocks || fData;
        window.ISIN_MAP = {};
        Object.keys(window.FUND).forEach(key => {
            const stock = window.FUND[key];
            if (stock && stock.isin) window.ISIN_MAP[stock.isin] = key;
        });

        window.fundLoaded = true;
        console.log("🚀 Engine Sync: 100%");
        return true;
    } catch (e) {
        console.error("Engine Critical Error:", e);
        window.fundLoaded = true; 
        return false;
    } finally {
        window.pfRefreshing = false;
    }
}

/**
 * STAGE 3 Logic: THE COLOR & SCORING ENGINE
 * Evaluates raw data against fundamental benchmarks
 */
function getFormat(key, val, sector = "") {
    const n = parseFloat(val);
    if (isNaN(n) || val === null) return { text: '—', color: '#8b949e' };

    let color = '#fff';
    switch(key) {
        case 'roe': case 'roce': 
            color = n > 18 ? '#3fb950' : (n < 8 ? '#f85149' : '#d29922');
            break;
        case 'debt_eq':
            if (sector.includes('Bank') || sector.includes('NBFC') || sector.includes('Finance')) {
                color = '#8b949e'; // Leverage is a business model for Finance
            } else {
                color = n < 0.6 ? '#3fb950' : (n > 1.4 ? '#f85149' : '#d29922');
            }
            break;
        case 'chg1d': case 'chg5d':
            color = n > 0 ? '#3fb950' : (n < 0 ? '#f85149' : '#fff');
            break;
        case 'ath_pct': case 'w52_pct':
            color = n > -10 ? '#3fb950' : (n < -30 ? '#f85149' : '#d29922');
            break;
        case 'pe':
            color = n < 20 ? '#3fb950' : (n > 55 ? '#f85149' : '#fff');
            break;
    }
    
    // Formatting numbers
    let display = n.toFixed(1);
    if (key === 'ltp' || key === 'mcap' || key === 'sales') {
        display = Math.round(n).toLocaleString('en-IN');
    } else if (['roe', 'roce', 'opm_pct', 'chg1d', 'chg5d', 'ath_pct'].includes(key)) {
        display += '%';
    }
    
    return { text: display, color };
}

/**
 * INTERACTIVE LAYER: SORTING
 */
function handleSort(key) {
    const dir = (window.currentSort.key === key && window.currentSort.dir === 'desc') ? 'asc' : 'desc';
    window.currentSort = { key, dir };
    
    window.S.portfolio.sort((a, b) => {
        const getVal = (obj) => {
            const data = window.FUND[obj.sym] || window.FUND[window.ISIN_MAP[obj.isin]] || {};
            return data[key] ?? -999999;
        };
        const valA = getVal(a);
        const valB = getVal(b);
        return dir === 'desc' ? valB - valA : valA - valB;
    });
    renderPortfolio(document.getElementById('portfolio-container'));
}

/**
 * STAGE 2 & 3: THE RENDER ENGINE
 */
async function renderPortfolio(container) {
    if (!container) return;
    if (!window.fundLoaded) {
        container.innerHTML = `<div style="padding:60px 20px; color:#58a6ff; font-family:monospace; text-align:center;">[ BOOTING_PORTFOLIO_ENGINE ]</div>`;
        await loadFundamentals();
    }

    let html = `<div style="background:#02040a; min-height:100vh; color:#fff; font-family:-apple-system, sans-serif; padding:10px;">`;
    
    // Header Stats Bar
    html += `<div style="display:flex; justify-content:space-between; padding:10px; background:#0d1117; border:1px solid #30363d; border-radius:8px; margin-bottom:12px; font-size:11px;">
                <div style="color:#8b949e;">STOCKS: <span style="color:#fff;">${window.S.portfolio.length}</span></div>
                <div style="color:#8b949e;">SORT: <span style="color:#58a6ff; text-transform:uppercase;">${window.currentSort.key} (${window.currentSort.dir})</span></div>
             </div>`;

    // Table Container
    html += `<div style="overflow-x:auto; border:1px solid #30363d; border-radius:8px; background:#0d1117;">`;
    html += `<table style="width:100%; border-collapse:collapse; white-space:nowrap; font-size:12px;">`;
    
    // Configurable Headers
    const cols = [
        { l: 'Symbol', k: 'sym', a: 'left', sticky: true },
        { l: 'Price', k: 'ltp', a: 'right' },
        { l: '1D%', k: 'chg1d', a: 'center' },
        { l: '5D%', k: 'chg5d', a: 'center' },
        { l: 'ROE%', k: 'roe', a: 'center' },
        { l: 'OPM%', k: 'opm_pct', a: 'center' },
        { l: 'P/E', k: 'pe', a: 'center' },
        { l: 'D/E', k: 'debt_eq', a: 'center' },
        { l: 'MCAP(Cr)', k: 'mcap', a: 'center' },
        { l: '% off ATH', k: 'ath_pct', a: 'center' },
        { l: 'Signal', k: 'signal', a: 'center' }
    ];

    html += `<tr style="border-bottom:2px solid #30363d; background:#161b22;">`;
    cols.forEach(c => {
        const arrow = window.currentSort.key === c.k ? (window.currentSort.dir === 'desc' ? ' ↓' : ' ↑') : '';
        html += `<th onclick="handleSort('${c.k}')" style="padding:14px 12px; text-align:${c.a}; color:#8b949e; cursor:pointer; font-size:10px; text-transform:uppercase; ${c.sticky ? 'position:sticky; left:0; background:#161b22; z-index:10;' : ''}">
                    ${c.l}${arrow}
                 </th>`;
    });
    html += `</tr>`;

    // Data Rows
    window.S.portfolio.forEach((stock, idx) => {
        const f = window.FUND[stock.sym] || window.FUND[window.ISIN_MAP[stock.isin]] || {};
        const bg = idx % 2 === 0 ? '#0d1117' : '#161b22';
        
        // On-the-fly Scoring for Step 3 Indicator
        let pos = 0;
        if (f.roe > 20) pos++; if (f.opm_pct > 25) pos++; if (f.debt_eq < 0.5) pos++;

        html += `<tr style="background:${bg}; border-bottom:1px solid #21262d;" onclick="window.location.href='stock.html?s=${stock.sym}'">`;
        
        cols.forEach(c => {
            const fm = getFormat(c.k, f[c.k], f.sector || stock.sector);
            const isSym = c.k === 'sym';
            
            html += `<td style="padding:14px 12px; text-align:${c.a}; color:${fm.color}; ${isSym ? 'font-weight:bold; color:#58a6ff; position:sticky; left:0; background:'+bg+'; z-index:5;' : ''}">
                        ${isSym ? stock.sym : (c.k === 'signal' ? (f.signal || '—') : fm.text)}
                        ${isSym && pos >= 2 ? '<span style="color:#238636; font-size:8px; margin-left:4px;">★</span>' : ''}
                    </td>`;
        });
        
        html += `</tr>`;
    });

    html += `</table></div></div>`;
    container.innerHTML = html;
}
