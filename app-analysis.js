function _analysisStocks(){
  const now = Date.now();
  return S.portfolio.map(h=>{
    const mh = mergeHolding(h);
    const g  = GUIDANCE[mh.sym];
    let status = 'pending', statusLabel = 'Pending', daysOld = null;
    if(g && g.updated){
      daysOld = Math.floor((now - new Date(g.updated).getTime()) / 86400000);
      status      = daysOld > 90 ? 'outdated' : 'done';
      statusLabel = daysOld === 0 ? 'Today' : daysOld+'d ago';
    }
    const posVal = (mh.ltp>0 && mh.qty>0) ? mh.qty * mh.ltp : (mh.qty * (mh.avgBuy||0));
    return { ...mh, g, status, statusLabel, daysOld, posVal };
  });
}

// ANALYSIS TAB — Action Queue + Coverage Summary + Search + Bottom Sheet
function renderAnalysis(c){
  const all     = _analysisStocks();
  const total   = all.length;
  const nDone   = all.filter(s=>s.status==='done').length;
  const nOut    = all.filter(s=>s.status==='outdated').length;
  const nPend   = all.filter(s=>s.status==='pending').length;
  const pctDone = total ? Math.round(nDone/total*100) : 0;

  const sf    = analysisState.statusFilter;
  const srch  = analysisState.search.trim().toUpperCase();

  // Filter & sort
  let visible = [...all];
  if(sf) visible = visible.filter(s=>s.status===sf);
  if(srch) visible = visible.filter(s=>
    s.sym.includes(srch) || (s.name||'').toUpperCase().includes(srch)
  );

  // Action queue = pending + outdated sorted by posVal desc
  // Done = separate collapsed section (unless search active or statusFilter='done')
  const showingDone = srch || sf==='done';
  const actionRows  = visible.filter(s=>s.status!=='done')
    .sort((a,b)=>b.posVal - a.posVal);
  const doneRows    = visible.filter(s=>s.status==='done')
    .sort((a,b)=>b.posVal - a.posVal);

  function stockRow(s){
    const dot   = s.status==='done'?'🟢':s.status==='outdated'?'🟡':'⚪';
    const stCol = s.status==='done'?'#00e896':s.status==='outdated'?'#ffbf47':'#4a6888';
    const posK  = s.posVal>=1e5 ? (s.posVal/1e5).toFixed(1)+'L' : s.posVal>0 ? (s.posVal/1000).toFixed(0)+'K' : '—';
    return `
      <div onclick="openAnalysisSheet('${s.sym}')"
        style="display:flex;align-items:center;gap:10px;padding:10px 13px;
        border-bottom:1px solid var(--b1);cursor:pointer;
        ${s.status==='done'?'opacity:.55':''}"
        ontouchstart="this.style.background='rgba(249,115,22,.06)'"
        ontouchend="this.style.background=''">
        <span style="font-size:14px;flex-shrink:0">${dot}</span>
        <div class="u-f1min0">
          <div style="display:flex;align-items:baseline;gap:6px">
            <span style="font-family:var(--mono);font-weight:700;font-size:12px;color:var(--tx1)">${s.sym}</span>
            <span style="font-size:9px;color:var(--tx3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${(s.name||'').slice(0,22)}</span>
          </div>
          <div style="font-size:9px;color:var(--tx3);margin-top:1px">${s.sector||'—'} · ₹${posK}</div>
        </div>
        <div class="u-tar-fs0">
          <div style="font-size:9px;color:${stCol};font-weight:700">${s.statusLabel}</div>
          <div style="font-size:8px;color:var(--tx3);margin-top:1px">${s.ltp>0?'₹'+fmt(s.ltp):''}</div>
        </div>
        <span style="color:var(--tx3);font-size:11px">›</span>
      </div>`;
  }

  c.innerHTML = `<div class="fin" style="padding-bottom:80px">

    <!-- Header -->
    <div style="padding:13px 14px 10px;border-bottom:1px solid var(--b1)">
      <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:15px;color:var(--title)">🔬 Results Analysis</div>
      <div class="u-sub">Concall analysis · ${nDone}/${total} covered</div>
    </div>

    <!-- ① Coverage Summary -->
    <div style="padding:10px 13px;border-bottom:1px solid var(--b1)">
      <!-- Progress bar -->
      <div style="height:4px;background:var(--b1);border-radius:2px;margin-bottom:10px;overflow:hidden">
        <div style="height:100%;width:${pctDone}%;background:linear-gradient(90deg,#00e896,#00d084);border-radius:2px;transition:width .4s"></div>
      </div>
      <!-- Pill filters -->
      <div style="display:flex;gap:6px">
        ${[
          {k:null,  label:'All',      n:total, col:'#5878a8'},
          {k:'pending',  label:'Pending', n:nPend, col:'#4a6888'},
          {k:'outdated', label:'Outdated',n:nOut,  col:'#ffbf47'},
          {k:'done',     label:'Covered', n:nDone, col:'#00e896'},
        ].map(p=>{
          const active = sf===p.k;
          return `<button onclick="setAnalysisFilter(${p.k?`'${p.k}'`:'null'})"
            style="flex:1;padding:6px 4px;border-radius:8px;font-size:9px;font-weight:700;cursor:pointer;
            background:${active?'rgba(249,115,22,.15)':'var(--card)'};
            border:1px solid ${active?'var(--ac)':p.col+'44'};
            color:${active?'var(--ac)':p.col}">
            ${p.label}<br><span style="font-size:12px;font-weight:800">${p.n}</span>
          </button>`;
        }).join('')}
      </div>
    </div>

    <!-- ② Search -->
    <div style="padding:8px 13px;border-bottom:1px solid var(--b1)">
      <div style="display:flex;align-items:center;gap:8px;background:var(--s1);border:1px solid var(--b1);border-radius:8px;padding:7px 10px">
        <span style="color:var(--tx3);font-size:12px">🔍</span>
        <input id="an-search" type="text" placeholder="Search symbol or name…"
          value="${analysisState.search}"
          oninput="anSearchUpdate(this.value)"
          style="flex:1;background:none;border:none;outline:none;color:var(--tx1);font-size:12px;font-family:var(--mono)">
        ${analysisState.search?`<button onclick="analysisState.search='';anSearchClear()"
          style="background:none;border:none;color:var(--tx3);font-size:14px;cursor:pointer;padding:0">✕</button>`:''}
      </div>
    </div>

    <!-- ③ Action Queue (pending + outdated) -->
    <div style="padding:7px 13px 4px">
      <div id="an-action-title" style="font-size:8px;color:var(--tx3);text-transform:uppercase;letter-spacing:.6px">
        ${sf==='done'?'Covered':'Action Queue'} · ${actionRows.length} stock${actionRows.length!==1?'s':''}
      </div>
    </div>
    <div id="an-action-list" style="background:var(--card);border-top:1px solid var(--b1);border-bottom:1px solid var(--b1)">
      ${actionRows.length ? actionRows.map(stockRow).join('') : (!srch && sf!=='done') ? `
      <div style="padding:30px 20px;text-align:center;color:var(--tx3)">
        <div class="u-28mb">🎉</div>
        <div style="font-size:12px;font-weight:700;color:var(--tx2)">All stocks covered</div>
        <div style="font-size:10px;margin-top:4px">Check back after next earnings quarter</div>
      </div>` : ''}
    </div>

    <!-- ④ Done stocks (collapsed by default) -->
    <div id="an-done-toggle" style="padding:10px 13px;${(!showingDone && doneRows.length)?'':'display:none'}">
      <button onclick="analysisState.showDone=!analysisState.showDone;renderAnalysis(document.getElementById('content'))"
        style="width:100%;padding:9px;background:var(--card);border:1px solid var(--b1);border-radius:8px;
        color:var(--tx3);font-size:10px;font-weight:700;cursor:pointer;text-align:left">
        🟢 ${analysisState.showDone?'Hide':'Show'} ${doneRows.length} covered stock${doneRows.length!==1?'s':''}
        <span style="float:right">${analysisState.showDone?'▴':'▾'}</span>
      </button>
      ${analysisState.showDone ? `<div style="background:var(--card);border:1px solid var(--b1);border-radius:0 0 8px 8px;overflow:hidden;margin-top:-1px">
        ${doneRows.map(stockRow).join('')}
      </div>` : ''}
    </div>

    <!-- Done rows when filter=done or search active -->
    ${showingDone && doneRows.length ? `
    <div style="padding:7px 13px 4px">
      <div style="font-size:8px;color:var(--tx3);text-transform:uppercase;letter-spacing:.6px">Covered · ${doneRows.length}</div>
    </div>
    <div id="an-done-list" style="background:var(--card);border-top:1px solid var(--b1);border-bottom:1px solid var(--b1)">
      ${doneRows.map(stockRow).join('')}
    </div>` : `<div id="an-done-list"></div>`}

    ${total===0?`<div style="padding:40px 20px;text-align:center;color:var(--tx3)">
      <div style="font-size:32px;margin-bottom:10px">📂</div>
      <div style="font-size:12px">Import your portfolio first</div>
    </div>`:''}

  </div>`;
}

