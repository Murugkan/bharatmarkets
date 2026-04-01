# BharatMarkets Pro — Project State
*Last updated: April 2026*

## Live
- **URL:** murugkan.github.io/bharatmarkets
- **Repo:** github.com/Murugkan/bharatmarkets
- **Stack:** iPhone PWA, GitHub Pages, vanilla JS, GitHub Actions

---

## Architecture

### JS Module Files (load order matters)
| File | Size | Purpose |
|---|---|---|
| `app-core.js` | 16KB | Globals, state, utils, render shell, tab routing, localStorage |
| `app-import.js` | 30KB | CDSL XLS/text import, symbol resolution, sync to GitHub |
| `app-portfolio.js` | 46KB | Fundamentals load, signal computation, portfolio table render |
| `app-watchlist.js` | 38KB | Watchlist, GitHub sync, macro tab, market movers, sector heatmap |
| `app-drill.js` | 77KB | Stock drill-down: overview, insights, technical, chart, news |
| `app-analysis.js` | 44KB | Analysis tab, concall workflow, guidance parse/save/load |
| `app-settings.js` | 14KB | Upload/settings tab, guidance debug panel |
| `app-boot.js` | 1KB | `boot()` — runs LAST after all modules are loaded |

**Critical:** `app-boot.js` must be the last `<script>` in `index.html`. It calls `loadFundamentals()` (app-portfolio.js) and `loadGuidanceFromGitHub()` (app-analysis.js) — both must exist before boot runs.

### Data Files
| File | Purpose |
|---|---|
| `symbols.json` | Single source of truth — all portfolio + watchlist stocks with ISIN + resolved sym |
| `prices.json` | Live prices fetched every 15min by GitHub Actions |
| `fundamentals.json` | Fundamentals fetched daily by GitHub Actions |
| `guidance.json` | Concall analysis (manual, per stock) — committed by app on save |
| `charts/SYM.json` | OHLC bar data per symbol |
| `macro_data.json` | Static macro indicator data |
| `symbol_map.json` | NSE→Yahoo Finance ticker overrides + index symbols |
| `index.html` | HTML structure + all CSS (including Bloomberg terminal styles) |

### GitHub Actions Workflows
| File | Purpose |
|---|---|
| `.github/workflows/fetch-prices.yml` | Price + fundamentals fetch, triggered on schedule + manual |
| `.github/workflows/pages.yml` | Minifies all app-*.js → app-*.min.js, deploys to GitHub Pages |
| `.github/workflows/keepalive.yml` | Commits `.keepalive` weekly — prevents GitHub disabling schedules |

**pages.yml watches:** `index.html`, all `app-*.js`, `pages.yml` itself. Any change to these files triggers a redeploy. Previously only watched `app.js` (old monolith) — this was a bug causing deployments to be missed.

---

## Cross-Module Globals (declared in app-core.js)
All globals shared across modules are declared in `app-core.js` which loads first:

```js
let S = { portfolio, watchlist, settings, ... }  // all UI + app state
let FUND = {}          // { SYM: fundamentals } — populated by app-portfolio.js
let GUIDANCE = {}      // { SYM: concall data } — populated by app-analysis.js
let ISIN_MAP = {}      // { ISIN: sym } — built from symbols.json on boot
let fundLoaded = false
let pfRefreshing = false
let pfLastRefresh = null
let NSE_DB = []        // DEPRECATED — always empty, nse_db.json removed
let MACRO_DATA = []
let _staticDataReady   // Promise — resolves when ISIN_MAP is populated
```

**Never re-declare these in module files.** The previous bug was `FUND`, `GUIDANCE` etc. being declared in `app-portfolio.js`, causing them to be undefined when `app-core.js` (which loads first) tried to use them.

---

## Data Flow

### Boot Sequence
```
app-core.js loads    → globals declared
app-import.js loads  → import functions ready
app-portfolio.js loads → loadFundamentals, mergeHolding, renderPortfolio ready
app-watchlist.js loads → renderWatchlist, GitHub sync ready
app-drill.js loads   → renderOverview, charts ready
app-analysis.js loads → renderAnalysis, loadGuidanceFromGitHub ready
app-settings.js loads → renderUpload ready
app-boot.js loads    → boot() called:
  1. loadState()              — restore S from localStorage
  2. render()                 — immediate render with cached data
  3. loadStaticData()         — fetch symbols.json → build ISIN_MAP
     → then render() again
  4. loadFundamentals()       — fetch fundamentals.json → populate FUND
     → then render() again
  5. loadGuidanceFromGitHub() — fetch guidance.json → populate GUIDANCE
     → then render() again
```

