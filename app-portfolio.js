// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - FULL RESTORATION (STABLE & TUNED)
// ─────────────────────────────────────────────────────────────

// 1. CONSTANTS
const CSS = {
    GRN_B: 'background:#003a20;color:#fff;font-weight:600',
    RED_B: 'background:#3a0010;color:#fff;font-weight:600',
    GRN_BD: 'background:#003a20;color:#fff;font-weight:700',
    RED_BD: 'background:#3a0010;color:#fff;font-weight:700',
    DIM: 'color:#4a6888',
    MUTE: 'color:#8eb0d0'
};

const TH_COLS = [
    ['sym','Ticker'],['sector','Sector'],['pos','Pos'],['neg','Neg'],['ath','ATH%'],
    ['w52','52W%'],['prom','Prom%'],['roe','ROE%'],['pe','P/E'],['sales','Sales'],
    ['cfo','CFO'],['mcap','MCAP'],['chg1d','%1D'],['ltp','LTP'],['qty','Qty'],
    ['avg','Avg'],['pnl','P&L'],['pnlpct','P&L%'],['wt','Wt%'],['sig','Sig']
];

// 2. FORMATTERS
const fn = (v, dp=1, pre='', suf='') => (v == null || isNaN(v)) ? '—' : pre + Number(v).toFixed(dp) + suf;
const fnCr = (v) => {
    if (v == null || isNaN(v)) return '—';
    return v >= 100000 ? (v/100000).toFixed(1)+'LCr' : v >= 1000 ? (v/1000).toFixed(1)+'KCr' : v.toFixed(0)+'Cr';
};

// 3. LOGIC: MERGE & SIGNALS
function mergeHolding(h) {
    const f = (typeof FUND !== 'undefined') ? FUND[h.sym] : {};
    const ltp = h.liveLtp || f?.ltp || 0;
    
    // Signal Logic
    let p = f?.pos || 0, n = f?.neg || 0;
    if (!f?.pos) {
        const roe = f?.roe || h?.roe || 0;
        const pe = f?.pe || h?.pe || 0;
        if (roe > 15) p++; else if (roe > 0 && roe < 8) n++;
        if (pe > 0 && pe < 18) p++; else if (pe > 35) n++;
    }
    const net = p - n;
    
    return {
        ...h, ...f, ltp, pos: p, neg: n,
        sector: f?.sector || h?.sector || '—',
        sig: f?.signal || (net >= 2 ? 'BUY' : net <= -2 ? 'SELL' : 'HOLD'),
        w52_pct: (ltp && f?.w52h) ? ((ltp/f.w52h - 1)*100) : null
    };
}

// 4. UI COMPONENTS
function renderKpis(t, count) {
    const pCol = t.pnl >= 0 ? '#00e896' : '#ff6b85';
    return `
    <div class="kpi-strip" style="display:flex; justify-content:space-between; padding:15px; background:#0d1525; border-radius:8px; margin-bottom:10px;">
        <div class="kpi"><small style="${CSS.MUTE}">Invested</small><br><b style="color:#64b5f6">₹${(t.inv/100000).toFixed(2)}L</b><br><small>${count} stocks</small></div>
        <div class="kpi" style="text-align:right;"><small style="${CSS.MUTE}">Total P&L</small><br><b style="color:${pCol}">₹${(Math.abs(t.pnl)/100000).toFixed(2)}L</b><br><small style="color:${pCol}">${t.pnlP.toFixed(2)}%</small></div>
    </div>`;
}

