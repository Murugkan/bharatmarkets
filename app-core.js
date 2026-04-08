/** ONYX v25.0 - EXACT RESTORE FROM OLD FILES */
window.S = JSON.parse(localStorage.getItem('bm_settings')) || { 
    settings: { ghToken: '', ghRepo: '' },
    watchlist: [],
    portfolio: [] 
};
window.ALIAS_MAP = JSON.parse(localStorage.getItem('bm_aliases')) || {};
window.FUND = window.FUND || {};

// --- RESTORED: dataLog (From your old debug-window setup) ---
function dataLog(msg, type = 'info') {
    const log = document.getElementById('debug-console');
    if (!log) return;
    const colors = { info: '#aaa', error: '#ff6b85', success: '#00e896', warn: '#ffbf47' };
    const div = document.createElement('div');
    div.style.cssText = `border-bottom:1px solid #111; padding:6px; font-size:11px; color:${colors[type]}`;
    div.innerHTML = `<span style="color:#555">[${new Date().toLocaleTimeString()}]</span> ${msg}`;
    log.prepend(div);
}

// --- RESTORED: wlSearch Logic (From app-watchlist.js) ---
async function resolveSymbol(val) {
    const q = val.trim().toUpperCase();
    if(!q) return null;

    // 1. Check Alias Map
    if (window.ALIAS_MAP[q]) return { symbol: window.ALIAS_MAP[q] };

    // 2. Build Universe exactly as per old file
    const universe = [...new Set([
        ...Object.keys(window.FUND),
        ...S.portfolio.map(h => h.sym || h.symbol)
    ])].map(sym => ({
        sym,
        name: (window.FUND[sym]?.name || sym).toUpperCase(),
    }));

    // 3. Priority Filtering: Exact > Prefix > Partial
    const exact   = universe.filter(s => s.sym === q);
    const prefix  = universe.filter(s => s.sym !== q && s.sym.startsWith(q));
    const partial = universe.filter(s => !s.sym.startsWith(q) && (s.sym.includes(q) || s.name.includes(q)));

    const hit = [...exact, ...prefix, ...partial][0];
    if (hit) return { symbol: hit.sym };

    // 4. External Fallback (Only if Universe fails)
    try {
        const res = await fetch(`https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&region=IN`);
        const d = await res.json();
        const qts = (d.quotes || []).filter(x => x.symbol && (x.symbol.endsWith('.NS') || x.symbol.endsWith('.BO')));
        if (qts.length > 0) return { symbol: qts[0].symbol.replace('.NS','').replace('.BO','') };
    } catch (e) { dataLog(`Network Load Failed: ${q}`, 'error'); }

    return { symbol: 'FAILED', error: true };
}

function updateAlias(rawName, symbol) {
    const q = rawName.trim().toUpperCase();
    window.ALIAS_MAP[q] = symbol.toUpperCase().replace(/\.NS$/, '').trim();
    localStorage.setItem('bm_aliases', JSON.stringify(window.ALIAS_MAP));
}

// --- RESTORED: PAT Module (From image.png-58c7ebcb-f0c3-4ab0-97e0-e24805ed3e31) ---
async function testGitHubConnection() {
    const token = S.settings.ghToken?.trim();
    const repo = S.settings.ghRepo?.trim();
    const diag = document.getElementById('gh-diag');
    if(!diag || !token || !repo) return;
    
    diag.innerHTML = '<div style="color:#555">Checking...</div>';
    const h = { 'Authorization':'token '+token, 'Accept':'application/vnd.github.v3+json' };
    try {
        const r1 = await fetch('https://api.github.com/repos/'+repo, {headers:h});
        const r2 = await fetch('https://api.github.com/repos/'+repo+'/contents/.github/workflows/fetch-prices.yml', {headers:h});
        diag.innerHTML = `
            <div style="display:flex; justify-content:space-between; font-size:12px; margin-top:8px">
                <span style="color:#888">① Repo Access</span><span>${r1.ok?'✅':'❌'}</span>
            </div>
            <div style="display:flex; justify-content:space-between; font-size:12px">
                <span style="color:#888">② Workflow File</span><span>${r2.ok?'✅':'❌'}</span>
            </div>`;
    } catch(e) { dataLog("GitHub Connection Failed", "error"); }
}