function setAnalysisFilter(f){
  analysisState.statusFilter = f;
  renderAnalysis(document.getElementById('content'));
}

// Search update — only re-renders the list rows, not the whole tab
// Preserves input focus on every keystroke (same pattern as pfSearchUpdate)
let _anSearchTimer = null;
function anSearchUpdate(val){
  analysisState.search = val;
  clearTimeout(_anSearchTimer);
  _anSearchTimer = setTimeout(()=>_anRenderRows(), 120);
}
function anSearchClear(){
  analysisState.search = '';
  renderAnalysis(document.getElementById('content'));
}

// Re-render only the queue rows without touching the search input
function _anRenderRows(){
  const all    = _analysisStocks();
  const sf     = analysisState.statusFilter;
  const srch   = analysisState.search.trim().toUpperCase();

  let visible = [...all];
  if(sf)   visible = visible.filter(s=>s.status===sf);
  if(srch) visible = visible.filter(s=>
    s.sym.includes(srch) || (s.name||'').toUpperCase().includes(srch)
  );

  const showingDone = srch || sf==='done';
  const actionRows  = visible.filter(s=>s.status!=='done').sort((a,b)=>b.posVal-a.posVal);
  const doneRows    = visible.filter(s=>s.status==='done').sort((a,b)=>b.posVal-a.posVal);

  function stockRow(s){
    const dot   = s.status==='done'?'🟢':s.status==='outdated'?'🟡':'⚪';
    const stCol = s.status==='done'?'#00e896':s.status==='outdated'?'#ffbf47':'#4a6888';
    const posK  = s.posVal>=1e5?(s.posVal/1e5).toFixed(1)+'L':s.posVal>0?(s.posVal/1000).toFixed(0)+'K':'—';
    return `<div onclick="openAnalysisSheet('${s.sym}')"
      style="display:flex;align-items:center;gap:10px;padding:10px 13px;
      border-bottom:1px solid var(--b1);cursor:pointer;${s.status==='done'?'opacity:.55':''}"
      ontouchstart="this.style.background='rgba(249,115,22,.06)'"
      ontouchend="this.style.background=''">
      <span style="font-size:14px;flex-shrink:0">${dot}</span>
      <div class="u-f1min0">
        <div style="display:flex;align-items:baseline;gap:6px">
          <span style="font-family:var(--mono);font-weight:700;font-size:12px;color:var(--tx1)">${s.sym}</span>
          <span style="font-size:9px;color:var(--tx3);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${(s.name||'').slice(0,22)}</span>
        </div>
        <div style="font-size:9px;color:var(--tx3);margin-top:1px">${s.sector||'—'} · ₹${posK}</div>
      </div>
      <div class="u-tar-fs0">
        <div style="font-size:9px;color:${stCol};font-weight:700">${s.statusLabel}</div>
        <div style="font-size:8px;color:var(--tx3);margin-top:1px">${s.ltp>0?'₹'+fmt(s.ltp):''}</div>
      </div>
      <span style="color:var(--tx3);font-size:11px">›</span>
    </div>`;
  }

  const aq = document.getElementById('an-action-list');
  const dl = document.getElementById('an-done-list');
  const at = document.getElementById('an-action-title');
  const dt = document.getElementById('an-done-toggle');

  if(aq) aq.innerHTML = actionRows.map(stockRow).join('') ||
    ((!srch && sf!=='done') ? `<div style="padding:30px 20px;text-align:center;color:var(--tx3)">
      <div class="u-28mb">🎉</div>
      <div style="font-size:12px;font-weight:700;color:var(--tx2)">All stocks covered</div>
    </div>` : '');
  if(at) at.textContent = (sf==='done'?'Covered':'Action Queue')+' · '+actionRows.length+' stock'+(actionRows.length!==1?'s':'');
  if(dl && showingDone) dl.innerHTML = doneRows.map(stockRow).join('');
  if(dt) dt.style.display = (!showingDone && doneRows.length) ? '' : 'none';
}

