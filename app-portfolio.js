// --- UPDATED ROW LOGIC FOR STEP 2 ---
for (var j = 0; j < window.S.portfolio.length; j++) {
    var h = window.S.portfolio[j];
    
    // 1. TRY MATCHING BY SYMBOL DIRECTLY
    var f = window.FUND[h.sym];
    
    // 2. IF FAIL, TRY MATCHING BY ISIN
    if (!f && h.isin && window.ISIN_MAP[h.isin]) {
        f = window.FUND[window.ISIN_MAP[h.isin]];
    }
    
    // 3. IF STILL FAIL, TRY CLEANED SYMBOL (Handle any weird %26 or & issues)
    if (!f) {
        var cleanSym = h.sym.replace(/[^a-zA-Z0-0]/g, "");
        f = window.FUND[cleanSym];
    }

    f = f || {}; // Fallback to empty object if all matchers fail

    html += '<tr style="border-bottom:1px solid #1e3350;">';
    html += '<td style="padding:12px; font-weight:bold; color:#58a6ff;">' + h.sym + '</td>';
    
    // Fix: Prioritize Sector from Symbols.json, then fallback to Fundamentals
    var displaySector = h.sector || f.sector || '—';
    html += '<td style="padding:12px; color:#8b949e;">' + displaySector + '</td>';
    
    // Fix: Ensure ROE is treated as a number
    var roeVal = (f.roe !== undefined) ? f.roe : '—';
    var roeColor = (parseFloat(roeVal) > 15) ? '#3fb950' : '#fff';
    
    html += '<td style="padding:12px; text-align:right; color:' + roeColor + ';">' + roeVal + (roeVal !== '—' ? '%' : '') + '</td>';
    html += '</tr>';
}
