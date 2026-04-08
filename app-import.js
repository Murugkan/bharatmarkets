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

        lines.forEach((line, index) => {
            // Clean the line and split by comma
            const cols = line.split(',').map(c => c.trim());
            
            // Look for the ISIN pattern (IN...) in any column to identify data rows
            const isinIdx = cols.findIndex(c => c.startsWith('IN') && c.length === 12);
            
            if (isinIdx !== -1) {
                // Based on your file: Name is Col 0, ISIN is Col 1, Sector is Col 2, Qty is Col 3, Price is Col 4
                const qty = parseFloat(cols[isinIdx + 2]);
                const price = parseFloat(cols[isinIdx + 3]);

                if (!isNaN(qty) && qty > 0) {
                    parsed.push({
                        sym: cols[isinIdx - 1] || "Unknown",
                        isin: cols[isinIdx],
                        sector: cols[isinIdx + 1] || "Others",
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
            log(`Successfully parsed ${parsed.length} rows.`);
        } else {
            document.getElementById('file-status').innerHTML = `❌ No valid data found. Check console.`;
            log("Parsing failed: No rows matched the ISIN pattern.");
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
                const oldQty = S.portfolio[idx].qty;
                const newQty = oldQty + newItem.qty;
                // Avoid division by zero
                if (newQty > 0) {
                    S.portfolio[idx].avg = ((oldQty * S.portfolio[idx].avg) + (newItem.qty * newItem.avg)) / newQty;
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
