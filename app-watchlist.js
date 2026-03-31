function renderWatchlist(c){
  // Merge live fundamentals into each watchlist item
  const wl = S.watchlist.map(w=>{
    const f = FUND[w.symbol] || {};
    const ltp = f.ltp || w.ltp || 0;
    return {
      ...w,
      ltp,
      change:   w.change || f.chg1d || 0,
      pe:       f.pe     || null,
      pb:       f.pb     || null,
      roe:      f.roe    || null,
      roce:     f.roce   || null,
      opm:      f.opm_pct|| null,
      week52H:  f.w52h   || null,
      week52L:  f.w52l   || null,
      mcap:     f.mcap   || null,
      eps:      f.eps    || null,
      beta:     f.beta   || null,
      div:      f.div_yield || null,
      debt_eq:  f.debt_eq  || null,
      score:    w.score  || 65,
    };
  });
  const gainers=wl.filter(s=>s.change>0);
  const avg=wl.length?Math.round(wl.reduce((a,s)=>a+(s.score||65),0)/wl.length):0;

  c.innerHTML=`<div class="fin">

  ${!wl.length?`<div class="empty-state"><div class="empty-icon">👁</div><div class="empty-title">Watchlist Empty</div><div class="empty-sub">Search below to add stocks</div></div>`:`
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:7px;padding:10px 13px 8px">
    <div class="card" style="text-align:center;border-top:2px solid var(--ac)">
      <div style="font-size:8px;color:var(--label);text-transform:uppercase;font-weight:700;letter-spacing:.8px">Watching</div>
      <div style="font-family:var(--mono);font-size:18px;font-weight:700;color:var(--ac);margin-top:4px">${wl.length}</div>
    </div>
    <div class="card" style="text-align:center;border-top:2px solid var(--gr)">
      <div style="font-size:8px;color:var(--label);text-transform:uppercase;font-weight:700;letter-spacing:.8px">Rising</div>
      <div style="font-family:var(--mono);font-size:18px;font-weight:700;color:var(--gr2);margin-top:4px">${gainers.length}/${wl.length}</div>
    </div>
  </div>
  <div style="padding:0 13px 80px">
    ${wl.map(s=>{
      const bull=s.change>=0, col=bull?'var(--gr2)':'var(--rd2)';
      const m2 = (k,v,u) => v!=null&&v!==0&&v!==''?'<span style="color:var(--tx3);font-size:8px">'+k+'</span><span style="color:var(--tx2);font-size:9px;font-family:var(--mono);margin-right:8px"> '+v+u+'</span>':'';
      return '<div style="padding:8px 0;border-bottom:1px solid var(--b1)">'
        +'<div style="display:flex;justify-content:space-between;align-items:center;cursor:pointer;margin-bottom:3px" onclick="openStock('+JSON.stringify(s).replace(/"/g,"'")+')"><div>'
        +'<span style="font-size:12px;font-weight:700;color:var(--tx1);font-family:var(--mono)">'+s.symbol+'</span>'
        +'<span style="font-size:9px;color:var(--tx3);margin-left:6px">'+trunc(s.name,22)+'</span>'
        +'</div><div class="u-row">'
        +'<span style="font-size:12px;font-weight:700;color:var(--tx1);font-family:var(--mono)">'+(s.ltp>0?'₹'+s.ltp.toFixed(1):'—')+'</span>'
        +'<span style="font-size:10px;font-weight:600;color:'+col+'">'+(bull?'▲':'▼')+Math.abs(s.change).toFixed(1)+'%</span>'
        +'<button onclick="event.stopPropagation();removeFromWL(this.getAttribute(\'data-sym\'))" data-sym="'+s.symbol+'" style="background:none;border:none;color:#3a5a72;font-size:12px;cursor:pointer;padding:0 4px">✕</button>'
        +'</div></div>'
        +'<div style="display:flex;flex-wrap:wrap;gap:0;align-items:center">'
        +m2('PE',s.pe?fn(s.pe,1):null,'x')
        +m2('ROE',s.roe?fn(s.roe,1):null,'%')
        +m2('OPM',s.opm?fn(s.opm,1):null,'%')
        +m2('PB',s.pb?fn(s.pb,1):null,'x')
        +m2('DE',s.debt_eq!=null?fn(s.debt_eq,1):null,'x')
        +m2('EPS',s.eps?'₹'+fn(s.eps,1):null,'')
        +(s.mcap?'<span style="color:var(--tx3);font-size:8px">MCap</span><span style="color:var(--tx2);font-size:9px;font-family:var(--mono);margin-right:8px"> '+s.mcap+'Cr</span>':'')
        +'</div></div>';
    }).join('')}
  </div>`}

  <div style="padding:10px 13px;background:var(--bg);border-top:1px solid var(--b1);position:sticky;bottom:56px">
    <div class="search-box" style="margin:0">
      <span class="srch-ico">🔍</span>
      <input class="srch-inp" id="wl-add-inp" type="text"
        placeholder="Search symbol or name to add…"
        autocapitalize="characters" autocomplete="off" spellcheck="false"
        oninput="wlSearch(this.value)"
        value="${S.wlSearch||''}"/>
    </div>
    <div id="wl-results" style="margin-top:4px"></div>
  </div>

  </div>`;

  // Re-render search results if there's an active query
  if(S.wlSearch) wlSearch(S.wlSearch);
}

