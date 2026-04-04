/**
 * APP-PORTFOLIO.JS - V3.5 (PRODUCTION READY)
 * FULL PARITY: Personal Holdings, Market Data, Global Sort, & Combined Totals
 */

// --- GLOBAL STATE ---
window.currentSort = { key: 'mcap', dir: 'desc' };
window.fundLoaded = false;
window.pfRefreshing = false;

/**
 * STAGE 1: DATA ENGINE
 * Merges symbols.json (Holdings) with fundamentals.json (Market Data)
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

        // Map Personal Holdings
        window.S = { portfolio: sData.map(item => ({
            sym: item.sym || '?',
            isin: item.isin || '',
            qty: parseFloat(item.qty || 0),
            avg: parseFloat(item.avg || 0),
            sector: item.sector || 'N/A'
        }))};

        // Map Market Fundamentals
        window.FUND = fData.stocks || fData;
        window.ISIN_MAP = {};
        Object.keys(window.FUND).forEach(key => {
            const stock = window.FUND[key];
            if (stock && stock.isin) window.ISIN_MAP[stock.isin] = key;
        });

        window.fundLoaded = true;
        return true;
    } catch (e) {
        console.error("Critical Sync Error:", e);
        window.fundLoaded = true; 
        return false;
    } finally {
        window.pfRefreshing = false;
    }
}

/**
 * STAGE 3: UNIVERSAL SORTING ENGINE
 * Works for both Market data (LTP, ROE) and Holding data (Qty, P/L)
 */
function handleSort(key) {
    const dir = (window.currentSort.key === key && window.currentSort.dir === 'desc') ? 'asc' : 'desc';
    window.currentSort = { key, dir };
    
    window.S.portfolio.sort((a, b) => {
        const fA = window.FUND[a.sym] || window.FUND[window.ISIN_MAP[a.isin]] || {};
        const fB = window.FUND[b.sym] || window.FUND[window.ISIN_MAP[b.isin]] || {};
        
        // Helper to get value regardless of which file it lives in
        const getVal = (obj, fund) => {
            if (key === 'invested') return obj.qty * obj.avg;
            if (key === 'pnl') return (obj.qty * (fund.ltp || 0)) - (obj.qty * obj.avg);
            return obj[key] !== undefined ? obj[key] : (fund[key] ?? -999999);
        };

        const vA = getVal(a, fA);
        const vB = getVal(b, fB);
        
        return dir === 'desc' ? vB - vA : vA - vB;
    });
    renderPortfolio(document.getElementById('portfolio-container'));
}

/**
 * COLOR & FORMATTING ENGINE
 */
function getCellStyle(key, val, sector = "") {
    const n = parseFloat(val);
    if (isNaN(n) || val === null) return { text: '—', color: '#8b949e' };
    
    let color = '#fff';
    // Logic matches your "Old Portfolio" requirements
    if (['roe', 'roce'].includes(key)) color = n > 15 ? '#3fb950' : (n < 8 ? '#f85149' : '#d29922');
    if (['pnl', 'chg1d'].includes(key)) color = n > 0 ? '#3fb950' : (n < 0 ? '#f85149' : '#fff');
    if (key === 'pos') color = n >= 4 ? '#3fb950' : '#fff';
    if (key === 'neg') color = n > 0 ? '#f85149' : '#8b949e';
    if (key === 'pe') color = n < 20 ? '#3fb950' : (n > 60 ? '#f85149' : '#fff');

    let display = n.toLocaleString('en-IN', { maximumFractionDigits: 1 });
    if (key === 'qty' || key === 'pos' || key === 'neg') display = Math.round(n);
    
    return { text: display, color };
}

/**
 * THE RENDER ENGINE
 */