### ISIN_MAP Build (critical for import)
- `loadStaticData()` fetches `symbols.json` and builds `ISIN_MAP = { ISIN: sym }`
- `_staticDataReady` is a Promise that resolves when this is done
- `processImportText()` calls `await ensureStaticData()` before parsing — **never skip this**
- Without ISIN_MAP, import derives wrong symbols from stock names (e.g. ACMESOLARHOL instead of ACMESOLAR)
- `nse_db.json` is **deprecated and removed** — do not reference NSE_DB anywhere

### Stock Import Flow
1. User drops CDSL XLS → `handleFileSelect()` → SheetJS → CSV text
2. `processImportText()` → `await ensureStaticData()` → `parseCDSLXls()`
3. For each row: `ISIN_MAP[isin]` → correct sym (e.g. ACMESOLAR)
4. If ISIN not in map: derive best-guess sym, add warning — workflow will resolve
5. `applyImport()` → writes to `S.portfolio` → `savePF()`
6. `autoSyncPortfolioSymbols()` → commits `symbols.json` to GitHub
7. Triggers `fetch_type:'all'` workflow → `RESOLVE=true` → Yahoo confirms all syms
8. Workflow writes back `symbols.json` with confirmed symbols + fetches prices/fundamentals

### Price Refresh Flow
- On boot: `refreshPortfolioData()` called if portfolio non-empty
- Fetches `./prices.json` → matches `quotes[h.sym]` against `S.portfolio[].sym`
- Updates `h.ltp`, `h.liveLtp`, `h.change`, `h.chg5d`, `h.week52H/L`
- **Sym must match exactly** — if portfolio has wrong sym, prices won't apply

### Scheduled Fetch (GitHub Actions)
- Prices: `*/15 3-11 * * 1-5` → every 15min, 8:30–4:30 IST Mon-Fri
- Fundamentals: `30 12 * * 1-5` → daily 6PM IST Mon-Fri
- `RESOLVE=false` on scheduled runs — only resolves on `fetch_type:'all'`
- **keepalive.yml** commits `.keepalive` weekly — required to prevent GitHub auto-disabling schedules on "inactive" repos

### Workflow Trigger Map
| fetch_type | RESOLVE | CLEAN_STALE | When |
|---|---|---|---|
| `all` | true | false | After import / watchlist add |
| `prices_only` | false | false | Manual ↻ Prices |
| `fundamentals_only` | false | false | Manual ↻ Fund |
| `clean` | false | true | After delete / clear |
| scheduled | false | false | Automatic |

### GUIDANCE Data Flow
- Saved: `saveAnalysis(sym)` → `parseAnalysisTable()` → `GUIDANCE[sym]` → `saveGuidanceAll()`
  - `saveGuidanceAll()` = localStorage + `saveGuidanceToGitHub()` (commits `guidance.json`)
- Loaded: `loadGuidanceFromGitHub()` on boot
  - Fetches `./guidance.json` → merges with localStorage
  - GitHub is authoritative for parsed fields; localStorage retains `raw_table` + `insights`
- `clearStockAnalysis(sym)` — wipes concall fields, **preserves `.insights`**
- `deletePortfolioStock(sym)` — removes from `S.portfolio` only, **GUIDANCE untouched**
- `clearPortfolio()` — removes all holdings, **GUIDANCE untouched**

---

## Key Functions by Module

### app-core.js
| Function | Purpose |
|---|---|
| `loadState()` | Restore S from localStorage on boot |
| `loadStaticData()` | Fetch symbols.json → build ISIN_MAP. Sets `_staticDataReady` Promise |
| `ensureStaticData()` | Await `_staticDataReady` — call before any ISIN_MAP usage |
| `render()` | Main render dispatcher — routes to tab render functions |
| `showTab(t, btn)` | Switch active tab |
| `openStock(w)` | Open drill-down for a watchlist stock |
| `savePF() / saveWL() / saveSettings()` | Persist to localStorage |

### app-import.js
| Function | Purpose |
|---|---|
| `processImportText(text, filename, statusEl)` | **async** — awaits ensureStaticData(), routes to parser |
| `parseCDSLXls(csv)` | Parse CDSL XLS export → holdings array |
| `parsePortfolioText(text)` | Parse manual CSV / CDSL text |
| `applyImport(mode)` | Write parsed holdings to S.portfolio |
| `autoSyncPortfolioSymbols()` | Commit symbols.json to GitHub + trigger `all` workflow |

