// ============================================
// bridge.js — Data Bridge for Old JS Files
// ============================================
// Reuses app-analysis.js + app-drill.js WITHOUT modification
// Maps IndexedDB → old globals (MASTER, FUND, GUIDANCE, S)

let MASTER = [];           // Portfolio array
let FUND = {};             // Fund data by ticker
let GUIDANCE = {};         // Guidance data by ticker
let S = {                  // State object
  portfolio: [],
  selStock: null,
  drillTab: 'overview'
};

const DB_NAME = 'OnyxPortfolioDB';
const STORE_NAME = 'Stocks';

async function initBridge() {
  console.log('🌉 Initializing data bridge...');
  
  return new Promise((resolve) => {
    const req = indexedDB.open(DB_NAME);
    
    req.onsuccess = (e) => {
      const db = e.target.result;
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const getAllReq = store.getAll();
      
      getAllReq.onsuccess = () => {
        const records = getAllReq.result || [];
        console.log(`📚 Loaded ${records.length} records from IndexedDB`);
        
        // 1. MASTER array (portfolio data with aliases for old code)
        MASTER = records.map(stock => ({
          ...stock,
          sym: stock.ticker,           // Alias for old code
          symbol: stock.ticker,        // Alias for old code
          ltp: stock.ltp || 0,
          qty: stock.qty || 0,
          avg: stock.avg || 0,
          avgBuy: stock.avg || 0       // Alias
        }));
        
        // 2. FUND object (fundamental data by ticker)
        FUND = {};
        records.forEach(stock => {
          FUND[stock.ticker] = {
            ...stock,
            name: stock.name,
            sector: stock.sector,
            pe: stock.pe,
            pb: stock.pb,
            roe: stock.roe,
            roce: stock.roce,
            opm: stock.opm,
            npm: stock.npm,
            eps: stock.eps,
            sales: stock.sales,
            ebitda: stock.ebitda,
            cfo: stock.cfo,
            quarterly: stock.quarterly || [],
            ltp: stock.ltp,
            change: stock.change,
            changePct: stock.changePct,
            mcap: stock.mcap
          };
        });
        
        // 3. GUIDANCE object (concall/insights by ticker)
        GUIDANCE = {};
        records.forEach(stock => {
          GUIDANCE[stock.ticker] = {
            guidance: stock.guidance || null,
            insights: stock.insights || null,
            updated: stock.guidance?.updated || null
          };
        });
        
        // 4. S.portfolio (legacy compatibility)
        S.portfolio = MASTER;
        
        console.log(`✅ Bridge ready: ${MASTER.length} stocks`);
        console.log(`✅ FUND map: ${Object.keys(FUND).length} entries`);
        console.log(`✅ GUIDANCE map: ${Object.keys(GUIDANCE).length} entries`);
        
        resolve();
      };
      
      getAllReq.onerror = () => {
        console.error('❌ Failed to read IndexedDB');
        resolve();
      };
    };
    
    req.onerror = () => {
      console.error('❌ Failed to open IndexedDB');
      resolve();
    };
  });
}

// Helper: Select a stock for drill view
function selectStock(ticker) {
  const stock = MASTER.find(s => s.ticker === ticker || s.sym === ticker);
  if (!stock) {
    console.warn(`⚠️ Stock ${ticker} not found in MASTER`);
    return false;
  }
  S.selStock = stock;
  console.log(`✅ Selected: ${stock.ticker}`);
  return true;
}

// Helper: Get stock by ticker
function getStock(ticker) {
  return MASTER.find(s => s.ticker === ticker || s.sym === ticker);
}
