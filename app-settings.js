function renderUpload(c){
  const ghOk    = !!(S.settings.ghToken && S.settings.ghRepo);
  const ghColor = S.settings._ghStatus==='ok'?'#00e896':S.settings._ghStatus==='fail'?'#ff6b85':'#4a6888';
  const ghDot   = S.settings._ghStatus==='ok'?'#00d084':S.settings._ghStatus==='fail'?'#ff3b5c':'#4a6888';
  const ghLabel = S.settings._ghStatus==='ok'?'Connected':S.settings._ghStatus==='fail'?'Failed':'Not tested';

  c.innerHTML = `<div style="padding:10px 13px 80px;display:flex;flex-direction:column;gap:12px">

    <!-- ── Section: Portfolio Import ── -->
    <div class="u-card">
      <div style="padding:10px 13px;background:rgba(249,115,22,.08);border-bottom:1px solid var(--b1)">
        <div style="font-size:12px;font-weight:700;color:var(--ac)">📂 Portfolio Import</div>
        <div class="u-sub">Load your CDSL holdings into the app</div>
      </div>
      <div style="padding:10px 13px;font-size:10px;color:var(--tx3);line-height:1.8;border-bottom:1px solid var(--b1)">
        <b class="u-gr2">Recommended — CDSL XLS</b><br>
        CDSL Easiest → Portfolio → Equity Summary Details → Download XLS<br>
        Single file: symbol, sector, qty, avg buy — complete import<br><br>
        <b class="u-yw2">Fallback — CDSL Text or Manual CSV</b><br>
        Copy-paste from CDSL statement · or type <code style="color:#64b5f6">SYMBOL, QTY, AVG</code> manually<br>
        <span class="u-yel">⚠ Avg buy not available in CDSL text format</span>
      </div>
      <div class="u-pad">
        <button onclick="openImport()"
          style="width:100%;padding:11px;background:rgba(249,115,22,.12);border:1px solid rgba(249,115,22,.4);border-radius:8px;color:var(--ac);font-size:12px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif">
          📂 Open Import Panel
        </button>
      </div>
    </div>

    <!-- ── Section: GitHub Config ── -->
    <div class="u-card">
      <div class="u-indig">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <div>
            <div class="u-ind">⚙ GitHub Config</div>
            <div class="u-sub">Repo + PAT for auto price/fundamentals fetch</div>
          </div>
          <div class="u-row5">
            <div style="width:8px;height:8px;border-radius:50%;background:${ghDot}"></div>
            <span style="font-size:10px;color:${ghColor}">${ghLabel}</span>
          </div>
        </div>
      </div>

      ${S.settings._lastSync?`
      <div style="padding:7px 13px;font-size:10px;border-bottom:1px solid var(--b1);
        color:${S.settings._lastSyncOk?'#00e896':'#ff6b85'}">
        ${S.settings._lastSyncOk?'✅':'❌'} Last sync: ${new Date(S.settings._lastSync).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:false})} — ${S.settings._lastSyncMsg||''}
      </div>`:''}

      <div style="padding:10px 13px;display:flex;flex-direction:column;gap:8px">
        <div>
          <div class="u-sb">
            <span class="u-tx3-10">Anthropic API Key</span>
            <div class="u-row5">
              <div style="width:7px;height:7px;border-radius:50%;background:${S.settings.aiKey?'#00d084':'#4a6888'}"></div>
              <a href="https://console.anthropic.com/settings/keys" target="_blank" style="font-size:9px;color:var(--ac);text-decoration:none">Get key ↗</a>
            </div>
          </div>
          <div class="u-rel">
            <input id="ai-key-inp" type="password" autocomplete="off" autocorrect="off" autocapitalize="off"
              value="${S.settings.aiKey||''}" placeholder="sk-ant-xxxxxxxxxxxx"
              oninput="S.settings.aiKey=this.value.trim();saveSettings()"
              style="width:100%;box-sizing:border-box;background:var(--s1);border:1px solid ${S.settings.aiKey?'rgba(0,208,132,.4)':'var(--b1)'};border-radius:7px;padding:7px 36px 7px 10px;color:var(--tx1);font-size:11px;font-family:var(--mono);outline:none"/>
            <span onclick="toggleKeyVis('ai-key-inp')" style="position:absolute;right:10px;top:50%;transform:translateY(-50%);cursor:pointer;color:var(--tx3)">👁</span>
          </div>
          <div style="font-size:8px;color:var(--mu);margin-top:2px">For AI Guidance · stored locally · never leaves device</div>
        </div>
        <div>
          <div class="u-sb">
            <span class="u-tx3-10">Repository</span>
            <div style="width:7px;height:7px;border-radius:50%;background:${S.settings.ghRepo?'#00d084':'#4a6888'}"></div>
          </div>
          <input id="gh-repo-inp" value="${S.settings.ghRepo||''}" placeholder="owner/repo  e.g. Murugkan/bharatmarkets"
            oninput="S.settings.ghRepo=this.value;saveSettings()"
            style="width:100%;box-sizing:border-box;background:var(--s1);border:1px solid ${S.settings.ghRepo?'rgba(0,208,132,.4)':'var(--b1)'};border-radius:7px;padding:7px 10px;color:var(--tx1);font-size:11px;font-family:var(--mono);outline:none"/>
        </div>
        <div>
          <div class="u-sb">
            <span class="u-tx3-10">GitHub PAT</span>
            <div class="u-row5">
              <div style="width:7px;height:7px;border-radius:50%;background:${S.settings.ghToken?'#00d084':'#4a6888'}"></div>
              <a href="https://github.com/settings/tokens/new?scopes=repo,workflow&description=BharatMarkets" target="_blank" style="font-size:9px;color:var(--ac);text-decoration:none">Generate ↗</a>
            </div>
          </div>
          <div class="u-rel">
            <input id="gh-token-inp" type="password" autocomplete="off" autocorrect="off" autocapitalize="off"
              value="${S.settings.ghToken||''}" placeholder="ghp_xxxxxxxxxxxx"
              oninput="S.settings.ghToken=this.value.trim();saveSettings()"
              style="width:100%;box-sizing:border-box;background:var(--s1);border:1px solid ${S.settings.ghToken?'rgba(0,208,132,.4)':'var(--b1)'};border-radius:7px;padding:7px 36px 7px 10px;color:var(--tx1);font-size:11px;font-family:var(--mono);outline:none"/>
            <span onclick="toggleKeyVis('gh-token-inp')" style="position:absolute;right:10px;top:50%;transform:translateY(-50%);cursor:pointer;color:var(--tx3)">👁</span>
          </div>
          <div style="font-size:8px;color:var(--mu);margin-top:2px">Needs scopes: <b>repo</b> + <b>workflow</b></div>
        </div>
      </div>
    </div>

    <!-- ── Section: Data Fetch ── -->
    <div class="u-card">
      <div style="padding:10px 13px;background:rgba(0,188,212,.06);border-bottom:1px solid var(--b1)">
        <div style="font-size:12px;font-weight:700;color:#4dd0e1">⚡ Data Fetch</div>
        <div class="u-sub">Trigger GitHub Actions to refresh prices & fundamentals</div>
      </div>
      <div style="padding:10px 13px;font-size:10px;color:var(--tx3);line-height:1.8;border-bottom:1px solid var(--b1)">
        <b class="u-tx2">Prices</b> — Updated every 15 min during NSE hours (9:15–15:35) via scheduled Action<br>
        <b class="u-tx2">Fundamentals</b> — Updated daily at 6PM IST via scheduled Action<br>
        Use manual triggers below if you need fresh data immediately.
      </div>
      <div style="padding:10px 13px;display:flex;flex-direction:column;gap:7px">
        <button onclick="manualTriggerWorkflow('prices_only')"
          style="width:100%;padding:10px;background:rgba(0,188,212,.08);border:1px solid rgba(0,188,212,.3);border-radius:8px;color:#4dd0e1;font-size:11px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif;text-align:left">
          ▶ Fetch Prices Now &nbsp;<span class="u-9op">updates prices.json (~2 min)</span>
        </button>
        <button onclick="manualTriggerWorkflow('fundamentals_only')"
          style="width:100%;padding:10px;background:rgba(156,39,176,.08);border:1px solid rgba(156,39,176,.3);border-radius:8px;color:#ce93d8;font-size:11px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif;text-align:left">
          ▶ Fetch Fundamentals Now &nbsp;<span class="u-9op">updates fundamentals.json (~5 min)</span>
        </button>
        <button onclick="manualTriggerWorkflow('all')"
          style="width:100%;padding:10px;background:rgba(245,166,35,.08);border:1px solid rgba(245,166,35,.3);border-radius:8px;color:#ffbf47;font-size:11px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif;text-align:left">
          ▶ Fetch Both Now &nbsp;<span class="u-9op">prices + fundamentals</span>
        </button>
      </div>
    </div>

    <!-- ── Section: Diagnostic ── -->
    <div class="u-card">
      <div class="u-indig">
        <div class="u-ind">🔌 Diagnostic</div>
        <div class="u-sub">Test GitHub connection · verify workflow · check all 3 steps</div>
      </div>
      <div style="padding:10px 13px;display:flex;flex-direction:column;gap:8px">
        <button onclick="testGitHubConnection()"
          style="width:100%;padding:10px;background:rgba(99,102,241,.1);border:1px solid rgba(99,102,241,.4);border-radius:8px;color:#818cf8;font-size:12px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif">
          🔌 Run Full Diagnostic
        </button>
        <div id="gh-diag" style="display:none;background:var(--bg);border:1px solid var(--b1);border-radius:8px;padding:10px;font-family:'JetBrains Mono',monospace;font-size:10px;line-height:1.9"></div>
        <div id="fetch-result" style="display:none;background:var(--bg);border:1px solid var(--b1);border-radius:8px;padding:10px;font-family:'JetBrains Mono',monospace;font-size:10px"></div>
      </div>
    </div>

    <!-- ── Section: Guidance Debug ── -->
    <div class="u-card">
      <div class="u-indig">
        <div class="u-ind">🔍 Guidance Debug</div>
        <div class="u-sub">Inspect what GUIDANCE data is loaded in memory</div>
      </div>
      <div class="u-pad" style="display:flex;flex-direction:column;gap:8px">
        <button onclick="showGuidanceDebug()"
          style="width:100%;padding:10px;background:rgba(100,181,246,.08);border:1px solid rgba(100,181,246,.25);border-radius:8px;color:#64b5f6;font-size:12px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif">
          🔍 Inspect GUIDANCE
        </button>
        <pre id="guidance-debug-out"
          style="font-family:'JetBrains Mono',monospace;font-size:9px;color:var(--tx2);background:#02040a;border:1px solid #1e3350;border-radius:6px;padding:8px;white-space:pre-wrap;word-break:break-all;max-height:320px;overflow-y:auto;margin:0">Tap above to inspect</pre>
      </div>
    </div>

    <!-- ── Section: Clear Portfolio ── -->
    <div class="u-card">
      <div style="padding:10px 13px;background:rgba(255,59,92,.06);border-bottom:1px solid var(--b1)">
        <div style="font-size:12px;font-weight:700;color:#ff6b85">🗑 Clear Portfolio</div>
        <div class="u-sub">Remove all holdings from the app. Analysis data is kept.</div>
      </div>
      <div class="u-pad">
        <button onclick="clearPortfolio()"
          style="width:100%;padding:10px;background:rgba(255,59,92,.08);border:1px solid rgba(255,59,92,.3);border-radius:8px;color:#ff6b85;font-size:12px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif">
          🗑 Clear All Holdings
        </button>
      </div>
    </div>

    <!-- ── Section: Push App ── -->
    ${ghOk?`
    <div class="u-card">
      <div class="u-indig">
        <div class="u-ind">⬆ Push App to GitHub</div>
        <div class="u-sub">Save latest index.html to repo — accessible from any device</div>
      </div>
      <div class="u-pad">
        <button id="push-btn" onclick="pushIndexToGitHub()"
          style="width:100%;padding:10px;background:rgba(99,102,241,.1);border:1px solid rgba(99,102,241,.35);border-radius:8px;color:#818cf8;font-size:12px;font-weight:700;cursor:pointer;font-family:'Syne',sans-serif">
          ⬆ Push index.html to GitHub
        </button>
      </div>
    </div>`:''}

  </div>`;
}

