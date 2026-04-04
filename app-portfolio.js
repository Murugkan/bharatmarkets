/**
 * APP-PORTFOLIO.JS - V4.3 (FULL PRODUCTION MODULE)
 * 100% Data Sync: changePct, opm, npm, pe, mcap, etc.
 * Features: Multi-column Sort, Grand Totals, Sticky Headers, Color-Coding.
 */

// --- GLOBAL STATE & CONFIG ---
window.currentSort = { key: 'mcap', dir: 'desc' };
window.fundLoaded = false;
window.pfRefreshing = false;

/**
 * STAGE 1: DATA ENGINE
 * Merges holdings (symbols.json) with market data (fundamentals.json)
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

        // Standardize holdings: Handles 'sym' or 'SYMBOL'
        window.S = { portfolio: sData.map(item => ({
            sym: (item.sym || item.SYMBOL || "?").toUpperCase().trim(),
            qty: parseFloat(item.qty || item.QTY || 0),
            avg: parseFloat(item.avg || item.AVG || 0)
        }))};

        // Standardize Market Data
        window.FUND = fData.stocks || fData;

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
 * STAGE 2: UNIVERSAL SORTING ENGINE
 * Maps UI keys to JSON keys (e.g., 1D% -> changePct)
 */
function handleSort(key) {
    const dir = (window.currentSort.key === key && window.currentSort.dir === 'desc') ? 'asc' : 'desc';
    window.currentSort = { key, dir };
    
    window.S.portfolio.sort((a, b) => {
        const fA = window.FUND[a.sym] || {};
        const fB = window.FUND[b.sym] || {};
        
        const getVal = (obj, f) => {
            // Priority 1: Calculated Fields
            if (key === 'invested') return obj.qty * obj.avg;
            if (key === 'pnl') return (obj.qty * (f.ltp || 0)) - (obj.qty * obj.avg);
            // Priority 2: Direct Holding Props
            if (obj[key] !== undefined) return obj[key];
            // Priority 3: Market Data Props
            return f[key] ?? -999999999;
        };

        const vA = getVal(a, fA);
        const vB = getVal(b, fB);
        return dir === 'desc' ? vB - vA : vA - vB;
    });
    renderPortfolio(document.getElementById('portfolio-container'));
}

/**
 * STAGE 3: COLOR & FORMATTING
 */
function getCellStyle(k, v) {
    const n = parseFloat(v);
    if (isNaN(n) || v === null) return { text: '—', color: '#8b949e' };
    
    let color = '#fff';
    if (['roe', 'roce'].includes(k)) color = n > 15 ? '#3fb950' : (n < 8 ? '#f85149' : '#d29922');
    if (['pnl', 'changePct'].includes(k)) color = n > 0 ? '#3fb950' : (n < 0 ? '#f85149' : '#fff');
    if (k === 'pos') color = n >= 4 ? '#3fb950' : '#fff';
    if (k === 'neg') color = n > 0 ? '#f85149' : '#8b949e';

    let display = n.toLocaleString('en-IN', { maximumFractionDigits: 1 });
    // Append % to specific financial ratios
    if (['roe', 'roce', 'opm', 'npm', 'changePct', 'ath_pct', 'prom_pct', 'fii_pct'].includes(k)) {
        display += '%';
    }
    return { text: display, color };
}

/**
 * STAGE 4: RENDER ENGINE
 */
