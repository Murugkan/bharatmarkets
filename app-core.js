/** ONYX v17.0 - RESTORED SEARCH UNIVERSE & PAT MODULE */
window.S = JSON.parse(localStorage.getItem('bm_settings')) || { 
    settings: { ghToken: '', ghRepo: '' },
    watchlist: [],
    portfolio: [] 
};
window.ALIAS_MAP = JSON.parse(localStorage.getItem('bm_aliases')) || {};
window.FUND = window.FUND || {}; // Global Fundamentals store

// --- RESTORED: Universe-Based Resolution (from app-watchlist.js) ---

function normalizeName(n) {
  if (!n) return '';
  return n.toString().toUpperCase()
    .replace(/\b(LTD|LIMITED|CORP|INC|PLC|EQUITY|EQ|IND|INDUSTRIES|SERVICES|GROUP|HOLDINGS)\b/g, '')
    .replace(/[^\w\s]/gi, '').replace(/\s+/g, ' ').trim();
}

/** * Matches logic in wlSearch: Builds universe from FUND keys + portfolio symbols 
 *
 */
async function resolveSymbol(rawName) {
  const q = normalizeName(rawName);
  
  // Tier 1: User Alias Memory
  if (window.ALIAS_MAP[q]) return { symbol: window.ALIAS_MAP[q], method: 'LEARNED' };

  // Tier 2: Search Universe Construction
  const universe = [...new Set([
    ...Object.keys(window.FUND),
    ...S.portfolio.map(h => h.sym || h.symbol)
  ])].map(sym => ({
    sym,
    name: normalizeName(window.FUND[sym]?.name || sym),
  }));

  // Exact Match
  const exact = universe.find(s => s.sym === q || s.name === q);
  if (exact) return { symbol: exact.sym, method: 'UNIVERSE' };

  // Fuzzy Match (Prefix)
  const fuzzy = universe.find(s => s.sym.startsWith(q) || s.name.startsWith(q));
  if (fuzzy) return { symbol: fuzzy.sym, method: 'FUZZY' };

  // Tier 3: External Fallback (Yahoo)
  try {
    const res = await fetch(`https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&region=IN`);
    const data = await res.json();
    const quotes = (data.quotes || []).filter(q => q.symbol && (q.symbol.endsWith('.NS') || q.symbol.endsWith('.BO')));
    if (quotes.length > 0) return { symbol: quotes[0].symbol, method: 'AUTO' };
  } catch (e) { console.warn("External search blocked"); }
  
  return null;
}

function updateAlias(rawName, symbol) {
  const clean = normalizeName(rawName);
  window.ALIAS_MAP[clean] = symbol.toUpperCase().replace(/\.NS$/, '').trim();
  localStorage.setItem('bm_aliases', JSON.stringify(window.ALIAS_MAP));
}

// --- FROZEN: PAT & Diagnostic Module ---

async function testGitHubConnection() {
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  const diag  = document.getElementById('gh-diag');
  if(!diag || !token || !repo) return;

  diag.style.display = 'block';
  diag.innerHTML = '<div style="color:#ffbf47;font-size:11px">Running…</div>';
  const headers = { 'Authorization':'token '+token, 'Accept':'application/vnd.github.v3+json' };
  const results = [{step:'① Repo',ok:null},{step:'② Workflow',ok:null},{step:'③ Trigger',ok:null}];

  try {
    const r1 = await fetch('https://api.github.com/repos/'+repo, {headers});
    results[0].ok = r1.ok;
    const r2 = await fetch('https://api.github.com/repos/'+repo+'/contents/.github/workflows/fetch-prices.yml', {headers});
    results[1].ok = r2.ok;
    const r3 = await fetch('https://api.github.com/repos/'+repo+'/actions/workflows/fetch-prices.yml/dispatches', {
      method:'POST', headers, body: JSON.stringify({ ref:'main', inputs:{ fetch_type:'prices_only' } })
    });
    results[2].ok = r3.status===204;
  } catch(e) { console.error(e); }

  diag.innerHTML = results.map(r => `
    <div style="display:flex; justify-content:space-between; padding:4px 0; border-bottom:1px solid #111; font-size:11px">
      <span style="color:#888">${r.step}</span>
      <span style="color:${r.ok?'#00e896':'#ff6b85'}">${r.ok?'✅':'❌'}</span>
    </div>`).join('');
}
