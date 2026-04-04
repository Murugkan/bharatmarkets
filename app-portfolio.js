// Global state flags
var fundLoaded = false;
var pfRefreshing = false;

async function loadFundamentals() {
    if (pfRefreshing) return;
    pfRefreshing = true;

    try {
        var ts = Date.now();
        
        // 1. Fetch Master List (The Array from symbols.json)
        var sRes = await fetch('./symbols.json?v=' + ts);
        var sData = await sRes.json();
        
        // 2. Fetch Data (The Object from fundamentals.json)
        var fRes = await fetch('./fundamentals.json?v=' + ts);
        var fData = await fRes.json();

        // 3. Set the Master List into the portfolio global
        window.S = window.S || {};
        window.S.portfolio = sData;

        // 4. Set the Data into the FUND global
        window.FUND = fData.stocks || fData;
        
        // 5. Build a basic ISIN map for bridging
        window.ISIN_MAP = {};
        var fundKeys = Object.keys(window.FUND);
        for (var i = 0; i < fundKeys.length; i++) {
            var k = fundKeys[i];
            if (window.FUND[k].isin) {
                window.ISIN_MAP[window.FUND[k].isin] = k;
            }
        }

        fundLoaded = true;
        return true;
    } catch (e) {
        console.error("Load Error:", e);
        return false;
    } finally {
        pfRefreshing = false;
    }
}

async function renderPortfolio(container) {
    if (!container) return;

    // Force hide any app-level "Syncing" overlays
    var overlay = document.querySelector('.loading, #sync-overlay');
    if (overlay) overlay.style.display = 'none';

    // If not loaded, run the loader
    if (!fundLoaded) {
        container.innerHTML = '<div style="padding:40px;color:#58a6ff;">> LOADING DATA...</div>';
        await loadFundamentals();
    }

    // Safety check
    if (!window.S || !window.S.portfolio) {
        container.innerHTML = '<div style="padding:40px;color:red;">❌ DATA NOT FOUND</div>';
        return;
    }

    // --- SIMPLE TABLE RENDER ---
    var stocks = window.S.portfolio;
    var html = '<div style="padding:10px; background:#02040a; color:#fff; font-family:sans-serif;">';
    html += '<div style="margin-bottom:10px; font-weight:bold;">' + stocks.length + ' Stocks Found</div>';
    html += '<table style="width:100%; border-collapse:collapse; font-size:13px;">';
    
    for (var j = 0; j < stocks.length; j++) {
        var h = stocks[j];
        // Match by Symbol or by ISIN
        var f = window.FUND[h.sym] || (h.isin ? window.FUND[window.ISIN_MAP[h.isin]] : null) || {};
        
        html += '<tr style="border-bottom:1px solid #1e3350;">';
        html += '<td style="padding:12px; font-weight:bold; color:#58a6ff;">' + h.sym + '</td>';
        html += '<td style="padding:12px; color:#8b949e;">' + (h.sector || f.sector || '—') + '</td>';
        html += '<td style="padding:12px; text-align:right;">ROE: ' + (f.roe || '—') + '%</td>';
        html += '</tr>';
    }

    html += '</table></div>';
    container.innerHTML = html;
}
