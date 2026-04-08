/** ONYX v15.0 CORE - Professional Resolution + Original PAT Logic */
window.S = JSON.parse(localStorage.getItem('bm_settings')) || { settings: { ghToken: '', ghRepo: '' } };
window.ALIAS_MAP = JSON.parse(localStorage.getItem('bm_aliases')) || {};

// --- Tiered Resolution Engine (Professional Standard) ---

function normalizeName(n) {
  if (!n) return '';
  return n.toString().toUpperCase()
    .replace(/\b(LTD|LIMITED|CORP|INC|PLC|EQUITY|EQ|IND|INDUSTRIES|SERVICES|GROUP|HOLDINGS)\b/g, '')
    .replace(/[^\w\s]/gi, '').replace(/\s+/g, ' ').trim();
}

async function resolveSymbol(rawName) {
  const clean = normalizeName(rawName);
  
  // Tier 1: User Alias Memory
  if (window.ALIAS_MAP[clean]) return { symbol: window.ALIAS_MAP[clean], method: 'LEARNED' };

  // Tier 2: Dynamic Normalization Search
  try {
    const res = await fetch(`https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(clean)}&region=IN`);
    const data = await res.json();
    const quotes = (data.quotes || []).filter(q => q.symbol && (q.symbol.endsWith('.NS') || q.symbol.endsWith('.BO')));
    
    if (quotes.length > 0) {
      // Return first NSE/BSE match
      return { symbol: quotes[0].symbol, method: 'AUTO' };
    }
  } catch (e) { console.warn("Search blocked"); }
  
  return null;
}

function updateAlias(rawName, symbol) {
  const clean = normalizeName(rawName);
  window.ALIAS_MAP[clean] = symbol.toUpperCase().trim();
  localStorage.setItem('bm_aliases', JSON.stringify(window.ALIAS_MAP));
}

// --- Original PAT & Workflow Module (Frozen Logic) ---

async function testGitHubConnection() {
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  const diag  = document.getElementById('gh-diag');
  if(!diag || !token || !repo) return;

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

  diag.innerHTML = results.map(r => `<div>${r.step}: ${r.ok?'✅':'❌'}</div>`).join('');
}

async function manualTriggerWorkflow(type) {
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  const headers = { 'Authorization':'token '+token, 'Content-Type':'application/json' };
  await fetch(`https://api.github.com/repos/${repo}/actions/workflows/fetch-prices.yml/dispatches`, {
    method:'POST', headers, body: JSON.stringify({ ref:'main', inputs:{ fetch_type: type } })
  });
}