// Live search across NSE_DB (300+ symbols)
function wlSearch(val){
  S.wlSearch = val.trim();
  const el = document.getElementById('wl-results');
  if(!el) return;
  if(!S.wlSearch){el.innerHTML='';return;}

  const q = S.wlSearch.toUpperCase();
  const already = new Set(S.watchlist.map(w=>w.symbol));

  // Search NSE_DB — by symbol prefix first, then name contains
  const exact   = NSE_DB.filter(s=>s.sym===q);
  const prefix  = NSE_DB.filter(s=>s.sym!==q&&s.sym.startsWith(q));
  const partial = NSE_DB.filter(s=>!s.sym.startsWith(q)&&(s.sym.includes(q)||s.name.toUpperCase().includes(q)||s.sector.toUpperCase().includes(q)));
  const hits = [...exact,...prefix,...partial].filter(s=>!already.has(s.sym)).slice(0,8);

  if(!hits.length){
    el.innerHTML=`<div class="srch-results"><div style="padding:12px;text-align:center;font-size:11px;color:var(--mu)">No results for "${S.wlSearch}"</div></div>`;
    return;
  }

  el.innerHTML=`<div class="srch-results">
    ${hits.map(h=>`
      <div class="sr-row" onclick="addToWL('${h.sym}')">
        <div>
          <div class="sr-sym">${h.sym}</div>
          <div class="sr-name">${h.name}</div>
          <div class="sr-sect">${h.sector}</div>
        </div>
        <span class="sr-add">+ Add</span>
      </div>`).join('')}
  </div>`;
}

// Add stock to watchlist + sync to GitHub
function addToWL(sym){
  sym = sym.toUpperCase().replace(/\.NS$/,'');
  if(S.watchlist.find(w=>w.symbol===sym)){toast(sym+' already in watchlist');return;}
  const info = NSE_DB.find(s=>s.sym===sym)||{name:sym,sector:'Diversified'};
  S.watchlist.push({
    symbol:sym, name:info.name, sector:info.sector,
    ltp:0, change:0,
  });
  S.wlSearch='';
  saveWL();
  syncWatchlistToGitHub(sym);
  render();
}

// Remove stock from watchlist + sync to GitHub
function removeFromWL(sym){
  S.watchlist=S.watchlist.filter(w=>w.symbol!==sym);
  saveWL();
  syncWatchlistToGitHub(null);
  render();
}

// ── GitHub API: Push index.html to repo ───────────────────
// GITHUB API — push index.html, sync watchlist, diagnostics
async function pushIndexToGitHub(){
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  if(!token || !repo){
    toast('⚠ Set GitHub repo and PAT in Settings first');
    return;
  }

  toast('⬆ Pushing to GitHub…');

  try {
    const headers = {
      'Authorization': 'token '+token,
      'Content-Type':  'application/json',
      'Accept':        'application/vnd.github.v3+json',
    };

    const fileUrl = `https://api.github.com/repos/${repo}/contents/index.html`;

    // Get current SHA
    let sha = null;
    try {
      const get = await fetch(fileUrl, {headers});
      if(get.ok){ const d = await get.json(); sha = d.sha; }
    } catch(e){}

    // Get HTML from document directly — no network fetch needed
    const html = '<!DOCTYPE html>\n' + document.documentElement.outerHTML;
    
    // Encode to base64
    const encoded = btoa(unescape(encodeURIComponent(html)));

    const body = {
      message: 'BharatMarkets: update ' + new Date().toLocaleString('en-IN',{timeZone:'Asia/Kolkata'}),
      content: encoded,
    };
    if(sha) body.sha = sha;

    const put = await fetch(fileUrl, {method:'PUT', headers, body:JSON.stringify(body)});

    if(put.ok){
      toast('✅ Pushed to '+repo+' — Pages rebuilding (~1 min)');
      const btn = document.getElementById('push-btn');
      if(btn){ btn.textContent='✅ Pushed!'; btn.style.background='rgba(0,232,150,.2)'; }
      setTimeout(()=>{
        if(btn){ btn.textContent='⬆ Push index.html to GitHub'; btn.style.background=''; }
      }, 4000);
    } else {
      const err = await put.json();
      toast('❌ Push failed: '+(err.message||put.status));
    }
  } catch(e){
    toast('❌ Error: '+e.message);
  }
}

function headerPricesTap(){
  // Spin the ↻ while fetching
  const spin = document.getElementById('hdr-prices-spin');
  if(spin){ spin.classList.add('spin'); }
  refreshPortfolioData().finally(()=>{
    if(spin) spin.classList.remove('spin');
  });
}

async function headerFundTap(){
  const spin = document.getElementById('hdr-fund-spin');
  if(spin){ spin.classList.add('spin'); }
  try{
    await manualTriggerWorkflow('fundamentals_only');
  } finally {
    if(spin) spin.classList.remove('spin');
  }
}

function toggleKeyVis(id){
  const el = document.getElementById(id);
  if(!el) return;
  el.type = el.type==='password' ? 'text' : 'password';
}

function updateGhDots(){
  // Re-render watchlist to reflect new dot states
  if(S.curTab==='watchlist') render();
}