// Open the bottom-sheet workflow for a stock
function openAnalysisSheet(sym){
  analysisState.selSym = sym;
  analysisState.filing = null;

  const existing = document.getElementById('analysis-sheet');
  if(existing) existing.remove();

  const f  = FUND[sym]||{};
  const g  = GUIDANCE[sym];
  const mh = _analysisStocks().find(s=>s.sym===sym)||{};
  const posVal = mh.posVal||0;
  const posK   = posVal>=1e5?(posVal/1e5).toFixed(1)+'L':posVal>0?(posVal/1000).toFixed(0)+'K':'—';
  const hasDone= g && (g.updated || g.tone || g.summary || g.revenue_guidance);

  const sheet = document.createElement('div');
  sheet.id = 'analysis-sheet';
  sheet.style.cssText = `
    position:fixed;inset:0;z-index:600;
    display:flex;flex-direction:column;justify-content:flex-end;
  `;
  sheet.innerHTML = `
    <!-- Backdrop -->
    <div onclick="closeAnalysisSheet()"
      style="position:absolute;inset:0;background:rgba(0,0,0,.6);backdrop-filter:blur(2px)"></div>

    <!-- Sheet panel -->
    <div id="as-panel" style="
      position:relative;z-index:1;
      background:var(--bg,#060c18);
      border-radius:18px 18px 0 0;
      border-top:1px solid var(--b1);
      max-height:88vh;
      display:flex;flex-direction:column;
      transform:translateY(100%);
      transition:transform .28s cubic-bezier(.32,1,.6,1);
    ">
      <!-- Drag handle -->
      <div style="padding:10px 0 4px;text-align:center;flex-shrink:0">
        <div style="width:36px;height:4px;background:var(--b2);border-radius:2px;display:inline-block"></div>
      </div>

      <!-- Stock header -->
      <div style="padding:8px 16px 12px;border-bottom:1px solid var(--b1);flex-shrink:0">
        <div class="u-sb-top">
          <div>
            <div style="font-family:var(--mono);font-weight:800;font-size:16px;color:var(--ac)">${sym}</div>
            <div class="u-tx3-10mt">${f.name||''} · ${f.sector||''}</div>
          </div>
          <div class="u-tar">
            <div style="font-family:var(--mono);font-size:13px;color:var(--tx1)">₹${fmt(f.ltp||0)}</div>
            <div class="u-tx3-9">PE: ${f.pe||'—'}x · ₹${posK}</div>
          </div>
        </div>
        <!-- Status + actions row -->
        <div style="display:flex;gap:6px;margin-top:10px">
          ${hasDone?`
          <div style="flex:1;padding:6px 8px;background:rgba(0,232,150,.06);border:1px solid rgba(0,232,150,.2);border-radius:7px">
            <div style="font-size:8px;color:var(--tx3)">Last analysed</div>
            <div style="font-size:10px;color:#00e896;font-weight:700">${mh.statusLabel||'—'}
              <span style="font-size:8px;color:var(--tx3);font-weight:400"> · ${g.quarter||''}</span>
            </div>
          </div>
          <button onclick="clearStockAnalysis('${sym}')"
            id="btn-clear-${sym}"
            style="padding:6px 10px;background:rgba(255,59,92,.08);border:1px solid rgba(255,59,92,.25);
            border-radius:7px;color:#ff6b85;font-size:10px;font-weight:700;cursor:pointer">
            🗑 Clear
          </button>` : `
          <div style="flex:1;padding:6px 8px;background:rgba(74,104,136,.08);border:1px solid rgba(74,104,136,.25);border-radius:7px">
            <div style="font-size:10px;color:#4a6888;font-weight:700">⚪ Not yet analysed</div>
          </div>`}
        </div>
      </div>

      <!-- Scrollable body -->
      <div style="flex:1;overflow-y:auto;-webkit-overflow-scrolling:touch">

        <!-- Existing guidance card — shown prominently above steps -->
        ${hasDone ? `
        <div style="margin:12px 16px 0;padding:12px;background:rgba(0,232,150,.04);
          border:1px solid rgba(0,232,150,.2);border-radius:10px">
          <div style="font-size:8px;color:#00e896;text-transform:uppercase;letter-spacing:.6px;
            font-weight:700;margin-bottom:8px">📋 Saved Analysis · ${g.quarter||''} · ${new Date(g.updated).toLocaleDateString('en-IN')}</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:8px">
            ${[
              ['Tone',       g.tone,             g.tone==='Positive'?'#00e896':g.tone==='Negative'?'#ff6b85':'#ffbf47'],
              ['Confidence', g.confidence,       '#8eb0d0'],
              ['Revenue',    g.revenue_guidance, '#64b5f6'],
              ['Margin',     g.margin_guidance,  '#a78bfa'],
              ['Growth',     g.growth_target,    '#64b5f6'],
              ['Rating',     g.analyst_rating,   '#f59e0b'],
            ].filter(r=>r[1]).map(([label,val,col])=>`
              <div style="padding:5px 7px;background:rgba(0,0,0,.2);border-radius:6px">
                <div style="font-size:7px;color:var(--tx3);text-transform:uppercase">${label}</div>
                <div style="font-size:10px;color:${col};font-weight:700;margin-top:1px">${String(val).slice(0,30)}</div>
              </div>`).join('')}
          </div>
          ${g.summary?`<div style="font-size:9px;color:var(--tx2);line-height:1.5;padding:6px 7px;
            background:rgba(0,0,0,.2);border-radius:6px;margin-bottom:6px">${g.summary}</div>`:''}
          ${g.risks_flagged?.length?`<div style="font-size:8px;color:#ff6b85;line-height:1.5">
            ⚠ ${g.risks_flagged.slice(0,2).join(' · ')}</div>`:''}
        </div>` : ''}


        <!-- Step 1: Find Filing -->
        <div style="padding:12px 16px;border-bottom:1px solid var(--b1)">
          <div class="u-title-10">
            <span style="background:var(--ac);color:#fff;border-radius:50%;width:16px;height:16px;
              display:inline-flex;align-items:center;justify-content:center;font-size:8px;margin-right:6px">1</span>
            Find Latest Results Filing
          </div>
          <button onclick="findFiling('${sym}')" id="btn-find-filing"
            style="background:rgba(99,102,241,.15);border:1px solid rgba(99,102,241,.4);border-radius:8px;
            padding:8px 16px;color:#818cf8;font-size:11px;font-weight:700;cursor:pointer;width:100%">
            🔍 Search BSE/NSE Filing
          </button>
          <div id="filing-result" style="margin-top:8px"></div>
        </div>

        <!-- Step 2: Generate Prompt -->
        <div style="padding:12px 16px;border-bottom:1px solid var(--b1)">
          <div class="u-title-10">
            <span style="background:var(--ac);color:#fff;border-radius:50%;width:16px;height:16px;
              display:inline-flex;align-items:center;justify-content:center;font-size:8px;margin-right:6px">2</span>
            Open Claude.ai with Analysis Prompt
          </div>
          <div style="font-size:9px;color:var(--tx3);margin-bottom:8px">Copies prompt → open Claude.ai → attach the PDF → paste response below</div>
          <button onclick="openClaudeAnalysis('${sym}')"
            style="background:rgba(0,208,132,.12);border:1px solid rgba(0,208,132,.3);border-radius:8px;
            padding:8px 16px;color:#00e896;font-size:11px;font-weight:700;cursor:pointer;width:100%">
            📋 Copy Prompt &amp; Open Claude.ai ↗
          </button>
        </div>

        <!-- Step 3: Paste Response -->
        <div style="padding:12px 16px">
          <div class="u-title-10">
            <span style="background:var(--ac);color:#fff;border-radius:50%;width:16px;height:16px;
              display:inline-flex;align-items:center;justify-content:center;font-size:8px;margin-right:6px">3</span>
            Paste Claude's Response
          </div>
          <div style="font-size:10px;color:var(--tx3);line-height:1.6;margin-bottom:10px;padding:8px 10px;
            background:var(--s2);border-radius:7px;border-left:3px solid var(--ac)">
            Action signal, guidance, geography, products & risks shown in the stock's
            <b class="u-tx2">Overview tab</b> all come from this paste.
          </div>
          <textarea id="ta-response" placeholder="Paste Claude's response here…"
            style="width:100%;box-sizing:border-box;height:160px;background:var(--s1);
            border:1px solid var(--b1);border-radius:8px;padding:10px;color:var(--tx1);
            font-size:10px;font-family:var(--mono);resize:vertical;outline:none"></textarea>
          <div style="display:flex;gap:6px;margin-top:8px">
            <button onclick="saveAnalysis('${sym}')"
              style="flex:2;background:var(--ac);border:none;border-radius:8px;padding:10px 0;
              color:#fff;font-size:12px;font-weight:800;cursor:pointer;font-family:'Syne',sans-serif">
              💾 Save Analysis
            </button>
          </div>

          <!-- bottom safe area -->
          <div style="height:24px"></div>
        </div>

      </div><!-- /scrollable body -->
    </div><!-- /sheet panel -->
  `;

  document.body.appendChild(sheet);
  // Animate in
  requestAnimationFrame(()=>{
    requestAnimationFrame(()=>{
      document.getElementById('as-panel').style.transform = 'translateY(0)';
    });
  });
}

