/* ═══════════════════════════════════════════════════════════
   app-portfolio.js - DIRECT DB RENDERER
═══════════════════════════════════════════════════════════ */

async function renderPortfolio(container) {
    if (!container) return;
    
    try {
        const db = await initEngineDB();
        const stocks = await new Promise((resolve) => {
            const tx = db.transaction('UnifiedStocks', 'readonly');
            tx.objectStore('UnifiedStocks').getAll().onsuccess = (e) => resolve(e.target.result || []);
        });

        log(`Portfolio UI: Processing ${stocks.length} stocks`);

        if (stocks.length === 0) {
            container.innerHTML = `<div style="padding:100px 20px; text-align:center; color:var(--tx3)">DB is Empty (0 stocks)</div>`;
            return;
        }

        let html = `<div style="padding:20px; background:var(--s1); border-bottom:1px solid var(--b1); font-weight:bold">${stocks.length} Stocks Found</div><div style="padding:16px">`;
        stocks.forEach(s => {
            html += `<div style="background:var(--s2); padding:15px; margin-bottom:10px; border-radius:10px; border:1px solid var(--b1)">
                <div style="font-weight:bold">${s.sym}</div>
                <div style="font-size:12px; color:var(--tx3)">Qty: ${s.qty}</div>
            </div>`;
        });
        html += `</div>`;
        container.innerHTML = html;

    } catch (err) {
        container.innerHTML = `<div style="padding:40px">Error: ${err}</div>`;
    }
}
