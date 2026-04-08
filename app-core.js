window.S = JSON.parse(localStorage.getItem('bm_settings')) || { 
    settings: { ghToken: '', ghRepo: '' },
    portfolio: [],
    watchlist: []
};
window.ALIAS_MAP = JSON.parse(localStorage.getItem('bm_aliases')) || {};
window.FUND = window.FUND || {};

function dataLog(msg, type = 'info') {
    const log = document.getElementById('debug-console');
    if (!log) return;
    const colors = { info: '#aaa', error: '#ff6b85', success: '#00e896', warn: '#ffbf47' };
    const div = document.createElement('div');
    div.style.cssText = `border-bottom:1px solid #111; padding:6px; font-size:11px; color:${colors[type]}`;
    div.innerHTML = `<span style="color:#555">[${new Date().toLocaleTimeString()}]</span> ${msg}`;
    log.prepend(div);
}

async function resolveSymbol(val) {
    const raw = (val || "").toString().trim().toUpperCase();
    if(!raw || raw.includes("EQUITY SUMMARY") || raw === "STOCK NAME") return null;

    // 1. Clean the name for better matching
    const q = raw.replace(/\b(LTD|LIMITED|CORP|INC|PLC|EQUITY|EQ|IND|GROUP|HOLDINGS)\b/g, '').trim();

    // 2. Check Alias Map (Manual Fixes)
    if (window.ALIAS_MAP[raw]) return { symbol: window.ALIAS_MAP[raw] };

    // 3. Build Universe
    const portfolioSymbols = (window.S.portfolio || []).map(h => h.sym || h.symbol).filter(Boolean);
    const universe = [...new Set([...Object.keys(window.FUND), ...portfolioSymbols])].map(sym => ({
        sym,
        name: (window.FUND[sym]?.name || sym).toUpperCase(),
    }));

    // 4. Search Logic
    const exact = universe.filter(s => s.sym === q);
    const prefix = universe.filter(s => s.sym !== q && s.sym.startsWith(q));
    const partial = universe.filter(s => !s.sym.startsWith(q) && (s.sym.includes(q) || s.name.includes(q)));
    const hit = [...exact, ...prefix, ...partial][0];
    
    if (hit) return { symbol: hit.sym };

    // 5. Last Ditch Fetch
    try {
        const res = await fetch(`https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&region=IN`);
        const d = await res.json();
        const qts = (d.quotes || []).filter(x => x.symbol && (x.symbol.endsWith('.NS') || x.symbol.endsWith('.BO')));
        if (qts.length > 0) return { symbol: qts[0].symbol.replace('.NS','').replace('.BO','') };
    } catch (e) { 
        dataLog(`Network Failed: ${q}`, 'error'); 
    }

    return { symbol: 'FAILED', error: true };
}

function updateAlias(rawName, symbol) {
    const q = rawName.trim().toUpperCase();
    window.ALIAS_MAP[q] = symbol.toUpperCase().replace(/\.NS$/, '').trim();
    localStorage.setItem('bm_aliases', JSON.stringify(window.ALIAS_MAP));
    dataLog(`Mapped: ${symbol}`, 'success');
}

async function testGitHubConnection() {
    const token = document.getElementById('p').value;
    const repo = document.getElementById('r').value;
    window.S.settings = { ghToken: token, ghRepo: repo };
    localStorage.setItem('bm_settings', JSON.stringify(window.S));

    const diag = document.getElementById('gh-diag');
    diag.innerHTML = '<div style="color:#555">Checking...</div>';
    const h = { 'Authorization':'token '+token, 'Accept':'application/vnd.github.v3+json' };
    try {
        const r1 = await fetch('https://api.github.com/repos/'+repo, {headers:h});
        const r2 = await fetch('https://api.github.com/repos/'+repo+'/contents/.github/workflows/fetch-prices.yml', {headers:h});
        diag.innerHTML = `<div style="font-size:12px; margin-top:8px">Repo: ${r1.ok?'✅':'❌'} | Workflow: ${r2.ok?'✅':'❌'}</div>`;
    } catch(e) { dataLog("GitHub Fail", "error"); }
}