// 3-step diagnostic: ① repo access ② workflow file ③ trigger
async function manualTriggerWorkflow(fetchType){
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  if(!token || !repo){
    toast('⚠ Configure GitHub repo + PAT in settings first');
    return;
  }
  const diag = document.getElementById('fetch-result') || document.getElementById('gh-diag');
  if(diag){ diag.style.display='block'; diag.innerHTML='<span class="u-yel">⏳ Triggering '+fetchType+' fetch…</span>'; }

  const headers = { 'Authorization':'token '+token, 'Content-Type':'application/json', 'Accept':'application/vnd.github.v3+json' };
  try{
    const r = await fetch('https://api.github.com/repos/'+repo+'/actions/workflows/fetch-prices.yml/dispatches', {
      method:'POST', headers,
      body: JSON.stringify({ ref:'main', inputs:{ fetch_type: fetchType } })
    });
    if(r.status === 204){
      const msg = '✅ Workflow triggered — check GitHub Actions tab for progress (~5 min)';
      if(diag){ diag.innerHTML='<span class="u-grn">'+msg+'</span>'; }
      S.settings._lastSync = Date.now();
      S.settings._lastSyncOk = true;
      S.settings._lastSyncMsg = fetchType+' triggered manually';
      saveSettings();
      toast('✅ '+fetchType+' workflow triggered');
    } else if(r.status === 403){
      const msg = '❌ 403 — PAT needs "workflow" scope. Go to github.com/settings/tokens and regenerate with repo + workflow scopes.';
      if(diag){ diag.innerHTML='<div class="u-red">'+msg+'</div>'; }
      toast('❌ PAT missing workflow scope');
    } else if(r.status === 422){
      const msg = '❌ 422 — workflow file not found. Ensure fetch-prices.yml is in .github/workflows/ on main branch.';
      if(diag){ diag.innerHTML='<div class="u-red">'+msg+'</div>'; }
    } else {
      const e = await r.json().catch(()=>({}));
      const msg = '❌ '+r.status+': '+(e.message||'unknown error');
      if(diag){ diag.innerHTML='<div class="u-red">'+msg+'</div>'; }
      toast(msg);
    }
  } catch(e){
    const msg = '❌ Network error: '+e.message;
    if(diag){ diag.innerHTML='<div class="u-red">'+msg+'</div>'; }
    toast(msg);
  }
}

async function testGitHubConnection(){
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  const diag  = document.getElementById('gh-diag');
  if(!diag) return;

  if(!token || !repo){
    diag.style.display = 'block';
    diag.innerHTML = diagRow('⚠ Enter Repository and GitHub PAT first', null, null);
    return;
  }

  diag.style.display = 'block';
  diag.innerHTML = '<div style="color:#ffbf47;font-size:11px">Running…</div>';

  const headers = { 'Authorization':'token '+token, 'Accept':'application/vnd.github.v3+json' };
  const results = [{step:'① Repo',ok:null,fix:null},{step:'② Workflow',ok:null,fix:null},{step:'③ Trigger',ok:null,fix:null}];
  let allOk = true, failMsg = '';

  function render(){
    const rows = results.map(r=>{
      const icon = r.ok===null?'<span style="color:#4a6888">—</span>':r.ok?'<span class="u-grn">✓</span>':'<span class="u-red">✗</span>';
      const fix  = (!r.ok&&r.ok!==null&&r.fix)?` <a href="${r.fix}" target="_blank" style="font-size:10px;color:#64b5f6;text-decoration:none;margin-left:4px">Fix ↗</a>`:'';
      return `<div style="display:flex;align-items:center;gap:8px;padding:4px 0;border-bottom:1px solid var(--b1)">
        <span style="font-size:11px;color:var(--tx3);width:80px;flex-shrink:0">${r.step}</span>
        <span style="font-size:12px">${icon}</span>${fix}
      </div>`;
    }).join('');
    const summary = allOk && results.every(r=>r.ok!==null)
      ? '<div style="margin-top:8px;font-size:11px;font-weight:700;color:#00e896">✅ Auto-fetch working</div>'
      : failMsg ? '<div style="margin-top:8px;font-size:11px;font-weight:700;color:#ff6b85">❌ '+failMsg+'</div>' : '';
    diag.innerHTML = rows + summary;
  }
  render();

  // ① Repo
  try{
    const r = await fetch('https://api.github.com/repos/'+repo, {headers});
    results[0].ok = r.ok;
    if(!r.ok){ allOk=false; failMsg='Auth failed — check PAT'; results[0].fix='https://github.com/settings/tokens'; }
  } catch(e){ results[0].ok=false; allOk=false; failMsg='Network error'; }
  render();

  // ② Workflow
  try{
    const r = await fetch('https://api.github.com/repos/'+repo+'/contents/.github/workflows/fetch-prices.yml', {headers});
    results[1].ok = r.ok;
    if(!r.ok){ allOk=false; failMsg='fetch-prices.yml not found'; results[1].fix='https://github.com/'+repo+'/tree/main/.github/workflows'; }
  } catch(e){ results[1].ok=false; allOk=false; failMsg='Network error'; }
  render();

  // ③ Trigger
  try{
    const r = await fetch('https://api.github.com/repos/'+repo+'/actions/workflows/fetch-prices.yml/dispatches', {
      method:'POST', headers,
      body: JSON.stringify({ ref:'main', inputs:{ fetch_type:'prices_only' } })
    });
    results[2].ok = r.status===204;
    if(!results[2].ok){
      allOk=false;
      if(r.status===403){ failMsg='PAT needs "workflow" scope'; results[2].fix='https://github.com/settings/tokens/new?scopes=repo,workflow&description=BharatMarkets'; }
      else if(r.status===422){ failMsg='Workflow not found on main branch'; }
      else { failMsg='Trigger failed ('+r.status+')'; }
    }
  } catch(e){ results[2].ok=false; allOk=false; failMsg='Network error'; }
  render();

  S.settings._ghStatus = allOk ? 'ok' : 'fail';
  saveSettings();
  if(S.curTab==='watchlist') render();
}

