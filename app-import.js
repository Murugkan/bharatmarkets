async function processImport() {
    const area = document.getElementById('import-area');
    const rawText = area.value.trim();
    
    // DEBUG TOOL: If you paste "DEBUG_QUERY_DB_ROWS", it lists the DB
    if (rawText === "DEBUG_QUERY_DB_ROWS") {
        log("🔍 Querying Database Rows...");
        const db = await initEngineDB();
        const tx = db.transaction('UnifiedStocks', 'readonly');
        const store = tx.objectStore('UnifiedStocks');
        store.getAll().onsuccess = (e) => {
            const all = e.target.result;
            if (all.length === 0) {
                log("❌ DB IS EMPTY", "error");
            } else {
                log(`✅ DB FOUND: ${all.length} total rows.`);
                // Show first 3 rows as samples
                all.slice(0, 3).forEach(s => {
                    log(`Row: ${s.sym} | Qty: ${s.qty} | Val: ${s.marketValue || 0}`);
                });
            }
        };
        return;
    }

    // --- Normal Import Logic Below ---
    log("Import: Starting Parse...");
    try {
        const lines = rawText.split('\n');
        const stocks = [];
        lines.forEach(line => {
            const parts = line.trim().split(/[\s,]+/);
            if (parts.length >= 2) {
                const sym = parts[0].toUpperCase().replace(/[^A-Z0-9]/g, '');
                const qty = parseInt(parts[1]);
                if (sym && !isNaN(qty)) stocks.push({ sym, qty });
            }
        });

        if (stocks.length === 0) {
            log("Import Error: No valid data found", "error");
            return;
        }

        const db = await initEngineDB();
        const tx = db.transaction('UnifiedStocks', 'readwrite');
        const store = tx.objectStore('UnifiedStocks');
        stocks.forEach(s => store.put(s));

        tx.oncomplete = () => {
            log(`Successfully saved ${stocks.length} stocks.`);
            showTab('portfolio');
        };
    } catch (err) {
        log("Import Crash: " + err.message, "error");
    }
}
