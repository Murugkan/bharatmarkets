/* ═══════════════════════════════════════════════════════════
   app-portfolio.js - MATURED PORTFOLIO RENDERER
   Logic: Pulls from Unified Engine -> Renders Swipeable Rows
═══════════════════════════════════════════════════════════ */

const FUND_CACHE_TTL = 60 * 60 * 1000; 

/**
 * 1. Main Entry Point: Renders the Portfolio Tab
 */
async function renderPortfolio(container) {
    if (!container) return;
    
    // Get Data from the Engine (IndexedDB) instead of raw memory
    const db = await initEngineDB();
    const stocks = await new Promise(r => {
        const tx = db.transaction('UnifiedStocks', 'readonly');
        tx.objectStore('UnifiedStocks').getAll().onsuccess = (e) => r(e.target.result);
    });

    if (stocks.length === 0) {
        container.innerHTML = `
            <div style="padding:60px 20px; text-align:center;">
                <div style="font-size:40px; margin-bottom:16px;">💼</div>
                <div style="color:var(--tx3); font-family:'Syne';">Portfolio is Empty</div>
                <button onclick="showTab('upload')" style="margin-top:20px; padding:10px 20px; background:var(--b2); border:none; border-radius:8px; color:white;">Import Data</button>
            </div>`;
        return;
    }

    // Sort Logic (Applying your default sort)
    stocks.sort((a, b) => (b.marketValue || 0) - (a.marketValue || 0));

    let html = `
        <div class="engine-status-bar">
            <span>UNIFIED ENGINE ACTIVE</span>
            <span style="color:var(--gr2)">● LIVE</span>
        </div>
        <div style="padding:12px 0;">
    `;

    stocks.forEach(s => {
        const isPositive = s.chg >= 0;
        
        html += `
        <div class="swipe-wrap">
            <div class="delete-underlay" onclick="deepPurge('${s.sym}')">
                <div class="delete-text">PURGE</div>
            </div>

            <div class="engine-row" 
                 onclick="viewStock('${s.sym}')"
                 ontouchstart="handleTouchStart(event)" 
                 ontouchmove="handleTouchMove(event)" 
                 ontouchend="handleTouchEnd(event, '${s.sym}')">
                
                <div style="flex:1">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="font-family:'Syne'; font-weight:800; font-size:15px;">${s.sym}</span>
                        <span class="sig-badge ${s.signalScore > 70 ? 'sig-buy' : ''}">
                            ${s.signalScore.toFixed(0)}
                        </span>
                    </div>
                    <div class="eng-meta">
                        <span class="sig-badge">W: ${s.weight.toFixed(1)}%</span>
                        <span class="sig-badge">ROE: ${s.roe}%</span>
                    </div>
                </div>

                <div style="text-align:right">
                    <div style="font-family:'JetBrains Mono'; font-weight:600; font-size:15px;">
                        ₹${Number(s.ltp).toLocaleString('en-IN')}
                    </div>
                    <div style="font-size:11px; font-weight:700; color:${isPositive ? 'var(--gr2)' : 'var(--rd2)'}">
                        ${isPositive ? '▲' : '▼'} ${Math.abs(s.chg).toFixed(2)}%
                    </div>
                </div>
            </div>
        </div>`;
    });

    html += `</div>`;
    container.innerHTML = html;
}

/**
 * 2. Helper: Signal Color Logic
 */
function getSignalClass(score) {
    if (score > 75) return 'sig-buy';
    if (score < 40) return 'sig-sell';
    return '';
}

/**
 * 3. Portfolio Summary Component (Mini)
 */
function renderPortfolioSummary(stocks) {
    const total = stocks.reduce((sum, s) => sum + (s.marketValue || 0), 0);
    const dayGain = stocks.reduce((sum, s) => sum + (s.plAbs || 0), 0);
    
    return `
        <div style="padding:16px; background:var(--s1); border-bottom:1px solid var(--b1);">
            <div style="color:var(--tx3); font-size:10px; font-weight:700; text-transform:uppercase;">Total Value</div>
            <div style="font-family:'Syne'; font-size:24px; font-weight:800;">₹${total.toLocaleString('en-IN')}</div>
        </div>
    `;
}
