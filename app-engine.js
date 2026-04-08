/**

- app-engine.js - The Core Data Engine
- GitHub Source → IndexedDB Shadow Store
  */

// 1. Database Configuration
const DB_NAME = ‘BharatEngineDB’;
const DB_VER = 1;
const STORES = {
UNIFIED: ‘UnifiedStocks’,
LEDGER: ‘ExclusionLedger’
};

// 2. Initialize IndexedDB
async function initEngineDB() {
return new Promise((resolve, reject) => {
const req = indexedDB.open(DB_NAME, DB_VER);
req.onupgradeneeded = (e) => {
const db = e.target.result;
if (!db.objectStoreNames.contains(STORES.UNIFIED))
db.createObjectStore(STORES.UNIFIED, { keyPath: ‘sym’ });
if (!db.objectStoreNames.contains(STORES.LEDGER))
db.createObjectStore(STORES.LEDGER, { keyPath: ‘sym’ });
};
req.onsuccess = (e) => resolve(e.target.result);
req.onerror = (e) => reject(e.target.error);
});
}

// 3. The Sync Orchestrator (Requirement #3)
async function runEngineSync() {
showToast(“⚡ Engine Syncing…”);
const db = await initEngineDB();

```
let fData, pData;

// STEP 1: Try loading from local files first (fastest, most reliable)
try {
    const [fRes, pRes] = await Promise.all([
        fetch('./fundamentals.json'),
        fetch('./prices.json')
    ]);
    
    if (!fRes.ok || !pRes.ok) {
        throw new Error(`Local files not found: fRes=${fRes.status}, pRes=${pRes.status}`);
    }
    
    fData = await fRes.json();
    pData = await pRes.json();
    showToast("✅ Loaded from local cache");
    console.log("✅ Local data loaded successfully");
    
} catch(localErr) {
    console.warn("⚠️ Local load failed, trying GitHub:", localErr);
    showToast("⚡ Syncing from GitHub...");
    
    try {
        // STEP 2: Fallback to GitHub if local fails
        const [fRes, pRes] = await Promise.all([
            fetch('https://raw.githubusercontent.com/murugkan/bharatmarkets/main/fundamentals.json'),
            fetch('https://raw.githubusercontent.com/murugkan/bharatmarkets/main/prices.json')
        ]);
        
        if (!fRes.ok || !pRes.ok) {
            throw new Error(`GitHub fetch failed: fRes=${fRes.status}, pRes=${pRes.status}`);
        }
        
        fData = await fRes.json();
        pData = await pRes.json();
        showToast("✅ Synced from GitHub");
        console.log("✅ GitHub data loaded successfully");
        
    } catch(githubErr) {
        console.error("❌ Both local and GitHub failed:", { localErr, githubErr });
        showToast("❌ Failed to load data. Check console.");
        return;  // Exit early to prevent crash
    }
}

// Check Exclusion Ledger (Requirement #4)
const ledger = await new Promise(r => {
    const tx = db.transaction(STORES.LEDGER, 'readonly');
    tx.objectStore(STORES.LEDGER).getAll().onsuccess = (e) => r(e.target.result.map(x => x.sym));
});

const tx = db.transaction(STORES.UNIFIED, 'readwrite');
const store = tx.objectStore(STORES.UNIFIED);

// Handle both array and object formats for stocks
const stocksArray = Array.isArray(fData.stocks) ? fData.stocks : Object.values(fData.stocks || {});

// Calculate Global Total for Weights (1 of 11 Computed Fields)
const totalVal = stocksArray.reduce((acc, s) => {
    const sym = s.sym || s.SYM || '';
    const p = pData[sym]?.ltp || 0;
    return acc + (p * (s.qty || 0));
}, 0);

stocksArray.forEach(stock => {
    const sym = stock.sym || stock.SYM || '';
    if (ledger.includes(sym)) return; // Skip "Deep Purged" items

    const p = pData[sym] || {};
    
    // Requirement #2: Unified Record (33 Raw + 11 Computed)
    const unified = {
        ...stock,
        sym: sym,  // Ensure sym field exists
        ltp: p.ltp || 0,
        chg: p.chg || 0,
        marketValue: (p.ltp || 0) * (stock.qty || 0),
        weight: totalVal > 0 ? (((p.ltp || 0) * (stock.qty || 0)) / totalVal) * 100 : 0,
        athDist: stock.ath ? ((stock.ath - p.ltp) / stock.ath) * 100 : 0,
        marginGap: stock.opm - (stock.avgOpm3Yr || 0),
        signalScore: (stock.roe * 0.4) + (stock.opm * 0.6)
    };
    store.put(unified);
});

tx.oncomplete = () => {
    console.log("✅ IndexedDB updated with", stocksArray.length, "stocks");
    showToast("✅ Engine Synced");
    // Trigger the UI refresh in app-portfolio.js
    if(typeof renderPortfolio === 'function') renderPortfolio(); 
};

tx.onerror = () => {
    console.error("❌ IndexedDB transaction failed");
    showToast("❌ Database error");
};
```

}
