/**
 * APP-PORTFOLIO.JS - V4.6 (THE FINAL CONSOLIDATED MASTER)
 * INSTRUCTIONS: Replace your ENTIRE app-portfolio.js file with this code.
 */

// 1. Global Configuration
window.currentSort = { key: 'mcap', dir: 'desc' };

// 2. The Sorting Trigger (Ensures sorting works on every click)
window.triggerSort = function(key) {
    const dir = (window.currentSort.key === key && window.currentSort.dir === 'desc') ? 'asc' : 'desc';
    window.currentSort = { key, dir };
    renderPortfolio(document.getElementById('portfolio-container'));
};

// 3. The Main Execution Engine
async function renderPortfolio(container) {
    if (!container) return;

    try {
        const ts = Date.now();
        // Fetch both files simultaneously
        const [sRes, fRes] = await Promise.all([
            fetch(`./symbols.json?v=${ts}`),
            fetch(`./fundamentals.json?v=${ts}`)
        ]);
        
        const sData = await sRes.json();
        const fDataRaw = await fRes.json();
        const fData = fDataRaw.stocks || fDataRaw;

        // --- STEP A: DATA BRIDGING ---
        // This merges your personal holdings with the market fundamentals
        let portfolio = sData.map(s => {
            const sym = (s.sym || s.SYMBOL || "").toUpperCase().trim();
            const f = fData[sym] || {};
            
            const qty = parseFloat(s.qty || s.QTY || 0);
            const avg = parseFloat(s.avg || s.AVG || 0);
            const ltp = parseFloat(f.ltp || 0);
            const inv = qty * avg;
            const pnl = (qty * ltp) - inv;

            return {
                sym: sym,
                qty: qty,
                avg: avg,
                ltp: ltp,
                invested: inv,
                pnl: pnl,
                changePct: f.changePct || 0,
                pos: f.pos || 0,
                neg: f.neg || 0,
                roe: f.roe || 0,
                roce: f.roce || 0,
                opm: f.opm || 0,
                npm: f.npm || 0,
                pe: f.pe || 0,
                pb: f.pb || 0,
                eps: f.eps || 0,
                mcap: f.mcap || 0,
                sales: f.sales || 0,
                cfo: f.cfo || 0,
                ebitda: f.ebitda || 0,
                prom_pct: f.prom_pct || 0,
                fii_pct: f.fii_pct || 0,
                dii_pct: f.dii_pct || 0,
                ath_pct: f.ath_pct || 0,
                w52_pct: f.w52_pct || 0,
                signal: f.signal || "HOLD"
            };
        });

        // --- STEP B: SORTING LOGIC ---
        portfolio.sort((a, b) => {
            const k = window.currentSort.key;
            const vA = (typeof a[k] === 'string') ? a[k] : (a[k] || -999999999);
            const vB = (typeof b[k] === 'string') ? b[k] : (b[k] || -999999999);
            return window.currentSort.dir === 'desc' ? (vB > vA ? 1 : -1) : (vA > vB ? 1 : -1);
        });

        // --- STEP C: CALCULATE GRAND TOTALS ---
        let gInv = 0, gPnl = 0;
        portfolio.forEach(i => { gInv += i.invested; gPnl += i.pnl; });

        // --- STEP D: COLUMN DEFINITION (Every single field) ---
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
            { l: 'FII%', k: 'fii_pct', a: 'center' },
            { l: 'DII%', k: 'dii_pct', a: 'center' },
            { l: 'ATH%', k: 'ath_pct', a: 'center' },
            { l: '52W%', k: 'w52_pct', a: 'center' },
            { l: 'SIGNAL', k: 'signal', a: 'center' }
        ];

        // --- STEP E: RENDER HTML ---
        let html = `<div style="background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif; padding:10px; font-size:11px;">`;
        html += `<div style="overflow-x:auto; border:1px solid #30363d; border-radius:8px; background:#0d1117; margin-bottom:100px;">`;
        html += `<table style="width:100%; border-collapse:collapse; white-space:nowrap;">`;

        // Generate Sticky Headers
        html += `<tr style="background:#161b22; border-bottom:2px solid #30363d; position:sticky; top:0; z-index:40;">`;
        cols.forEach(c => {
            const arrow = window.currentSort.key === c.k ? (window.currentSort.dir === 'desc' ? ' ↓' : ' ↑') : '';
            html += `<th onclick="triggerSort('${c.k}')" style="padding:14px 12px; text-align:${c.a}; color:#8b949e; cursor:pointer; font-size:10px; ${c.s ? 'position:sticky; left:0; background:#161b22; z-index:50;' : ''}">
                        ${c.l}${arrow}
                    </th>`;
        });
        html += `</tr>`;

        // Generate Rows
        portfolio.forEach((item, idx) => {
            const bg = idx % 2 === 0 ? '#0d1117' : '#161b22';
            html += `<tr style="background:${bg}; border-bottom:1px solid #21262d;">`;
            cols.forEach(c => {
                let val = item[c.k];
                let color = '#fff';
                
                // Formatting & Colors
                if (['pnl', 'changePct', 'ath_pct', 'w52_pct'].includes(c.k)) color = val > 0 ? '#3fb950' : (val < 0 ? '#f85149' : '#fff');
                if (['roe', 'roce'].includes(c.k)) color = val > 15 ? '#3fb950' : (val < 8 ? '#f85149' : '#d29922');
                if (c.k === 'pos') color = val >= 4 ? '#3fb950' : '#fff';
                if (c.k === 'neg') color = val > 0 ? '#f85149' : '#8b949e';

                let txt = (val === 0 && c.k !== 'qty' && c.k !== 'avg' && c.k !== 'sym') ? '—' : val.toLocaleString('en-IN', { maximumFractionDigits: 1 });
                if (['roe','roce','opm','npm','changePct','prom_pct','fii_pct','dii_pct','ath_pct','w52_pct'].includes(c.k) && txt !== '—') txt += '%';

                html += `<td style="padding:14px 12px; text-align:${c.a}; color:${color}; ${c.s ? 'position:sticky; left:0; background:'+bg+'; color:#58a6ff; font-weight:bold; border-right:1px solid #30363d;' : ''}">
                            ${c.k === 'signal' ? item.signal : txt}
                        </td>`;
            });
            html += `</tr>`;
        });

        html += `</table></div>`;

        // Grand Total Footer
        html += `<div style="position:fixed; bottom:0; left:0; right:0; background:#0d1117; border-top:2px solid #30363d; padding:20px; display:flex; justify-content:space-around; font-size:14px; z-index:100; font-weight:bold; box-shadow: 0 -10px 20px rgba(0,0,0,0.5);">
                    <div style="color:#8b949e;">INVESTED: <span style="color:#fff;">₹${Math.round(gInv).toLocaleString('en-IN')}</span></div>
                    <div style="color:#8b949e;">TOTAL P/L: <span style="color:${gPnl >= 0 ? '#3fb950' : '#f85149'};">₹${Math.round(gPnl).toLocaleString('en-IN')}</span></div>
                 </div>`;

        html += `</div>`;
        container.innerHTML = html;

    } catch (err) {
        container.innerHTML = `<div style="color:#f85149; padding:40px; text-align:center; font-family:monospace;">[ ERROR: ${err.message} ]</div>`;
    }
}
