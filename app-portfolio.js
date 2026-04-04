/* ═══════════════════════════════════════════════════════════
   app-portfolio.js - MATURED PORTFOLIO RENDERER
   Logic: Pulls from Unified Engine -> Renders Swipeable Rows
═══════════════════════════════════════════════════════════ */

/**
 * 1. Main Entry Point: Renders the Portfolio Tab
 */
async function renderPortfolio(container) {
    if (!container) return;
    log("Portfolio: Starting Render...");

    try {
        // Get Data from the Engine (IndexedDB)
        const db = await initEngineDB();
        const stocks = await new Promise((resolve, reject) => {
            const tx = db.transaction('UnifiedStocks', 'readonly');
            const store = tx.objectStore('UnifiedStocks');
            const req = store.getAll();
            req.onsuccess = () => resolve(req.result || []);
            req.onerror = () => reject("DB Read Error");
        });

        if (stocks.length === 0) {
            container.innerHTML = `
                <div style="padding:80px 20px; text-align:center;">
                    <div style="font-size:48px; margin-bottom:16px;">💼</div>
                    <div style="color:var(--tx3); font-family:'Syne'; font-size:18px;">Portfolio is Empty</div>
                    <p style="color:var(--tx3); font-size:13px; margin:10px 0 20px;">Import your holdings to start tracking.</p>
                    <button onclick="showTab('upload')" style="padding:12px 24px; background:var(--b2); border:none; border-radius:12px; color:white; font-weight:700;">Import Data</button>
                </div>`;
            return;
        }

        // 2. Build HTML Output
        let html = renderPortfolioSummary(stocks);

        html += `<div style="padding:10px 16px 100px;">`;
        
        // Sort by Market Value descending
        stocks.sort((a, b) => (b.marketValue || 0) - (a.marketValue || 0));

        stocks.forEach(s => {
            const isPositive = (s.chg || 0) >= 0;
            const signalClass = getSignalClass(s.score || 50);

            html += `
            <div class="stock-row-container" style="position:relative; margin-bottom:12px; overflow:hidden; border-radius:12px;">
                <div style="position:absolute; right:0; top:0; bottom:0; width:90px; background:var(--rd1); display:flex; align-items:center; justify-content:center; border-radius:0 12px 12px 0;">
                    <button onclick="deleteStock('${s.sym}')" style="background:none; border:none; color:white; font-weight:700;">DELETE</button>
                </div>

                <div class="stock-row" 
                     ontouchstart="handleTouchStart(event)" 
                     ontouchmove="handleTouchMove(event)" 
                     ontouchend="handleTouchEnd(event, '${s.sym}')"
                     onclick="if(Math.abs(swipeStartX - event.changedTouches[0].clientX) < 5) viewStock('${s.sym}')"
                     style="position:relative; background:var(--s2); padding:14px; display:flex; justify-content:space-between; align-items:center; transition: transform 0.3s ease; z-index:2; border:1px solid var(--b1);">
                    
                    <div style="display:flex; align-items:center; gap:12px">
                        <div class="signal-dot ${signalClass}"></div>
                        <div>
                            <div style="font-family:'Syne'; font-weight:700; font-size:15px; color:var(--tx1)">${s.sym}</div>
                            <div style="font-size:11px; color:var(--tx3); margin-top:2px;">
                                Qty: ${s.qty} · <span style="color:var(--tx2)">W: ${Number(s.weight || 0).toFixed(1)}%</span>
                            </div>
                        </div>
                    </div>

                    <div style="text-align:right">
                        <div style="font-family:'JetBrains Mono'; font-weight:600; font-size:15px; color:var(--tx1)">
                            ₹${Number(s.ltp || 0).toLocaleString('en-IN')}
                        </div>
                        <div style="font-size:11px; font-weight:700; color:${isPositive ? 'var(--gr2)' : 'var(--rd2)'}">
                            ${isPositive ? '▲' : '▼'} ${Math.abs(s.chg || 0).toFixed(2)}%
                        </div>
                    </div>
                </div>
            </div>`;
        });

        html += `</div>`;
        container.innerHTML = html;
        log("Portfolio: Render Complete");

    } catch (err) {
        log("Portfolio Error: " + err, "error");
        container.innerHTML = `<div style="padding:40px; color:var(--rd2)">Failed to load portfolio. Check Engine logs.</div>`;
    }
}

/**
 * 2. Portfolio Summary Component
 */
function renderPortfolioSummary(stocks) {
    const totalValue = stocks.reduce((sum, s) => sum + (s.marketValue || 0), 0);
    const dayPL = stocks.reduce((sum, s) => {
        const prevClose = (s.ltp || 0) / (1 + (s.chg || 0) / 100);
        return sum + ((s.ltp - prevClose) * s.qty);
    }, 0);
    const dayPct = totalValue > 0 ? (dayPL / (totalValue - dayPL)) * 100 : 0;

    return `
        <div style="padding:24px 16px; background:linear-gradient(180deg, var(--s1) 0%, var(--bg) 100%); border-bottom:1px solid var(--b1);">
            <div style="color:var(--tx3); font-size:12px; font-weight:600; text-transform:uppercase; letter-spacing:1px; margin-bottom:4px;">Current Value</div>
            <div style="font-family:'JetBrains Mono'; font-size:32px; font-weight:700; color:var(--tx1); margin-bottom:12px;">
                ₹${Math.round(totalValue).toLocaleString('en-IN')}
            </div>
            <div style="display:flex; gap:15px;">
                <div style="background:rgba(255,255,255,0.03); padding:8px 12px; border-radius:8px; border:1px solid var(--b1);">
                    <div style="color:var(--tx3); font-size:10px; margin-bottom:2px;">Day Returns</div>
                    <div style="font-weight:700; color:${dayPL >= 0 ? 'var(--gr2)' : 'var(--rd2)'}; font-size:14px;">
                        ${dayPL >= 0 ? '+' : ''}${Math.round(dayPL).toLocaleString('en-IN')} (${dayPct.toFixed(2)}%)
                    </div>
                </div>
            </div>
        </div>`;
}

/**
 * 3. Helper: Signal Color Logic
 */
function getSignalClass(score) {
    if (score > 75) return 'sig-buy';
    if (score < 40) return 'sig-sell';
    return 'sig-neutral';
}

/**
 * 4. Action: Delete Stock
 */
async function deleteStock(sym) {
    if (!confirm(`Remove ${sym} from portfolio?`)) return;
    try {
        const db = await initEngineDB();
        const tx = db.transaction('UnifiedStocks', 'readwrite');
        tx.objectStore('UnifiedStocks').delete(sym);
        tx.oncomplete = () => {
            showToast(`${sym} Removed`);
            render(); // Re-render the tab
        };
    } catch (e) {
        log("Delete failed: " + e.message, "error");
    }
}
