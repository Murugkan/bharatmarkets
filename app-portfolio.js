/**
 * BHARATMARKETS PRO - SINGLE STOCK MERGE (v19.0)
 * Objective: Merge Fundamentals and Prices for one specific stock.
 */
async function renderPortfolio(container) {
    if (!container) return;

    // Remove app-core/boot overlays to show the result
    const overlay = document.querySelector('.loading, #sync-overlay');
    if (overlay) overlay.style.display = 'none';

    try {
        // 1. Fetch both files independently
        const [fRes, pRes] = await Promise.all([
            fetch('fundamentals.json?v=' + Date.now()),
            fetch('prices.json?v=' + Date.now())
        ]);

        const fData = await fRes.json();
        const pData = await pRes.ok ? await pRes.json() : { stocks: {} };

        // 2. Identify the target stock (OLECTRA)
        const sym = "OLECTRA";
        const f = (fData.stocks || fData)[sym] || {};
        const p = (pData.stocks || pData)[sym] || {};

        // 3. Render the Merged Data Row
        container.innerHTML = `
            <div style="padding:20px; background:#02040a; min-height:100vh; font-family:sans-serif;">
                <div style="background:#111d30; border:1px solid #58a6ff; border-radius:12px; padding:20px; color:#fff;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <div style="color:#58a6ff; font-weight:bold; font-size:12px; margin-bottom:5px;">MERGED DATA NODE</div>
                            <h1 style="margin:0; font-size:28px;">${sym}</h1>
                            <div style="color:#8b949e; font-size:14px; margin-top:4px;">${f.sector || 'N/A'}</div>
                        </div>
                        <div style="text-align:right;">
                            <div style="font-size:24px; font-weight:bold;">₹${(p.ltp || f.ltp || 0).toFixed(0)}</div>
                            <div style="color:${(p.change || 0) >= 0 ? '#3fb950' : '#f85149'}; font-weight:bold;">
                                ${(p.change || 0) >= 0 ? '+' : ''}${(p.change || 0).toFixed(2)}%
                            </div>
                        </div>
                    </div>

                    <hr style="border:0; border-top:1px solid #1e3350; margin:20px 0;">

                    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:15px;">
                        <div style="background:#0d1117; padding:12px; border-radius:8px;">
                            <div style="color:#8b949e; font-size:10px;">FUNDAMENTAL ROE</div>
                            <div style="font-size:18px; font-weight:bold; color:#3fb950;">${f.roe || 'N/A'}%</div>
                        </div>
                        <div style="background:#0d1117; padding:12px; border-radius:8px;">
                            <div style="color:#8b949e; font-size:10px;">PRICE SOURCE</div>
                            <div style="font-size:16px; font-weight:bold;">${pRes.ok ? 'prices.json' : 'fundamentals.json'}</div>
                        </div>
                    </div>
                </div>
            </div>`;
    } catch (e) {
        container.innerHTML = `<div style="color:#f85149; padding:20px;">Merge Failed: ${e.message}</div>`;
    }
}
