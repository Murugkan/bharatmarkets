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

**Critical:** `app-boot.js` must be the last `<script>` in `index.html`.

### Data Files
| File | Purpose |
|---|---|
| `symbols.json` | Single source of truth — all portfolio + watchlist stocks with ISIN + resolved sym |
| `prices.json` | Live prices fetched by scheduled Action. Contains: ltp, changePct, pe, pb, eps, roe, w52h/l, opm, npm |
| `fundamentals.json` | Full fundamentals fetched daily. 1-hour localStorage cache (`fund_cache`) |
| `guidance.json` | Concall analysis — committed by app on save |
| `charts/SYM.json` | OHLC bar data per symbol |
| `macro_data.json` | Static macro data |
| `symbol_map.json` | NSE→Yahoo Finance ticker overrides + index symbols |
| `index.html` | HTML structure + all CSS |

### GitHub Actions Workflows
| File | Purpose |
|---|---|
| `.github/workflows/fetch-prices-scheduled.yml` | **Schedule only** — runs `fetch_prices.py` every 15min during market hours. No conditions, no inputs. Dead simple. |
| `.github/workflows/fetch-prices.yml` | **Manual dispatch only** — handles `all`, `prices_only`, `fundamentals_only`, `clean` with RESOLVE + CLEAN_STALE |
| `.github/workflows/pages.yml` | Minifies all `app-*.js` → `.min.js`, deploys to GitHub Pages |
| `.github/workflows/keepalive.yml` | Commits `.keepalive` weekly — prevents GitHub disabling schedules |

**Why two separate workflow files for fetch:**
Having both `schedule` and `workflow_dispatch` in one workflow caused GitHub's scheduler to fire unpredictably (only 2 runs/day instead of every 15min). Split into separate files fixes this.

**pages.yml watches:** `index.html` + all `app-*.js` files. Must include ALL module files or deploys get skipped silently.

---

## Cross-Module Globals (declared in app-core.js only)
```js
let S = { portfolio, watchlist, settings, ... }  // all UI + app state
let FUND = {}          // { SYM: fundamentals } — populated by loadFundamentals()
let GUIDANCE = {}      // { SYM: concall data } — populated by loadGuidanceFromGitHub()
let ISIN_MAP = {}      // { ISIN: sym } — built from symbols.json on boot
let fundLoaded = false
let pfRefreshing = false
let pfLastRefresh = null
let MACRO_DATA = []
let _staticDataReady   // Promise — resolves when ISIN_MAP is populated
```

**Never re-declare these in module files.** `NSE_DB` is fully removed — never reference it.

---

## Data Flow

### Boot Sequence
```
app-core.js     → globals declared
app-import.js   → import functions ready
app-portfolio.js → loadFundamentals, mergeHolding, renderPortfolio ready
app-watchlist.js → renderWatchlist, GitHub sync ready
app-drill.js    → renderOverview, charts ready
app-analysis.js → renderAnalysis, loadGuidanceFromGitHub ready
app-settings.js → renderUpload ready
app-boot.js     → boot():
  1. loadState()              — restore S from localStorage
  2. render()                 — immediate render with cached data
  3. loadStaticData()         — fetch ./symbols.json → build ISIN_MAP (same-origin, no CORS)
     → render() again
  4. loadFundamentals()       — fetch fundamentals.json → populate FUND
     → render() again
  5. loadGuidanceFromGitHub() — fetch guidance.json → populate GUIDANCE
     → render() again
```

### ISIN_MAP — Critical for Import
- Built from `./symbols.json` (same-origin Pages URL — **not** raw.githubusercontent.com)
- `_staticDataReady` Promise resolves when complete
- `processImportText()` **must** `await ensureStaticData()` before parsing
- Without ISIN_MAP, import derives wrong symbols from names (ACMESOLARHOL vs ACMESOLAR)
- `nse_db.json` **deprecated/removed** — never use NSE_DB

### Stock Import Flow
1. User drops CDSL XLS → SheetJS → CSV
2. `processImportText()` → `await ensureStaticData()` → `parseCDSLXls()`
3. `ISIN_MAP[isin]` → correct sym. If missing: best-guess sym + warning
4. `applyImport()` → `S.portfolio` → `savePF()`
5. `autoSyncPortfolioSymbols()` → commits `symbols.json` → triggers `fetch_type:'all'`
6. Workflow runs with `RESOLVE=true` → Yahoo confirms all syms → writes back `symbols.json`

### Price & Data Refresh Flow

**Scheduled (automatic):**
- `fetch-prices-scheduled.yml` fires every 15min during 3–11 UTC (8:30–4:30 IST) Mon-Fri
- Commits updated `prices.json` + `charts/` to repo
- GitHub free tier may throttle to 2–3 runs/day in practice

**Prices ↻ button (header):**
- `headerPricesTap()` → `refreshPortfolioData()`
- Fetches `raw.githubusercontent.com/{repo}/main/prices.json` (bypasses Pages CDN lag)
- Updates `h.ltp`, `h.liveLtp`, `h.change`, `h.chg5d`, `h.week52H/L`
- **Also updates `FUND[sym]` in-memory** with fresh fields (pe, pb, chg1d, opm, npm etc.) — bypasses 1-hour fundamentals cache
- Timestamp shown = `prices.json.updated` (when Action last ran, not when app fetched)

**Fund ↻ button (header):**
- `headerFundTap()` → `manualTriggerWorkflow('fundamentals_only')`
- Clears `fund_cache` + `fund_cache_ts` from localStorage immediately
- Waits 90s for Action to complete → `loadFundamentals(true)` (force refresh) → render()