// 5. MAIN RENDERER
function renderPortfolio(container) {
    if (typeof S === 'undefined' || !S.portfolio) {
        container.innerHTML = `<div style="padding:40px; color:#ff6b85;">Waiting for Global State...</div>`;
        return;
    }

    const pf = S.portfolio.map(mergeHolding);
    const t = {
        inv: pf.reduce((a, r) => a + (r.qty * r.avgBuy), 0),
        cur: pf.reduce((a, r) => a + (r.qty * r.ltp), 0),
        get pnl() { return this.cur - this.inv },
        get pnlP() { return (this.pnl / this.inv * 100) || 0 }
    };

    // Filter & Sort
    let filtered = pf.filter(r => (!S.pfSearch || r.sym.includes(S.pfSearch.toUpperCase())) && (S.pfFilter === 'All' || r.sig === S.pfFilter));
    filtered.sort((a,b) => S.pfSortDir === 'asc' ? (a[S.pfSort] - b[S.pfSort]) : (b[S.pfSort] - a[S.pfSort]));

    container.innerHTML = `
    <div class="bls">
        ${renderKpis(t, pf.length)}
        
        <div class="bls-tb" style="padding:10px 0; display:flex; gap:8px;">
            <input type="text" placeholder="Search..." value="${S.pfSearch || ''}" 
                oninput="S.pfSearch=this.value.toUpperCase(); renderPortfolio(container)" 
                style="flex:1; background:#0d1525; border:1px solid #1e3350; color:#fff; padding:8px; border-radius:4px; outline:none;">
        </div>

        <div class="bls-table-outer" style="overflow-x:auto; -webkit-overflow-scrolling:touch;">
            <table class="bls-t" style="width:100%; border-collapse:collapse; white-space:nowrap;">
                <thead>
                    <tr style="border-bottom:1px solid #1e3350;">
                        ${TH_COLS.map(([k,l]) => `<th onclick="S.pfSort='${k}'; S.pfSortDir=(S.pfSortDir==='asc'?'desc':'asc'); renderPortfolio(container)" style="padding:12px 8px; text-align:left; cursor:pointer; font-size:11px; color:#8eb0d0;">${l}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${filtered.map(r => {
                        const rPnl = (r.ltp - r.avgBuy) * r.qty;
                        const rPnlP = (rPnl / (r.qty * r.avgBuy) * 100) || 0;
                        const wt = (r.ltp * r.qty / t.cur * 100) || 0;
                        return `
                        <tr style="border-bottom:1px solid #0d1525; background:${r.sig==='BUY'?'rgba(0,160,80,.05)':r.sig==='SELL'?'rgba(200,30,50,.05)':'transparent'}" onclick="openPortfolioStock('${r.sym}')">
                            <td style="padding:10px;"><b>${r.sym}</b></td>
                            <td style="font-size:10px; color:#4a6888">${r.sector.slice(0,10)}</td>
                            <td><span class="pn-p">${r.pos}</span></td>
                            <td><span class="pn-n">${r.neg}</span></td>
                            <td style="${r.ath_pct > -5 ? CSS.GRN_B : ''}">${fn(r.ath_pct,1,'','%')}</td>
                            <td>${fn(r.w52_pct,1,'','%')}</td>
                            <td>${fn(r.prom_pct,1,'','%')}</td>
                            <td style="${r.roe > 15 ? CSS.GRN_B : ''}">${fn(r.roe,1,'','%')}</td>
                            <td>${fn(r.pe,1)}</td>
                            <td>${fnCr(r.sales)}</td>
                            <td>${fnCr(r.cfo)}</td>
                            <td>${fnCr(r.mcap)}</td>
                            <td style="${r.chg1d >= 0 ? CSS.GRN_BD : CSS.RED_BD}">${fn(r.chg1d,2,'','%')}</td>
                            <td>₹${r.ltp.toFixed(1)}</td>
                            <td>${r.qty}</td>
                            <td style="color:#4a6888">${r.avgBuy.toFixed(1)}</td>
                            <td style="color:${rPnl>=0?'#00e896':'#ff6b85'}">${rPnl.toFixed(0)}</td>
                            <td style="color:${rPnl>=0?'#00e896':'#ff6b85'}">${rPnlP.toFixed(1)}%</td>
                            <td style="color:#4a6888">${wt.toFixed(1)}%</td>
                            <td><span class="badge-${r.sig.toLowerCase()}">${r.sig}</span></td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>
        </div>

        <div style="margin-top:20px; font-size:9px; color:#1e3350; text-align:center;">
            System Stable | ${pf.length} nodes merged
        </div>
    </div>`;
}
