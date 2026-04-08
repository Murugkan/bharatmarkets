/** ONYX v18.0 - RESTORED WL_SEARCH RESOLUTION LOGIC */
window.S = JSON.parse(localStorage.getItem('bm_settings')) || { 
    settings: { ghToken: '', ghRepo: '' },
    watchlist: [],
    portfolio: [] 
};
window.ALIAS_MAP = JSON.parse(localStorage.getItem('bm_aliases')) || {};
window.FUND = window.FUND || {}; 

// --- RESTORED RESOLUTION FROM app-watchlist.js ---

function normalizeName(n) {
  if (!n) return '';
  return n.toString().toUpperCase()
    .replace(/\b(LTD|LIMITED|CORP|INC|PLC|EQUITY|EQ|IND|INDUSTRIES|SERVICES|GROUP|HOLDINGS)\b/g, '')
    .replace(/[^\w\s]/gi, '').replace(/\s+/g, ' ').trim();
}

async function resolveSymbol(rawName) {
  const q = normalizeName(rawName);
  
  // 1. Check User Alias Memory first
  if (window.ALIAS_MAP[q]) return { symbol: window.ALIAS_MAP[q], method: 'LEARNED' };

  // 2. Build Universe exactly as per wlSearch
  const universe = [...new Set([
    ...Object.keys(window.FUND),
    ...S.portfolio.map(h => h.sym)
  ])].map(sym => ({
    sym,
    name: (window.FUND[sym]?.name || sym).toUpperCase(),
  }));

  // 3. Apply wlSearch Filter Priority
  const exact   = universe.filter(s => s.sym === q);
  const prefix  = universe.filter(s => s.sym !== q && s.sym.startsWith(q));
  const partial = universe.filter(s => !s.sym.startsWith(q) && (s.sym.includes(q) || s.name.includes(q)));

  const hit = [...exact, ...prefix, ...partial][0];
  
  if (hit) return { symbol: hit.sym, method: 'INTERNAL' };

  // 4. Fallback to external if universe is empty
  try {
    const res = await fetch(`https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(q)}&region=IN`);
    const d = await res.json();
    const qts = (d.quotes || []).filter(x => x.symbol && (x.symbol.endsWith('.NS') || x.symbol.endsWith('.BO')));
    if (qts.length > 0) return { symbol: qts[0].symbol.replace('.NS','').replace('.BO',''), method: 'EXTERNAL' };
  } catch (e) { console.error("External lookup failed"); }

  return null;
}

function updateAlias(rawName, symbol) {
  const clean = normalizeName(rawName);
  window.ALIAS_MAP[clean] = symbol.toUpperCase().trim();
  localStorage.setItem('bm_aliases', JSON.stringify(window.ALIAS_MAP));
}

// --- FROZEN PAT MODULE ---
async function testGitHubConnection() {
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  const diag  = document.getElementById('gh-diag');
  if(!diag || !token || !repo) return;

  diag.style.display = 'block';
  diag.innerHTML = '<div style="color:#ffbf47;font-size:11px">Running…</div>';
  const headers = { 'Authorization':'token '+token, 'Accept':'application/vnd.github.v3+json' };
  const res = [{step:'① Repo',ok:null},{step:'② Workflow',ok:null},{step:'③ Trigger',ok:null}];

  try {
    const r1 = await fetch('https://api.github.com/repos/'+repo, {headers});
    res[0].ok = r1.ok;
    const r2 = await fetch('https://api.github.com/repos/'+repo+'/contents/.github/workflows/fetch-prices.yml', {headers});
    res[1].ok = r2.ok;
    const r3 = await fetch('https://api.github.com/repos/'+repo+'/actions/workflows/fetch-prices.yml/dispatches', {
      method:'POST', headers, body: JSON.stringify({ ref:'main', inputs:{ fetch_type:'prices_only' } })
    });
    res[2].ok = r3.status===204;
  } catch(e) {}

  diag.innerHTML = res.map(r => `<div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid #111;font-size:11px">
    <span style="color:#888">${r.step}</span><span>${r.ok?'✅':'❌'}</span></div>`).join('');
}
