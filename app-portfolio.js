async function renderPortfolio(container) {
    if (!container) return;
    
    // Kill the "Syncing" overlay immediately
    const overlay = document.querySelector('.loading, #sync-overlay');
    if (overlay) overlay.style.display = 'none';

    try {
        // 1. Fetch both data files simultaneously
        const [fRes, pRes] = await Promise.all([
            fetch('fundamentals.json?v=' + Date.now()),
            fetch('prices.json?v=' + Date.now()).catch(() => ({ ok: false })) // Handle missing prices.json
        ]);

        const fData = await fRes.json();
        const pData = pRes.ok ? await pRes.json() : { stocks: {} };
        
        const fStocks = fData.stocks || fData;
        const pStocks = pData.stocks || pData;
        const symbols = Object.keys(fStocks);

        container.innerHTML = `
            <div style="padding:16px; background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif;">
                <div style="background:#111d30; padding:15px; border-radius:12px; border:1px solid #1e3350; margin-bottom:15px; display:flex; justify-content:space-between;">
                    <div><small style="color:#8b949e">ASSETS</small><br><b>${symbols.length} Stocks</b></div>
                    <div style="text-align:right;"><small style="color:#3fb950">STATUS</small><br><b>LIVE SYNC</b></div>
                </div>

                <div style="background:#0d1117; border-radius:12px; border:1px solid #1e3350; overflow:hidden;">
                    <table style="width:100%; border-collapse:collapse;">
                        ${symbols.map(sym => {
                            const f = fStocks[sym] || {};
                            const p = pStocks[sym] || {};
                            
                            // Merge Price Data with Fundamental Data
                            const ltp = p.ltp || f.ltp || 0;
                            const chg = p.change || 0;

                            return `
                            <tr style="border-bottom:1px solid #1e3350;">
                                <td style="padding:14px 12px;">
                                    <b style="color:#58a6ff">${sym}</b><br>
                                    <small style="color:#8b949e">${f.sector || 'N/A'}</small>
                                </td>
                                <td style="text-align:center;">
                                    <small style="color:#8b949e">ROE</small><br>
                                    <span style="color:${f.roe > 15 ? '#3fb950' : '#fff'}">${f.roe ? f.roe.toFixed(1)+'%' : '--'}</span>
                                </td>
                                <td style="padding:14px 12px; text-align:right;">
                                    <div style="font-weight:bold;">₹${parseFloat(ltp).toFixed(0)}</div>
                                    <div style="font-size:10px; color:${chg >= 0 ? '#3fb950' : '#f85149'}">${chg >= 0 ? '+' : ''}${chg}%</div>
                                </td>
                            </tr>`;
                        }).join('')}
                    </table>
                </div>
            </div>`;
    } catch (e) {
        container.innerHTML = `<div style="padding:40px; color:#f85149;">Sync Error: ${e.message}</div>`;
    }
}