// Commit watchlist.txt to GitHub + trigger workflow for new symbols
async function syncWatchlistToGitHub(newSym){
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  if(!token || !repo){
    if(newSym) toast('⚠ GitHub not configured — set PAT in Watchlist settings');
    return;
  }

  const headers = {
    'Authorization': 'token '+token,
    'Content-Type':  'application/json',
    'Accept':        'application/vnd.github.v3+json',
  };

  try {
    // Step 1: Commit updated watchlist.txt
    const symbols = S.watchlist.map(w=>w.symbol).join('\n');
    const encoded = btoa(unescape(encodeURIComponent(symbols)));
    const fileUrl = `https://api.github.com/repos/${repo}/contents/watchlist.txt`;

    let sha = null;
    const get = await fetch(fileUrl, {headers});
    if(get.ok){ const d = await get.json(); sha = d.sha; }

    const fileBody = { message: newSym ? 'watchlist: add '+newSym : 'watchlist: update', content: encoded };
    if(sha) fileBody.sha = sha;
    const put = await fetch(fileUrl, { method:'PUT', headers, body:JSON.stringify(fileBody) });
    if(!put.ok){
      const err = await put.json();
      S.settings._lastSync=Date.now();S.settings._lastSyncOk=false;S.settings._lastSyncMsg=err.message||put.status;saveSettings();
      toast('⚠ GitHub sync failed: '+(err.message||put.status));
      return;
    }

    // Step 2: Trigger workflow_dispatch — wait 2s for watchlist.txt commit to land
    if(newSym){
      await new Promise(r=>setTimeout(r, 2000));
      const wfUrl = `https://api.github.com/repos/${repo}/actions/workflows/fetch-prices.yml/dispatches`;
      const wfRes = await fetch(wfUrl, {
        method: 'POST',
        headers,
        body: JSON.stringify({ ref:'main', inputs:{ fetch_type:'new_symbol', symbol:newSym } })
      });
      if(wfRes.status === 204){
        S.settings._lastSync=Date.now();S.settings._lastSyncOk=true;S.settings._lastSyncMsg=newSym+' added';saveSettings();
      toast('✅ '+newSym+' synced — fetching data (~3 min)');
      } else if(wfRes.status === 403){
        toast('⚠ PAT needs "workflow" scope — regenerate at github.com/settings/tokens');
      } else if(wfRes.status === 422){
        toast('⚠ Workflow not found — commit fetch-prices.yml to .github/workflows/');
      } else {
        const e = await wfRes.json().catch(()=>({}));
        toast('⚠ Trigger failed ('+wfRes.status+'): '+(e.message||'run Actions manually'));
      }
    } else {
      S.settings._lastSync=Date.now();S.settings._lastSyncOk=true;S.settings._lastSyncMsg='watchlist updated';saveSettings();
      toast('✅ watchlist.txt synced to GitHub');
    }
  } catch(e){
    toast('⚠ GitHub error: '+e.message);
  }
}

//  FIX #2: MACRO TAB — fully populated
// MACRO TAB — India macro indicators + live RSS news
function renderMacro(c){
  const filtered = S.macroFilter==='ALL'
    ? MACRO_DATA
    : MACRO_DATA.filter(m=>m.tag===S.macroFilter);

  c.innerHTML=`<div class="fin">
  <div style="padding:12px 13px 8px;display:flex;justify-content:space-between;align-items:center">
    <div>
      <div style="font-family:'Syne',sans-serif;font-size:15px;font-weight:700;color:var(--title)">India Macro Dashboard</div>
      <div class="u-tx3-10mt">Tap any indicator for detailed analysis</div>
    </div>
  </div>

  <!-- Filter chips -->
  <div class="chip-row">
    ${['ALL','RBI','MACRO','OIL','FII','GEO'].map(f=>`
      <div class="chip ${S.macroFilter===f?'active':''}" onclick="setMacroFilter('${f}')">${f}</div>`).join('')}
  </div>

  <!-- Macro cards -->
  <div style="padding:8px 13px 14px">
    ${filtered.map((m,i)=>`
      <div class="macro-card ${S.expMacro===i?'exp':''}" onclick="toggleMacro(${i})" style="border-left:3px solid ${m.ic}">
        <div class="u-sb-top">
          <div style="flex:1">
            <div style="display:flex;align-items:center;gap:7px;margin-bottom:4px">
              <span style="font-size:16px">${m.icon}</span>
              <span class="macro-name">${m.label}</span>
            </div>
            <div class="macro-val">${m.val}</div>
            <div class="macro-trend" style="color:${m.ic}">${m.trend}</div>
          </div>
          <div style="display:flex;flex-direction:column;align-items:flex-end;gap:5px">
            <span class="pill" style="background:${m.ic}18;color:${m.ic};border:1px solid ${m.ic}40">${m.impact}</span>
            <span class="pill pill-ac">${m.tag}</span>
          </div>
        </div>
        ${S.expMacro===i?`<div class="macro-detail">${m.detail}</div>`:''}
      </div>`).join('')}
  </div>

  <!-- FIX #2: Live news section from RSS -->
  <div style="padding:0 13px">
    <div class="sec-lbl">Live Market News</div>
    <div id="macro-news-list">
      <div style="text-align:center;padding:20px;color:var(--mu);font-size:11px">Loading news…</div>
    </div>
  </div>
  </div>`;

  // Load news asynchronously
  loadMacroNews();
}

