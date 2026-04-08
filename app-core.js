/** ONYX v16.0 - RESTORED PAT MODULE + DYNAMIC RESOLUTION */
window.S = JSON.parse(localStorage.getItem('bm_settings')) || { settings: { ghToken: '', ghRepo: '' } };
window.ALIAS_MAP = JSON.parse(localStorage.getItem('bm_aliases')) || {};

// --- Tiered Resolution Engine (Professional & Dynamic) ---

function normalizeName(n) {
  if (!n) return '';
  // Clean legal and market noise without hard-coding specific stocks
  return n.toString().toUpperCase()
    .replace(/\b(LTD|LIMITED|CORP|INC|PLC|EQUITY|EQ|IND|INDUSTRIES|SERVICES|GROUP|HOLDINGS)\b/g, '')
    .replace(/[^\w\s]/gi, '').replace(/\s+/g, ' ').trim();
}

async function resolveSymbol(rawName) {
  const clean = normalizeName(rawName);
  
  // Tier 1: User Alias Memory (Learning from your manual fixes)
  if (window.ALIAS_MAP[clean]) return { symbol: window.ALIAS_MAP[clean], method: 'LEARNED' };

  // Tier 2: Dynamic Search (Bypasses hard-coded indices)
  try {
    const res = await fetch(`https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(clean)}&region=IN`);
    const data = await res.json();
    const quotes = (data.quotes || []).filter(q => q.symbol && (q.symbol.endsWith('.NS') || q.symbol.endsWith('.BO')));
    
    if (quotes.length > 0) return { symbol: quotes[0].symbol, method: 'AUTO' };
  } catch (e) { console.warn("Search blocked by browser"); }
  
  return null; // Triggers "FAILED" UI for manual input
}

function updateAlias(rawName, symbol) {
  const clean = normalizeName(rawName);
  window.ALIAS_MAP[clean] = symbol.toUpperCase().trim();
  localStorage.setItem('bm_aliases', JSON.stringify(window.ALIAS_MAP));
}

// --- ORIGINAL PAT MODULE (Direct Port from app-watchlist.js) ---

async function testGitHubConnection() {
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  const diag  = document.getElementById('gh-diag');
  if(!diag) return;

  if(!token || !repo){
    diag.style.display = 'block';
    diag.innerHTML = '<div style="color:#ff6b85;font-size:11px">⚠ Enter Repo and PAT first</div>';
    return;
  }

  diag.style.display = 'block';
  diag.innerHTML = '<div style="color:#ffbf47;font-size:11px">Running…</div>';

  const headers = { 'Authorization':'token '+token, 'Accept':'application/vnd.github.v3+json' };
  const results = [{step:'① Repo',ok:null},{step:'② Workflow',ok:null},{step:'③ Trigger',ok:null}];

  // ① Repo Check
  try {
    const r = await fetch('https://api.github.com/repos/'+repo, {headers});
    results[0].ok = r.ok;
  } catch(e) { results[0].ok=false; }

  // ② Workflow Check
  try {
    const r = await fetch('https://api.github.com/repos/'+repo+'/contents/.github/workflows/fetch-prices.yml', {headers});
    results[1].ok = r.ok;
  } catch(e) { results[1].ok=false; }

  // ③ Trigger Test
  try {
    const r = await fetch('https://api.github.com/repos/'+repo+'/actions/workflows/fetch-prices.yml/dispatches', {
      method:'POST', headers, body: JSON.stringify({ ref:'main', inputs:{ fetch_type:'prices_only' } })
    });
    results[2].ok = r.status===204;
  } catch(e) { results[2].ok=false; }

  diag.innerHTML = results.map(r => `
    <div style="display:flex; justify-content:space-between; font-size:11px; padding:4px 0; border-bottom:1px solid #111">
      <span style="color:#888">${r.step}</span>
      <span style="color:${r.ok?'#00e896':'#ff6b85'}">${r.ok?'✓':'✗'}</span>
    </div>`).join('');
}

async function manualTriggerWorkflow(fetchType) {
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  const headers = { 'Authorization':'token '+token, 'Content-Type':'application/json', 'Accept':'application/vnd.github.v3+json' };
  try {
    const r = await fetch('https://api.github.com/repos/'+repo+'/actions/workflows/fetch-prices.yml/dispatches', {
      method:'POST', headers, body: JSON.stringify({ ref:'main', inputs:{ fetch_type: fetchType } })
    });
    return r.status === 204;
  } catch(e) { return false; }
}
