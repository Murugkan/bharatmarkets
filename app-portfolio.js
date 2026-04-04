/**
 * APP-PORTFOLIO.JS - MASTER MODULE v3.1
 * FULL RESOLUTION: STAGES 1, 2, & 3 COMPLETE
 */

// 1. GLOBAL STATE
window.pfRefreshing = false;
window.fundLoaded = false;
window.currentSort = { key: 'mcap', dir: 'desc' };

/**
 * STAGE 1: THE DATA ENGINE
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
        return true;
    } catch (e) {
        console.error("Sync Error:", e);
        window.fundLoaded = true; 
        return false;
    } finally {
        window.pfRefreshing = false;
    }
}

/**
 * STAGE 2 & 3: COLOR & FORMATTING LOGIC
 */
function getFormat(key, val, sector = "") {
    const n = parseFloat(val);
    if (isNaN(n) || val === null) return { text: '—', color: '#8b949e' };

    let color = '#fff';
    // Color Logic for Fields
    if (['roe', 'roce'].includes(key)) color = n > 18 ? '#3fb950' : (n < 8 ? '#f85149' : '#d29922');
    if (key === 'debt_eq') {
        const isFin = sector.includes('Bank') || sector.includes('NBFC') || sector.includes('Finance');
        color = isFin ? '#8b949e' : (n < 0.6 ? '#3fb950' : (n > 1.4 ? '#f85149' : '#d29922'));
    }
    if (['chg1d', 'chg5d'].includes(key)) color = n > 0 ? '#3fb950' : (n < 0 ? '#f85149' : '#fff');
    if (['ath_pct', 'w52_pct'].includes(key)) color = n > -10 ? '#3fb950' : (n < -35 ? '#f85149' : '#d29922');
    if (key === 'pe') color = n < 20 ? '#3fb950' : (n > 60 ? '#f85149' : '#fff');

    // Display Formatting
    let display = n.toFixed(1);
    if (['ltp', 'mcap', 'sales', 'ebitda', 'cfo', 'bv', 'ath', 'w52h', 'w52l'].includes(key)) {
        display = Math.round(n).toLocaleString('en-IN');
    } else if (['roe', 'roce', 'opm_pct', 'npm_pct', 'gpm_pct', 'chg1d', 'chg5d', 'ath_pct', 'w52_pct', 'prom_pct', 'fii_pct', 'dii_pct', 'public_pct', 'yf_insider_pct'].includes(key)) {
        display += '%';
    }
    
    return { text: display, color };
}

/**
 * INTERACTIVE SORTING
 */
function handleSort(key) {
    const dir = (window.currentSort.key === key && window.currentSort.dir === 'desc') ? 'asc' : 'desc';
    window.currentSort = { key, dir };
    
    window.S.portfolio.sort((a, b) => {
        const dataA = window.FUND[a.sym] || window.FUND[window.ISIN_MAP[a.isin]] || {};
        const dataB = window.FUND[b.sym] || window.FUND[window.ISIN_MAP[b.isin]] || {};
        const vA = dataA[key] ?? -999999;
        const vB = dataB[key] ?? -999999;
        return dir === 'desc' ? vB - vA : vA - vB;
    });
    renderPortfolio(document.getElementById('portfolio-container'));
}

/**
 * THE RENDER ENGINE (ALL 33+ COLUMNS)
 */