function setMacroFilter(f){
  S.macroFilter=f;
  if(S.curTab==='macro')renderMacro(document.getElementById('content'));
}
function toggleMacro(i){
  S.expMacro=S.expMacro===i?null:i;
  if(S.curTab==='macro')renderMacro(document.getElementById('content'));
}

// FIX #2 & #3: RSS News loader
async function loadMacroNews(){
  const el=document.getElementById('macro-news-list');
  if(!el)return;
  const FEEDS=[
    'https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms',
    'https://economictimes.indiatimes.com/economy/rssfeeds/1373380680.cms',
  ];
  const all=[];
  for(const feed of FEEDS){
    try{
      const url='https://api.rss2json.com/v1/api.json?rss_url='+encodeURIComponent(feed)+'&count=10';
      const res=await fetch(url,{signal:AbortSignal.timeout?AbortSignal.timeout(8000):undefined});
      const d=await res.json();
      if(d.status==='ok')all.push(...(d.items||[]));
    }catch(_){}
  }
  // Deduplicate
  const seen=new Set();
  const items=all.filter(i=>{if(seen.has(i.title))return false;seen.add(i.title);return true;})
    .sort((a,b)=>new Date(b.pubDate)-new Date(a.pubDate))
    .slice(0,12);

  if(!items.length){
    el.innerHTML=`<div class="u-pad14c">Could not load news — check connection</div>`;
    return;
  }

  const filterTag=S.macroFilter;
  const filtered=filterTag==='ALL'?items:items.filter(i=>classifyNews(i.title).tag===filterTag);

  el.innerHTML=(filtered.length?filtered:items).map(item=>{
    const{tag,imp}=classifyNews(item.title);
    const src=item.source?.name||extractDomain(item.link)||'ET Markets';
    const body=item.description?item.description.replace(/<[^>]+>/g,'').slice(0,120)+'…':'';
    return `<div class="news-item">
      <div class="news-src">
        <span>${src}</span>
        <span class="imp-badge imp-${imp}">${imp==='H'?'HIGH':imp==='M'?'MED':'LOW'}</span>
        <span class="pill pill-bl" style="font-size:7px">${tag}</span>
        <span>${timeAgo(new Date(item.pubDate))}</span>
      </div>
      <div class="news-title">${item.title}</div>
      ${body?`<div class="news-body">${body}</div>`:''}
    </div>`;
  }).join('');
}

