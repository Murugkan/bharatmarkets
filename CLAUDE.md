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
| `app.js` | All JS (~5500 lines) |
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
- App writes `name + isin + source`, `resolved:false`
- Fetch workflow resolves `sym` via Yahoo search, sets `resolved:true`
- Watchlist stocks set `resolved:true` immediately (sym known from NSE_DB)

---

## Data Flow

### Stock Import
1. User imports CDSL XLS → app parses name + isin (never trusts CDSL symbol)
2. `syncSymbolsDB()` → writes entries to `symbols.json` on GitHub
3. Triggers `all` workflow → `RESOLVE=true` → Yahoo resolves each name → writes `sym` back
4. App fetches from `raw.githubusercontent.com` (not GitHub Pages — no deploy lag)

### Scheduled Fetch
- Prices: every 15min, 3:00-11:00 UTC Mon-Fri (8:30-4:30 IST)
- Fundamentals: daily 12:30 UTC Mon-Fri (6PM IST)
- `RESOLVE=false` on scheduled runs — no Yahoo search calls

### Delete Flow
- Watchlist remove or portfolio clear → `syncSymbolsDB()` → triggers `clean` workflow
- `clean` → `CLEAN_STALE=true` → wipes all data not in current `symbols.json`
- Cleans: `prices.json`, `fundamentals.json`, `guidance.json`, `charts/`

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

- **Raw GitHub URLs** — data files fetched from `raw.githubusercontent.com` not `./` because Pages only redeploys on `index.html`/`app.js` changes, not data file commits
- **No sym guessing in app** — import writes name+isin only; workflow resolves sym via Yahoo
- **symbol_map.json** — single shared exchange override map replacing hardcoded `SPECIAL_MAP` (fetch_prices) and `NSE_TO_YAHOO` (fetch_fundamentals)
- **CLEAN_STALE at step level** — must be step-level `env:` in workflow yml, not job-level (GitHub Actions expression bug)
- **nse_db.json** — kept for watchlist local search only (2309 stocks); no longer used for import resolution
- **Watchlist search** — local NSE_DB for instant results + GFin↗ button opens Google Finance for stocks not in local DB

---

## Known Issues / Pending

1. **nse_db.json** — decision pending on whether to keep or drop. Only use is watchlist local search. If dropped, users rely entirely on GFin↗ button.

2. **Analysis tab restructure** — current tab shows flat list of 100 stocks, no search. Agreed design:
   - Action Queue (top) — outdated/pending stocks sorted by position size
   - Coverage Summary (middle) — visual coverage health
   - Search + Browse (bottom, collapsed) — filter by symbol/name
   - Search is the immediate pain point to fix first

3. **syncSymbolsDB verification** — confirm PAT has `contents:write` scope and repo field is `Murugkan/bharatmarkets` (no https://, no trailing slash). Silent failure if wrong.

4. **Portfolio sort bug** — columns 2-4 (Sector, Pos, Neg) sort broken. Root cause: `togglePfSort` has inline sort block missing these cases instead of delegating to shared `sortRows()`. Not yet fixed.

---

## Files to Upload (Current Session)
All verified 29/29 tests passing:
- `app.js`
- `fetch_prices.py`
- `fetch_fundamentals.py`
- `fetch-prices.yml` → `.github/workflows/fetch-prices.yml`
- `symbol_map.json` (new file)

## After Uploading
1. Trigger `clean` from Actions tab → wipes stale data
2. Clear portfolio in app
3. Re-import CDSL file → auto-triggers `all` workflow
4. Verify `symbols.json` gets updated (check repo directly)