async function renderPortfolio(container) {
    if (!container) return;
    if (!window.fundLoaded) await loadFundamentals();

    let gInv = 0, gPnl = 0;
    let html = `<div style="background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif; padding:10px;">`;
    
    // Main Table Container
    html += `<div style="overflow-x:auto; border:1px solid #30363d; border-radius:8px; background:#0d1117; margin-bottom:85px;">`;
    html += `<table style="width:100%; border-collapse:collapse; white-space:nowrap; font-size:10px;">`;
    
    // --- COLUMN DEFINITIONS (Matches your exact required order) ---
    const cols = [
        { l: 'SYMBOL', k: 'sym', a: 'left', s: true },
        { l: 'QTY', k: 'qty', a: 'center' },
        { l: 'AVG', k: 'avg', a: 'right' },
        { l: 'LTP', k: 'ltp', a: 'right' },
        { l: 'INVESTED', k: 'invested', a: 'right' },
        { l: 'P/L', k: 'pnl', a: 'right' },
        { l: '1D%', k: 'changePct', a: 'center' },
        { l: 'POS', k: 'pos', a: 'center' },
        { l: 'NEG', k: 'neg', a: 'center' },
        { l: 'ROE%', k: 'roe', a: 'center' },
        { l: 'ROCE%', k: 'roce', a: 'center' },
        { l: 'OPM%', k: 'opm', a: 'center' },
        { l: 'NPM%', k: 'npm', a: 'center' },
        { l: 'P/E', k: 'pe', a: 'center' },
        { l: 'P/B', k: 'pb', a: 'center' },
        { l: 'EPS', k: 'eps', a: 'center' },
        { l: 'MCAP', k: 'mcap', a: 'center' },
        { l: 'SALES', k: 'sales', a: 'center' },
        { l: 'CFO', k: 'cfo', a: 'center' },
        { l: 'EBITDA', k: 'ebitda', a: 'center' },
        { l: 'PROM%', k: 'prom_pct', a: 'center' },
        { l: 'ATH%', k: 'ath_pct', a: 'center' },
        { l: '52W%', k: 'w52_pct', a: 'center' },
        { l: 'SIGNAL', k: 'signal', a: 'center' }
    ];

    // Build Header Row (Sticky)
    html += `<tr style="background:#161b22; border-bottom:2px solid #30363d; position:sticky; top:0; z-index:20;">`;
    cols.forEach(c => {
        const arrow = window.currentSort.key === c.k ? (window.currentSort.dir === 'desc' ? ' ↓' : ' ↑') : '';
        html += `<th onclick="handleSort('${c.k}')" style="padding:12px; text-align:${c.a}; color:#8b949e; cursor:pointer; font-size:9px; text-transform:uppercase; ${c.s ? 'position:sticky; left:0; background:#161b22; z-index:30;' : ''}">
                    ${c.l}${arrow}
                </th>`;
    });
    html += `</tr>`;

    // Build Data Rows
    window.S.portfolio.forEach((s, idx) => {
        const f = window.FUND[s.sym] || {};
        const inv = s.qty * s.avg;
        const curValue = s.qty * (parseFloat(f.ltp) || 0);
        const pnl = curValue - inv;
        
        gInv += inv; 
        gPnl += pnl;

        const bg = idx % 2 === 0 ? '#0d1117' : '#161b22';
        html += `<tr style="background:${bg}; border-bottom:1px solid #21262d;" onclick="window.location.href='stock.html?s=${s.sym}'">`;
        
        cols.forEach(c => {
            let val = f[c.k];
            if (c.k === 'qty') val = s.qty; 
            if (c.k === 'avg') val = s.avg; 
            if (c.k === 'invested') val = inv; 
            if (c.k === 'pnl') val = pnl;
            
            const fm = getCellStyle(c.k, val);
            const isSym = c.k === 'sym';

            html += `<td style="padding:12px; text-align:${c.a}; color:${fm.color}; ${isSym ? 'font-weight:bold; color:#58a6ff; position:sticky; left:0; background:'+bg+'; z-index:10;' : ''}">
                        ${isSym ? s.sym : (c.k === 'signal' ? (f.signal || '—') : fm.text)}
                    </td>`;
        });
        html += `</tr>`;
    });

    html += `</table></div>`;

    // Grand Total Footer (Floating)
    html += `<div style="position:fixed; bottom:0; left:0; right:0; background:#0d1117; border-top:2px solid #30363d; padding:15px; display:flex; justify-content:space-around; font-size:12px; z-index:100; box-shadow: 0 -5px 15px rgba(0,0,0,0.5);">
                <div><span style="color:#8b949e;">INVESTED:</span> <span style="color:#fff; font-weight:bold;">₹${Math.round(gInv).toLocaleString('en-IN')}</span></div>
                <div><span style="color:#8b949e;">TOTAL P/L:</span> <span style="color:${gPnl >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">₹${Math.round(gPnl).toLocaleString('en-IN')}</span></div>
             </div>`;

    html += `</div>`;
    container.innerHTML = html;
}
