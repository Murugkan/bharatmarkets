/* ═══════════════════════════════════════════════════════════
   app-import.js - PERSISTENT WRITER
═══════════════════════════════════════════════════════════ */

async function processImport() {
    const area = document.getElementById('import-area');
    if (!area || !area.value.trim()) return;

    const rawText = area.value;
    log("Import: Processing text...");
    
    try {
        const lines = rawText.split('\n');
        const stocks = [];

        lines.forEach(line => {
            const parts = line.trim().split(/[\s,]+/);
            if (parts.length >= 2) {
                const sym = parts[0].toUpperCase().replace(/[^A-Z0-9]/g, '');
                const qty = parseInt(parts[1]);
                if (sym && !isNaN(qty)) {
                    stocks.push({ 
                        sym, qty, 
                        lastUpdated: Date.now(),
                        ltp: 0, chg: 0, marketValue: 0 
                    });
                }
            }
        });

        if (stocks.length === 0) {
            log("Import: No valid patterns.", "error");
            return;
        }

        const db = await initEngineDB();
        // Use a Promise to ensure the transaction FULLY completes
        await new Promise((resolve, reject) => {
            const tx = db.transaction('UnifiedStocks', 'readwrite');
            const store = tx.objectStore('UnifiedStocks');
            
            stocks.forEach(s => store.put(s));

            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });

        log(`✅ Saved ${stocks.length} stocks to DB.`);
        
        // FINAL VERIFICATION: Read it back immediately
        const verifyTx = db.transaction('UnifiedStocks', 'readonly');
        verifyTx.objectStore('UnifiedStocks').count().onsuccess = (e) => {
            log(`🔍 Post-Save Verify: ${e.target.result} rows exist.`);
            closePanel();
            showTab('portfolio');
        };

    } catch (err) {
        log("Import Crash: " + err.message, "error");
    }
}
