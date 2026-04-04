/* ═══════════════════════════════════════════════════════════
   app-import.js - DATA PARSER & DATABASE WRITER
═══════════════════════════════════════════════════════════ */

async function processImport() {
    const area = document.getElementById('import-area');
    if (!area || !area.value.trim()) {
        showToast("Please paste data first");
        return;
    }

    log("Import: Starting Parse...");
    const rawText = area.value;
    
    try {
        const lines = rawText.split('\n');
        const stocks = [];

        // Simple Parser: Matches "SYMBOL QTY"
        lines.forEach(line => {
            const parts = line.trim().split(/[\s,]+/);
            if (parts.length >= 2) {
                const sym = parts[0].toUpperCase().replace(/[^A-Z0-9]/g, '');
                const qty = parseInt(parts[1]);
                if (sym && !isNaN(qty)) {
                    stocks.push({ 
                        sym, 
                        qty, 
                        lastUpdated: Date.now(),
                        ltp: 0,
                        chg: 0,
                        marketValue: 0
                    });
                }
            }
        });

        if (stocks.length === 0) {
            log("Import Error: No valid stock patterns found", "error");
            showToast("Could not parse data");
            return;
        }

        log(`Import: Parsed ${stocks.length} stocks. Opening DB...`);

        const db = await initEngineDB();
        const tx = db.transaction('UnifiedStocks', 'readwrite');
        const store = tx.objectStore('UnifiedStocks');

        // Clear existing and add new
        stocks.forEach(s => store.put(s));

        tx.oncomplete = () => {
            log(`✅ SUCCESS: ${stocks.length} stocks saved to IndexedDB.`);
            showToast(`Imported ${stocks.length} Stocks`);
            
            // Close panel and switch to portfolio
            closePanel();
            
            // Trigger a re-render of the portfolio tab
            if (typeof showTab === 'function') {
                showTab('portfolio');
            }
        };

        tx.onerror = (e) => {
            log("❌ Database Write Error: " + e.target.error, "error");
        };

    } catch (err) {
        log("❌ Import Crash: " + err.message, "error");
    }
}
