/* ═══════════════════════════════════════════════════════════
   app-portfolio.js - RESILIENT RENDERER
   Fix: Handles hanging DB connections and empty states
═══════════════════════════════════════════════════════════ */

async function renderPortfolio(container) {
    if (!container) return;
    
    // 1. Immediate Visual Feedback
    container.innerHTML = `<div style="padding:40px; text-align:center; color:var(--tx3)">
        <div class="spinner" style="margin-bottom:10px">⌛</div> Loading Portfolio Data...
    </div>`;
    
    log("Portfolio: Fetching from IndexedDB...");

    try {
        // 2. Safety Check: Is the Engine even loaded?
        if (typeof initEngineDB !== 'function') {
            throw new Error("Engine Module Missing (app-engine.js)");
        }

        const db = await initEngineDB();
        
        // 3. Fetch with a 3-second internal timeout
        const stocks = await Promise.race([
            new Promise((resolve, reject) => {
                const tx = db.transaction('UnifiedStocks', 'readonly');
                const store = tx.objectStore('UnifiedStocks');
                const req = store.getAll();
                req.onsuccess = () => resolve(req.result || []);
                req.onerror = () => reject("Database Read Failed");
            }),
            new Promise((_, reject) => setTimeout(() => reject("DB Timeout"), 3000))
        ]);

        log(`Portfolio: Received ${stocks.length} stocks`);

        // 4. Handle Empty State
        if (stocks.length === 0) {
            container.innerHTML = `
                <div style="padding:80px 20px; text-align:center;">
                    <div style="font-size:48px; margin-bottom:16px;">💼</div>
                    <div style="color:var(--tx1); font-family:'Syne'; font-size:20px; font-weight:800">No Holdings Found</div>
                    <p style="color:var(--tx3); font-size:13px; margin:15px 0 25px;">Paste your CDSL/Broker data to start.</p>
                    <button onclick="showTab('upload')" style="padding:14px 28px; background:var(--b2); border:none; border-radius:12px; color:white; font-weight:700; font-family:'Syne'">Go to Import</button>
                </div>`;
            return;
        }

        // 5. Render Header Summary
        let html = renderPortfolioSummary(stocks);

        // 6. Render Stock List
        html += `<div style="padding:10px 16px 120px;">`;
        
        // Sort by Market Value
        stocks.sort((a, b) => (b.marketValue || 0) - (a.marketValue || 0));

        stocks.forEach(s => {
            const isPos = (s.chg || 0) >= 0;
            html += `
            <div class="stock-row-container" style="position:relative; margin-bottom:12px; border-radius:12px; overflow:hidden; border:1px solid var(--b1)">
                <div class="stock-row" 
                     ontouchstart="handleTouchStart(event)" 
                     ontouchmove="handleTouchMove(event)" 
                     ontouchend="handleTouchEnd(event, '${s.sym}')"
                     onclick="viewStock('${s.sym}')"
                     style="background:var(--s2); padding:16px; display:flex; justify-content:space-between; align-items:center; position:relative; z-index:2">
                    
                    <div>
                        <div style="font-family:'Syne'; font-weight:700; font-size:16px; color:var(--tx1)">${s.sym}</div>
                        <div style="font-size:11px; color:var(--tx3); margin-top:4px">
                            Qty: ${s.qty} · <span style="color:var(--tx2)">W: ${Number(s.weight || 0).toFixed(1)}%</span>
                        </div>
                    </div>

                    <div style="text-align:right">
                        <div style="font-family:'JetBrains Mono'; font-weight:600; font-size:16px; color:var(--tx1)">₹${Number(s.ltp || 0).toLocaleString('en-IN')}</div>
                        <div style="font-size:11px; font-weight:800; color:${isPos ? 'var(--gr2)' : 'var(--rd2)'}">
                            ${isPos ? '▲' : '▼'} ${Math.abs(s.chg || 0).toFixed(2)}%
                        </div>
                    </div>
                </div>
            </div>`;
        });

        html += `</div>`;
        container.innerHTML = html;

    } catch (err) {
        log("Portfolio Error: " + err, "error");
        container.innerHTML = `
            <div style="padding:40px; text-align:center;">
                <div style="color:var(--rd2); font-weight:bold; margin-bottom:10px">⚠️ Data Engine Error</div>
                <div style="font-size:12px; color:var(--tx3)">${err}</div>
                <button onclick="location.reload()" style="margin-top:20px; padding:8px 16px; background:var(--b2); border:none; border-radius:8px; color:white">Hard Reload</button>
            </div>`;
    }
}

function renderPortfolioSummary(stocks) {
    const totalValue = stocks.reduce((sum, s) => sum + (s.marketValue || 0), 0);
    return `
        <div style="padding:30px 20px; background:var(--s1); border-bottom:1px solid var(--b1);">
            <div style="color:var(--tx3); font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:1px">Portfolio Value</div>
            <div style="font-family:'JetBrains Mono'; font-size:34px; font-weight:700; color:var(--tx1); margin:5px 0">
                ₹${Math.round(totalValue).toLocaleString('en-IN')}
            </div>
            <div style="font-size:12px; color:var(--gr2); font-weight:600">● Live Connection Active</div>
        </div>`;
}
