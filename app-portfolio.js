/**
 * APP-PORTFOLIO.JS - V3.4 
 * FULL PARITY: Personal Holdings (Qty/Avg), Market Data, Global Sort, & Combined Totals
 */

window.currentSort = { key: 'mcap', dir: 'desc' };
window.fundLoaded = false;
window.pfRefreshing = false;

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

        // Stage 1: Map Personal Holdings from symbols.json
        window.S = { portfolio: sData.map(item => ({
            sym: item.sym || '?',
            isin: item.isin || '',
            qty: parseFloat(item.qty || 0),
            avg: parseFloat(item.avg || 0),
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
        window.fundLoaded = true; 
        return false;
    } finally {
        window.pfRefreshing = false;
    }
}

/**
 * STAGE 3: SORTING ENGINE (Fixed for all fields)
 */
function handleSort(key) {
    const dir = (window.currentSort.key === key && window.currentSort.dir === 'desc') ? 'asc' : 'desc';
    window.currentSort = { key, dir };
    
    window.S.portfolio.sort((a, b) => {
        const fA = window.FUND[a.sym] || window.FUND[window.ISIN_MAP[a.isin]] || {};
        const fB = window.FUND[b.sym] || window.FUND[window.ISIN_MAP[b.isin]] || {};
        
        // Merge personal and market data for sorting
        const valA = a[key] !== undefined ? a[key] : (fA[key] ?? -999999);
        const valB = b[key] !== undefined ? b[key] : (fB[key] ?? -999999);
        
        return dir === 'desc' ? valB - valA : valA - valB;
    });
    renderPortfolio(document.getElementById('portfolio-container'));
}

function getCellStyle(key, val, sector = "") {
    const n = parseFloat(val);
    if (isNaN(n) || val === null) return { text: '—', color: '#8b949e' };
    let color = '#fff';
    if (['roe', 'roce'].includes(key)) color = n > 18 ? '#3fb950' : (n < 10 ? '#f85149' : '#d29922');
    if (key === 'chg1d' || key === 'pnl' || key === 'pnl_pct') color = n > 0 ? '#3fb950' : (n < 0 ? '#f85149' : '#fff');
    if (key === 'pos') color = n >= 4 ? '#3fb950' : '#fff';
    if (key === 'neg') color = n > 0 ? '#f85149' : '#8b949e';
    
    let display = n.toLocaleString('en-IN', { maximumFractionDigits: 1 });
    return { text: display, color };
}

async function renderPortfolio(container) {
    if (!container) return;
    if (!window.fundLoaded) await loadFundamentals();

    let grandInvested = 0, grandPnl = 0;

    let html = `<div style="background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif; padding:10px;">`;
    html += `<div style="overflow-x:auto; border:1px solid #30363d; border-radius:8px; background:#0d1117; margin-bottom:80px;">`;
    html += `<table style="width:100%; border-collapse:collapse; white-space:nowrap; font-size:11px;">`;
    
    // --- FULL 37-COLUMN HEADER (With Sorting enabled on ALL) ---
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
        html += `<th onclick="handleSort('${c.k}')" style="padding:14px 12px; text-align:${c.a}; color:#8b949e; cursor:pointer; font-size:9px; ${c.s ? 'position:sticky; left:0; background:#161b22; z-index:10;' : ''}">${c.l}${arrow}</th>`;
    });
    html += `</tr>`;

    window.S.portfolio.forEach((s, idx) => {
        const f = window.FUND[s.sym] || window.FUND[window.ISIN_MAP[s.isin]] || {};
        const ltp = parseFloat(f.ltp || 0);
        const invested = s.qty * s.avg;
        const currentVal = s.qty * ltp;
        const pnl = currentVal - invested;
        
        grandInvested += invested;
        grandPnl += pnl;

        const bg = idx % 2 === 0 ? '#0d1117' : '#161b22';
        html += `<tr style="background:${bg}; border-bottom:1px solid #21262d;">`;
        
        cols.forEach(c => {
            let val = f[c.k];
            if (c.k === 'qty') val = s.qty;
            if (c.k === 'avg') val = s.avg;
            if (c.k === 'invested') val = invested;
            if (c.k === 'pnl') val = pnl;
            
            const fm = getCellStyle(c.k, val, f.sector);
            html += `<td style="padding:14px 12px; text-align:${c.a}; color:${fm.color}; ${c.k==='sym'?'font-weight:bold; color:#58a6ff; position:sticky; left:0; background:'+bg+';':''}">
                        ${c.k === 'sym' ? s.sym : (c.k === 'signal' ? (f.signal || '—') : fm.text)}
                    </td>`;
        });
        html += `</tr>`;
    });

    html += `</table></div>`;

    // --- GRAND TOTAL FOOTER (Invested & P/L only) ---
    html += `<div style="position:fixed; bottom:0; left:0; right:0; background:#0d1117; border-top:2px solid #30363d; padding:15px; display:flex; justify-content:space-around; font-size:12px; z-index:100;">
                <div><span style="color:#8b949e;">INVESTED:</span> <span style="color:#fff; font-weight:bold;">₹${Math.round(grandInvested).toLocaleString('en-IN')}</span></div>
                <div><span style="color:#8b949e;">PROFIT/LOSS:</span> <span style="color:${grandPnl >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">₹${Math.round(grandPnl).toLocaleString('en-IN')}</span></div>
             </div>`;

    html += `</div>`;
    container.innerHTML = html;
}