function closeAnalysisSheet(){
  const sheet = document.getElementById('analysis-sheet');
  if(!sheet) return;
  const panel = document.getElementById('as-panel');
  if(panel){
    panel.style.transform = 'translateY(100%)';
    setTimeout(()=>sheet.remove(), 300);
  } else {
    sheet.remove();
  }
  analysisState.selSym = null;
  analysisState.filing = null;
}

// Select a stock in the analysis queue (legacy — now uses sheet)
function selectAnalysisStock(sym){
  openAnalysisSheet(sym);
}

// Clear concall for a stock — called from sheet header (no event arg needed)
function clearStockAnalysis(sym, event){
  if(event) event.stopPropagation();
  if(!GUIDANCE[sym]) return;
  const btn = document.getElementById('btn-clear-'+sym);
  if(btn && btn.dataset.confirm !== '1'){
    btn.dataset.confirm = '1';
    btn.textContent = '✓ Confirm';
    btn.style.background = 'rgba(255,59,92,.2)';
    btn.style.borderColor = 'rgba(255,59,92,.5)';
    setTimeout(()=>{
      if(btn){ btn.dataset.confirm=''; btn.textContent='🗑 Clear';
        btn.style.background='rgba(255,59,92,.08)';
        btn.style.borderColor='rgba(255,59,92,.25)'; }
    }, 2500);
    return;
  }
  // Preserve insights — only wipe concall-derived fields
  const savedInsights = GUIDANCE[sym]?.insights;
  if(savedInsights){
    GUIDANCE[sym] = { sym, insights: savedInsights };
  } else {
    delete GUIDANCE[sym];
  }
  saveGuidanceAll();
  toast(sym+' analysis cleared' + (savedInsights ? ' · insights kept' : ''));
  closeAnalysisSheet();
  renderAnalysis(document.getElementById('content'));
}

