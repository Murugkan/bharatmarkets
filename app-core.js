/** ONYX v22.0 - ANTI-CRASH CORE */
window.S = JSON.parse(localStorage.getItem('bm_settings')) || { settings: {}, watchlist: [], portfolio: [] };
window.ALIAS_MAP = JSON.parse(localStorage.getItem('bm_aliases')) || {};
window.FUND = window.FUND || {};

function dataLog(msg, type = 'info') {
    const log = document.getElementById('debug-console');
    if (!log) return;
    const colors = { info: '#aaa', error: '#ff6b85', success: '#00e896', warn: '#ffbf47' };
    const div = document.createElement('div');
    div.style.cssText = `border-bottom:1px solid #111; padding:4px; font-size:10px; color:${colors[type]}`;
    div.innerHTML = `<span style="color:#555">[${new Date().toLocaleTimeString()}]</span> ${msg}`;
    log.prepend(div);
}

// Bypasses network "Load failed" for common stocks
const OFFLINE_MAP = {
    "TATA POWER": "TATAPOWER", "VEDANTA": "VEDL", "UNITED SPIRITS": "UNITDSPR", 
    "VOLTAMP": "VOLTAMP", "TITAN BIOTECH": "TITANBIO", "ZINKA": "ZINKA"
};

async function resolveSymbol(rawName) {
    try {
        const q = (rawName || "").toString().trim().toUpperCase();
        if (!q) return { symbol: 'EMPTY', error: true };

        // 1. Alias Map
        if (window.ALIAS_MAP[q]) return { symbol: window.ALIAS_MAP[q] };

        // 2. Offline Map
        for (let key in OFFLINE_MAP) {
            if (q.includes(key)) return { symbol: OFFLINE_MAP[key] };
        }

        // 3. Yahoo Fetch with Timeout to prevent hanging
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 3000);
        
        const res = await fetch(`https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&region=IN`, { signal: controller.signal });
        clearTimeout(timeout);
        
        const d = await res.json();
        const quotes = (d.quotes || []).filter(x => x.symbol && (x.symbol.endsWith('.NS') || x.symbol.endsWith('.BO')));
        if (quotes.length > 0) return { symbol: quotes[0].symbol.split('.')[0] };

    } catch (e) {
        dataLog(`Resolve Error (${rawName}): ${e.message}`, 'error');
    }
    return { symbol: 'FAILED', error: true }; 
}

function updateAlias(rawName, symbol) {
    const q = rawName.trim().toUpperCase();
    const sym = symbol.toUpperCase().replace(/\.NS$/, '').trim();
    window.ALIAS_MAP[q] = sym;
    localStorage.setItem('bm_aliases', JSON.stringify(window.ALIAS_MAP));
    dataLog(`Mapped: ${q} -> ${sym}`, 'success');
}
