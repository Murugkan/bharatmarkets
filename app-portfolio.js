/**
 * BHARATMARKETS PRO - FULL PORTFOLIO SYNC (v17.0)
 * Confirmed Data: ROE, LTP, and Sector are reachable.
 */
async function renderPortfolio(container) {
    if (!container) return;

    // 1. Force clear any stuck "Syncing" overlays
    const overlays = document.querySelectorAll('.loading, #sync-overlay');
    overlays.forEach(el => el.style.display = 'none');

    container.innerHTML = `<div style="padding:40px; color:#58a6ff; font-family:monospace;">> SYNCING ALL NODES...</div>`;

    try {
        const r = await fetch('fundamentals.json?v=' + Date.now());
        const data = await r.json();
        
        const stocksObj = data.stocks || data;
        const symbols = Object.keys(stocksObj);

        // 2. RENDER THE FULL TABLE
        container.innerHTML = `
            <div style="padding:16px; background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif;">
                <div style="background:#111d30; padding:15px; border-radius:12px; border:1px solid #1e3350; margin-bottom:15px; display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <div style="color:#8b949e; font-size:10px; letter-spacing:1px;">TOTAL ASSETS</div>
                        <div style="font-size:20px; font-weight:bold;">${symbols.length} Stocks</div>
                    </div>
                    <div style="text-align:right;">
                        <div style="color:#3fb950; font-size:10px;">SYSTEM STATUS</div>
                        <div style="font-size:14px; font-weight:bold;">CONNECTED</div>
                    </div>
                </div>

                <div style="background:#0d1117; border-radius:12px; border:1px solid #1e3350; overflow:hidden;">
                    <table style="width:100%; border-collapse:collapse; font-size:14px;">
                        <tbody>
                            ${symbols.map(sym => {
                                const s = stocksObj[sym];
                                const ltp = parseFloat(s.ltp || 0);
                                return `
                                <tr style="border-bottom:1px solid #1e3350;">
                                    <td style="padding:14px 12px;">
                                        <div style="font-weight:bold; color:#58a6ff;">${sym}</div>
                                        <div style="font-size:10px; color:#8b949e;">${s.sector || 'N/A'}</div>
                                    </td>
                                    <td style="text-align:center; padding:14px 12px;">
                                        <div style="font-size:10px; color:#8b949e;">ROE</div>
                                        <div style="color:${s.roe > 15 ? '#3fb950' : '#fff'}">${s.roe ? s.roe.toFixed(1)+'%' : '--'}</div>
                                    </td>
                                    <td style="text-align:right; padding:14px 12px;">
                                        <div style="font-weight:bold;">₹${ltp.toLocaleString('en-IN', {maximumFractionDigits: 0})}</div>
                                        <div style="font-size:10px; color:#484f58;">LIVE</div>
                                    </td>
                                </tr>`;
                            }).join('')}
                        </tbody>
                    </table>
                </div>
                <div style="height:80px;"></div>
            </div>`;

    } catch (e) {
        container.innerHTML = `<div style="padding:40px; color:#f85149;">❌ CRITICAL SYNC ERROR: ${e.message}</div>`;
    }
}