// Delete a single stock from portfolio — does NOT touch GUIDANCE or insights
// Called from: portfolio drill-down header OR analysis sheet
function deletePortfolioStock(sym){
  const btn = document.getElementById('btn-del-'+sym);
  if(btn && btn.dataset.confirm !== '1'){
    btn.dataset.confirm = '1';
    btn.textContent = '✓?';
    btn.style.background = 'rgba(255,59,92,.2)';
    btn.style.borderColor = 'rgba(255,59,92,.5)';
    setTimeout(()=>{
      if(btn){ btn.dataset.confirm=''; btn.textContent='✕';
        btn.style.background='rgba(255,59,92,.08)';
        btn.style.borderColor='rgba(255,59,92,.25)'; }
    }, 2500);
    return;
  }
  // Remove from portfolio only — GUIDANCE and insights are intentionally kept
  S.portfolio = S.portfolio.filter(h=>h.sym!==sym);
  savePF();
  toast(sym+' removed from portfolio');
  // Close whichever context is open
  closeAnalysisSheet();
  S.selStock = null;
  render();
}

// Search BSE/NSE/Screener for latest results filing links
async function findFiling(sym){
  const btn = document.getElementById('btn-find-filing');
  const res = document.getElementById('filing-result');
  if(!btn||!res) return;
  btn.textContent = 'Searching...'; btn.disabled = true;

  try{
    const name = FUND[sym]?.name || sym;
    // Search Google News RSS for latest BSE results filing
    const query = encodeURIComponent(`"${name}" quarterly results BSE filing site:bseindia.com OR site:nseindia.com`);
    const rssUrl = `https://news.google.com/rss/search?q=${query}&hl=en-IN&gl=IN&ceid=IN:en`;
    const apiUrl = `https://api.rss2json.com/v1/api.json?rss_url=${encodeURIComponent(rssUrl)}&count=5`;

    const r = await fetch(apiUrl);
    const d = await r.json();
    const items = d.items||[];

    // Screener — works directly with NSE symbol, has concalls + documents
    const screenerUrl  = `https://www.screener.in/company/${sym}/consolidated/`;
    const screenerConc = `https://www.screener.in/company/${sym}/concalls/`;
    // BSE results — search by company name
    const bseResultsUrl = `https://www.bseindia.com/corporates/Comp_Resultsnew.aspx?scripname=${encodeURIComponent(name)}`;
    // NSE — passes symbol directly
    const nseUrl = `https://www.nseindia.com/companies-listing/corporate-filings-financial-results?symbol=${encodeURIComponent(sym)}`;

    const filing = {
      sym, name,
      screenerUrl,
      screenerConc,
      bseUrl:     bseResultsUrl,
      nseUrl:     nseUrl,
      newsItems:  items.slice(0,3),
      quarter:    detectQuarter(),
    };
    analysisState.filing = filing;
    renderFilingResult(filing);
  } catch(e){
    if(res) res.innerHTML = `<div style="color:#ff6b85;font-size:9px;padding:6px">Search failed: ${e.message}</div>`;
  } finally {
    if(btn){ btn.textContent='🔍 Search BSE/NSE Filing'; btn.disabled=false; }
  }
}

function detectQuarter(){
  const m = new Date().getMonth()+1;
  const y = new Date().getFullYear();
  if(m>=4&&m<=6)  return `Q1 FY${y-1999}`;
  if(m>=7&&m<=9)  return `Q2 FY${y-1999}`;
  if(m>=10&&m<=12) return `Q3 FY${y-1999}`;
  return `Q4 FY${y-2000}`;
}

function renderFilingResult(filing){
  const res = document.getElementById('filing-result');
  if(!res) return;
  res.innerHTML = `
    <div style="background:rgba(0,0,0,.2);border-radius:8px;padding:10px;font-size:9px">
      <div style="color:var(--tx3);margin-bottom:6px">📄 Latest filing period: <b style="color:var(--tx1)">${filing.quarter}</b></div>
      <div style="display:flex;flex-direction:column;gap:5px">
        <a href="${filing.screenerUrl}" target="_blank"
          style="display:block;padding:8px 12px;background:rgba(0,208,132,.08);border:1px solid rgba(0,208,132,.3);border-radius:8px;color:#00e896;text-decoration:none;font-weight:700;font-size:10px">
          📊 Screener — ${filing.sym} (Financials + Documents) ↗
        </a>
        <a href="${filing.screenerConc}" target="_blank"
          style="display:block;padding:8px 12px;background:rgba(0,208,132,.08);border:1px solid rgba(0,208,132,.3);border-radius:8px;color:#00e896;text-decoration:none;font-weight:700;font-size:10px">
          🎙 Screener — ${filing.sym} Concall Transcripts ↗
        </a>
        <div style="display:flex;gap:5px">
          <a href="${filing.bseUrl}" target="_blank"
            style="flex:1;display:block;padding:6px 8px;background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.25);border-radius:6px;color:#818cf8;text-decoration:none;font-size:8px;font-weight:700;text-align:center">
            BSE Results ↗
          </a>
          <a href="${filing.nseUrl}" target="_blank"
            style="flex:1;display:block;padding:6px 8px;background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.25);border-radius:6px;color:#818cf8;text-decoration:none;font-size:8px;font-weight:700;text-align:center">
            NSE Results ↗
          </a>
        </div>
      </div>
      <div style="margin-top:6px;color:var(--tx3);font-size:8px">Tap a link → find the results PDF → save it → attach in Claude.ai</div>
    </div>`;
}

