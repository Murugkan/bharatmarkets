// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// CONFIG.JS - CENTRALIZED CONFIGURATION
// Single source of truth for entire application
// Used by: index.html, data.html, app-import.js
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const CONFIG = {
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // DATABASE CONFIGURATION
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  DB: {
    name: "OnyxPortfolioDB",
    version: 8,
    store: "Stocks",
    keyPath: "ticker"  // MUST match all files
  },

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // JSON DATA FILES (Source of truth)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FILES: {
    symbols: "unified-symbols.json",      // Required: Master stock list
    prices: "prices.json",                // Required: Market data
    fundamentals: "fundamentals.json",    // Required: Analysis data
    guidance: "guidance.json",            // Optional: Guidance data
    macro: "macro_data.json"              // Optional: Macro indicators
  },

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // FIELD NAME MAPPING (Database → Display)
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FIELDS: {
    // Core identity
    ticker: "Symbol",
    name: "Company Name",
    isin: "ISIN",
    
    // Classification
    sector: "Sector",
    industry: "Industry",
    type: "Category",
    source: "Source",
    
    // Portfolio
    qty: "Qty",
    avg: "Avg Price",
    
    // Price data
    ltp: "LTP (₹)",
    open: "Open",
    high: "High",
    low: "Low",
    prev: "Prev Close",
    change: "Change (₹)",
    changePct: "Change %",
    vol: "Volume",
    
    // Valuation
    pe: "P/E",
    pb: "P/B",
    eps: "EPS",
    
    // Performance
    w52h: "52W High",
    w52l: "52W Low",
    
    // Margins
    opm: "OPM %",
    npm: "NPM %",
    opmPct: "OPM %",
    npmPct: "NPM %",
    
    // Fundamentals
    roe: "ROE %",
    beta: "Beta",
    divYield: "Div Yield",
    
    // Analysis
    signal: "Signal",
    pos: "Positive",
    neg: "Negative",
    quarterly: "Quarterly",
    
    // Metadata
    pricesUpdatedAt: "Prices Updated",
    fundamentalsUpdatedAt: "Fundamentals Updated",
    userDataUpdatedAt: "Portfolio Updated"
  },

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // FIELD VALIDATION RULES
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  VALIDATION: {
    ticker: {
      type: "string",
      required: true,
      minLength: 1,
      maxLength: 20,
      pattern: /^[A-Z0-9&\-]*$/  // Alphanumeric, &, -
    },
    name: {
      type: "string",
      required: true,
      minLength: 1,
      maxLength: 100
    },
    qty: {
      type: "number",
      required: false,
      min: 0,
      default: 0
    },
    avg: {
      type: "number",
      required: false,
      min: 0,
      default: 0
    },
    isin: {
      type: "string",
      required: false
    },
    sector: {
      type: "string",
      required: false
    },
    industry: {
      type: "string",
      required: false
    },
    type: {
      type: "string",
      required: false,
      enum: ["portfolio", "watchlist"],
      default: "portfolio"
    }
  },

  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // FIELD RESOLUTION (for backwards compatibility)
  // Maps display field names to possible database field names
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  FIELD_ALIASES: {
    'SYM': ['ticker', 'SYM', 'symbol', 'TICKER'],
    'AVG': ['avg', 'AVG', 'AVGBUY', 'avgbuy'],
    'QTY': ['qty', 'QTY', 'quantity'],
    'LTP': ['ltp', 'LTP', 'PRICE', 'price'],
    'CHANGE': ['changePct', 'change', 'changePct', 'CHANGE_1D'],
    'PE': ['pe', 'PE', 'P/E'],
    'ROE': ['roe', 'ROE', 'ROE%'],
    'SIGNAL': ['signal', 'SIGNAL', 'TECH_SIGNAL'],
    'SECTOR': ['sector', 'SECTOR']
  }
};

// Export for use in all files
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CONFIG;
}