### app-portfolio.js
| Function | Purpose |
|---|---|
| `loadFundamentals(forceRefresh)` | Fetch fundamentals.json → populate FUND |
| `mergeHolding(h)` | Merge portfolio holding with FUND data |
| `computePos(h,f) / computeNeg(h,f)` | Count bullish/bearish signals |
| `calcSignalLocal(h,f)` | BUY/HOLD/SELL signal from local data |
| `sortRows(rows, skey, sdir)` | Sort portfolio rows — string cols default asc |
| `renderPortfolio(c)` | Render Bloomberg-style screener table |
| `renderBLSRows(rows, totalCur)` | Render table body rows |
| `refreshPortfolioData()` | Fetch prices.json → update ltps |
| `openPortfolioStock(sym)` | Build selStock + open drill-down |

### app-watchlist.js
| Function | Purpose |
|---|---|
| `renderWatchlist(c)` | Render watchlist tab |
| `wlSearch(val)` | Search FUND keys + portfolio for add-to-watchlist |
| `syncWatchlistToGitHub(sym)` | Add sym to symbols.json on GitHub + trigger workflow |
| `testGitHubConnection()` | Run 3-step diagnostic: repo → workflow → trigger |
| `renderMovers(c)` | Market movers tab — gainers/losers/indices/sectors |
| `renderMacro(c)` | Macro tab |
| `drawSectorHeatmap(universe)` | Sector performance heatmap |

### app-drill.js
| Function | Purpose |
|---|---|
| `renderDrill(c)` | Drill-down shell — tabs + back button |
| `renderOverview(s)` | Price strip, metrics, position, guidance cards |
| `renderInsights(s)` | AI portfolio signal tab |
| `renderTechnical(s)` | Candlestick chart + MA overlays + signal table |
| `drawCandlestick(s)` | Canvas chart render |
| `renderFundamentals(s)` | Fundamentals tab |
| `renderNewsTab(s)` | News tab |
| `pill(txt,col) / krow(label,val,col) / blist(arr,col)` | Overview UI helpers (top-level) |

### app-analysis.js
| Function | Purpose |
|---|---|
| `_analysisStocks()` | Build status array from portfolio + GUIDANCE |
| `renderAnalysis(c)` | Full analysis tab render |
| `_anRenderRows()` | Partial re-render of list rows only (preserves search focus) |
| `openAnalysisSheet(sym)` | Slide-up bottom sheet for 3-step concall workflow |
| `hasDone` check | `g && (g.updated \|\| g.tone \|\| g.summary \|\| g.revenue_guidance)` |
| `saveAnalysis(sym)` | Parse + save pasted Claude response |
| `parseAnalysisTable(sym, text)` | Multi-format parser: table / Key:Value / numbered list |
| `clearStockAnalysis(sym)` | Wipe concall fields, keep .insights |
| `saveGuidanceToGitHub()` | Commit guidance.json to repo |
| `loadGuidanceFromGitHub()` | Fetch guidance.json, merge with localStorage |

---

## Key Principles
- **Analyse first, confirm before coding**
- `app-boot.js` must load last — it calls functions from all other modules
- Cross-module globals declared in `app-core.js` only — never re-declare in modules
- `processImportText` must `await ensureStaticData()` before touching ISIN_MAP
- `nse_db.json` is deprecated — `NSE_DB` is always `[]`, do not use
- ISIN_MAP is built from `symbols.json` (resolved entries only)
- Deleting a stock must never wipe GUIDANCE or insights
- String sort columns (sym, sector, name, sig) default to `asc` on first click
- Grand total footer uses `rows` (filtered), not `pf` (full portfolio)
- `pages.yml` must watch all `app-*.js` files — missing a file means deploys are skipped
- Scheduled workflows need `keepalive.yml` — GitHub disables them on inactive repos
- `CLEAN_STALE` env vars must be at step level in workflow yml

---

## Known Issues / Pending
1. **Guidance not loading for most stocks** — `guidance.json` on GitHub may only have 3 stocks; investigate what was committed vs what was saved locally
2. **5 stocks with ISIN not in map** — CAPITALNUMBE, HIGHENERGYBA, IBSCL, KPL, SHREEREFRIGE — workflow RESOLVE=true will confirm after next import+sync
