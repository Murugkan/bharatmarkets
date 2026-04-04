// ─────────────────────────────────────────────────────────────
//  PORTFOLIO MODULE - EMERGENCY RECOVERY (v4.1)
// ─────────────────────────────────────────────────────────────

// 1. FAIL-SAFE DEBUGGER (Renders immediately)
const initDebug = () => {
    const existing = document.getElementById('emergency-debug');
    if (existing) return;
    const div = document.createElement('div');
    div.id = 'emergency-debug';
    div.style.cssText = "position:fixed;top:0;left:0;right:0;height:150px;background:#000;color:#0f0;z-index:99999;font-size:10px;overflow-y:auto;padding:10px;border-bottom:2px solid #333;font-family:monospace;";
    div.innerHTML = "<b>CONSOLE ACTIVE - WAITING FOR LOGS...</b><br>";
    document.body.appendChild(div);
};

window.logErr = (msg) => {
    initDebug();
    const el = document.getElementById('emergency-debug');
    el.innerHTML = `[${new Date().toLocaleTimeString()}] ERROR: ${msg}<br>` + el.innerHTML;
};

// 2. THE RENDERER WITH "TRY-CATCH" PROTECTION
function renderPortfolio(container) {
    initDebug();
    try {
        if (!container) throw new Error("Container not found");
        if (typeof S === 'undefined') throw new Error("Global S is undefined");

        // Simple Mapping Logic
        const pf = (S.portfolio || []).map(h => {
            const sym = h.sym ? h.sym.toUpperCase() : '';
            // Look for stock data in window[sym]
            const f = window[sym] || {};
            const ltp = h.liveLtp || f.ltp || 0;
            const avg = h.avgBuy || 0;
            return { ...h, ...f, ltp, pnlP: (((ltp - avg) / avg) * 100) || 0 };
        });

        // Generate HTML
        let html = `
        <div style="margin-top:160px; padding:15px; background:#000; color:#fff;">
            <h2 style="color:#64b5f6">Portfolio (${pf.length})</h2>
            <table style="width:100%; border-collapse:collapse; font-size:14px;">
                <tr style="color:#888; border-bottom:1px solid #333; text-align:left;">
                    <th style="padding:10px 0;">Stock</th>
                    <th>ROE%</th>
                    <th style="text-align:right;">P&L%</th>
                </tr>
                ${pf.map(r => `
                    <tr style="border-bottom:1px solid #222;">
                        <td style="padding:15px 0;"><b>${r.sym}</b></td>
                        <td style="color:${r.roe > 15 ? '#00e896' : '#ccc'}">${r.roe ? r.roe.toFixed(1) : '—'}</td>
                        <td style="text-align:right; color:${r.pnlP >= 0 ? '#00e896' : '#ff6b85'}">${r.pnlP.toFixed(1)}%</td>
                    </tr>
                `).join('')}
            </table>
        </div>`;

        container.innerHTML = html;
        logErr("Render successful: " + pf.length + " stocks.");

    } catch (e) {
        logErr("CRASH: " + e.message);
    }
}

// 3. AUTO-BOOT
setTimeout(() => {
    initDebug();
    if (typeof S === 'undefined') logErr("System Error: 'S' state is missing.");
}, 500);
