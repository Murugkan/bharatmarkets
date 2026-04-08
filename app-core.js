/** ONYX v20.0 - DEBUG & LOG CAPTURE ENGINE */
window.S = JSON.parse(localStorage.getItem('bm_settings')) || { settings: {}, watchlist: [], portfolio: [] };
window.ALIAS_MAP = JSON.parse(localStorage.getItem('bm_aliases')) || {};
window.FUND = window.FUND || {};

// --- DEBUG ENGINE: Capture Logs to UI ---
function dataLog(msg, type = 'info') {
    const log = document.getElementById('debug-console');
    if (!log) return;
    const colors = { info: '#aaa', error: '#ff6b85', success: '#00e896', warn: '#ffbf47' };
    const div = document.createElement('div');
    div.style.cssText = `border-bottom:1px solid #111; padding:4px; font-size:10px; color:${colors[type]}`;
    div.innerHTML = `<span style="color:#555">[${new Date().toLocaleTimeString()}]</span> ${msg}`;
    log.prepend(div);
}

// Intercept window errors
window.onerror = (m, s, l, c, e) => dataLog(`${m} at L${l}`, 'error');

// --- UPDATED RESOLUTION WITH LOGGING ---
async function resolveSymbol(rawName) {
    const q = rawName.trim().toUpperCase();
    dataLog(`Resolving: "${q}"...`, 'info');

    // 1. Alias Check
    if (window.ALIAS_MAP[q]) {
        dataLog(`Match found in ALIAS_MAP: ${window.ALIAS_MAP[q]}`, 'success');
        return { symbol: window.ALIAS_MAP[q] };
    }

    // 2. Universe Check
    const universe = Object.keys(window.FUND);
    if (universe.length === 0) {
        dataLog(`Warning: FUND universe is empty. Run GitHub sync first.`, 'warn');
    }
    
    const hit = universe.find(sym => sym === q || (window.FUND[sym]?.name || '').toUpperCase().includes(q));
    if (hit) {
        dataLog(`Match found in FUND: ${hit}`, 'success');
        return { symbol: hit };
    }

    // 3. Yahoo Fallback with Error Capture
    try {
        dataLog(`Attempting Yahoo Search for "${q}"...`, 'info');
        const res = await fetch(`https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&region=IN`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const d = await res.json();
        const quotes = (d.quotes || []).filter(x => x.symbol && (x.symbol.endsWith('.NS') || x.symbol.endsWith('.BO')));
        
        if (quotes.length > 0) {
            const sym = quotes[0].symbol.replace('.NS','').replace('.BO','');
            dataLog(`Yahoo Match: ${sym}`, 'success');
            return { symbol: sym };
        }
    } catch (e) {
        dataLog(`Yahoo Search Failed: ${e.message}`, 'error');
    }

    dataLog(`Failed to resolve "${q}"`, 'error');
    return null;
}

function updateAlias(rawName, symbol) {
    const q = rawName.trim().toUpperCase();
    const sym = symbol.toUpperCase().replace(/\.NS$/, '').trim();
    window.ALIAS_MAP[q] = sym;
    localStorage.setItem('bm_aliases', JSON.stringify(window.ALIAS_MAP));
    dataLog(`Mapped "${q}" to "${sym}"`, 'success');
}

// Frozen PAT Logic from previous turns
async function testGitHubConnection() {
    // ... (Keep existing testGitHubConnection logic)
}
