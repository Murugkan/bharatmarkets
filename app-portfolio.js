/**
 * APP-PORTFOLIO.JS - V4.8 (UI-FIRST ARCHITECTURE)
 * FOCUS: STICKY HEADERS, STICKY COLUMNS, & GRID INTEGRITY
 */

window.currentSort = { key: 'mcap', dir: 'desc' };

window.triggerSort = function(key) {
    const dir = (window.currentSort.key === key && window.currentSort.dir === 'desc') ? 'asc' : 'desc';
    window.currentSort = { key, dir };
    renderPortfolio(document.getElementById('portfolio-container'));
};

async function renderPortfolio(container) {
    if (!container) return;

    // 1. HARD-CODED COLUMN SCHEMA (Order is Permanent)
    const cols = [
        { l: 'SYMBOL', k: 'sym', a: 'left', sticky: true },
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
        { l: 'MCAP ↓', k: 'mcap', a: 'center' },
        { l: 'SALES', k: 'sales', a: 'center' },
        { l: 'CFO', k: 'cfo', a: 'center' },
        { l: 'EBITDA', k: 'ebitda', a: 'center' },
        { l: 'PROM%', k: 'prom_pct', a: 'center' },
        { l: 'FII%', k: 'fii_pct', a: 'center' },
        { l: 'DII%', k: 'dii_pct', a: 'center' },
        { l: 'ATH%', k: 'ath_pct', a: 'center' },
        { l: '52W%', k: 'w52_pct', a: 'center' },
        { l: 'SIGNAL', k: 'signal', a: 'center' }
    ];

    try {
        const ts = Date.now();
        const [sRes, fRes] = await Promise.all([
            fetch(`./symbols.json?v=${ts}`).catch(() => ({ json: () => [] })),
            fetch(`./fundamentals.json?v=${ts}`).catch(() => ({ json: () => ({}) }))
        ]);
        
        const sData = await sRes.json();
        const fRaw = await fRes.json();
        const fData = fRaw.stocks || fRaw;

        // 2. DATA MAPPING
        let portfolio = sData.map(s => {
            const sym = (s.sym || s.SYMBOL || "").toUpperCase();
            const f = fData[sym] || {};
            const qty = parseFloat(s.qty || s.QTY || 0);
            const avg = parseFloat(s.avg || s.AVG || 0);
            const ltp = parseFloat(f.ltp || 0);
            return {
                ...f, sym, qty, avg, ltp,
                invested: qty * avg,
                pnl: (qty * ltp) - (qty * avg)
            };
        });

        // 3. SORT
        portfolio.sort((a, b) => {
            const vA = a[window.currentSort.key] || 0;
            const vB = b[window.currentSort.key] || 0;
            return window.currentSort.dir === 'desc' ? vB - vA : vA - vB;
        });

        // 4. GENERATE UI
        let html = `
        <style>
            .pf-wrapper { background:#02040a; height:100vh; display:flex; flex-direction:column; color:#fff; font-family:sans-serif; }
            .scroll-area { overflow: auto; flex: 1; border: 1px solid #30363d; margin: 10px; border-radius: 8px; }
            table { border-collapse: separate; border-spacing: 0; width: 100%; font-size: 11px; }
            th { 
                position: sticky; top: 0; background: #161b22; z-index: 10; 
                padding: 12px; text-align: center; border-bottom: 2px solid #30363d; color: #8b949e;
            }
            td { padding: 12px; border-bottom: 1px solid #21262d; background: #0d1117; }
            .sticky-col { 
                position: sticky; left: 0; z-index: 5; border-right: 1px solid #30363d; 
                font-weight: bold; color: #58a6ff; background: #0d1117 !important; 
            }
            th.sticky-col { z-index: 15; background: #161b22 !important; }
            .footer { background: #0d1117; border-top: 2px solid #30363d; padding: 15px; display: flex; justify-content: space-around; font-weight: bold; }
        </style>
        <div class="pf-wrapper">
            <div class="scroll-area">
                <table>
                    <thead>
                        <tr>
                            ${cols.map(c => `<th class="${c.sticky ? 'sticky-col' : ''}" onclick="triggerSort('${c.k}')">
                                ${c.l}${window.currentSort.key === c.k ? (window.currentSort.dir === 'desc' ? ' ↓' : ' ↑') : ''}
                            </th>`).join('')}
                        </tr>
                    </thead>
                    <tbody>
                        ${portfolio.map(item => `
                            <tr>
                                ${cols.map(c => {
                                    const val = item[c.k] || 0;
                                    let display = (val === 0 && c.k !== 'qty') ? '—' : val.toLocaleString('en-IN');
                                    if(['roe','opm','npm','changePct'].includes(c.k) && display !== '—') display += '%';
                                    return `<td class="${c.sticky ? 'sticky-col' : ''}" style="text-align:${c.a};">
                                        ${c.k === 'sym' ? item.sym : (c.k === 'signal' ? (item.signal || 'HOLD') : display)}
                                    </td>`;
                                }).join('')}
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
            <div class="footer">
                <div>INVESTED: ₹${portfolio.reduce((a,b)=>a+b.invested,0).toLocaleString('en-IN')}</div>
                <div>P/L: ₹${portfolio.reduce((a,b)=>a+b.pnl,0).toLocaleString('en-IN')}</div>
            </div>
        </div>`;

        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = "Table Load Error";
    }
}
