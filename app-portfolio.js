/**
 * APP-PORTFOLIO.JS - FULL PRODUCTION MODULE (v2.0)
 * Step 1: Engine | Step 2: Mapping | Ready for Step 3: Expansion
 */

// 1. GLOBAL STATE
if (typeof window.pfRefreshing === 'undefined') window.pfRefreshing = false;
if (typeof window.fundLoaded === 'undefined') window.fundLoaded = false;

/**
 * LOADER ENGINE
 * Handles JSON fetching with cache-busting and error recovery
 */
async function loadFundamentals() {
    if (window.pfRefreshing) return;
    window.pfRefreshing = true;

    try {
        const ts = Date.now();
        // Simultaneous fetch of both required files
        const [sRes, fRes] = await Promise.all([
            fetch(`./symbols.json?v=${ts}`),
            fetch(`./fundamentals.json?v=${ts}`)
        ]);

        if (!sRes.ok || !fRes.ok) throw new Error("File fetch failed");

        const sData = await sRes.json();
        const fData = await fRes.json();

        // Map Master List (from symbols.json)
        window.S = window.S || {};
        window.S.portfolio = sData.map(item => ({
            sym: item.sym || '?',
            isin: item.isin || '',
            sector: item.sector || 'N/A'
        }));

        // Map Fundamental Data (from fundamentals.json)
        window.FUND = fData.stocks || fData;

        // Build ISIN Bridge
        window.ISIN_MAP = {};
        Object.keys(window.FUND).forEach(key => {
            const stock = window.FUND[key];
            if (stock && stock.isin) window.ISIN_MAP[stock.isin] = key;
        });

        window.fundLoaded = true;
        console.log("✅ Engine Ready: Data mapped for " + window.S.portfolio.length + " symbols.");
        return true;
    } catch (e) {
        console.error("❌ Engine Error:", e);
        // Safety: set loaded to true so the UI can at least show the Symbol list if fetch fails
        window.fundLoaded = true; 
        return false;
    } finally {
        window.pfRefreshing = false;
    }
}

/**
 * RENDER ENGINE
 * Handles the visual output and Step 2 Data Mapping
 */
async function renderPortfolio(container) {
    if (!container) return;

    // Clear system-level overlays
    const overlay = document.querySelector('.loading, #sync-overlay');
    if (overlay) overlay.style.display = 'none';

    // Trigger loader if not ready
    if (!window.fundLoaded) {
        container.innerHTML = `<div style="padding:40px;color:#58a6ff;font-family:monospace;">> BOOTING ENGINE...</div>`;
        await loadFundamentals();
    }

    // Safety check for global data existence
    if (!window.S || !window.S.portfolio) {
        container.innerHTML = `<div style="padding:40px;color:#f85149;">❌ DATA_NOT_FOUND</div>`;
        return;
    }

    // Diagnostic Hit Counter
    let dataHits = 0;
    window.S.portfolio.forEach(h => {
        if (window.FUND[h.sym] || (h.isin && window.FUND[window.ISIN_MAP[h.isin]])) dataHits++;
    });

    // Start UI Build
    let html = `<div style="padding:10px; background:#02040a; min-height:100vh; color:#fff; font-family:sans-serif;">`;
    
    // Status Header
    html += `<div style="margin-bottom:15px; padding:10px; background:#0d1117; border:1px solid #1e3350; border-radius:4px; font-size:11px; font-family:monospace;">
                <span style="color:#3fb950;">● ENGINE: READY</span> | 
                <span style="color:#58a6ff;">STOCKS: ${window.S.portfolio.length}</span> | 
                <span style="color:#d29922;">DATA HITS: ${dataHits}</span>
             </div>`;

    // Responsive Table Wrapper
    html += `<div style="overflow-x:auto; border:1px solid #1e3350; border-radius:8px;">`;
    html += `<table style="width:100%; border-collapse:collapse; white-space:nowrap; font-size:12px;">`;
    
    // THE HEADER (Restored Missing Elements)
    html += `<tr style="background:#0d1117; border-bottom:2px solid #1e3350; color:#8b949e; text-transform:uppercase; font-size:10px;">
                <th style="padding:12px; text-align:left; position:sticky; left:0; background:#0d1117; z-index:2;">Symbol</th>
                <th style="padding:12px; text-align:left;">Sector</th>
                <th style="padding:12px; text-align:center;">ROE %</th>
                <th style="padding:12px; text-align:center;">OPM %</th>
                <th style="padding:12px; text-align:center;">P/E</th>
                <th style="padding:12px; text-align:center;">MCAP (Cr)</th>
                <th style="padding:12px; text-align:center;">52W High</th>
                <th style="padding:12px; text-align:center;">52W Low</th>
                <th style="padding:12px; text-align:right;">Price (LTP)</th>
             </tr>`;

    // THE DATA ROWS
    window.S.portfolio.forEach((h, index) => {
        // Step 2 Mapping: Extract data based on symbol or ISIN match
        const f = window.FUND[h.sym] || (h.isin ? window.FUND[window.ISIN_MAP[h.isin]] : null) || {};
        
        // Field Extraction from fundamentals.json
        const roe = f.roe ?? '—';
        const opm = f.opm_pct ?? '—';
        const pe = f.pe ?? '—';
        const mcap = f.mcap ?? '—';
        const w52h = f.w52h ?? '—';
        const w52l = f.w52l ?? '—';
        const ltp = f.ltp || 0;
        
        // Dynamic Styles
        const rowBg = index % 2 === 0 ? 'transparent' : '#0d1117';
        const roeColor = (parseFloat(roe) > 15) ? '#3fb950' : (parseFloat(roe) < 0 ? '#f85149' : '#fff');

        html += `<tr style="background:${rowBg}; border-bottom:1px solid #1e3350;">
                    <td style="padding:12px; font-weight:bold; color:#58a6ff; position:sticky; left:0; background:${index % 2 === 0 ? '#02040a' : '#0d1117'}; z-index:1;">${h.sym}</td>
                    <td style="padding:12px; color:#8b949e;">${h.sector || f.sector || '—'}</td>
                    <td style="padding:12px; text-align:center; font-weight:bold; color:${roeColor}">${roe !== '—' ? roe + '%' : '—'}</td>
                    <td style="padding:12px; text-align:center; color:#d29922;">${opm !== '—' ? opm + '%' : '—'}</td>
                    <td style="padding:12px; text-align:center;">${pe !== '—' ? Number(pe).toFixed(1) : '—'}</td>
                    <td style="padding:12px; text-align:center;">${mcap !== '—' ? Math.round(mcap).toLocaleString('en-IN') : '—'}</td>
                    <td style="padding:12px; text-align:center; color:#8b949e;">${w52h !== '—' ? '₹' + Number(w52h).toLocaleString('en-IN') : '—'}</td>
                    <td style="padding:12px; text-align:center; color:#8b949e;">${w52l !== '—' ? '₹' + Number(w52l).toLocaleString('en-IN') : '—'}</td>
                    <td style="padding:12px; text-align:right; font-weight:bold; color:#fff;">₹${Number(ltp).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                </tr>`;
    });

    html += `</table></div></div>`;
    container.innerHTML = html;
}
