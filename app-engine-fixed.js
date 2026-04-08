/**
 * app-engine.js - The Core Data Engine
 * GitHub Source to IndexedDB Shadow Store
 */

// Toast notification (works without external dependencies)
function showToast(message, duration) {
    duration = duration || 2000;
    console.log("[TOAST]", message);
    
    // Create toast element if needed
    let toast = document.getElementById('app-toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'app-toast';
        toast.style.cssText = 'position:fixed;bottom:20px;left:50%;transform:translateX(-50%);background:#00f2ff;color:#000;padding:12px 24px;border-radius:4px;font-size:12px;font-weight:800;z-index:9999;opacity:0.9;';
        document.body.appendChild(toast);
    }
    
    toast.textContent = message;
    toast.style.display = 'block';
    
    setTimeout(function() {
        toast.style.display = 'none';
    }, duration);
}

// 1. Database Configuration
var DB_NAME = 'BharatEngineDB';
var DB_VER = 1;
var STORES = { 
    UNIFIED: 'UnifiedStocks', 
    LEDGER: 'ExclusionLedger' 
};

// 2. Initialize IndexedDB
function initEngineDB() {
    return new Promise(function(resolve, reject) {
        var req = indexedDB.open(DB_NAME, DB_VER);
        req.onupgradeneeded = function(e) {
            var db = e.target.result;
            if (!db.objectStoreNames.contains(STORES.UNIFIED))
                db.createObjectStore(STORES.UNIFIED, { keyPath: 'sym' });
            if (!db.objectStoreNames.contains(STORES.LEDGER))
                db.createObjectStore(STORES.LEDGER, { keyPath: 'sym' });
        };
        req.onsuccess = function(e) { resolve(e.target.result); };
        req.onerror = function(e) { reject(e.target.error); };
    });
}

// 3. The Sync Orchestrator
function runEngineSync() {
    return initEngineDB().then(function(db) {
        showToast("Engine Syncing...");
        console.log("Starting data sync...");
        
        var fData, pData;
        
        // STEP 1: Try loading from local files first
        return Promise.all([
            fetch('./fundamentals.json'),
            fetch('./prices.json')
        ])
        .then(function(responses) {
            if (!responses[0].ok || !responses[1].ok) {
                throw new Error('Local files not found');
            }
            return Promise.all([responses[0].json(), responses[1].json()]);
        })
        .then(function(data) {
            fData = data[0];
            pData = data[1];
            showToast("Loaded from local cache");
            console.log("Local data loaded:", Object.keys(fData.stocks || {}).length, "stocks");
            return processAndStore(db, fData, pData);
        })
        .catch(function(localErr) {
            console.warn("Local load failed, trying GitHub:", localErr);
            showToast("Syncing from GitHub...");
            
            // STEP 2: Fallback to GitHub if local fails
            return Promise.all([
                fetch('https://raw.githubusercontent.com/murugkan/bharatmarkets/main/fundamentals.json'),
                fetch('https://raw.githubusercontent.com/murugkan/bharatmarkets/main/prices.json')
            ])
            .then(function(responses) {
                if (!responses[0].ok || !responses[1].ok) {
                    throw new Error('GitHub fetch failed');
                }
                return Promise.all([responses[0].json(), responses[1].json()]);
            })
            .then(function(data) {
                fData = data[0];
                pData = data[1];
                showToast("Synced from GitHub");
                console.log("GitHub data loaded:", Object.keys(fData.stocks || {}).length, "stocks");
                return processAndStore(db, fData, pData);
            });
        });
    }).catch(function(error) {
        console.error("Sync failed:", error);
        showToast("Sync failed");
    });
}

function processAndStore(db, fData, pData) {
    return new Promise(function(resolve, reject) {
        var tx = db.transaction(STORES.UNIFIED, 'readwrite');
        var store = tx.objectStore(STORES.UNIFIED);
        
        // Handle both array and object formats
        var stocksData = fData.stocks || {};
        var stocksArray = Array.isArray(stocksData) ? stocksData : Object.keys(stocksData).map(function(k) { 
            return Object.assign({sym: k}, stocksData[k]); 
        });
        
        console.log("Processing", stocksArray.length, "stocks...");
        
        // Calculate total for weights
        var totalVal = 0;
        stocksArray.forEach(function(s) {
            var sym = s.sym || s.SYM || '';
            var p = pData[sym] || {};
            totalVal += (p.ltp || 0) * (s.qty || 0);
        });
        
        // Store each stock
        stocksArray.forEach(function(stock) {
            var sym = stock.sym || stock.SYM || '';
            var p = pData[sym] || {};
            
            var unified = Object.assign({}, stock, {
                sym: sym,
                ltp: p.ltp || 0,
                chg: p.chg || 0,
                marketValue: (p.ltp || 0) * (stock.qty || 0),
                weight: totalVal > 0 ? (((p.ltp || 0) * (stock.qty || 0)) / totalVal) * 100 : 0,
                athDist: stock.ath ? ((stock.ath - p.ltp) / stock.ath) * 100 : 0,
                marginGap: (stock.opm || 0) - (stock.avgOpm3Yr || 0),
                signalScore: (stock.roe || 0) * 0.4 + (stock.opm || 0) * 0.6
            });
            store.put(unified);
        });
        
        tx.oncomplete = function() {
            console.log("IndexedDB sync complete!");
            showToast("Engine Synced");
            
            if(typeof renderPortfolio === 'function') {
                console.log("Calling renderPortfolio...");
                renderPortfolio();
            } else {
                console.warn("renderPortfolio not found");
                window.dispatchEvent(new CustomEvent('engine-updated'));
            }
            resolve();
        };
        
        tx.onerror = function() {
            console.error("Transaction failed:", tx.error);
            showToast("Database error");
            reject(tx.error);
        };
    });
}