//  MOVERS TAB
// MOVERS TAB — gainers/losers/sector heatmap from live prices
// Data: portfolio + watchlist stocks with live LTP
function renderMovers(c){
  // Universe = portfolio + watchlist stocks only (not stale/irrelevant symbols)
  const pfSyms = new Set(S.portfolio.map(h=>h.sym));
  const wlSyms = new Set(S.watchlist.map(w=>w.symbol));
  const tracked = new Set([...pfSyms, ...wlSyms]);

  // Build live price lookup from portfolio + watchlist (updated by refreshPortfolioData)
  const livePrices = {};
  S.portfolio.forEach(h=>{ if(h.ltp>0) livePrices[h.sym] = {ltp:h.ltp, chg:h.change||h.chg1d||0}; });
  S.watchlist.forEach(w=>{ if(w.ltp>0) livePrices[w.symbol] = {ltp:w.ltp, chg:w.change||0}; });

  const universe = [...tracked]
    .map(sym=>{
      const f    = FUND[sym] || {};
      const live = livePrices[sym] || {};
      return {
        sym,
        ltp:    live.ltp  || f.ltp    || 0,
        chg:    live.chg  || f.chg1d  || 0,
        sector: f.sector  || '—',
        name:   f.name    || sym,
        mcap:   f.mcap    || 0,
        pe:     f.pe      || null,
        inPF:   pfSyms.has(sym),
      };
    })
    .filter(s => s.ltp > 0 && s.chg !== 0);

  // Sort for gainers/losers
  const gainers = [...universe].sort((a,b)=>b.chg-a.chg).slice(0,8);
  const losers  = [...universe].sort((a,b)=>a.chg-b.chg).slice(0,8);

  // Index data from FUND (fetched as special symbols)
  const indexMap = {
    'NIFTY':            'NIFTY 50',
    'BANKNIFTY':        'Bank Nifty',
    'NIFTYMIDCAP100':   'Midcap 100',
    'CNXIT':            'Nifty IT',
    'NIFTYPSE':         'Nifty PSE',
    'NIFTYSMALLCAP100': 'Smallcap 100',
  };
  const indices = Object.entries(indexMap).map(([sym, name])=>{
    const f = FUND[sym] || {};
    return { name, ltp: f.ltp||0, chg: f.chg1d||0, prev: f.prev||0 };
  }).filter(i=>i.ltp>0);

  // Sector performance — average chg1d by sector
  const sectorData = {};
  universe.forEach(s=>{
    if(!s.sector||s.sector==='—') return;
    if(!sectorData[s.sector]) sectorData[s.sector] = {sum:0, n:0};
    sectorData[s.sector].sum += s.chg;
    sectorData[s.sector].n++;
  });
  const sectors = Object.entries(sectorData)
    .map(([s,d])=>({name:s, avg: d.sum/d.n}))
    .filter(s=>s.avg!==0)
    .sort((a,b)=>Math.abs(b.avg)-Math.abs(a.avg))
    .slice(0,10);

  const fundLoaded = Object.keys(FUND).length > 0;
  const fundKeys = Object.keys(FUND);
  const dataTime = fundKeys.length > 0 && FUND[fundKeys[0]]?.updated
    ? new Date(FUND[fundKeys[0]].updated).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:true})
    : '—';

  c.innerHTML=`<div class="fin" style="padding:12px 13px 14px">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <div style="font-family:'Syne',sans-serif;font-size:15px;font-weight:700;color:var(--title)">Market Movers</div>
      <div style="font-size:9px;color:var(--tx3);font-family:var(--mono)">
        ${fundLoaded ? universe.length+' stocks · '+dataTime : '⚠ Run Actions to load data'}
      </div>
    </div>

    ${!fundLoaded ? `<div style="padding:30px;text-align:center;color:var(--tx3);font-size:11px">
      No data yet — import portfolio or configure GitHub Sync in Watchlist settings
    </div>` : `

    <!-- Indices -->
    ${indices.length ? `<div class="card" style="margin-bottom:10px">
      <div style="font-weight:700;font-size:11px;color:var(--title);margin-bottom:8px;font-family:'Syne',sans-serif">📊 Index Snapshot</div>
      ${indices.map(i=>{
        const up=i.chg>=0;
        const pts = i.prev>0 ? ((i.chg/100)*i.prev).toFixed(0) : '—';
        return `<div style="display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-bottom:1px solid var(--b1)">
          <div style="font-size:11px;font-weight:600;color:var(--tx2)">${i.name}</div>
          <div class="u-tar">
            <div style="font-size:12px;font-weight:700;font-family:var(--mono);color:var(--tx1)">₹${i.ltp.toLocaleString('en-IN')}</div>
            <div style="font-size:10px;font-weight:700;color:${up?'#00e896':'#ff6b85'}">${up?'▲':'▼'} ${Math.abs(i.chg).toFixed(2)}% ${up?'+':''}${pts}pts</div>
          </div>
        </div>`;
      }).join('')}
    </div>` : ''}

    <!-- Gainers / Losers -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:12px">
      <div class="card">
        <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:12px;color:var(--gr2);padding-bottom:7px;margin-bottom:8px;border-bottom:1px solid var(--b1)">🟢 Top Gainers</div>
        ${gainers.length ? gainers.map(s=>`
          <div class="mover-row" style="border-left-color:var(--gr)">
            <div style="min-width:0;flex:1">
              <div class="mover-sym">${s.sym}</div>
              <div class="mover-why">${s.sector}</div>
            </div>
            <div class="u-tar-fs0">
              <div style="color:#00e896;font-weight:700;font-size:11px">+${s.chg.toFixed(2)}%</div>
              <div style="color:var(--tx3);font-size:9px">₹${s.ltp.toFixed(1)}</div>
            </div>
          </div>`).join('') : '<div style="color:var(--tx3);font-size:10px">No gainers today</div>'}
      </div>
      <div class="card">
        <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:12px;color:var(--rd2);padding-bottom:7px;margin-bottom:8px;border-bottom:1px solid var(--b1)">🔴 Top Losers</div>
        ${losers.length ? losers.map(s=>`
          <div class="mover-row" style="border-left-color:var(--rd)">
            <div style="min-width:0;flex:1">
              <div class="mover-sym">${s.sym}</div>
              <div class="mover-why">${s.sector}</div>
            </div>
            <div class="u-tar-fs0">
              <div style="color:#ff6b85;font-weight:700;font-size:11px">${s.chg.toFixed(2)}%</div>
              <div style="color:var(--tx3);font-size:9px">₹${s.ltp.toFixed(1)}</div>
            </div>
          </div>`).join('') : '<div style="color:var(--tx3);font-size:10px">No losers today</div>'}
      </div>
    </div>

    <!-- Sector Heatmap — canvas treemap -->
    <div class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:11px;color:var(--title)">🗺 Sector Heatmap</div>
        <div style="display:flex;gap:6px;font-size:9px;color:var(--tx3)">
          <span>Size = Portfolio Value</span>
          <span class="u-grn">■ Up</span>
          <span class="u-red">■ Down</span>
        </div>
      </div>
      <canvas id="cv-heatmap" style="width:100%;border-radius:6px;cursor:pointer"></canvas>
      <div id="hm-tooltip" style="display:none;position:fixed;background:#0d1929;border:1px solid #1e3350;border-radius:8px;padding:8px 12px;font-family:var(--mono);font-size:10px;color:var(--tx1);pointer-events:none;z-index:999"></div>
    </div>

    <!-- My sector bar chart -->
    ${sectors.length ? `<div class="card" class="u-mt10">
      <div style="font-family:'Syne',sans-serif;font-weight:700;font-size:11px;color:var(--title);margin-bottom:10px">📊 My Sectors</div>
      <div style="display:flex;flex-direction:column;gap:5px">
        ${sectors.map(s=>{
          const up = s.avg>=0;
          const barW = Math.min(100, Math.abs(s.avg)*15).toFixed(0);
          return `<div class="u-row">
            <div style="width:90px;font-size:9px;color:var(--tx2);text-align:right;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${s.name}</div>
            <div style="flex:1;background:var(--s2);border-radius:3px;height:13px;position:relative;overflow:hidden">
              <div style="position:absolute;${up?'left:0':'right:0'};top:0;height:100%;width:${barW}%;background:${up?'rgba(0,208,132,.4)':'rgba(255,59,92,.4)'};border-radius:3px"></div>
            </div>
            <div style="width:40px;font-size:9px;font-weight:700;color:${up?'#00e896':'#ff6b85'};font-family:var(--mono);text-align:right">${up?'+':''}${s.avg.toFixed(2)}%</div>
          </div>`;
        }).join('')}
      </div>
    </div>` : ''}
    `}
  </div>`;

  // Draw heatmap after DOM renders
  requestAnimationFrame(()=>requestAnimationFrame(()=>drawSectorHeatmap(universe)));
}

