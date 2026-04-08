/**
 * Soya Intelligence Hub - Visual Scan Parser
 * Optimized for CDSL/Broker Portfolio Exports
 */

window.PENDING_DATA = null;

window.openImport = () => {
    const ov = document.getElementById('ov');
    const panel = document.getElementById('import-panel');
    const body = document.getElementById('import-panel-body');
    if (!ov || !panel || !body) return;

    body.innerHTML = `
        <div class="upload-zone" style="border:2px dashed #444; border-radius:20px; padding:40px; text-align:center; margin-bottom:20px; cursor:pointer;" onclick="document.getElementById('file-input').click()">
            <div style="font-size:40px; opacity:0.8; margin-bottom:10px;">📊</div>
            <div style="font-weight:700; color:#fff;">Select Portfolio File</div>
            <div style="font-size:11px; color:var(--tx3); margin-top:8px;">Accepts CSV/XLS text exports</div>
            <input type="file" id="file-input" hidden onchange="handleFileSelect(event)">
        </div>
        <div id="file-status" style="font-family:var(--mono); font-size:12px; margin-bottom:20px; color:var(--ac); text-align:center;"></div>
        <div id="import-actions" style="display:none; gap:10px; grid-template-columns: 1fr 1fr;">
            <button class="import-btn" style="background:#222; color:#fff;" onclick="commitImport(true)">Replace All</button>
            <button class="import-btn" onclick="commitImport(false)">Append Data</button>
        </div>
    `;
    ov.classList.add('on');
    panel.classList.add('on');
};

window.handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
        const raw = event.target.result;
        const lines = raw.split(/\r?\n/);
        const parsed = [];

        log(`Visual Scan: Processing ${lines.length} lines...`);

        lines.forEach((line) => {
            // Split by common delimiters and clean metadata artifacts
            const cells = line.split(/,|\t/).map(c => c.trim().replace(/^"|"$/g, ''));
            
            // 1. Identify valid data rows by filtering out headers/footers
            // We look for cells that look like an ISIN or contain valid stock names
            const isinIdx = cells.findIndex(c => /^IN[A-Z0-9]{10}$/.test(c));
            
            if (isinIdx !== -1) {
                // 2. Extract relative to the anchor (ISIN)
                [span_1](start_span)// In your file, Name is immediately before ISIN[span_1](end_span)
                const name = cells[isinIdx - 1]; 
                
                [span_2](start_span)// 3. Scan for numeric data points after the ISIN[span_2](end_span)
                // We extract all numeric-looking values in the row
                const rowNumbers = cells.slice(isinIdx + 1)
                    .map(c => parseFloat(c.replace(/[^0-9.-]/g, '')))
                    .filter(n => !isNaN(n));

                // Mapping based on Equity_Summary structure:
                [span_3](start_span)// After ISIN/Sector, index 1 is Quantity, index 2 is Avg Price[span_3](end_span)
                if (rowNumbers.length >= 2) {
                    parsed.push({
                        sym: name || "Unknown",
                        isin: cells[isinIdx],
                        qty: rowNumbers[1], 
                        avg: rowNumbers[2] 
                    });
                }
            }
        });

        if (parsed.length > 0) {
            window.PENDING_DATA = parsed;
            document.getElementById('file-status').innerHTML = `✅ Detected ${parsed.length} Holdings`;
            document.getElementById('import-actions').style.display = 'grid';
            log(`Scan Complete: Captured ${parsed.length} items.`);
        } else {
            document.getElementById('file-status').innerHTML = `❌ No valid data detected.`;
            log("Error: Visual anchor (ISIN) not found in any row.");
        }
    };
    reader.readAsText(file);
};

window.commitImport = (replaceAll) => {
    if (!window.PENDING_DATA) return;

    if (replaceAll) {
        S.portfolio = [...window.PENDING_DATA];
    } else {
        // Professional Merge: Weighted Average Costing
        window.PENDING_DATA.forEach(newItem => {
            const idx = S.portfolio.findIndex(p => p.isin === newItem.isin);
            if (idx > -1) {
                const oldQty = S.portfolio[idx].qty || 0;
                const newQty = oldQty + newItem.qty;
                if (newQty > 0) {
                    const currentCost = oldQty * (S.portfolio[idx].avg || 0);
                    const incomingCost = newItem.qty * newItem.avg;
                    S.portfolio[idx].avg = (currentCost + incomingCost) / newQty;
                }
                S.portfolio[idx].qty = newQty;
            } else {
                S.portfolio.push(newItem);
            }
        });
    }

    localStorage.setItem('soya_portfolio', JSON.stringify(S.portfolio));
    toast(replaceAll ? "Portfolio Overwritten" : "Data Appended");
    if (typeof render === 'function') render();
    closePanel();
};
