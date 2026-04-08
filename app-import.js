window.PENDING_DATA = null;

window.openImport = () => {
    const ov = document.getElementById('ov');
    const panel = document.getElementById('import-panel');
    const body = document.getElementById('import-panel-body');
    if (!ov || !panel || !body) return;

    body.innerHTML = `
        <div class="upload-zone" style="border:2px dashed #444; border-radius:20px; padding:40px; text-align:center;" onclick="document.getElementById('file-input').click()">
            <div style="font-size:30px;">📄</div>
            <b style="color:#fff; display:block; margin-top:10px;">Select Portfolio XLS</b>
            <input type="file" id="file-input" hidden onchange="handleFileSelect(event)">
        </div>
        <div id="file-status" style="margin:20px 0; text-align:center; color:var(--ac); font-family:var(--mono);"></div>
        <div id="import-actions" style="display:none; gap:10px;">
            <button class="import-btn" style="background:#222;" onclick="commitImport(true)">Replace All</button>
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

        lines.forEach(line => {
            // Split by comma and clean quotes
            const p = line.split(',').map(item => item.trim().replace(/^"|"$/g, ''));
            
            // The "Clueless" Fix: Back to exact column counting.
            // If the row has data and isn't a header, grab the 3 columns.
            if (p.length >= 5 && p[1] !== "" && !p[1].includes("Details")) {
                const qty = parseFloat(p[4].replace(/[^0-9.]/g, ''));
                const avg = parseFloat(p[5].replace(/[^0-9.]/g, ''));

                if (!isNaN(qty) && qty > 0) {
                    parsed.push({
                        sym: p[1], // Stock Name
                        qty: qty,  // Quantity
                        avg: avg   // Average Price
                    });
                }
            }
        });

        if (parsed.length > 0) {
            window.PENDING_DATA = parsed;
            document.getElementById('file-status').innerText = `✅ Detected ${parsed.length} items`;
            document.getElementById('import-actions').style.display = 'grid';
        } else {
            document.getElementById('file-status').innerText = `❌ No data found in file`;
        }
    };
    reader.readAsText(file);
};

window.commitImport = (replace) => {
    if (!window.PENDING_DATA) return;
    if (replace) S.portfolio = [...window.PENDING_DATA];
    else S.portfolio = [...S.portfolio, ...window.PENDING_DATA];
    
    localStorage.setItem('soya_portfolio', JSON.stringify(S.portfolio));
    if (window.render) render();
    closePanel();
    toast("Portfolio Updated");
};
