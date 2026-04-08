window.PENDING_DATA = null;

window.openImport = () => {
    const ov = document.getElementById('ov');
    const panel = document.getElementById('import-panel');
    const body = document.getElementById('import-panel-body');
    if (!ov || !panel || !body) return;

    body.innerHTML = `
        <div class="upload-zone" style="border:2px dashed #333; border-radius:20px; padding:40px; text-align:center; margin-bottom:20px;" onclick="document.getElementById('file-input').click()">
            <div style="font-size:40px; margin-bottom:10px;">📁</div>
            <div style="font-weight:700;">Tap to select CDSL XLS file</div>
            <input type="file" id="file-input" hidden onchange="handleFileSelect(event)" accept=".xls,.xlsx,.csv">
        </div>
        <div id="file-status" style="font-family:var(--mono); font-size:12px; margin-bottom:20px; color:var(--ac);"></div>
        <div id="import-actions" style="display:none; gap:10px;">
            <button class="import-btn" style="background:#222; color:#fff;" onclick="commitImport(true)">Import (Replace All)</button>
            <button class="import-btn" onclick="commitImport(false)">Append to Existing</button>
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

        // Skip the first 5 rows (headers/metadata)
        for (let i = 5; i < lines.length; i++) {
            const cols = lines[i].split(',');
            if (cols.length < 5) continue;

            const isin = cols[1]?.trim(); // ISIN is Column 1
            if (isin && isin.startsWith('IN')) {
                parsed.push({
                    sym: cols[0]?.trim(),        // Stock Name
                    isin: isin,
                    qty: parseFloat(cols[3]) || 0, // Quantity
                    avg: parseFloat(cols[4]) || 0, // Average Cost
                    sector: cols[2]?.trim() || "Others" // Sector
                });
            }
        }

        if (parsed.length > 0) {
            window.PENDING_DATA = parsed;
            document.getElementById('file-status').innerHTML = `✅ Decoded ${parsed.length} stocks.`;
            document.getElementById('import-actions').style.display = 'grid';
            document.getElementById('import-actions').style.gridTemplateColumns = '1fr 1fr';
        } else {
            document.getElementById('file-status').innerHTML = `❌ Could not decode data.`;
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
                // Update existing: Weighted Average Price
                const oldQty = S.portfolio[idx].qty;
                const newQty = oldQty + newItem.qty;
                S.portfolio[idx].avg = ((oldQty * S.portfolio[idx].avg) + (newItem.qty * newItem.avg)) / newQty;
                S.portfolio[idx].qty = newQty;
            } else {
                S.portfolio.push(newItem);
            }
        });
    }

    localStorage.setItem('soya_portfolio', JSON.stringify(S.portfolio));
    toast("Portfolio Updated!");
    if (typeof render === 'function') render();
    closePanel();
};