// Build analysis prompt from FUND data + concall context,
// copy to clipboard, open Claude.ai
function openClaudeAnalysis(sym){
  const f = FUND[sym]||{};
  const name = f.name || sym;
  const sector = f.sector || '';
  const quarter = detectQuarter();

  // Build quarterly trend from FUND
  const qtrs = (f.quarterly||[]).slice(0,4);
  const qtrText = qtrs.length ? qtrs.map(q=>
    `  ${q.d||'?'}: Rev ₹${q.rev||'—'}Cr | EPS ₹${q.eps||'—'} | Net ₹${q.net||'—'}Cr | OPM ${q.opm||'—'}%`
  ).join('\n') : '  No quarterly data available';

  const prompt = `You are a senior equity research analyst. Analyse the attached ${quarter} results document for ${name} (NSE: ${sym}).

COMPANY CONTEXT:
- Sector: ${sector}
- Current Price: ₹${f.ltp||'—'} | P/E: ${f.pe||'—'}x | Forward P/E: ${f.fwd_pe||'—'}x
- ROE: ${f.roe||'—'}% | OPM: ${f.opm_pct||'—'}% | Debt/Equity: ${f.debt_eq||'—'}
- Promoter: ${f.prom_pct||'—'}% | MCap: ₹${f.mcap||'—'}Cr

LAST 4 QUARTERS TREND:
${qtrText}

TASK: Analyse this earnings concall / results document thoroughly.
Return ONLY in the KEY: VALUE format below — one field per line, no markdown table, no bold, no bullets, no extra text before or after. This format is chosen so it can be easily copied on mobile.

Quarter: Q3 FY26 etc
Action Signal: BUY MORE / HOLD / REDUCE / EXIT with 1-line reason
One Line Verdict: Most important takeaway for investor in 1 sentence
Revenue Guidance: Specific target next quarter and full year
Revenue Growth Target: YoY or QoQ growth % guided
EBITDA Margin Target: Guided range
PAT Margin Target: Guided range
Order Book: Total order book value and execution timeline
Deal Wins: New deals this quarter - size and client type
Pipeline: Sales pipeline or deal pipeline commentary
Customer Changes: New customers added; any major losses
Segment Growth: Which segments growing vs declining
Geographic Mix: Domestic vs export split % e.g. India 60% US 25% Europe 15%
Geographic Presence: Countries/regions actively operating in and expansion plans
Headcount Plans: Hiring / layoff plans; utilisation rate
Raw Material Outlook: Cost pressure or easing expected
Working Capital: Receivables, inventory, cash conversion trend
Debt Reduction Plan: Repayment timeline; net debt target
Capex Plan: Amount, purpose, funding source
Capacity Expansion: New plants or lines with timeline
New Products: Launching products, services or business lines
Key Products Portfolio: Top 3-5 existing products/segments with revenue contribution %
Market Share: Gaining or losing share; pricing strategy
Competition: Key threats or advantages mentioned
Acquisitions: M&A, JVs, partnerships announced
Geographic Expansion: New markets, international plans
Promoter Actions: Insider buying/selling, pledge, buyback
Dividend Guidance: Dividend commitment or payout ratio guided
Regulatory Impact: Policy, export/import, licensing changes
Currency Exposure: FX sensitivity and hedging strategy
Litigation: Ongoing legal or regulatory issues
Management Tone: Positive/Cautious/Negative with specific reason
Management Credibility: Delivered last quarter guidance? Yes/Partially/No
Specific Commitments: Top 3 promises with numbers and timelines
Key Risks: Top 3 risks - rate each High/Medium/Low
Analyst Consensus: Buy/Hold/Sell count and price target range
Confidence Level: High/Medium/Low based on specificity of guidance

RULES:
- Use ONLY information from the attached document
- Write "Not mentioned" if absent - never guess or fabricate
- Be specific - use actual numbers not vague statements
- Action Signal must reflect valuation + guidance quality together
- One Line Verdict must be actionable not descriptive
- Do NOT use markdown table format — plain KEY: VALUE only`;

  showPromptPanel(sym, prompt);
  if(navigator.clipboard && window.isSecureContext){
    navigator.clipboard.writeText(prompt)
      .then(()=> toast("Prompt copied — paste in Claude"))
      .catch(()=> toast("Copy the prompt from the panel below"));
  }
}

// Show full prompt in a modal for copy-paste on mobile
function showPromptPanel(sym, prompt){
  // Show a modal with the prompt + Open Claude button
  const existing = document.getElementById('prompt-modal');
  if(existing) existing.remove();

  const modal = document.createElement('div');
  modal.id = 'prompt-modal';
  modal.style.cssText = `
    position:fixed;inset:0;z-index:500;
    background:rgba(0,0,0,.85);
    display:flex;flex-direction:column;
    padding:0;overflow:hidden;
  `;
  modal.innerHTML = `
    <div style="display:flex;justify-content:space-between;align-items:center;
      padding:14px 16px;background:#0d1929;border-bottom:1px solid #1e3350;flex-shrink:0">
      <div>
        <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:13px;color:#f0f6ff">Analysis Prompt — ${sym}</div>
        <div style="font-size:9px;color:#5878a8;margin-top:2px">Copy → Open Claude.ai → Paste → Attach PDF</div>
      </div>
      <button onclick="document.getElementById('prompt-modal').remove()"
        style="background:none;border:1px solid #1e3350;border-radius:6px;padding:4px 10px;color:#8eb0d0;font-size:11px;cursor:pointer">✕ Close</button>
    </div>

    <!-- Open Claude buttons -->
    <div style="display:flex;gap:8px;padding:12px 16px;background:#060c18;border-bottom:1px solid #1e3350;flex-shrink:0">
      <a href="https://claude.ai/new" target="_blank"
        style="flex:1;display:block;text-align:center;padding:10px;
        background:rgba(249,115,22,.15);border:1px solid var(--ac);border-radius:8px;
        color:var(--ac);font-weight:800;font-size:11px;text-decoration:none;font-family:'Syne',sans-serif">
        🤖 Open Claude.ai ↗
      </a>
      <button onclick="
        const ta=document.getElementById('pm-prompt');
        ta.select();document.execCommand('copy');
        toast('Copied!');this.textContent='✓ Copied';"
        style="flex:1;padding:10px;background:rgba(0,208,132,.1);border:1px solid rgba(0,208,132,.3);
        border-radius:8px;color:#00e896;font-weight:800;font-size:11px;cursor:pointer;font-family:'Syne',sans-serif">
        📋 Copy Prompt
      </button>
    </div>

    <!-- Prompt text -->
    <textarea id="pm-prompt" readonly
      style="flex:1;width:100%;box-sizing:border-box;
      background:#02040a;border:none;outline:none;
      padding:14px 16px;color:#8eb0d0;
      font-size:10px;font-family:'JetBrains Mono',monospace;
      line-height:1.6;resize:none;overflow-y:auto"
    >${prompt.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</textarea>

    <div style="padding:10px 16px;background:#060c18;border-top:1px solid #1e3350;
      font-size:8px;color:#4a6888;text-align:center;flex-shrink:0">
      Steps: Copy prompt → Open Claude.ai → Paste prompt → Attach the PDF from BSE/NSE → Come back and paste Claude's response
    </div>
  `;
  document.body.appendChild(modal);
}



