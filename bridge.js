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

// ===== SIMPLE DRILL VIEW (replaces app-drill.js renderDrill) =====
function renderDrill(container) {
  const s = S.selStock;
  if (!s) {
    closeStock();
    return;
  }
  
  // Safe number conversion
  const num = (val) => {
    if (typeof val === 'number') return val;
    if (typeof val === 'string') {
      const n = parseFloat(val);
      return isNaN(n) ? 0 : n;
    }
    return 0;
  };
  
  const fmt = (val, decimals = 2) => {
    const n = num(val);
    return n === 0 && val === '—' ? '—' : n.toFixed(decimals);
  };
  
  const bull = num(s.changePct) >= 0;
  const col = bull ? 'var(--gr)' : 'var(--rd)';
  
  container.innerHTML = `
    <div style="padding:12px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; padding-bottom:12px; border-bottom:1px solid var(--b1);">
        <div style="flex:1;">
          <div style="font-size:16px; font-weight:800; color:var(--bl);">${s.symbol}</div>
          <div style="font-size:12px; color:var(--tx); margin-top:4px;">${s.name}</div>
          <div style="font-size:10px; color:#666; margin-top:2px;">${s.sector || '—'}</div>
        </div>
        <div style="text-align:right;">
          <div style="font-size:14px; font-weight:800;">₹${fmt(s.ltp)}</div>
          <div style="font-size:12px; color:${col}; margin-top:2px;">${bull ? '▲' : '▼'} ${Math.abs(num(s.changePct)).toFixed(2)}%</div>
        </div>
      </div>
      
      <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:12px;">
        <div style="background:var(--s1); padding:10px; border-radius:4px;">
          <div style="font-size:9px; color:#666; margin-bottom:4px;">PE Ratio</div>
          <div style="font-size:13px; font-weight:800; color:var(--bl);">${fmt(s.pe)}</div>
        </div>
        <div style="background:var(--s1); padding:10px; border-radius:4px;">
          <div style="font-size:9px; color:#666; margin-bottom:4px;">ROE %</div>
          <div style="font-size:13px; font-weight:800; color:var(--gr);">${fmt(s.roe)}%</div>
        </div>
        <div style="background:var(--s1); padding:10px; border-radius:4px;">
          <div style="font-size:9px; color:#666; margin-bottom:4px;">OPM %</div>
          <div style="font-size:13px; font-weight:800; color:var(--bl);">${fmt(s.opm)}%</div>
        </div>
        <div style="background:var(--s1); padding:10px; border-radius:4px;">
          <div style="font-size:9px; color:#666; margin-bottom:4px;">Market Cap</div>
          <div style="font-size:13px; font-weight:800; color:var(--bl);">₹${(num(s.mcap) / 100000).toFixed(1)}L</div>
        </div>
      </div>
      
      <div style="background:var(--s1); padding:12px; border-radius:4px;">
        <div style="font-size:11px; font-weight:800; margin-bottom:8px; color:var(--bl);">Financial Metrics</div>
        <table style="width:100%; font-size:10px;">
          <tr><td style="padding:6px 0; color:#666;">EPS</td><td style="text-align:right; font-weight:700;">₹${fmt(s.eps)}</td></tr>
          <tr><td style="padding:6px 0; color:#666;">Sales</td><td style="text-align:right; font-weight:700;">₹${(num(s.sales) / 1000).toFixed(0)}K Cr</td></tr>
          <tr><td style="padding:6px 0; color:#666;">EBITDA</td><td style="text-align:right; font-weight:700;">₹${(num(s.ebitda) / 1000).toFixed(0)}K Cr</td></tr>
          <tr><td style="padding:6px 0; color:#666;">NPM %</td><td style="text-align:right; font-weight:700;">${fmt(s.npm)}%</td></tr>
        </table>
      </div>
      
      <div style="margin-top:12px; padding:12px; background:var(--s1); border-radius:4px; font-size:10px; color:#666;">
        <div style="margin-bottom:6px;"><strong>Holdings</strong></div>
        <div>Qty: ${num(s.qty)}</div>
        <div>Avg: ₹${fmt(s.avg)}</div>
        <div style="margin-top:6px; color:var(--bl); font-weight:700;">P&L: ₹${((num(s.ltp) - num(s.avg)) * num(s.qty)).toFixed(0)}</div>
      </div>
    </div>
  `;
}