**Upload tab buttons → trigger `fetch-prices.yml` (manual dispatch):**
- ▶ Fetch Prices Now → `prices_only`
- ▶ Fetch Fundamentals Now → `fundamentals_only`
- ▶ Fetch Both → `all` with `RESOLVE=true`

**Auto-refresh intervals:**
- Every 5min during market hours (IST 9:15–15:35)
- Every 30min outside market hours
- On visibility change (returning to app)

### Workflow Trigger Map
| fetch_type | RESOLVE | CLEAN_STALE | When |
|---|---|---|---|
| `all` | true | false | After import / watchlist add |
| `prices_only` | false | false | Manual ↻ Prices button |
| `fundamentals_only` | false | false | Manual ↻ Fund button |
| `clean` | false | true | After delete / clear |
| scheduled | false | false | fetch-prices-scheduled.yml |

### GUIDANCE Data Flow
- Saved: `saveAnalysis(sym)` → `parseAnalysisTable()` → `GUIDANCE[sym]` → `saveGuidanceAll()`
  - `saveGuidanceAll()` = localStorage + `saveGuidanceToGitHub()` (commits `guidance.json`)
- Loaded on boot: `loadGuidanceFromGitHub()` — fetches `./guidance.json`, merges with localStorage
  - GitHub authoritative for parsed fields; localStorage retains `raw_table` + `insights`
- `clearStockAnalysis(sym)` — wipes concall fields, **preserves `.insights`**
- `deletePortfolioStock(sym)` — removes from `S.portfolio` only, **GUIDANCE untouched**
- `clearPortfolio()` — removes all holdings, **GUIDANCE untouched**

---

## Key Functions by Module

### app-core.js
| Function | Purpose |
|---|---|
| `loadState()` | Restore S from localStorage |
| `loadStaticData()` | Fetch `./symbols.json` → build ISIN_MAP. Sets `_staticDataReady` |
| `ensureStaticData()` | Await `_staticDataReady` — call before ISIN_MAP usage |
| `render()` | Main dispatcher → routes to tab render functions |
| `openStock(w)` | Open drill-down for watchlist stock |

### app-import.js
| Function | Purpose |
|---|---|
| `processImportText()` | **async** — awaits ensureStaticData(), routes to parser |
| `parseCDSLXls(csv)` | Parse CDSL XLS → holdings array |
| `applyImport(mode)` | Write parsed holdings to S.portfolio |
| `autoSyncPortfolioSymbols()` | Commit symbols.json + trigger `all` workflow |

### app-portfolio.js
| Function | Purpose |
|---|---|
| `loadFundamentals(forceRefresh)` | Fetch fundamentals.json → populate FUND. 1hr cache unless forceRefresh |
| `mergeHolding(h)` | Merge holding with FUND. ltp = h.liveLtp → f.ltp → 0 |
| `refreshPortfolioData()` | Fetch prices.json from raw.githubusercontent.com. Updates h.* AND FUND[sym].* |
| `sortRows(rows, skey, sdir)` | String cols (sym/sector/name/sig) default to asc |
| `renderPortfolio(c)` | Bloomberg screener. Footer uses filtered `rows` not full `pf` |
| `showPfDebug()` | DBG button — FUND keys, per-stock match, ISIN_MAP count |

### app-watchlist.js
| Function | Purpose |
|---|---|
| `headerPricesTap()` | Calls refreshPortfolioData() |
| `headerFundTap()` | Triggers workflow + clears cache + force-reloads after 90s |
| `wlSearch(val)` | Searches FUND keys + portfolio (NSE_DB removed) |
| `testGitHubConnection()` | 3-step diagnostic |
| `renderMovers(c)` | Uses global `fundLoaded` — do not re-declare locally |

### app-analysis.js
| Function | Purpose |
|---|---|
| `openAnalysisSheet(sym)` | `hasDone = g && (g.updated \|\| g.tone \|\| g.summary \|\| g.revenue_guidance)` |
| `saveAnalysis(sym)` | Parse + save pasted Claude response |
| `loadGuidanceFromGitHub()` | Fetches `./guidance.json`, merges with localStorage |

---

## Key Principles
- **Analyse first, confirm before coding**
- `app-boot.js` loads last — calls functions from all other modules
- Cross-module globals in `app-core.js` only — never re-declare in modules
- `processImportText` must `await ensureStaticData()` before touching ISIN_MAP
- `symbols.json` fetched via `./` (same-origin) — avoids CORS issues
- `prices.json` + `fundamentals.json` fetched via `raw.githubusercontent.com` — avoids Pages CDN lag
- `NSE_DB` fully removed — never reference it anywhere
- Schedule and manual dispatch in **separate workflow files** — mixing causes scheduler to fire unpredictably
- `pages.yml` must watch all `app-*.js` files
- `keepalive.yml` commits weekly — prevents GitHub disabling schedules
- Deleting a stock must never wipe GUIDANCE or insights
- String sort cols default asc; grand total uses filtered `rows` not full `pf`

---

## Known Issues / Pending
1. **Guidance** — only 3 stocks in `guidance.json`. Need to investigate `saveGuidanceToGitHub()` — may not be committing correctly for all stocks.
2. **5 stocks ISIN not in map** — CAPITALNUMBE, HIGHENERGYBA, IBSCL, KPL, SHREEREFRIGE — will resolve after next import triggers `RESOLVE=true`.
3. **Schedule frequency** — GitHub free tier throttles `*/15` crons to ~2–3 runs/day. No fix available on free tier.
