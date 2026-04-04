/* ═══════════════════════════════════════════════════════════
   app-portfolio.js - PORTFOLIO VIEW RENDERER
═══════════════════════════════════════════════════════════ */

async function renderPortfolio(container) {
    if (!container) return;
    
    try {
        if (typeof initEngineDB !== 'function') throw new Error("Engine Missing");

        const db = await initEngineDB();
        const stocks = await new Promise((resolve) => {
            const tx = db.transaction('UnifiedStocks', 'readonly');
            const req = tx.objectStore('UnifiedStocks').getAll();
            req.onsuccess = () => resolve(req.result || []);
        });

        if (stocks.length === 0) {
            container.innerHTML = `
                <div style="padding:100px 20px; text-align:center;">
                    <div style="font-size:64px; margin-bottom:20px;">📁</div>
                    <div style="color:var(--tx1); font-family:'Syne'; font-size:22px; font-weight:800">No Data in DB</div>
                    <p style="color:var(--tx3); font-size:14px; margin:15px auto 30px; line-height:1.5">
                        Import logic ready. Please paste data in the Upload tab.
                    </p>
                    <button onclick="showTab('upload')" style="padding:16px 32px; background:var(--b2); border:none; border-radius:12px; color:white; font-weight:700;">
                        Open Importer
                    </button>
                </div>`;
            return;
        }

        // Render Summary
        const totalVal = stocks.reduce((acc, s) => acc + (s.marketValue || 0), 0);
        let html = `
            <div style="padding:30px 20px; background:var(--s1); border-bottom:1px solid var(--b1);">
                <div style="color:var(--tx3); font-size:11px; font-weight:700; text-transform:uppercase;">Portfolio Value</div>
                <div style="font-family:'JetBrains Mono'; font-size:34px; font-weight:700; color:var(--tx1); margin:5px 0">
                    ₹${Math.round(totalVal).toLocaleString('en-IN')}
                </div>
            </div>
            <div style="padding:16px 16px 120px;">`;

        // Render Rows
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
        container.innerHTML = `<div style="padding:50px; color:var(--rd2); text-align:center">Error: ${err.message}</div>`;
    }
}
