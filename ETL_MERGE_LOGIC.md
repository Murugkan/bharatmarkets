# ETL Merging & Data Mapping Logic

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Data Flow](#data-flow)
3. [JSON File Structures](#json-file-structures)
4. [Wrapper Detection](#wrapper-detection)
5. [Merging Logic](#merging-logic)
6. [Field Mapping](#field-mapping)
7. [Calculated Fields](#calculated-fields)
8. [Extending the System](#extending-the-system)

---

## Architecture Overview

The system follows a **single source of truth** pattern:

```
┌─────────────────────────────────────┐
│    GitHub Repository (5 Files)      │
│  - unified-symbols.json             │
│  - prices.json                      │
│  - fundamentals.json                │
│  - guidance.json                    │
│  - macro_data.json                  │
└──────────────┬──────────────────────┘
               │
               ↓
┌──────────────────────────────────────────┐
│   ETL Data Center (data.html)            │
│  ✓ Fetches from GitHub                  │
│  ✓ Detects JSON wrappers                │
│  ✓ Merges by ticker key                 │
│  ✓ Normalizes field names               │
│  ✓ Calculates derived fields            │
└──────────────┬───────────────────────────┘
               │
               ↓
┌──────────────────────────────────────────┐
│     IndexedDB (Onyx PortfolioDB)        │
│  Store: "Stocks"                        │
│  Key Path: "ticker"                     │
│  Records: ~87 enriched stock objects    │
└──────────────┬───────────────────────────┘
               │
       ┌───────┴────────┐
       ↓                ↓
   Portfolio        Data/Wizard
   (READ ONLY)      (READ ONLY)
```

---

## Data Flow

### Step 1: Initialization (Auto-load on startup)
```
ETL starts → Fetches unified-symbols.json → Saves 87 records → Displays in symbols table
```

### Step 2: Full Merge (LOAD ALL button)
```
User clicks "LOAD ALL" 
  ↓
Fetch all 5 files in parallel
  ↓
Parse each file's wrapper structure
  ↓
Extract ticker maps
  ↓
Merge by ticker across all sources
  ↓
Calculate derived fields
  ↓
Save merged records to IndexedDB
  ↓
Re-render portfolio
```

### Step 3: Portfolio View
```
User clicks "Portfolio" or "SYNC"
  ↓
Load all records from IndexedDB
  ↓
Enrich with calculated fields
  ↓
Render with sorting/filtering
```

---

## JSON File Structures

### 1. unified-symbols.json
**Structure:** Array wrapped in `symbols` key
```json
{
  "symbols": [
    {
      "ticker": "INFY",
      "name": "Infosys Limited",
      "sector": "IT Services",
      "qty": 100,
      "avg": 1500.50
    },
    ...
  ]
}
```

**Root Keys:** `symbols` (array of objects)  
**Ticker Access:** `symbols[i].ticker`

---

### 2. prices.json
**Structure:** Object wrapped in `quotes` key with ticker keys
```json
{
  "updated": "2026-04-14T09:55:54...",
  "quotes": {
    "INFY": {
      "ticker": "INFY",
      "ltp": 1850.25,
      "change": 25.5,
      "changePct": 1.39,
      "open": 1825.0,
      "high": 1875.0,
      "low": 1820.0,
      "vol": 2500000
    },
    "TCS": { ... }
  }
}
```

**Root Keys:** `updated`, `quotes`, `lastLoadedAt`, `source`, `count`  
**Wrapper:** `quotes`  
**Ticker Access:** `quotes[ticker]`

---

### 3. fundamentals.json
**Structure:** Object wrapped in `stocks` key with ticker keys
```json
{
  "updated": "2026-04-12T11:15:47...",
  "stocks": {
    "INFY": {
      "ticker": "INFY",
      "pe": 25.76,
      "pb": 2.77,
      "eps": 13.27,
      "bv": 123.04,
      "roe": 11.5,
      "roce": 9.33,
      "npm_pct": 11.07,
      "opm_pct": 15.16,
      "mcap": 89652.25,
      "sales": 31611.01,
      "ebitda": 12345.67,
      "cfo": -27935.0,
      "prom_pct": 68.57,
      "fii_pct": 5.15,
      "dii_pct": 14.67,
      "ath_pct": -7.4,
      "w52_pct": -10.2
    },
    "TCS": { ... }
  }
}
```

**Root Keys:** `updated`, `stocks`, `lastLoadedAt`, `source`, `count`, `sources`, `delisted`  
**Wrapper:** `stocks`  
**Ticker Access:** `stocks[ticker]`

---

### 4. guidance.json
**Structure:** Direct ticker keys with `_metadata`
```json
{
  "_metadata": {
    "loadedAt": "2026-04-12T09:48:31Z"
  },
  "SHILCHAR": {
    "guidance": {
      "updated": "27/03/26",
      "quarter": "Q3 FY26",
      "revenue_guidance": "...",
      "growth_target": "28% YoY",
      ...
    },
    "insights": {
      "updated": "27/03/26",
      "bullets": [ ... ]
    }
  },
  "OLECTRA": { ... },
  "WAAREEENER": { ... }
}
```

**Root Keys:** `_metadata` (special), ticker keys  
**Wrapper:** None (direct keys)  
**Ticker Access:** `guidanceData[ticker]`  
**Special Handling:** Skip `_metadata` key when extracting tickers

---

### 5. macro_data.json
**Structure:** Array wrapped in `indicators` key
```json
{
  "_metadata": {
    "loadedAt": "2026-04-12T09:48:31Z"
  },
  "indicators": [
    {
      "icon": "🏛️",
      "label": "RBI Repo Rate",
      "val": "6.25%",
      "trend": "→ Stable",
      "impact": "Neutral",
      "detail": "RBI held rates steady..."
    },
    ...
  ]
}
```

**Root Keys:** `_metadata`, `indicators`  
**Wrapper:** `indicators` (ARRAY, not per-ticker)  
**Ticker Access:** Not applicable (dashboard data)

---

## Wrapper Detection

### Challenge
Different files have different wrapper structures:
- `prices.json` → `"quotes"` wrapper
- `fundamentals.json` → `"stocks"` wrapper
- `unified-symbols.json` → `"symbols"` array
- `guidance.json` → direct ticker keys
- `macro_data.json` → `"indicators"` array

### Solution: Multi-Level Detection

```javascript
// Prices: Check for quotes/stocks/prices wrappers
let priceMap = {};
if (pricesData.quotes && typeof pricesData.quotes === 'object' && !Array.isArray(pricesData.quotes)) {
    priceMap = pricesData.quotes;
} else if (pricesData.stocks && typeof pricesData.stocks === 'object' && !Array.isArray(pricesData.stocks)) {
    priceMap = pricesData.stocks;
} else if (pricesData.prices && typeof pricesData.prices === 'object' && !Array.isArray(pricesData.prices)) {
    priceMap = pricesData.prices;
} else {
    // Last resort: direct ticker keys
    priceMap = Object.keys(pricesData).some(k => k === k.toUpperCase() && k !== 'QUOTES') 
        ? pricesData 
        : {};
}

// Fundamentals: Similar approach
let fundMap = {};
if (fundamentalsData.stocks && typeof fundamentalsData.stocks === 'object' && !Array.isArray(fundamentalsData.stocks)) {
    fundMap = fundamentalsData.stocks;
} else if (fundamentalsData.fundamentals && typeof fundamentalsData.fundamentals === 'object' && !Array.isArray(fundamentalsData.fundamentals)) {
    fundMap = fundamentalsData.fundamentals;
} else {
    fundMap = Object.keys(fundamentalsData).some(k => k === k.toUpperCase() && k !== 'STOCKS') 
        ? fundamentalsData 
        : {};
}

// Guidance: Direct keys, skip metadata
const guidMap = {};
Object.keys(guidanceData).forEach(key => {
    if (key !== '_metadata' && guidanceData[key]) {
        guidMap[key] = guidanceData[key];
    }
});

// Macro: Check for indicators array
const macroMap = {};
if (macroData.indicators && Array.isArray(macroData.indicators)) {
    // Don't merge macro (dashboard data)
} else {
    const macroObj = macroData.macro || macroData;
    Object.keys(macroObj).forEach(key => {
        if (key !== '_metadata') {
            macroMap[key] = macroObj[key];
        }
    });
}
```

### Key Detection Rules
1. **Check for explicit wrapper keys** (e.g., `quotes`, `stocks`)
2. **Verify it's an object** (not metadata, not array)
3. **Skip metadata keys** (`_metadata`, `updated`, `lastLoadedAt`)
4. **Detect ticker keys** by uppercase naming convention
5. **Handle arrays specially** (like indicators)

---

## Merging Logic

### Merge Sequence

```javascript
// 1. Get all unique tickers from symbols (primary source)
const allTickers = Object.keys(symbolsMap);

// 2. For each ticker, merge data from all sources
const mergedRecords = allTickers.map(ticker => {
    const symbolData = symbolsMap[ticker] || {};
    const priceData = priceMap[ticker] || {};
    const fundData = fundMap[ticker] || {};
    const guidData = guidMap[ticker] || {};
    
    // 3. Merge in priority order (later overwrites earlier)
    const merged = {
        ...symbolData,        // Base: symbols (qty, avg, sector)
        ...priceData,         // Add: prices (ltp, change)
        ...fundData,          // Add: fundamentals (pe, pb, roe, fii_pct, dii_pct)
        ...guidData,          // Add: guidance (insights, recommendations)
        ticker: ticker        // Ensure ticker is set
    };
    
    // 4. Enrich with calculations
    enrichStock(merged);
    
    return merged;
});

// 5. Save to IndexedDB
db.transaction('Stocks', 'readwrite')
  .objectStore('Stocks')
  .put(merged);
```

### Merge Rules

1. **Ticker as Key**: All merging happens on the `ticker` field
2. **Order Matters**: Later sources overwrite earlier ones
3. **Null/Undefined Safe**: Missing fields don't break merge
4. **All Sources Optional**: Works even if some files are missing
5. **Calculated Fields Added**: After merge, before save

### Why This Order?

```
Symbols → Prices → Fundamentals → Guidance
   ↓        ↓            ↓           ↓
Base    Real-time    Ratios      Long-term
(qty)   (ltp, vol)   (pe, roe)   (insights)
```

---

## Field Mapping

### Problem
JSON files use different field names:
- `ltp` vs `LTP` vs `price`
- `fii_pct` vs `fii` vs `FII%`
- `roe` vs `ROE` vs `ROE%`

### Solution: Fallback Chains

Each UI field maps to multiple possible source names:

```javascript
const mappings = {
    'LTP': ['ltp', 'LTP', 'PRICE', 'price'],
    'QTY': ['qty', 'QTY', 'quantity'],
    'AVG': ['avg', 'AVG', 'AVGBUY', 'avgbuy'],
    'PE': ['pe', 'PE', 'P/E'],
    'PB': ['pb', 'PB', 'P/B'],
    'ROE%': ['roe', 'ROE%', 'ROE', 'roe'],
    'ROCE%': ['roce', 'ROCE%', 'ROCE'],
    'OPM%': ['opm', 'OPM%', 'OPM', 'opmPct'],
    'NPM%': ['npm', 'NPM%', 'NPM', 'npmPct'],
    'FII%': ['fii', 'FII%', 'fii_pct'],
    'DII%': ['dii', 'DII%', 'dii_pct'],
    'PROM%': ['prom', 'PROM%', 'prom_pct'],
    'ATH%': ['ath', 'ATH%', 'ath_pct'],
    '52W%': ['w52', '52W%', '52WEEK', 'w52_pct'],
    'SECTOR': ['sector', 'SECTOR']
};
```

### Resolution Algorithm

```javascript
function resolve(stock, fieldName) {
    const targetNames = mappings[fieldName] || [fieldName];
    
    // Try each target name in order
    for (let name of targetNames) {
        if (stock[name] !== undefined) {
            return stock[name];  // Found!
        }
        
        // Try without % suffix (e.g., 'roe' for 'ROE%')
        const cleanName = name.replace('%', '');
        if (stock[cleanName] !== undefined) {
            return stock[cleanName];
        }
    }
    
    return '—';  // Not found, return blank
}
```

### How to Add New Fields

1. Add to `mappings` object:
```javascript
'NEW_FIELD': ['new_field', 'NEW_FIELD', 'new_field_pct']
```

2. Add to `UI_FIELDS` array:
```javascript
const UI_FIELDS = [..., 'NEW_FIELD'];
```

3. Add formatting rule if needed:
```javascript
if (field === 'NEW_FIELD') return value.toFixed(2);
```

---

## Calculated Fields

### Fields NOT in JSON (Calculated)

Some important fields don't exist in the JSON files. The system calculates them:

#### 1. INVESTED (Portfolio Cost Basis)
**Formula:** `QTY × AVG`  
**Example:** 100 shares × ₹1500 = ₹150,000  
**Used for:** Portfolio allocation, tracking total invested amount

```javascript
stock.invested = cleanNum(stock.qty) * cleanNum(stock.avg);
```

#### 2. PNL (Profit/Loss Amount)
**Formula:** `(LTP - AVG) × QTY`  
**Example:** (₹1600 - ₹1500) × 100 = ₹10,000  
**Used for:** Absolute P&L tracking

```javascript
stock.pnl = (cleanNum(stock.ltp) - cleanNum(stock.avg)) * cleanNum(stock.qty);
```

#### 3. PNL% (Profit/Loss Percentage)
**Formula:** `((LTP - AVG) / AVG) × 100`  
**Example:** ((₹1600 - ₹1500) / ₹1500) × 100 = 6.67%  
**Used for:** Return percentage, easy comparison

```javascript
stock.pnlPct = ((cleanNum(stock.ltp) - cleanNum(stock.avg)) / cleanNum(stock.avg)) * 100;
```

### Enrichment Function

```javascript
function enrichStock(stock) {
    // Calculate INVESTED = QTY * AVG
    const qty = cleanNum(resolve(stock, 'QTY'));
    const avg = cleanNum(resolve(stock, 'AVG'));
    if (qty && avg && !stock.invested) {
        stock.invested = qty * avg;
    }
    
    // Calculate PNL = (LTP - AVG) * QTY
    const ltp = cleanNum(resolve(stock, 'LTP'));
    if (qty && avg && ltp && !stock.pnl) {
        stock.pnl = (ltp - avg) * qty;
    }
    
    // Calculate PNL% = ((LTP - AVG) / AVG) * 100
    if (avg && ltp && !stock.pnlPct) {
        stock.pnlPct = ((ltp - avg) / avg) * 100;
    }
    
    return stock;
}
```

### When Enrichment Happens

1. **During LOAD ALL**: Calculated before saving to IndexedDB
2. **During Portfolio Render**: Calculated before display
3. **Idempotent**: Won't recalculate if already present (`!stock.invested` check)

---

## Extending the System

### Adding a New Data Source

**Example: Add dividend.json**

1. **Update DATA_SOURCES** in data.html:
```javascript
const DATA_SOURCES = [
    { path: 'unified-symbols.json' },
    { path: 'prices.json' },
    { path: 'fundamentals.json' },
    { path: 'guidance.json' },
    { path: 'macro_data.json' },
    { path: 'dividend.json' }  // NEW
];
```

2. **Update fetch order** in loadAllData():
```javascript
const [symData, priceData, fundData, guidData, macroData, divData] = await Promise.all([...]);
const dividendData = divData || {};
```

3. **Add wrapper detection**:
```javascript
let divMap = {};
if (dividendData.dividends && typeof dividendData.dividends === 'object') {
    divMap = dividendData.dividends;
} else {
    divMap = dividendData;
}
log(`✅ Dividend map has ${Object.keys(divMap).length} tickers`);
```

4. **Add to merge**:
```javascript
const merged = {
    ...symbolData,
    ...priceData,
    ...fundData,
    ...guidData,
    ...divData,      // NEW
    ticker: ticker
};
```

5. **Add field mappings** in index.html:
```javascript
'DIVIDEND': ['dividend', 'DIVIDEND', 'div_yield'],
'EX_DATE': ['ex_date', 'EX_DATE', 'exDate']
```

6. **Add to UI_FIELDS**:
```javascript
const UI_FIELDS = [..., 'DIVIDEND', 'EX_DATE'];
```

---

### Handling Different Wrapper Names

If a new file uses a non-standard wrapper name:

```javascript
// Old approach (fragile)
const newMap = newData.oldWrapper || newData;

// New approach (flexible)
const newMap = newData.newWrapper 
    || newData.alternativeWrapper 
    || newData.yetAnother
    || (isDirectKeys(newData) ? newData : {});

function isDirectKeys(obj) {
    return Object.keys(obj).some(k => k === k.toUpperCase() && k !== 'METADATA');
}
```

---

### Adding Calculated Fields

1. **Add calculation logic**:
```javascript
function enrichStock(stock) {
    // ... existing calculations
    
    // NEW: Dividend per share
    if (!stock.divPerShare && stock.dividend && stock.eps) {
        stock.divPerShare = stock.dividend / stock.eps;
    }
}
```

2. **Add field mapping**:
```javascript
'DIV_PER_SHARE': ['divPerShare', 'DIV_PER_SHARE']
```

3. **Add to UI**:
```javascript
const UI_FIELDS = [..., 'DIV_PER_SHARE'];
```

---

## Error Handling

### Robust Merge with Fallbacks

```javascript
try {
    // Fetch with timeout
    const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    
    const data = await response.json();
    if (!data || typeof data !== 'object') throw new Error('Invalid JSON');
    
    return data;
} catch (err) {
    log(`❌ Error: ${url} - ${err.message}`);
    return {};  // Empty object, merge continues with other sources
}
```

### Partial Merge Safety

Even if one file fails, the system continues:
- ✅ Symbols loaded? → Portfolio shows tickers
- ✅ Prices loaded? → Portfolio shows LTP
- ✅ Fundamentals loaded? → Portfolio shows PE, ROE
- ❌ Guidance failed? → Guidance fields stay blank, everything else works

---

## Performance Optimization

### Current Approach
- **Parallel fetch**: `Promise.all()` for all 5 files simultaneously
- **Single merge pass**: O(n) where n = number of tickers
- **IndexedDB write**: Batch put operations
- **Field resolution**: O(1) field lookup with mappings

### Timing
- **Fetch**: ~2-3 seconds (network dependent)
- **Parse**: ~100ms
- **Merge**: ~50ms
- **IndexedDB save**: ~500ms
- **Total**: ~3-4 seconds for full LOAD ALL

### Memory Usage
- **In memory**: 87 stocks × ~3KB per record ≈ 260KB
- **IndexedDB**: Similar (~260KB)
- **Acceptable for**: Web app with <1000 records

---

## Debugging

### Enable Detailed Logging

Console shows:
```
[4:08:39 PM] ✅ Fetched unified-symbols.json successfully
[4:08:39 PM] ✅ Found prices in "quotes" wrapper
[4:08:39 PM] ✅ Found fundamentals in "stocks" wrapper
[4:08:39 PM] ✅ Price map has 90 tickers: ?, ABCAPITAL, ABFRL
[4:08:39 PM] ✅ Fund map has 87 tickers: ABCAPITAL, ABFRL, ACMESOLAR
[4:08:39 PM] ✅ Guidance map has 3 tickers: SHILCHAR, OLECTRA, WAAREEENER
[4:08:39 PM] ✅ Merged 87 records to IndexedDB
```

### Troubleshooting Missing Fields

1. **Check console logs** for wrapper detection
2. **Check field mappings** - is the source field name in the list?
3. **Check calculation** - is enrichStock() being called?
4. **Check IndexedDB** - open DevTools → Application → IndexedDB → Stocks → Look for field

---

## Summary

| Aspect | Approach |
|--------|----------|
| **Architecture** | Single source of truth (IndexedDB) |
| **Merge Key** | ticker field (unique identifier) |
| **Wrapper Handling** | Multi-level detection with fallbacks |
| **Field Mapping** | Fallback chains for name variations |
| **Calculated Fields** | Added during enrichment phase |
| **Error Handling** | Partial merge continues if file fails |
| **Performance** | Parallel fetch, single merge pass |
| **Extensibility** | Easy to add new files and fields |

