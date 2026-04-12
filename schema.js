// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// SCHEMA.JS - DATA MODEL DEFINITION
// Defines structure and validation for all data
// Used by: data.html, app-import.js, utils.js
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

const SCHEMA = {
  version: "1.0",
  
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  // STOCKS COLLECTION
  // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  stocks: {
    name: "Stocks",
    description: "Master stock records with all merged data",
    keyPath: "ticker",
    
    properties: {
      // ========== IDENTITY (Required) ==========
      ticker: {
        type: "string",
        description: "Stock symbol/ticker (unique key)",
        required: true,
        example: "INFY"
      },
      
      // ========== BASE INFO (Required) ==========
      name: {
        type: "string",
        description: "Company full name",
        required: true,
        example: "Infosys Limited"
      },
      
      // ========== CLASSIFICATION ==========
      isin: {
        type: "string",
        description: "ISIN number",
        required: false,
        example: "INE009A01021"
      },
      
      sector: {
        type: "string",
        description: "Industry sector",
        required: false,
        example: "Information Technology"
      },
      
      industry: {
        type: "string",
        description: "Industry sub-category",
        required: false,
        example: "IT Services"
      },
      
      type: {
        type: "string",
        enum: ["portfolio", "watchlist"],
        description: "Stock category",
        required: false,
        default: "portfolio"
      },
      
      source: {
        type: "string",
        description: "Data source",
        required: false,
        example: "merge"
      },
      
      // ========== PORTFOLIO DATA ==========
      qty: {
        type: "number",
        description: "Quantity held in portfolio",
        required: false,
        min: 0,
        default: 0,
        example: 100
      },
      
      avg: {
        type: "number",
        description: "Average buy price",
        required: false,
        min: 0,
        default: 0,
        example: 1500.50
      },
      
      // ========== PRICE DATA ==========
      ltp: {
        type: "number",
        description: "Last traded price",
        required: false,
        example: 1850.25
      },
      
      open: {
        type: "number",
        description: "Opening price",
        required: false
      },
      
      high: {
        type: "number",
        description: "Day high",
        required: false
      },
      
      low: {
        type: "number",
        description: "Day low",
        required: false
      },
      
      prev: {
        type: "number",
        description: "Previous close",
        required: false
      },
      
      change: {
        type: "number",
        description: "Price change in rupees",
        required: false
      },
      
      changePct: {
        type: "number",
        description: "Price change percentage",
        required: false,
        example: 5.25
      },
      
      vol: {
        type: "number",
        description: "Trading volume",
        required: false
      },
      
      // ========== VALUATION ==========
      pe: {
        type: "number",
        description: "Price to Earnings ratio",
        required: false,
        example: 25.5
      },
      
      pb: {
        type: "number",
        description: "Price to Book ratio",
        required: false
      },
      
      eps: {
        type: "number",
        description: "Earnings per share",
        required: false
      },
      
      // ========== PERFORMANCE ==========
      w52h: {
        type: "number",
        description: "52-week high",
        required: false
      },
      
      w52l: {
        type: "number",
        description: "52-week low",
        required: false
      },
      
      // ========== MARGINS ==========
      opm: {
        type: "number",
        description: "Operating profit margin %",
        required: false
      },
      
      opmPct: {
        type: "number",
        description: "Operating profit margin percentage",
        required: false
      },
      
      npm: {
        type: "number",
        description: "Net profit margin %",
        required: false
      },
      
      npmPct: {
        type: "number",
        description: "Net profit margin percentage",
        required: false
      },
      
      // ========== FUNDAMENTALS ==========
      roe: {
        type: "number",
        description: "Return on equity %",
        required: false,
        example: 25.50
      },
      
      beta: {
        type: "number",
        description: "Beta (volatility measure)",
        required: false
      },
      
      divYield: {
        type: "number",
        description: "Dividend yield %",
        required: false
      },
      
      // ========== ANALYSIS ==========
      signal: {
        type: "string",
        description: "Technical analysis signal",
        required: false,
        example: "BUY"
      },
      
      pos: {
        type: "string",
        description: "Positive indicators",
        required: false
      },
      
      neg: {
        type: "string",
        description: "Negative indicators",
        required: false
      },
      
      quarterly: {
        type: "array",
        description: "Quarterly data (nested)",
        required: false,
        items: {
          type: "object",
          properties: {
            q: { type: "string" },
            eps: { type: "number" },
            revenue: { type: "number" }
          }
        }
      },
      
      // ========== METADATA ==========
      pricesUpdatedAt: {
        type: "string",
        description: "Last prices.json update timestamp (ISO 8601)",
        required: false,
        example: "2026-04-12T16:46:00Z"
      },
      
      fundamentalsUpdatedAt: {
        type: "string",
        description: "Last fundamentals.json update timestamp",
        required: false
      },
      
      userDataUpdatedAt: {
        type: "string",
        description: "Last user edit timestamp",
        required: false
      }
    },
    
    // Fields that MUST always be present
    required: ["ticker", "name"],
    
    // Example record (valid)
    example: {
      ticker: "INFY",
      name: "Infosys Limited",
      isin: "INE009A01021",
      sector: "Information Technology",
      industry: "IT Services",
      type: "portfolio",
      qty: 100,
      avg: 1500.50,
      ltp: 1850.25,
      change: 350.25,
      changePct: 23.33,
      pe: 25.5,
      roe: 28.75,
      signal: "BUY",
      pricesUpdatedAt: "2026-04-12T16:46:00Z"
    }
  }
};

// Export for use in all files
if (typeof module !== 'undefined' && module.exports) {
  module.exports = SCHEMA;
}
