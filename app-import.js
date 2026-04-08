window.PENDING_DATA = null;

window.openImport = () => {
    const ov = document.getElementById('ov');
    const panel = document.getElementById('import-panel');
    const body = document.getElementById('import-panel-body');
    if (!ov || !panel || !body) return;

    body.innerHTML = `
        <div class="upload-zone" style="border:2px dashed #444; border-radius:20px; padding:40px; text-align:center; margin-bottom:20px; cursor:pointer;" onclick="document.getElementById('file-input').click()">
            <div style="font-size:40px; margin-bottom:10px;">📊</div>
            <div style="font-weight:700; color:#fff;">Select Portfolio File</div>
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

        lines.forEach((line) => {
            // Split by comma and clean up quotes/whitespace
            const parts = line.split(',').map(p => p.trim().replace(/^"|"$/g, ''));
            
            // 1. Identify a Stock Name row
            // We look for the first part that is not empty and not a header/total row
            const nameIdx = parts.findIndex(p => 
                p.length > 2 && 
                !p.includes("Details") && 
                !p.includes("Stock Name") && 
                !p.includes("TOTAL")
            );

            if (nameIdx !== -1) {
                const stockName = parts[nameIdx];
                
                // 2. Scan the rest of the row for the first two numeric values
                const numbers = parts.slice(nameIdx + 1)
                    .map(p => parseFloat(p.replace(/[^0-9.-]/g, '')))
                    .filter(n => !isNaN(n) && n > 0);

                // 3. Extract Quantity (1st number) and Avg Price (2nd number)
                if (numbers.length >= 2) {
                    parsed.push({
                        sym: stockName,
                        [span_3](start_span)qty: numbers[1], // Index 1 is typically Quantity in your CSV[span_3](end_span)
                        [span_4](start_span)avg: numbers[2]  // Index 2 is typically Average Price in your CSV[span_4](end_span)
                    });
                }
            }
        });

        if (parsed.length > 0) {
            window.PENDING_DATA = parsed;
            document.getElementById('file-status').innerHTML = `✅ Found ${parsed.length} Stocks`;
            document.getElementById('import-actions').style.display = 'grid';
        } else {
            document.getElementById('file-status').innerHTML = `❌ No data found.`;
        }
    };
    reader.readAsText(file);
};

window.commitImport = (replaceAll) => {
    if (!window.PENDING_DATA) return;

    if (replaceAll) {
        S.portfolio = [...window.PENDING_DATA];
    } else {
        window.PENDING_DATA.forEach(newItem => {
            const idx = S.portfolio.findIndex(p => p.sym === newItem.sym);
            if (idx > -1) {
                const oldQty = S.portfolio[idx].qty || 0;
                const newQty = oldQty + newItem.qty;
                if (newQty > 0) {
                    const totalCost = (oldQty * (S.portfolio[idx].avg || 0)) + (newItem.qty * newItem.avg);
                    S.portfolio[idx].avg = totalCost / newQty;
                }
                S.portfolio[idx].qty = newQty;
            } else {
                S.portfolio.push(newItem);
            }
        });
    }

    localStorage.setItem('soya_portfolio', JSON.stringify(S.portfolio));
    toast(replaceAll ? "Portfolio Replaced" : "Portfolio Appended");
    if (typeof render === 'function') render();
    closePanel();
};