// ── Sector Heatmap Treemap ────────────────────────────
// Squarified treemap — size = portfolio holding value, colour = %chg
function drawSectorHeatmap(universe){
  const cv = document.getElementById('cv-heatmap');
  if(!cv) return;

  const dpr = window.devicePixelRatio || 1;
  const W = Math.max(cv.offsetWidth || window.innerWidth - 30, 180);
  const H = W; // perfect square
  cv.width  = W * dpr; cv.height = H * dpr;
  cv.style.width = W+'px'; cv.style.height = H+'px';
  const ctx = cv.getContext('2d');
  ctx.scale(dpr, dpr);
  ctx.fillStyle = '#060c18';
  ctx.fillRect(0, 0, W, H);

  if(!universe.length){
    ctx.fillStyle='rgba(140,176,208,.4)';
    ctx.font='11px sans-serif'; ctx.textAlign='center';
    ctx.fillText('Add stocks to see heatmap', W/2, H/2);
    return;
  }

  // Group by sector
  const sMap = {};
  universe.forEach(s=>{
    const sec = (s.sector && s.sector!=='—') ? s.sector : 'Other';
    if(!sMap[sec]) sMap[sec]={name:sec, holdVal:0, mcap:0, chgSum:0, n:0, stocks:[]};
    // Use portfolio holding value as size (qty*ltp) — most meaningful for personal portfolio
    // For watchlist stocks without qty, use mcap rank as proxy
    const pf = S.portfolio.find(h=>h.sym===s.sym);
    const holdingVal = pf && pf.ltp>0 ? pf.qty*pf.ltp : 0;
    sMap[sec].holdVal += holdingVal;
    sMap[sec].mcap    += (s.mcap||0);
    sMap[sec].chgSum  += (s.chg||0);
    sMap[sec].n++;
    sMap[sec].stocks.push(s);
  });

  const nodes = Object.values(sMap)
    .map(d=>({
      name:   d.name,
      // Size priority: 1) portfolio holding value, 2) mcap if available, 3) stock count
      size:   d.holdVal > 0 ? d.holdVal :
              d.mcap    > 0 ? d.mcap    :
              d.n * 1000,
      chg:    d.chgSum / d.n,
      n:      d.n,
      stocks: [...d.stocks].sort((a,b)=>Math.abs(b.chg)-Math.abs(a.chg)),
    }))
    .sort((a,b)=>b.size-a.size);

  // Normalise sizes to W*H
  const totalSize = nodes.reduce((a,b)=>a+b.size, 0);
  nodes.forEach(n=>{ n.size = (n.size/totalSize) * W * H; });

  // Squarified treemap — standard Bruls algorithm
  const rects = [];

  function worstRatio(row, w){
    if(!w||!row.length) return Infinity;
    const s = row.reduce((a,b)=>a+b.size, 0);
    const maxS = Math.max(...row.map(r=>r.size));
    const minS = Math.min(...row.map(r=>r.size));
    return Math.max((w*w*maxS)/(s*s), (s*s)/(w*w*minS));
  }

  function layoutRow(row, x, y, w, h){
    const s = row.reduce((a,b)=>a+b.size, 0);
    let cx=x, cy=y;
    if(w >= h){
      // horizontal strip
      const stripW = s/h;
      row.forEach(item=>{
        const ih = item.size / stripW;
        rects.push({...item,
          x: Math.max(0,cx), y: Math.max(0,cy),
          w: Math.min(stripW, W-cx), h: Math.min(ih, H-cy)
        });
        cy += ih;
      });
      return {x:x+stripW, y:y, w:w-stripW, h:h};
    } else {
      // vertical strip
      const stripH = s/w;
      row.forEach(item=>{
        const iw = item.size / stripH;
        rects.push({...item,
          x: Math.max(0,cx), y: Math.max(0,cy),
          w: Math.min(iw, W-cx), h: Math.min(stripH, H-cy)
        });
        cx += iw;
      });
      return {x:x, y:y+stripH, w:w, h:h-stripH};
    }
  }

  function squarify(children, x, y, w, h){
    if(!children.length||w<1||h<1) return;
    let row=[], rem=[...children];
    const shortest = Math.min(w,h);
    while(rem.length){
      const test=[...row, rem[0]];
      if(row.length>0 && worstRatio(test,shortest) > worstRatio(row,shortest)) break;
      row.push(rem.shift());
    }
    const next = layoutRow(row, x, y, w, h);
    squarify(rem, next.x, next.y, next.w, next.h);
  }

  squarify(nodes, 0, 0, W, H);

  // Color by % change — use distinct bands for easy reading
  // -3% and below = deep red, 0 = dark neutral, +3% and above = deep green
  function tileColor(chg){
    // Clamp to [-4, +4] range
    const c = Math.max(-4, Math.min(4, chg));
    if(c === 0) return 'rgba(35,50,75,0.85)';
    if(c > 0){
      // Green intensity: 0.1% = dim, 4% = full bright
      const t = c / 4;
      const g = Math.round(80  + 150*t);   // 80 → 230
      const r = Math.round(5   + 15*t);    // keeps it green not yellow
      const b = Math.round(10  + 20*t);
      return 'rgba('+r+','+g+','+b+',0.90)';
    } else {
      const t = (-c) / 4;
      const r = Math.round(80  + 150*t);   // 80 → 230
      const g = Math.round(10  + 15*t);
      const b = Math.round(15  + 20*t);
      return 'rgba('+r+','+g+','+b+',0.90)';
    }
  }

  const PAD = 2;
  rects.forEach(r=>{
    const rx=r.x+PAD, ry=r.y+PAD, rw=r.w-PAD*2, rh=r.h-PAD*2;
    if(rw<3||rh<3) return;

    ctx.fillStyle = tileColor(r.chg);
    ctx.beginPath();
    if(ctx.roundRect) ctx.roundRect(rx,ry,rw,rh,3); else ctx.rect(rx,ry,rw,rh);
    ctx.fill();
    ctx.strokeStyle='rgba(6,12,24,0.8)'; ctx.lineWidth=1; ctx.stroke();

    if(rw<16||rh<12) return;
    ctx.save();
    ctx.beginPath(); ctx.rect(rx,ry,rw,rh); ctx.clip();
    ctx.textAlign='center';
    const sign = r.chg>=0?'+':'';
    const pct  = sign+r.chg.toFixed(2)+'%';
    const cx   = rx+rw/2;

    if(rw>=54&&rh>=36){
      const fs=Math.min(12,Math.max(8,Math.floor(Math.min(rw/7,rh/3.5))));
      ctx.font='700 '+fs+'px \'JetBrains Mono\',monospace';
      ctx.fillStyle='rgba(255,255,255,0.96)';
      const lbl=r.name.length>13?r.name.slice(0,12)+'\u2026':r.name;
      ctx.fillText(lbl, cx, ry+rh*0.42);
      ctx.font=Math.max(7,fs-1)+'px \'JetBrains Mono\',monospace';
      ctx.fillStyle=r.chg>=0?'rgba(190,255,210,0.95)':'rgba(255,195,195,0.95)';
      ctx.fillText(pct, cx, ry+rh*0.42+fs+4);
    } else if(rw>=34&&rh>=22){
      const fs=Math.min(9,Math.max(6,Math.floor(Math.min(rw/6,rh/3))));
      ctx.font='700 '+fs+'px monospace';
      ctx.fillStyle='rgba(255,255,255,0.92)';
      ctx.fillText(r.name.slice(0,9), cx, ry+rh*0.40);
      ctx.font=Math.max(6,fs-1)+'px monospace';
      ctx.fillStyle=r.chg>=0?'rgba(190,255,210,0.9)':'rgba(255,195,195,0.9)';
      ctx.fillText(pct, cx, ry+rh*0.40+fs+3);
    } else {
      ctx.font='6px monospace';
      ctx.fillStyle='rgba(255,255,255,0.85)';
      ctx.fillText(pct, cx, ry+rh/2+3);
    }
    ctx.restore();
  });

  // Tap tooltip
  cv.onclick=(e)=>{
    const br=cv.getBoundingClientRect();
    const scX=W/br.width, scY=H/br.height;
    const mx=(e.clientX-br.left)*scX, my=(e.clientY-br.top)*scY;
    const hit=rects.find(r=>mx>=r.x&&mx<=r.x+r.w&&my>=r.y&&my<=r.y+r.h);
    const tip=document.getElementById('hm-tooltip');
    if(hit&&tip){
      const sign=hit.chg>=0?'+':'';
      tip.innerHTML='<b style="color:'+(hit.chg>=0?'#00e896':'#ff6b85')+'">'+hit.name+'</b>'
        +' <b>'+sign+hit.chg.toFixed(2)+'%</b><br>'
        +'<span class="u-tx3">'+hit.n+' stock'+(hit.n>1?'s':'')+'</span><br>'
        +'<span style="font-size:8px;color:var(--tx2)">'+hit.stocks.slice(0,5).map(s=>s.sym+' '+(s.chg>=0?'+':'')+s.chg.toFixed(1)+'%').join('  ')+'</span>';
      tip.style.display='block';
      tip.style.left=Math.min(e.clientX+10,window.innerWidth-170)+'px';
      tip.style.top=Math.max(e.clientY-70,8)+'px';
      setTimeout(()=>{tip.style.display='none';},3500);
    }
  };
}

// STOCK DRILL-DOWN — tabbed detail view for any stock
// Tabs: Overview · Technical · Fundamentals · News · Insights
