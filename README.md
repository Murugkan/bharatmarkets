# BharatMarkets Pro - Portfolio Management Platform

## 🎯 What is BharatMarkets?

BharatMarkets is a **lightweight, web-based portfolio management platform** for Indian stock investors. It lets you track your holdings, analyze fundamentals, and make data-driven investment decisions—all without ads, paywalls, or external tracking.

**Live Demo:** [murugkan.github.io/bharatmarkets](https://murugkan.github.io/bharatmarkets)

---

## ✨ Key Features

### 1. **Portfolio Management**
- **Import holdings** from CSV (stock symbol, quantity, average price)
- **Track P&L** (profit/loss) with real-time prices
- **Auto-calculate** invested amount, PNL%, 1-day returns
- **Visualize** portfolio by sector (color-coded bar chart)
- **Sort & filter** by any metric (PE, ROE%, OPM%, etc.)

### 2. **Fundamental Analysis**
- **30+ metrics per stock:** PE, PB, EPS, ROE%, ROCE%, OPM%, NPM%, MCAP, SALES, EBITDA, CFO
- **Valuation:** P/E, P/B, EPS, Book Value
- **Returns:** ROE%, OPM%, NPM% (profit margins)
- **Size:** Market cap, Sales, EBITDA, Cash flow
- **Performance:** 52-week high/low, ATH%, Beta, Dividend yield
- **Historical:** Quarterly data for trend analysis

### 3. **Real-Time Data**
- **Live prices** from Yahoo Finance (LTP, 1D%, high/low)
- **Latest fundamentals** from Yahoo Finance + Screener.in
- **Weekly updates** via GitHub Actions (automatic)
- **99 NSE stocks** pre-configured (extensible)

### 4. **Offline-First**
- **IndexedDB storage** — Portfolio persists locally in browser
- **No server needed** — All computation happens client-side
- **Works offline** — View portfolio without internet
- **Privacy** — Your data never leaves your device

---

## 🏗️ Architecture

```
┌─ DATA LAYER ──────────────────────────────────────┐
│                                                    │
│  unified-symbols.json      (99 stocks)            │
│  • ticker, name, sector, isin                      │
│  ↓                                                 │
│  ├─ fetch_fundamentals.py ─→ fundamentals.json   │
│  │  (PE, ROE%, OPM%, MCAP, etc.)                  │
│  │                                                 │
│  └─ fetch_prices.py ─→ prices.json               │
│     (LTP, 1D%, changePct)                         │
│                                                    │
└────────────────────────────────────────────────────┘
           ↓
    Browser Downloads
           ↓
┌─ CLIENT LAYER ─────────────────────────────────────┐
│                                                    │
│  index.html (Portfolio Page)                      │
│  • SYNC button fetches 3 JSON files               │
│  • Merges data in JavaScript                      │
│  • Stores in IndexedDB (OnyxPortfolioDB)         │
│  • Renders table with 30+ columns                │
│                                                    │
│  data.html (Data Management)                      │
│  • Upload CSV file                                │
│  • View available stocks                          │
│                                                    │
│  app-import.js (7-Step Wizard)                    │
│  • Parse CSV → Map tickers → Validate → Store   │
│  • Updates unified-symbols.json                   │
│                                                    │
└────────────────────────────────────────────────────┘
```

---

## 🔄 Data Flow (Complete)

### **Step 1: Portfolio Import (Manual)**
```
your-portfolio.csv
     ↓
data.html (Upload)
     ↓
app-import.js (7 steps)
  1. Read CSV
  2. Extract: ticker, qty, avg
  3. Map to NSE symbols
  4. Validate against unified-symbols.json
  5. Show preview
  6. Store in IndexedDB
  7. Update unified-symbols.json
     ↓
unified-symbols.json (99 stocks with portfolio flag)
```

**CSV Format Expected:**
```
Symbol,Quantity,AvgPrice
HDFC,10,1500
INFY,5,1200
TCS,3,3000
```

---

### **Step 2: Fundamentals Fetch (Automatic - GitHub Actions)**
```
unified-symbols.json (99 tickers)
     ↓
python3 fetch_fundamentals.py
     ↓
  Yahoo Finance API
  + Screener.in (optional)
     ↓
fundamentals.json (94 stocks)
  ✅ PE, PB, EPS, BV
  ✅ ROE%, OPM%, NPM%, etc.
  ✅ MCAP, SALES, EBITDA, CFO
  ✅ 52W%, ATH%, BETA, DIV%
  ✅ Quarterly data
```

**Fields per stock:**
```json
{
  "HDFC": {
    "ltp": 1820.45,
    "pe": 28.5,
    "pb": 3.2,
    "eps": 64.0,
    "roe": 15.2,
    "opm_pct": 32.5,
    "npm_pct": 18.0,
    "mcap": 6850000,
    "sales": 120000,
    "ebitda": 45000,
    "cfo": 38000,
    "w52h": 1950,
    "w52l": 1200,
    "w52_pct": 45.0,
    "ath_pct": -6.5,
    "beta": 0.85,
    "div_yield": 1.2
  }
}
```

---

### **Step 3: Prices Fetch (Automatic - GitHub Actions)**
```
unified-symbols.json (99 tickers)
     ↓
python3 fetch_prices.py
     ↓
  Yahoo Finance API
     ↓
prices.json (93 stocks)
  ✅ LTP (last traded price)
  ✅ 1D% (1-day change %)
  ✅ Open, High, Low
  ✅ Previous close
```

**Structure:**
```json
{
  "updated": "2026-04-10T16:05:39Z",
  "count": 93,
  "quotes": {
    "HDFC": {
      "ltp": 1820.45,
      "changePct": 1.25,
      "change": 22.5,
      "open": 1798.0,
      "high": 1825.0,
      "low": 1795.0,
      "prev": 1797.95
    }
  }
}
```

---

### **Step 4: Browser Sync (Manual)**
```
User clicks SYNC button
     ↓
index.html runEngineSync()
     ↓
Fetch 3 JSON files:
  • unified-symbols.json (99 stocks, ticker map)
  • fundamentals.json (94 stocks, metrics)
  • prices.json (93 prices, LTP & change)
     ↓
Merge in JavaScript:
  • Build tickerMap from unified-symbols
  • Match fundamentals by ticker
  • Add prices from prices.json
  • Calculate derived fields (INVESTED, etc.)
     ↓
Store in IndexedDB (OnyxPortfolioDB)
  Store: "Stocks"
  Records: ~94 stock objects with 30+ fields
     ↓
render() — Draw portfolio table
  • 94 rows (one per stock)
  • 30 columns (ticker, price, fundamentals, etc.)
  • Color-coded by sector
  • Sortable by any field
```

---

## 📊 Portfolio Page (index.html)

### **Layout**
```
HEADER
├─ Title: "BharatMarkets Pro"
├─ Stats: 94 Holdings | ₹X Crore P&L | SYNC ↻ button
└─ Sector Chart (horizontal bar, color-coded)

MAIN TABLE
├─ 94 rows (one per stock)
├─ 30+ columns:
│  ├─ Identifier: SYM, name, SECTOR
│  ├─ Portfolio: QTY, AVG, INVESTED, PNL, PNL%
│  ├─ Price: LTP, 1D%
│  ├─ Valuation: PE, PB, EPS
│  ├─ Returns: ROE%, OPM%, NPM%
│  ├─ Size: MCAP, SALES, EBITDA, CFO
│  ├─ Performance: 52W%, ATH%, BETA
│  └─ Analysis: SIGNAL, POS, NEG, PROM%, FII%, DII%
│
└─ Features:
   ├─ Sort by any column (click header)
   ├─ Color-coded rows by sector
   ├─ Green/red for gains/losses
   ├─ Real-time price updates
   └─ Debug log (bottom-right corner)

FOOTER
├─ PORTFOLIO tab (active)
├─ DATA tab (manage stocks)
└─ IMPORT tab (import CSV)
```

### **Sortable Columns**
Click any column header to sort:
- **Price metrics:** LTP, 1D%, changePct
- **Valuation:** PE, PB, EPS
- **Returns:** ROE%, OPM%, NPM%
- **Size:** MCAP, SALES, EBITDA, CFO
- **Performance:** 52W%, ATH%, BETA
- **Portfolio:** PNL, PNL%, INVESTED

---

## 📁 Data Management (data.html)

**Upload new holdings or update stock master:**
1. Prepare CSV: `Symbol, Quantity, AvgPrice`
2. Click **DATA** tab
3. Click **Upload File**
4. Select your CSV
5. System validates symbols against unified-symbols.json
6. Preview shows matches & conflicts
7. Click **Import** to merge

**Download current stock list:**
- Click **EXPORT** to get unified-symbols.json
- Contains all 99 stocks with metadata

---

## 📥 Import Wizard (app-import.js)

**7-Step Process:**

```
Step 1: Parse CSV
  └─ Read file, extract columns: Symbol, Qty, Avg

Step 2: Map Tickers
  └─ Normalize symbols (uppercase, remove spaces)

Step 3: Validate
  └─ Check against unified-symbols.json
  └─ Flag unknown symbols

Step 4: Show Preview
  └─ Display matched stocks
  └─ Show any errors

Step 5: Merge with Existing
  └─ Add new symbols to portfolio
  └─ Update quantities if duplicate

Step 6: Store in IndexedDB
  └─ Save to local browser database

Step 7: Update unified-symbols.json
  └─ Add new portfolio flag to symbols
  └─ Persist to GitHub
```

---

## 🔧 Technologies & Tools

### **Frontend**
- **HTML5** — Semantic markup
- **CSS3** — Responsive design, sector color scheme
- **JavaScript (ES5)** — Compatible with iPhone Safari
- **IndexedDB** — Local storage (no server needed)

### **Backend (Python Scripts)**
- **fetch_fundamentals.py** — Scrapes Yahoo Finance + Screener.in
- **fetch_prices.py** — Gets live prices from Yahoo Finance
- **GitHub Actions** — Runs scripts weekly (free CI/CD)

### **Data Sources**
| Source | Data | Frequency |
|--------|------|-----------|
| Yahoo Finance | PE, PB, EPS, ROE%, MCAP, prices | Daily (prices), Weekly (fundamentals) |
| Screener.in | PROM%, FII%, DII% (optional) | Weekly |
| User Import | QTY, AVG (portfolio) | Manual |

### **Data Storage**
- **JSON files** — unified-symbols.json, fundamentals.json, prices.json
- **IndexedDB** — OnyxPortfolioDB/Stocks (client-side)
- **GitHub** — Version control + CDN (free hosting)

---

## 📈 Key Metrics Explained

### **Valuation**
- **PE (Price-to-Earnings):** Stock price ÷ EPS. Lower = undervalued
- **PB (Price-to-Book):** Stock price ÷ Book value per share. <1 = good
- **EPS:** Earnings per share. Higher = more profitable

### **Profitability**
- **ROE% (Return on Equity):** Net profit ÷ Equity. Higher = efficient
- **OPM% (Operating margin %):** (Operating profit ÷ Sales) × 100. Higher = good
- **NPM% (Net margin %):** (Net profit ÷ Sales) × 100

### **Size**
- **MCAP:** Market capitalization (stock price × shares outstanding)
- **SALES:** Annual revenue
- **EBITDA:** Earnings before interest, tax, depreciation, amortization
- **CFO:** Operating cash flow (quality of earnings)

### **Performance**
- **52W%:** 52-week high/low performance
- **ATH%:** All-time high percentage (how far from peak)
- **BETA:** Volatility vs market (>1 = more volatile)

### **Portfolio**
- **QTY:** Shares you hold
- **AVG:** Average buy price
- **INVESTED:** QTY × AVG
- **PNL:** Profit/loss in ₹ (INVESTED - current value)
- **PNL%:** (PNL ÷ INVESTED) × 100

---

## 🚀 How to Use (Step-by-Step)

### **First Time Setup**
1. Go to [murugkan.github.io/bharatmarkets](https://murugkan.github.io/bharatmarkets)
2. Click **DATA** tab
3. Prepare CSV: `Symbol, Quantity, AvgPrice`
4. Upload your portfolio
5. Review preview, click **Import**
6. System creates unified-symbols.json with your stocks

### **Daily Use**
1. Go to portfolio page
2. Click **SYNC ↻** button (top right)
3. Wait for debug log: "✅ Loaded 94 stocks"
4. Portfolio table updates with latest prices & fundamentals
5. Click column headers to sort by PE, ROE%, etc.

### **Analysis Workflow**
1. **Find cheap stocks:** Sort by PE ascending (lowest first)
2. **Find profitable:** Sort by ROE% descending
3. **Find margins:** Sort by OPM% or NPM%
4. **Find quality:** Look for PE <20, ROE% >15%, OPM% >20%
5. **Check quality of earnings:** High CFO indicates strong cash generation

### **Update Holdings**
1. Click **DATA** tab
2. Upload new CSV (can overwrite quantities)
3. System merges with existing portfolio

---

## 📱 Browser Compatibility

| Browser | Support | Notes |
|---------|---------|-------|
| Chrome/Edge | ✅ Full | Desktop & Mobile |
| Firefox | ✅ Full | All platforms |
| Safari | ✅ Full | iPhone/iPad/Mac |
| IE 11 | ❌ No | Use modern browser |

**Requirements:**
- IndexedDB support (all modern browsers)
- ES5 JavaScript (no arrow functions for Safari)
- LocalStorage for token storage

---

## 🔐 Privacy & Security

✅ **100% Client-Side Processing**
- No server backend — all computation in your browser
- Data never sent to external servers
- Prices fetched directly from Yahoo Finance API

✅ **Local Storage Only**
- Portfolio stored in browser IndexedDB
- CSV upload processed in-memory, not uploaded
- GitHub PAT stored in browser localStorage (optional)

⚠️ **Limitations**

**Data Persistence:**
- Data lost if browser cache cleared (mobile especially)
- Export/backup your CSV regularly
- GitHub PAT stored in plain text (use read-only token)

**Mobile Usage:**
- ✅ Works on mobile Safari, Chrome, Firefox
- ⚠️ Touch-optimized UI limited (table is wide, requires horizontal scroll)
- ⚠️ IndexedDB storage limits vary by device (typically 50MB-500MB)
- ⚠️ File upload may be unreliable on slow connections
- ❌ Notifications/alerts not fully supported
- 💡 **Recommendation:** Use on desktop for best experience

**CORS (Cross-Origin Restrictions):**
- ❌ **Cannot fetch prices directly from Screener.in** — CORS blocked
  - Workaround: Screener.in data optional, Yahoo Finance works fine
- ❌ **Cannot fetch prices from external finance APIs** — CORS blocks browser requests
  - Workaround: Use Python scripts (fetch_prices.py, fetch_fundamentals.py) to fetch once, store as JSON
- ✅ **GitHub Pages allows CORS** — Can fetch JSON files from GitHub CDN
- ✅ **Yahoo Finance API works** — Their CORS policy allows browser requests
- 💡 **Why we use JSON files:** Pre-fetched via Python scripts, served as static files (no CORS issues)

---

## 🛠️ Setup for Developers

### **Install & Run Locally**

```bash
# Clone repo
git clone https://github.com/murugkan/bharatmarkets.git
cd bharatmarkets

# Install Python dependencies
pip install yfinance requests beautifulsoup4

# Update fundamentals (optional)
python3 fetch_fundamentals.py
# Output: fundamentals.json (94 stocks)

# Update prices (optional)
python3 fetch_prices.py
# Output: prices.json (93 stocks)

# Push to GitHub (if you have write access)
git add fundamentals.json prices.json
git commit -m "Update fundamentals & prices"
git push

# View at: https://yourname.github.io/bharatmarkets
```

### **File Structure**
```
bharatmarkets/
├── index.html              # Portfolio page (main UI)
├── data.html               # Data management
├── app-engine.js           # Sync engine (IndexedDB)
├── app-import.js           # CSV import wizard
├── app-import-COMPLETE.js  # Backup
├── unified-symbols.json    # Master stock list (99 stocks)
├── fundamentals.json       # Fundamental metrics (94 stocks)
├── prices.json             # Live prices (93 stocks)
├── fetch_fundamentals.py   # Fundamentals fetcher script
├── fetch_prices.py         # Prices fetcher script
├── symbol_map.json         # (Optional) Ticker overrides
├── .github/
│   └── workflows/
│       ├── fetch_fundamentals.yml  # Auto-runs weekly
│       └── fetch_prices.yml        # Auto-runs daily
└── README.md               # This file
```

### **GitHub Actions Automation**

**Weekly Fundamentals Update:**
```yaml
# .github/workflows/fetch_fundamentals.yml
- Runs every Sunday at 10 AM UTC
- Fetches PE, ROE%, OPM%, etc. from Yahoo Finance
- Updates fundamentals.json
- Auto-commits to GitHub
```

**Daily Prices Update:**
```yaml
# .github/workflows/fetch_prices.yml
- Runs every weekday at 3:30 PM IST
- Fetches LTP, 1D% from Yahoo Finance
- Updates prices.json
- Auto-commits to GitHub
```

---

## 🐛 Troubleshooting

### **SYNC shows error "The string did not match the expected pattern"**
- **Cause:** One of the 3 JSON files has parsing error
- **Fix:** Check browser console, look for which file fails
- **Debug:** Use index.html debug log (bottom right)

### **Portfolio shows 0 stocks**
- **Cause:** IndexedDB not loaded or CSV not imported
- **Fix:** Click **DATA** → Upload CSV → Click **SYNC**

### **Some stocks missing from portfolio**
- **Cause:** Stock not in unified-symbols.json
- **Fix:** Add stock manually to unified-symbols.json or GitHub issue

### **Prices not updating**
- **Cause:** GitHub Actions workflow failed or not enabled
- **Fix:** Check `.github/workflows/fetch_prices.yml` is enabled
- **Manual:** Run `python3 fetch_prices.py` locally, commit & push

### **Can't upload CSV**
- **Cause:** Browser didn't allow file access
- **Fix:** Refresh page, try again, check file format (CSV, not XLSX)

---

## 📞 Support & Contribution

**Issues?** Create GitHub issue with:
- Stock symbol that's failing
- Screenshot of error
- Browser + OS info

**Want to contribute?**
- Add new data sources (screener.in, moneycontrol, etc.)
- Improve UI/UX
- Add new metrics
- Fix bugs

**Fork the repo:** [github.com/murugkan/bharatmarkets](https://github.com/murugkan/bharatmarkets)

---

## 📄 License

MIT — Use freely, modify, redistribute

---

## 🎯 Roadmap

- [ ] Support INE (equity), derivatives, mutual funds
- [ ] Compare portfolio metrics vs Nifty 50 benchmark
- [ ] Tax loss harvesting recommendations
- [ ] Dividend tracking & reinvestment calculator
- [ ] Alert when PE crosses threshold
- [ ] Support for other assets (crypto, forex, gold)
- [ ] Mobile app (PWA)

---

**Built with ❤️ for Indian investors**

Last Updated: 2026-04-10
