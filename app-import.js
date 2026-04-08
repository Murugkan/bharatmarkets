window.PENDING_DATA = null;

window.openImport = () => {
    const ov = document.getElementById('ov');
    const panel = document.getElementById('import-panel');
    const body = document.getElementById('import-panel-body');
    if (!ov || !panel || !body) return;

    body.innerHTML = `
        <div class="upload-zone" style="border:2px dashed #333; border-radius:20px; padding:40px; text-align:center; margin-bottom:20px;" onclick="document.getElementById('file-input').click()">
            <div style="font-size:40px; margin-bottom:10px;">📁</div>
            <div style="font-weight:700; color:#fff;">Select CDSL XLS/CSV</div>
            <input type="file" id="file-input" hidden onchange="handleFileSelect(event)" accept=".xls,.xlsx,.csv">
        </div>
        <div id="file-status" style="font-family:var(--mono); font-size:12px; margin-bottom:20px; color:var(--ac);"></div>
        <div id="import-actions" style="display:none; gap:10px; grid-template-columns: 1fr 1fr;">
            <button class="import-btn" style="background:#222; color:#fff;" onclick="commitImport(true)">Replace All</button>
            <button class="import-btn" onclick="commitImport(false)">Append</button>
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

        log(`Processing ${lines.length} lines...`);

        lines.forEach((line) => {
            // Split by comma and clean whitespace
            const cols = line.split(',').map(c => c.trim());
            
            // FLEXIBLE SEARCH: Find any column that looks like an ISIN (Starts with IN, 12 chars)
            const isinIdx = cols.findIndex(c => /^IN[A-Z0-9]{10}$/.test(c));
            
            if (isinIdx !== -1) {
                // Mapping based on your Equity_Summary_Details structure:
                // Name is always the column immediately before ISIN
                // Qty is 2 columns after ISIN, Price is 3 columns after ISIN
                const name = cols[isinIdx - 1];
                const qty = parseFloat(cols[isinIdx + 2]);
                const price = parseFloat(cols[isinIdx + 3]);
                const sector = cols[isinIdx + 1] || "Others";

                if (!isNaN(qty) && qty > 0) {
                    parsed.push({
                        sym: name || "Unknown",
                        isin: cols[isinIdx],
                        sector: sector,
                        qty: qty,
                        avg: price || 0
                    });
                }
            }
        });

        if (parsed.length > 0) {
            window.PENDING_DATA = parsed;
            document.getElementById('file-status').innerHTML = `✅ Found ${parsed.length} stocks`;
            document.getElementById('import-actions').style.display = 'grid';
            log(`Success: Decoded ${parsed.length} stocks.`);
        } else {
            document.getElementById('file-status').innerHTML = `❌ No valid rows found.`;
            log("Parsing failed: No ISIN pattern detected in columns.");
        }
    };
    reader.readAsText(file);
};

window.commitImport = (replaceAll) => {
    if (!window.PENDING_DATA) return toast("No data to commit");

    if (replaceAll) {
        S.portfolio = [...window.PENDING_DATA];
    } else {
        window.PENDING_DATA.forEach(newItem => {
            const idx = S.portfolio.findIndex(p => p.isin === newItem.isin);
            if (idx > -1) {
                // Update existing: Weighted Average Calculation
                const oldQty = S.portfolio[idx].qty;
                const newQty = oldQty + newItem.qty;
                if (newQty > 0) {
                    S.portfolio[idx].avg = ((oldQty * (S.portfolio[idx].avg || 0)) + (newItem.qty * newItem.avg)) / newQty;
                }
                S.portfolio[idx].qty = newQty;
            } else {
                S.portfolio.push(newItem);
            }
        });
    }

    localStorage.setItem('soya_portfolio', JSON.stringify(S.portfolio));
    toast(replaceAll ? "Portfolio Reset" : "Portfolio Appended");
    if (typeof render === 'function') render();
    closePanel();
};
