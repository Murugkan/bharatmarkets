# Bharat·Markets — GitHub Pages Edition

A mobile-first NSE stock watchlist app that runs entirely on GitHub Pages.  
No server. No Cloudflare. No API keys. **Safari-safe — zero CORS.**

---

## How It Works

```
GitHub Actions (Python)          GitHub Pages (static)
─────────────────────            ─────────────────────
Every 15 min (market hours)  →  prices.json  ←  iPhone Safari fetches ./prices.json
yfinance fetches NSE quotes       (same origin = no CORS)
commits to repo
```

---

## Deploy in 5 Minutes

### 1. Fork / create this repo

Push all files to a GitHub repo:

```
your-repo/
  index.html              ← the iPhone web app
  prices.json             ← seed file (auto-overwritten by Action)
  fetch_prices.py         ← price fetcher script
  watchlist.txt           ← symbols to fetch (edit this)
  .github/workflows/
    fetch-prices.yml      ← the GitHub Action
```

### 2. Enable GitHub Pages

Go to **Settings → Pages → Source → Deploy from branch → `main` / `(root)`**

Your app will be live at: `https://YOUR_USERNAME.github.io/YOUR_REPO/`

### 3. Run the Action once manually

Go to **Actions → "Fetch NSE Prices" → Run workflow**

This writes `prices.json` with real data immediately.  
After that it runs automatically every 15 min on weekdays during market hours.

### 4. Open on iPhone

Visit `https://YOUR_USERNAME.github.io/YOUR_REPO/` in Safari  
→ Tap **Share → Add to Home Screen** for a full-screen native feel.

---

## Customise Which Stocks Are Fetched

Edit `watchlist.txt` — one NSE symbol per line (no `.NS`):

```
RELIANCE
TCS
INFY
HDFCBANK
```

Commit the change. The next Action run will fetch prices for your updated list.

The in-app search lets you add any of 80+ stocks to your personal watchlist.  
Prices for those symbols are loaded from `prices.json` — if the symbol isn't  
in `watchlist.txt`, add it there so the Action fetches it too.

---

## Files

| File | Purpose |
|---|---|
| `index.html` | Complete iPhone web app (single file) |
| `fetch_prices.py` | Python script run by GitHub Actions |
| `.github/workflows/fetch-prices.yml` | Scheduled Action (every 15 min, market hours) |
| `watchlist.txt` | Symbols to fetch |
| `prices.json` | Auto-generated price data (do not edit manually) |

---

## Features

- **Watchlist** with search across 80+ NSE stocks
- **Scrolling ticker strip**
- **Price freshness indicator** (green/amber/red based on age)
- **Stock drill-down**: Fundamentals · Technicals · News
- **AI analysis** on each stock (Claude via Anthropic API)
- **52-week range bar**, OHLC, MA50/MA200 signals
- **Offline-first**: last prices cached in localStorage
- Add to Home Screen on iPhone for native app feel

---

## Data Freshness

- During market hours (Mon–Fri 9:15–15:30 IST): refreshed every 15 min
- Outside market hours: last fetched prices remain in the file
- The app shows a coloured freshness dot: 🟢 < 30 min · 🟡 30–120 min · 🔴 > 2 hrs

---

## Limitations

- Price data is delayed ~15 min during market hours (Action schedule)
- GitHub Actions free tier: 2,000 min/month — this workflow uses ~30 min/month
- yfinance data accuracy is best-effort (Yahoo Finance sourced)
