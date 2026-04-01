// ── Boot — must load LAST, after all app-*.js modules ──────────
// loadFundamentals  → app-portfolio.js
// loadGuidanceFromGitHub → app-analysis.js
// All other functions → app-core.js

function boot(){
  loadState();
  buildTicker();
  setInterval(updClock,10000);
  updClock();

  // Load static data first (ISIN_MAP), then render
  loadStaticData().then(()=>{
    render();
    buildTicker();
  });

  // Also render immediately with cached state while static data loads
  render();

  // Load fresh data in background
  loadFundamentals()
    .catch(e => console.warn('loadFundamentals failed:', e))
    .then(() => { buildTicker(); render(); });

  loadGuidanceFromGitHub()
    .catch(e => console.warn('loadGuidanceFromGitHub failed:', e))
    .then(() => render());
}
boot();
