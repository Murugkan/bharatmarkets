/** ONYX v21.0 - OFFLINE-FIRST RESOLUTION */
window.S = JSON.parse(localStorage.getItem('bm_settings')) || { settings: {}, watchlist: [], portfolio: [] };
window.ALIAS_MAP = JSON.parse(localStorage.getItem('bm_aliases')) || {};
window.FUND = window.FUND || {};

// --- EMERGENCY OFFLINE MAP (Bypasses "Load failed") ---
const OFFLINE_MAP = {
    "TATA POWER COMPANY LTD": "TATAPOWER",
    "UNITED SPIRITS LTD": "UNITDSPR",
    "VEDANTA LTD": "VEDL",
    "VOLTAMP TRANSFORMERS LTD": "VOLTAMP",
    "TITAN BIOTECH LTD": "TITANBIO",
    "ZINKA LOGISTICS SOL LTD": "ZINKA",
    "VENTIVE HOSPITALITY LTD": "VENTIVE"
};

function dataLog(msg, type = 'info') {
    const log = document.getElementById('debug-console');
    if (!log) return;
    const colors = { info: '#aaa', error: '#ff6b85', success: '#00e896', warn: '#ffbf47' };
    const div = document.createElement('div');
    div.style.cssText = `border-bottom:1px solid #111; padding:4px; font-size:10px; color:${colors[type]}`;
    div.innerHTML = `<span style="color:#555">[${new Date().toLocaleTimeString()}]</span> ${msg}`;
    log.prepend(div);
}

async function resolveSymbol(rawName) {
    const q = rawName.trim().toUpperCase();
    const cleanQ = q.replace(/\b(LTD|LIMITED|SOLUTIONS|COMPANY)\b/g, '').trim();
    
    dataLog(`Resolving: "${q}"...`, 'info');

    // Tier 1: User Alias Memory
    if (window.ALIAS_MAP[q]) {
        dataLog(`Match in ALIAS_MAP: ${window.ALIAS_MAP[q]}`, 'success');
        return { symbol: window.ALIAS_MAP[q] };
    }

    // Tier 2: Emergency Offline Map
    for (let key in OFFLINE_MAP) {
        if (q.includes(key) || key.includes(q)) {
            dataLog(`Match in OFFLINE_MAP: ${OFFLINE_MAP[key]}`, 'success');
            return { symbol: OFFLINE_MAP[key] };
        }
    }

    // Tier 3: Internal FUND Check
    const universe = Object.keys(window.FUND);
    const hit = universe.find(sym => sym === cleanQ || (window.FUND[sym]?.name || '').toUpperCase().includes(cleanQ));
    if (hit) {
        dataLog(`Match in FUND: ${hit}`, 'success');
        return { symbol: hit };
    }

    // Tier 4: Yahoo (The "Load failed" risk)
    try {
        const res = await fetch(`https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(cleanQ)}&region=IN`);
        const d = await res.json();
        const quotes = (d.quotes || []).filter(x => x.symbol && (x.symbol.endsWith('.NS') || x.symbol.endsWith('.BO')));
        if (quotes.length > 0) {
            const sym = quotes[0].symbol.split('.')[0];
            dataLog(`Yahoo Match: ${sym}`, 'success');
            return { symbol: sym };
        }
    } catch (e) {
        dataLog(`Network Blocked: Using Clean String as Fallback`, 'warn');
        // If everything fails, suggest the cleaned-up name as a likely ticker
        return { symbol: cleanQ.split(' ')[0], fallback: true };
    }

    return null;
}

function updateAlias(rawName, symbol) {
    const q = rawName.trim().toUpperCase();
    const sym = symbol.toUpperCase().replace(/\.NS$/, '').trim();
    window.ALIAS_MAP[q] = sym;
    localStorage.setItem('bm_aliases', JSON.stringify(window.ALIAS_MAP));
    dataLog(`Saved Mapping: ${q} → ${sym}`, 'success');
}

// Keep the Frozen PAT logic as it was successful in your screenshot