// Parse pasted Claude response, save to GUIDANCE + GitHub
function saveAnalysis(sym){
  const ta = document.getElementById('ta-response');
  if(!ta || !ta.value.trim()){
    toast('Paste Claude response first'); return;
  }

  const text = ta.value.trim();
  const guidance = parseAnalysisTable(sym, text);

  // Always save — parser has fallback for any format
  GUIDANCE[sym] = guidance;
  saveGuidanceAll();

  toast('Analysis saved for '+sym+' ✓');
  ta.value = '';
  analysisState.filing = null;
  closeAnalysisSheet();
  renderAnalysis(document.getElementById('content'));
}

// Multi-format parser for Claude concall response:
// Format 1: markdown table | Field | Value |
// Format 2: Key: Value lines (ALL formats run unconditionally)
// Format 3: numbered list  1. Field — Value
function parseAnalysisTable(sym, text){
  const data = {};

  // ── Format 1: Markdown table  | Field | Value |
  const tableLines = text.split('\n').filter(l=>l.includes('|'));
  if(tableLines.length >= 3){
    tableLines.forEach(line=>{
      const cells = line.split('|').map(c=>c.trim()).filter(Boolean);
      if(cells.length >= 2 && !cells[0].match(/^[-:]+$/) && !cells[0].match(/^Field$/i)){
        const key = cells[0].toLowerCase().replace(/[^a-z0-9]/g,'_').replace(/_+/g,'_');
        const val = cells.slice(1).join(' | ').trim();
        if(key && val && val!=='Not mentioned' && val!=='—' && val!=='-')
          data[key] = val;
      }
    });
  }

  // ── Format 2: Key: Value — ALWAYS runs (Claude mixes table + plain lines)
  // Handles **Revenue Guidance**: ₹4200 Cr  OR  Revenue Guidance: ₹4200 Cr
  text.split('\n').forEach(line=>{
    const clean = line.replace(/\*\*/g,'').replace(/\*/g,'').replace(/^[-•>\s]+/,'').trim();
    const m = clean.match(/^([A-Za-z][A-Za-z\s\/\(\)]+?)[\s]*[:：][\s]*(.+)$/);
    if(m && m[1] && m[2]){
      const key = m[1].trim().toLowerCase().replace(/[^a-z0-9]/g,'_').replace(/_+/g,'_');
      const val = m[2].trim();
      // Don't overwrite value already captured from Format 1 table
      if(key && val && val!=='Not mentioned' && val!=='—' && val!=='-' && !data[key])
        data[key] = val;
    }
  });

  // ── Format 3: Numbered list — ALWAYS runs
  text.split('\n').forEach(line=>{
    const clean = line.replace(/\*\*/g,'').trim();
    const m = clean.match(/^\d+[\.\)]\s*([A-Za-z][A-Za-z\s\/]+?)\s*[—–-]+\s*(.+)$/);
    if(m && m[1] && m[2]){
      const key = m[1].trim().toLowerCase().replace(/[^a-z0-9]/g,'_').replace(/_+/g,'_');
      const val = m[2].trim();
      if(key && val && !data[key]) data[key] = val;
    }
  });

  // If still nothing — store raw and let user see it
  if(Object.keys(data).length < 2){
    // Minimal fallback — store raw text as summary
    return {
      sym,
      updated:      new Date().toISOString(),
      quarter:      detectQuarter(),
      summary:      text.slice(0,500),
      tone:         text.match(/positive/i)?'Positive':text.match(/negative|caution|concern/i)?'Negative':'Neutral',
      confidence:   'Low',
      raw_table:    text,
      key_commitments: [],
      risks_flagged:   [],
    };
  }

  // Helper to find value by multiple possible key names
  function get(...keys){
    for(const k of keys){
      const norm = k.toLowerCase().replace(/[^a-z0-9]/g,'_').replace(/_+/g,'_');
      // exact match
      if(data[norm]) return data[norm];
      // partial match
      const found = Object.keys(data).find(dk=>dk.includes(norm)||norm.includes(dk));
      if(found) return data[found];
    }
    return null;
  }

  const toneRaw = get('management_tone','tone','sentiment') || '';
  const tone = toneRaw.match(/positive/i)?'Positive':toneRaw.match(/negative|bearish|caution/i)?'Negative':'Neutral';

  const commitRaw = get('key_commitments','commitments','management_commitments') || '';
  const risksRaw  = get('key_risks','risks','risk_factors') || '';

  const g = {
    sym,
    updated:          new Date().toISOString(),
    quarter:          get('quarter','period','reporting_period') || detectQuarter(),
    revenue_guidance: get('revenue_guidance','revenue_target','revenue'),
    growth_target:    get('revenue_growth_target','growth_target','revenue_growth'),
    margin_guidance:  [get('ebitda_margin_target','ebitda_margin'), get('pat_margin_target','pat_margin')].filter(Boolean).join(' | ') || get('margin_guidance','margin'),
    capex_plan:       get('capex_plan','capex','capital_expenditure'),
    expansion:        [get('capacity_expansion','capacity'), get('new_products_segments','new_products'), get('geographic_expansion','expansion')].filter(Boolean).join('; ') || null,
    ma_plans:         get('acquisitions_partnerships','acquisitions','m_a'),
    // ── Fields that render as standalone visual blocks in Overview ──
    geographic_presence:  get('geographic_presence','geographic_mix','geographic_expansion','geographic','geography'),
    geographic_mix:       get('geographic_mix','geographic_presence','geographic'),
    geographic_expansion: get('geographic_expansion','expansion_plans','new_markets'),
    key_products_portfolio: get('key_products_portfolio','key_products','products_portfolio','product_mix','segments','key_segments','segment_mix'),
    tone,
    tone_detail:      toneRaw || null,
    key_commitments:  commitRaw ? commitRaw.split(/[;,]|\d[\.\)]/).map(s=>s.trim()).filter(s=>s.length>5) : [],
    eps_estimate:     get('analyst_eps_estimate','eps_estimate','forward_eps'),
    price_target:     get('analyst_price_target','price_target','target_price'),
    analyst_rating:   get('analyst_rating','rating','recommendation'),
    risks_flagged:    risksRaw ? risksRaw.split(/[;,]|\d[\.\)]/).map(s=>s.trim()).filter(s=>s.length>5) : [],
    confidence:       get('confidence_level','confidence') || 'Medium',
    summary:          get('summary','overview','outlook'),
    raw_table:        text,
  };

  return g;
}

