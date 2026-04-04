/* ═══════════════════════════════════════════════════════════
   app-portfolio.js - FINAL RESILIENT RENDERER
   Goal: Handle "0 Stocks" state with a clear UI
═══════════════════════════════════════════════════════════ */

async function renderPortfolio(container) {
    if (!container) return;
    
    // 1. Loading State
    container.innerHTML = `<div style="padding:60px; text-align:center; color:var(--tx3)">
        <div style="font-size:24px; margin-bottom:10px">⏳</div> Fetching Portfolio...
    </div>`;
    
    log("Portfolio: Fetching from IndexedDB...");

    try {
        if (typeof initEngineDB !== 'function') throw new Error("Engine Missing");

        const db = await initEngineDB();
        const stocks = await new Promise((resolve, reject) => {
            const tx = db.transaction('UnifiedStocks', 'readonly');
            const store = tx.objectStore('UnifiedStocks');
            const req = store.getAll();
            req.onsuccess = () => resolve(req.result || []);
            req.onerror = () => reject("Read Failed");
        });

        log(`Portfolio: Received ${stocks.length} stocks`);

        // 2. THE "EMPTY STATE" FIX
        if (stocks.length === 0) {
            container.innerHTML = `
                <div style="padding:100px 20px; text-align:center;">
                    <div style="font-size:64px; margin-bottom:20px;">📁</div>
                    <div style="color:var(--tx1); font-family:'Syne'; font-size:22px; font-weight:800">Portfolio Empty</div>
                    <p style="color:var(--tx3); font-size:14px; margin:15px auto 30px; max-width:250px; line-height:1.5">
                        Your local database has no holdings. Paste your data in the Import tab to begin.
                    </p>
                    <button onclick="showTab('upload')" style="width:200px; padding:16px; background:var(--gr1); color:var(--bg); border:none; border-radius:12px; font-weight:800; font-family:'Syne'; text-transform:uppercase; letter-spacing:1px; box-shadow: 0 10px 20px rgba(0,242,255,0.2)">
                        Go to Import
                    </button>
                </div>`;
            return;
        }

        // 3. RENDER DATA (If stocks > 0)
        let html = `
            <div style="padding:30px 20px; background:var(--s1); border-bottom:1px solid var(--b1);">
                <div style="color:var(--tx3); font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:1px">Total Holdings</div>
                <div style="font-family:'JetBrains Mono'; font-size:34px; font-weight:700; color:var(--tx1); margin:5px 0">
                    ${stocks.length} <span style="font-size:16px; color:var(--tx3)">Stocks</span>
                </div>
            </div>
            <div style="padding:10px 16px 120px;">`;

        stocks.forEach(s => {
            html += `
            <div style="background:var(--s2); padding:16px; margin-bottom:12px; border-radius:12px; border:1px solid var(--b1); display:flex; justify-content:space-between; align-items:center">
                <div>
                    <div style="font-family:'Syne'; font-weight:700; font-size:16px; color:var(--tx1)">${s.sym}</div>
                    <div style="font-size:12px; color:var(--tx3)">Qty: ${s.qty}</div>
                </div>
                <div style="text-align:right">
                    <div style="font-family:'JetBrains Mono'; color:var(--tx1)">₹${Number(s.ltp || 0).toLocaleString('en-IN')}</div>
                </div>
            </div>`;
        });

        html += `</div>`;
        container.innerHTML = html;

    } catch (err) {
        log("Portfolio Error: " + err, "error");
        container.innerHTML = `<div style="padding:50px; color:var(--rd2); text-align:center">⚠️ Render Error: ${err}</div>`;
    }
}
