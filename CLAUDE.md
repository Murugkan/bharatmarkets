# BharatMarkets Pro — Project State
*Last updated: March 2026*

## Live
- **URL:** murugkan.github.io/bharatmarkets
- **Repo:** github.com/Murugkan/bharatmarkets
- **Stack:** iPhone PWA, GitHub Pages, vanilla JS, GitHub Actions

---

## Architecture

### Files
| File | Purpose |
|---|---|
| `index.html` | HTML + CSS only |
| `app.js` | All JS (~5800 lines) |
| `symbols.json` | Single source of truth — portfolio + watchlist stocks |
| `prices.json` | Live prices, fetched every 15min |
| `fundamentals.json` | Fundamentals, fetched daily |
| `guidance.json` | Concall analysis results (manual, per stock) |
| `charts/SYM.json` | OHLC chart data per symbol |
| `macro_data.json` | Static macro data |
| `nse_db.json` | NSE stock list — watchlist local search only |
| `symbol_map.json` | Shared exchange overrides (NSE→Yahoo mapping) |
| `fetch_prices.py` | Fetches prices.json + charts/ |
| `fetch_fundamentals.py` | Fetches fundamentals.json + guidance.json cleanup |
| `fetch-prices.yml` | GitHub Actions workflow |
| `pages.yml` | GitHub Pages deploy — triggers on index.html/app.js only |

### symbols.json schema
```json
[{
  "sym":      "ZENTEC",
  "name":     "ZEN TECHNOLOGIES LIMITED",
  "isin":     "INE251B01027",
  "sector":   "Industrials",
  "source":   ["portfolio"],
  "resolved": true
}]
```

---

## Data Flow

### Stock Import
1. User imports CDSL XLS → app parses name + isin
2. `syncSymbolsDB()` → writes entries to `symbols.json` on GitHub
3. Triggers `all` workflow → `RESOLVE=true` → Yahoo resolves sym → writes back
4. App fetches from `raw.githubusercontent.com` (not Pages — no deploy lag)

### Scheduled Fetch
- Prices: every 15min, 3:00-11:00 UTC Mon-Fri
- Fundamentals: daily 12:30 UTC Mon-Fri
- `RESOLVE=false` on scheduled runs

### Delete Flow
- Watchlist remove or portfolio clear → `syncSymbolsDB()` → triggers `clean` workflow
- `clean` → `CLEAN_STALE=true` → wipes all data not in current `symbols.json`

### Workflow Trigger Map
| fetch_type | RESOLVE | CLEAN_STALE | When |
|---|---|---|---|
| `all` | true | false | After import / watchlist add |
| `prices_only` | false | false | Manual ↻ Prices |
| `fundamentals_only` | false | false | Manual ↻ Fund |
| `clean` | false | true | After delete / clear |
| scheduled | false | false | Automatic |

---

## Key Decisions Made

- **Raw GitHub URLs** — data fetched from `raw.githubusercontent.com` not `./`
- **No sym guessing in app** — import writes name+isin only; workflow resolves sym
- **symbol_map.json** — single shared exchange override map
- **CLEAN_STALE at step level** — must be step-level `env:` in workflow yml
- **nse_db.json** — kept for watchlist local search only (decision pending on drop)
- **Watchlist search** — local NSE_DB + GFin↗ button for stocks not in DB

---

## Analysis Tab — Current State (March 2026)

### What was built this session
- **Coverage Summary** — progress bar + 4 pill filters (All / Pending / Outdated / Covered)
- **Action Queue** — pending + outdated stocks sorted by position value (qty × ltp)
- **Done stocks** — collapsed by default, toggle to expand
- **Search** — debounced 120ms partial re-render via `anSearchUpdate()` + `_anRenderRows()`
  - Only re-renders list rows, not full tab — preserves input focus
- **Bottom sheet** — slide-up 88vh overlay for the 3-step workflow
  - Step 1: Find BSE/NSE filing
  - Step 2: Copy prompt → Claude.ai
  - Step 3: Paste response → Save
  - Guidance card shown prominently above steps when analysis exists
- **Remove stock** — moved to portfolio drill-down header (✕ button, two-tap confirm)
  - Does NOT touch GUIDANCE or insights

### GUIDANCE data model
- `GUIDANCE[sym]` holds both concall fields AND `GUIDANCE[sym].insights`
- `clearStockAnalysis` — field-level wipe, preserves `.insights`
- `deletePortfolioStock` — removes from S.portfolio only, GUIDANCE untouched
- `clearPortfolio` — removes all holdings, GUIDANCE untouched

### Known bug — guidance card not showing (PARTIALLY FIXED)
- Root cause: `hasDone = g && g.updated` was false for stocks where
  `clearStockAnalysis` had been run (`.updated` wiped when preserving insights)
- Fix applied in session: `hasDone = g && (g.updated || g.tone || g.summary || g.revenue_guidance)`
- **Status: fix written but NOT yet deployed** — app.js edit was in working copy
  `/home/claude/app.js` at end of session, not committed to repo
- On next session: apply this one-liner fix to the uploaded app.js

### Key functions
| Function | Purpose |
|---|---|
| `_analysisStocks()` | Builds status array from portfolio + GUIDANCE |
| `renderAnalysis(c)` | Full tab render |
| `anSearchUpdate(val)` | Debounced search — updates `analysisState.search` |
| `_anRenderRows()` | Partial re-render of list only (preserves input focus) |
| `openAnalysisSheet(sym)` | Opens bottom sheet for a stock |
| `closeAnalysisSheet()` | Slides sheet down + removes from DOM |
| `setAnalysisFilter(f)` | Sets pill filter + full re-render |
| `clearStockAnalysis(sym)` | Wipes concall fields, keeps `.insights` |
| `deletePortfolioStock(sym)` | Removes from portfolio, GUIDANCE untouched |
| `saveAnalysis(sym)` | Parses + saves pasted Claude response |

---

## Portfolio Sort — Fixed
- `togglePfSort` correctly delegates to `sortRows()` for all columns
- `sortRows()` has cases for sector, pos, neg, and all other columns
- No inline sort block in `togglePfSort` — fully delegated

---

## Known Issues / Pending

1. **Guidance card not showing** — fix ready, needs deploying (see above)
2. **nse_db.json** — decision pending on whether to keep or drop
3. **`syncSymbolsDB` verification** — confirm PAT has `contents:write` scope

---

## Key Principles
- **Analyse first, confirm before coding**
- Deleting a stock must never wipe analysis/guidance data
- GitHub Pages has deploy lag — always fetch from `raw.githubusercontent.com`
- `CLEAN_STALE` env vars must be at step level in GitHub Actions
- Search inputs: debounced partial re-renders targeting specific DOM IDs
- Verification checks passing ≠ bug fixed; confirm root cause in actual logic path