// ── Boot ──────────────────────────────────────────────

// ── Guidance JSON — strip raw_table to keep file lean ─────────────
// GUIDANCE STORAGE — concall analysis + AI insights
// Persisted to both localStorage AND GitHub (guidance.json)
// raw_table stripped before GitHub commit to keep file lean
function guidanceForStorage(){
  const out = {};
  Object.entries(GUIDANCE).forEach(([sym, g])=>{
    const { raw_table, ...rest } = g;   // drop raw_table — parsed fields only
    out[sym] = rest;
  });
  return out;
}

// Commit guidance.json to GitHub repo (fire-and-forget)
async function saveGuidanceToGitHub(){
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  if(!token || !repo) return;  // silent — not configured

  const json    = JSON.stringify(guidanceForStorage(), null, 2);
  const encoded = btoa(unescape(encodeURIComponent(json)));
  const headers = { 'Authorization':'token '+token, 'Content-Type':'application/json', 'Accept':'application/vnd.github.v3+json' };
  const fileUrl = 'https://api.github.com/repos/'+repo+'/contents/guidance.json';

  try{
    let sha = null;
    const get = await fetch(fileUrl, {headers});
    if(get.ok){ const d = await get.json(); sha = d.sha; }

    const body = { message:'guidance: update '+new Date().toISOString().slice(0,10), content: encoded };
    if(sha) body.sha = sha;
    const put = await fetch(fileUrl, { method:'PUT', headers, body:JSON.stringify(body) });
    if(put.ok){
    } else {
      console.warn('guidance.json save failed:', await put.json().catch(()=>({})));
    }
  } catch(e){
    console.warn('saveGuidanceToGitHub error:', e.message);
  }
}

// On boot: fetch guidance.json from GitHub Pages CDN,
// merge with localStorage. GitHub wins for parsed fields;
// localStorage retains raw_table and insights.
async function loadGuidanceFromGitHub(){
  const repo  = S.settings.ghRepo?.trim();
  if(!repo) {
    // Fallback to localStorage
    try{ const c = localStorage.getItem('bm_guidance'); if(c) GUIDANCE = JSON.parse(c); }catch(e){}
    return;
  }
  try{
    // Fetch from GitHub Pages (same-origin CDN, no auth needed)
    const r = await fetch('./guidance.json?t='+Date.now(), {cache:'no-store'});
    if(r.ok){
      const d = await r.json();
      // Merge with localStorage — GitHub is authoritative for saved fields,
      // but raw_table only exists in localStorage (never committed)
      const local = {};
      try{ const c = localStorage.getItem('bm_guidance'); if(c) Object.assign(local, JSON.parse(c)); }catch(e){}
      // Merge: GitHub fields + raw_table from localStorage if same stock
      Object.entries(d).forEach(([sym, g])=>{
        GUIDANCE[sym] = { ...g };
        if(local[sym]?.raw_table) GUIDANCE[sym].raw_table = local[sym].raw_table;
        if(local[sym]?.insights)  GUIDANCE[sym].insights  = local[sym].insights;
      });
      // Also keep any local-only stocks not yet pushed
      Object.entries(local).forEach(([sym, g])=>{
        if(!GUIDANCE[sym]) GUIDANCE[sym] = g;
      });
    } else {
      // guidance.json not yet in repo — use localStorage
      try{ const c = localStorage.getItem('bm_guidance'); if(c) GUIDANCE = JSON.parse(c); }catch(e){}
    }
  } catch(e){
    console.warn('loadGuidanceFromGitHub error:', e.message);
    try{ const c = localStorage.getItem('bm_guidance'); if(c) GUIDANCE = JSON.parse(c); }catch(e2){}
  }
}

// Write GUIDANCE to localStorage only (no GitHub)
function saveGuidanceLocal(){
  try{ localStorage.setItem('bm_guidance', JSON.stringify(GUIDANCE)); }catch(e){}
}

// Primary save: localStorage + GitHub (always call this)
function saveGuidanceAll(){
  saveGuidanceLocal();
  saveGuidanceToGitHub();  // fire-and-forget
}

// BOOT — initialise app on load
// Order: load state → load fundamentals → load guidance → render

// UPLOAD TAB — all data import, sync, and config in one place