function showGuidanceDebug(){
  const keys = Object.keys(GUIDANCE);
  const out = [];
  out.push('GUIDANCE in memory: ' + keys.length + ' stocks');
  out.push('Keys: ' + (keys.join(', ') || '(none)'));
  out.push('');
  keys.forEach(sym => {
    const g = GUIDANCE[sym];
    out.push('── ' + sym + ' ──');
    out.push('  all keys: ' + Object.keys(g).join(', '));
    out.push('  tone: '           + (g.tone             || '—'));
    out.push('  summary: '        + (g.summary           || '—').slice(0, 80));
    out.push('  action_signal: '  + (g.action_signal     || '—'));
    out.push('  revenue_guidance:'+ (g.revenue_guidance  || '—'));
    out.push('  updated: '        + (g.updated           || '—'));
    out.push('');
  });
  if(!keys.length) out.push('⚠ GUIDANCE is empty — nothing loaded into memory.');

  out.push('── localStorage bm_guidance ──');
  try {
    const raw = localStorage.getItem('bm_guidance');
    if(raw){
      const parsed = JSON.parse(raw);
      const lsKeys = Object.keys(parsed);
      out.push('Keys (' + lsKeys.length + '): ' + lsKeys.join(', '));
      lsKeys.forEach(sym => {
        const g = parsed[sym];
        out.push('  ' + sym + ': tone=' + (g.tone||'—') + ' updated=' + (g.updated||'—'));
      });
    } else {
      out.push('(empty — nothing in localStorage)');
    }
  } catch(e) {
    out.push('parse error: ' + e.message);
  }

  const el = document.getElementById('guidance-debug-out');
  if(el) el.textContent = out.join('\n');
}

// Load static data from JSON files