async function renderPortfolio(container) {
    if (!container) return;
    if (!window.fundLoaded) {
        container.innerHTML = `<div style="padding:50px; color:#58a6ff; font-family:monospace; text-align:center;">[ LOADING PORTFOLIO... ]</div>`;
        await loadFundamentals();
    }

    let gInvested = 0, gPnl = 0;

    let html = `<div style="background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif; padding:10px;">`;
    html += `<div style="overflow-x:auto; border:1px solid #30363d; border-radius:8px; background:#0d1117; margin-bottom:80px;">`;
    html += `<table style="width:100%; border-collapse:collapse; white-space:nowrap; font-size:11px;">`;
    
    // --- COLUMN HEADERS ---
    const cols = [
        { l: 'Symbol', k: 'sym', a: 'left', s: true },
        { l: 'Qty', k: 'qty', a: 'center' },
        { l: 'Avg Price', k: 'avg', a: 'right' },
        { l: 'LTP', k: 'ltp', a: 'right' },
        { l: 'Invested', k: 'invested', a: 'right' },
        { l: 'P/L', k: 'pnl', a: 'right' },
        { l: 'Pos', k: 'pos', a: 'center' },
        { l: 'Neg', k: 'neg', a: 'center' },
        { l: 'ROE%', k: 'roe', a: 'center' },
        { l: 'P/E', k: 'pe', a: 'center' },
        { l: 'MCAP', k: 'mcap', a: 'center' },
        { l: 'Signal', k: 'signal', a: 'center' }
    ];

    html += `<tr style="background:#161b22; border-bottom:2px solid #30363d;">`;
    cols.forEach(c => {
        const arrow = window.currentSort.key === c.k ? (window.currentSort.dir === 'desc' ? ' ↓' : ' ↑') : '';
        html += `<th onclick="handleSort('${c.k}')" style="padding:14px 12px; text-align:${c.a}; color:#8b949e; cursor:pointer; font-size:10px; ${c.s ? 'position:sticky; left:0; background:#161b22; z-index:10;' : ''}">
                    ${c.l}${arrow}
                </th>`;
    });
    html += `</tr>`;

    // --- DATA ROWS ---
    window.S.portfolio.forEach((s, idx) => {
        const f = window.FUND[s.sym] || window.FUND[window.ISIN_MAP[s.isin]] || {};
        
        const invested = s.qty * s.avg;
        const pnl = (s.qty * (f.ltp || 0)) - invested;
        
        gInvested += invested;
        gPnl += pnl;

        const bg = idx % 2 === 0 ? '#0d1117' : '#161b22';
        html += `<tr style="background:${bg}; border-bottom:1px solid #21262d;" onclick="window.location.href='stock.html?s=${s.sym}'">`;
        
        cols.forEach(c => {
            let val = f[c.k];
            if (c.k === 'qty') val = s.qty;
            if (c.k === 'avg') val = s.avg;
            if (c.k === 'invested') val = invested;
            if (c.k === 'pnl') val = pnl;
            
            const fm = getCellStyle(c.k, val, f.sector);
            const isSym = c.k === 'sym';

            html += `<td style="padding:14px 12px; text-align:${c.a}; color:${fm.color}; ${isSym ? 'font-weight:bold; color:#58a6ff; position:sticky; left:0; background:'+bg+';' : ''}">
                        ${isSym ? s.sym : (c.k === 'signal' ? (f.signal || '—') : fm.text)}
                    </td>`;
        });
        html += `</tr>`;
    });

    html += `</table></div>`;

    // --- GRAND TOTAL FOOTER (Invested & P/L) ---
    html += `<div style="position:fixed; bottom:0; left:0; right:0; background:#0d1117; border-top:2px solid #30363d; padding:15px; display:flex; justify-content:space-around; font-size:12px; z-index:100; box-shadow: 0 -5px 15px rgba(0,0,0,0.5);">
                <div><span style="color:#8b949e;">INVESTED:</span> <span style="color:#fff; font-weight:bold;">₹${Math.round(gInvested).toLocaleString('en-IN')}</span></div>
                <div><span style="color:#8b949e;">PROFIT/LOSS:</span> <span style="color:${gPnl >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">₹${Math.round(gPnl).toLocaleString('en-IN')}</span></div>
             </div>`;

    html += `</div>`;
    container.innerHTML = html;
}
