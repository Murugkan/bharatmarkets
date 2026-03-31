// ── Boot — must load LAST, after all app-*.js modules ──────────
// loadFundamentals  → app-portfolio.js
// loadGuidanceFromGitHub → app-analysis.js
// All other functions → app-core.js

function boot(){
  loadState();
  loadStaticData().then(()=>{ buildTicker(); render(); });
  buildTicker();
  setInterval(updClock,10000);
  updClock();

  // Render immediately with whatever is in localStorage — never block on network
  render();

  // Then load fresh data in background and re-render when ready
  loadFundamentals()
    .catch(e => console.warn('loadFundamentals failed:', e))
    .then(() => { buildTicker(); render(); });

  loadGuidanceFromGitHub()
    .catch(e => console.warn('loadGuidanceFromGitHub failed:', e))
    .then(() => render());
}
boot();
