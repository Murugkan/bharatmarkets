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
  
  // Show immediate status on page
  const appEl = document.getElementById('app');
  if (appEl) {
    appEl.innerHTML = '<div style="padding:20px; color:#00f2ff; font-size:12px;">⏳ Loading data...</div>';
  }
  
  return new Promise((resolve) => {
    try {
      const req = indexedDB.open(DB_NAME);
      
      req.onsuccess = (e) => {
        try {
          const db = e.target.result;
          const tx = db.transaction(STORE_NAME, 'readonly');
          const store = tx.objectStore(STORE_NAME);
          const getAllReq = store.getAll();
          
          getAllReq.onsuccess = () => {
            try {
              const records = getAllReq.result || [];
              console.log(`📚 Loaded ${records.length} records from IndexedDB`);
              
              if (records.length === 0) {
                console.error('❌ No records in IndexedDB');
                if (appEl) appEl.innerHTML = '<div style="padding:20px; color:#ff4d6d;">❌ No data in IndexedDB. Run LOAD JSON in Data tab first.</div>';
                resolve();
                return;
              }
              
              // 1. MASTER array
              MASTER = records.map(stock => ({
                ...stock,
                sym: stock.ticker,
                symbol: stock.ticker,
                ltp: stock.ltp || 0,
                qty: stock.qty || 0,
                avg: stock.avg || 0,
                avgBuy: stock.avg || 0
              }));
              
              // 2. FUND object
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
              
              // 3. GUIDANCE object
              GUIDANCE = {};
              records.forEach(stock => {
                GUIDANCE[stock.ticker] = {
                  guidance: stock.guidance || null,
                  insights: stock.insights || null,
                  updated: stock.guidance?.updated || null
                };
              });
              
              // 4. S.portfolio
              S.portfolio = MASTER;
              
              console.log(`✅ Bridge ready: ${MASTER.length} stocks`);
              console.log(`✅ FUND map: ${Object.keys(FUND).length} entries`);
              console.log(`✅ GUIDANCE map: ${Object.keys(GUIDANCE).length} entries`);
              
              if (appEl) appEl.innerHTML = '';  // Clear loading message
              resolve();
            } catch (err) {
              console.error('❌ Error processing records:', err.message);
              if (appEl) appEl.innerHTML = '<div style="padding:20px; color:#ff4d6d;">❌ Error: ' + err.message + '</div>';
              resolve();
            }
          };
          
          getAllReq.onerror = () => {
            console.error('❌ Failed to read IndexedDB');
            if (appEl) appEl.innerHTML = '<div style="padding:20px; color:#ff4d6d;">❌ Failed to read IndexedDB</div>';
            resolve();
          };
        } catch (err) {
          console.error('❌ Transaction error:', err.message);
          if (appEl) appEl.innerHTML = '<div style="padding:20px; color:#ff4d6d;">❌ Error: ' + err.message + '</div>';
          resolve();
        }
      };
      
      req.onerror = () => {
        console.error('❌ Failed to open IndexedDB');
        if (appEl) appEl.innerHTML = '<div style="padding:20px; color:#ff4d6d;">❌ Failed to open IndexedDB</div>';
        resolve();
      };
    } catch (err) {
      console.error('❌ Critical error:', err.message);
      if (appEl) appEl.innerHTML = '<div style="padding:20px; color:#ff4d6d;">❌ Critical error: ' + err.message + '</div>';
      resolve();
    }
  });
}

// Helper: Select a stock for drill view
function selectStock(ticker) {
  let stock = MASTER.find(s => s.ticker === ticker || s.sym === ticker);
  if (!stock) {
    console.warn(`⚠️ Stock ${ticker} not found in MASTER`);
    return false;
  }
  
  // Ensure all aliases are set
  stock.sym = stock.ticker;
  stock.symbol = stock.ticker;
  stock.ltp = stock.ltp || 0;
  stock.qty = stock.qty || 0;
  stock.avg = stock.avg || 0;
  stock.change = stock.change || 0;
  stock.changePct = stock.changePct || 0;
  stock.sector = stock.sector || '—';
  stock.name = stock.name || ticker;
  stock.score = stock.score || 65;
  
  S.selStock = stock;
  console.log(`✅ Selected: ${stock.ticker}`);
  console.log(`📋 Stock object:`, stock);
  return true;
}

// Helper: Get stock by ticker
function getStock(ticker) {
  return MASTER.find(s => s.ticker === ticker || s.sym === ticker);
}

// ===== UTILITY FUNCTIONS (for old JS files) =====
function mergeHolding(h) {
  return {
    ...h,
    sym: h.ticker,
    symbol: h.ticker,
    ltp: h.ltp || 0,
    qty: h.qty || 0,
    avg: h.avg || 0,
    avgBuy: h.avg || 0,
    change: h.change || 0,
    changePct: h.changePct || 0
  };
}

function fmt(val, decimals = 2) {
  if (typeof val !== 'number') return '—';
  return val.toFixed(decimals);
}

function trunc(str, len) {
  if (!str) return '';
  return str.length > len ? str.substring(0, len) + '...' : str;
}

function scoreColor(score) {
  if (score >= 80) return '#00ff88';  // Green
  if (score >= 60) return '#00f2ff';  // Blue
  if (score >= 40) return '#ffb800';  // Orange
  return '#ff4d6d';  // Red
}

function scoreLabel(score) {
  if (score >= 80) return 'Strong';
  if (score >= 60) return 'Good';
  if (score >= 40) return 'Fair';
  return 'Weak';
}

function setDrillTab(tab) {
  S.drillTab = tab;
  if (S.selStock) renderDrill(document.getElementById('app'));
}

function closeStock() {
  S.selStock = null;
  window.history.back();
}

function deletePortfolioStock(ticker) {
  console.log(`Delete requested for ${ticker}`);
  alert(`Delete functionality not yet implemented for ${ticker}`);
}

// ===== CLEANUP: Remove duplicate function =====

// ===== STUB RENDER FUNCTIONS (if app-drill.js functions missing) =====
if (typeof renderOverview === 'undefined') {
  window.renderOverview = (s) => `<div style="padding:12px; color:#8ab4f8;">Overview tab - Stock: ${s.symbol}</div>`;
}
if (typeof renderTechnical === 'undefined') {
  window.renderTechnical = (s) => `<div style="padding:12px; color:#8ab4f8;">Technical tab - Stock: ${s.symbol}</div>`;
}
if (typeof renderFundamentals === 'undefined') {
  window.renderFundamentals = (s) => `<div style="padding:12px; color:#8ab4f8;">Fundamentals tab - Stock: ${s.symbol}</div>`;
}
if (typeof renderNewsTab === 'undefined') {
  window.renderNewsTab = (s) => `<div style="padding:12px; color:#8ab4f8;">News tab - Stock: ${s.symbol}</div>`;
}
if (typeof renderInsights === 'undefined') {
  window.renderInsights = (s) => `<div style="padding:12px; color:#8ab4f8;">Insights tab - Stock: ${s.symbol}</div>`;
}