async function renderPortfolio(container) {
    if (!container) return;
    if (!window.fundLoaded) {
        container.innerHTML = `<div style="padding:60px; color:#58a6ff; font-family:monospace; text-align:center;">[ LOADING ENGINE... ]</div>`;
        await loadFundamentals();
    }

    let html = `<div style="background:#02040a; min-height:100vh; color:#fff; font-family:-apple-system, sans-serif; padding:10px;">`;
    
    // Header Info
    html += `<div style="display:flex; justify-content:space-between; padding:10px; background:#0d1117; border:1px solid #30363d; border-radius:8px; margin-bottom:12px; font-size:10px;">
                <div style="color:#8b949e;">TOTAL STOCKS: <span style="color:#fff;">${window.S.portfolio.length}</span></div>
                <div style="color:#3fb950;">● ENGINE READY</div>
             </div>`;

    html += `<div style="overflow-x:auto; border:1px solid #30363d; border-radius:8px; background:#0d1117;">`;
    html += `<table style="width:100%; border-collapse:collapse; white-space:nowrap; font-size:11px;">`;
    
    // --- FULL 33-COLUMN DEFINITION ---
    const cols = [
        { l: 'Symbol', k: 'sym', a: 'left', sticky: true },
        { l: 'Price', k: 'ltp', a: 'right' },
        { l: '1D%', k: 'chg1d', a: 'center' },
        { l: '5D%', k: 'chg5d', a: 'center' },
        { l: 'ROE%', k: 'roe', a: 'center' },
        { l: 'ROCE%', k: 'roce', a: 'center' },
        { l: 'GPM%', k: 'gpm_pct', a: 'center' },
        { l: 'OPM%', k: 'opm_pct', a: 'center' },
        { l: 'NPM%', k: 'npm_pct', a: 'center' },
        { l: 'P/E', k: 'pe', a: 'center' },
        { l: 'F-PE', k: 'fwd_pe', a: 'center' },
        { l: 'P/B', k: 'pb', a: 'center' },
        { l: 'EPS', k: 'eps', a: 'center' },
        { l: 'BV', k: 'bv', a: 'center' },
        { l: 'D/E', k: 'debt_eq', a: 'center' },
        { l: 'MCAP(Cr)', k: 'mcap', a: 'center' },
        { l: 'Sales', k: 'sales', a: 'center' },
        { l: 'EBITDA', k: 'ebitda', a: 'center' },
        { l: 'CFO', k: 'cfo', a: 'center' },
        { l: 'Div%', k: 'div_yield', a: 'center' },
        { l: 'Beta', k: 'beta', a: 'center' },
        { l: 'PROM%', k: 'prom_pct', a: 'center' },
        { l: 'FII%', k: 'fii_pct', a: 'center' },
        { l: 'DII%', k: 'dii_pct', a: 'center' },
        { l: 'PUB%', k: 'public_pct', a: 'center' },
        { l: 'Insdr%', k: 'yf_insider_pct', a: 'center' },
        { l: '% off 52W', k: 'w52_pct', a: 'center' },
        { l: '% off ATH', k: 'ath_pct', a: 'center' },
        { l: '52W H', k: 'w52h', a: 'center' },
        { l: '52W L', k: 'w52l', a: 'center' },
        { l: 'ATH', k: 'ath', a: 'center' },
        { l: 'Signal', k: 'signal', a: 'center' },
        { l: 'Pos/Neg', k: 'pos', a: 'center' }
    ];

    // Header Generator
    html += `<tr style="border-bottom:2px solid #30363d; background:#161b22;">`;
    cols.forEach(c => {
        const arrow = window.currentSort.key === c.k ? (window.currentSort.dir === 'desc' ? ' ↓' : ' ↑') : '';
        html += `<th onclick="handleSort('${c.k}')" style="padding:14px 12px; text-align:${c.a}; color:#8b949e; cursor:pointer; font-size:9px; text-transform:uppercase; ${c.sticky ? 'position:sticky; left:0; background:#161b22; z-index:10;' : ''}">
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
            const fm = getFormat(c.k, f[c.k], f.sector || stock.sector);
            const isSym = c.k === 'sym';
            
            // Logic for Specific Columns
            let cellContent = fm.text;
            if (c.k === 'pos') {
                cellContent = `<span style="color:#3fb950">${f.pos||0}P</span> / <span style="color:#f85149">${f.neg||0}N</span>`;
            } else if (c.k === 'signal') {
                cellContent = f.signal || '—';
            }

            html += `<td style="padding:14px 12px; text-align:${c.a}; color:${fm.color}; ${isSym ? 'font-weight:bold; color:#58a6ff; position:sticky; left:0; background:'+bg+'; z-index:5;' : ''}">
                        ${isSym ? stock.sym : cellContent}
                    </td>`;
        });
        html += `</tr>`;
    });

    html += `</table></div></div>`;
    container.innerHTML = html;
}
