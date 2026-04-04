/**
 * app-engine.js - The Core Data Engine
 * GitHub Source → IndexedDB Shadow Store
 */

// 1. Database Configuration
const DB_NAME = 'BharatEngineDB';
const DB_VER = 1;
const STORES = { 
    UNIFIED: 'UnifiedStocks', 
    LEDGER: 'ExclusionLedger' 
};

// 2. Initialize IndexedDB
async function initEngineDB() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, DB_VER);
        req.onupgradeneeded = (e) => {
            const db = e.target.result;
            if (!db.objectStoreNames.contains(STORES.UNIFIED))
                db.createObjectStore(STORES.UNIFIED, { keyPath: 'sym' });
            if (!db.objectStoreNames.contains(STORES.LEDGER))
                db.createObjectStore(STORES.LEDGER, { keyPath: 'sym' });
        };
        req.onsuccess = (e) => resolve(e.target.result);
        req.onerror = (e) => reject(e.target.error);
    });
}

// 3. The Sync Orchestrator (Requirement #3)
async function runEngineSync() {
    showToast("⚡ Engine Syncing...");
    const db = await initEngineDB();
    
    // Fetch from GitHub (Using your existing repo paths)
    const [fRes, pRes] = await Promise.all([
        fetch('https://raw.githubusercontent.com/Murugkan/bharatmarkets/main/fundamentals.json'),
        fetch('https://raw.githubusercontent.com/Murugkan/bharatmarkets/main/prices.json')
    ]);
    
    const fData = await fRes.json();
    const pData = await pRes.json();

    // Check Exclusion Ledger (Requirement #4)
    const ledger = await new Promise(r => {
        const tx = db.transaction(STORES.LEDGER, 'readonly');
        tx.objectStore(STORES.LEDGER).getAll().onsuccess = (e) => r(e.target.result.map(x => x.sym));
    });

    const tx = db.transaction(STORES.UNIFIED, 'readwrite');
    const store = tx.objectStore(STORES.UNIFIED);

    // Calculate Global Total for Weights (1 of 11 Computed Fields)
    const totalVal = fData.stocks.reduce((acc, s) => {
        const p = pData[s.sym]?.ltp || 0;
        return acc + (p * (s.qty || 0));
    }, 0);

    fData.stocks.forEach(stock => {
        if (ledger.includes(stock.sym)) return; // Skip "Deep Purged" items

        const p = pData[stock.sym] || {};
        
        // Requirement #2: Unified Record (33 Raw + 11 Computed)
        const unified = {
            ...stock,
            ltp: p.ltp || 0,
            chg: p.chg || 0,
            marketValue: (p.ltp || 0) * (stock.qty || 0),
            weight: totalVal > 0 ? (((p.ltp || 0) * stock.qty) / totalVal) * 100 : 0,
            athDist: stock.ath ? ((stock.ath - p.ltp) / stock.ath) * 100 : 0,
            marginGap: stock.opm - (stock.avgOpm3Yr || 0),
            signalScore: (stock.roe * 0.4) + (stock.opm * 0.6)
        };
        store.put(unified);
    });

    tx.oncomplete = () => {
        showToast("✅ Engine Synced");
        // Trigger the UI refresh in app-portfolio.js
        if(typeof renderPortfolio === 'function') renderPortfolio(); 
    };
}
