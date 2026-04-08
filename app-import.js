/**
 * Soya Intelligence Hub - Import Logic
 * Handles CDSL XLS parsing and Portfolio Merging
 */

// Global storage for data waiting to be committed
window.PENDING_DATA = null;

/**
 * Entry point: Called from index.html when Stock Upload is clicked
 */
window.openImport = () => {
    const ov = document.getElementById('ov');
    const panel = document.getElementById('import-panel');
    const body = document.getElementById('import-panel-body');

    if (!ov || !panel || !body) return;

    // Inject the UI if empty
    body.innerHTML = `
        <div class="upload-zone" style="border:2px dashed #333; border-radius:20px; padding:40px; text-align:center; margin-bottom:20px;" onclick="document.getElementById('file-input').click()">
            <div style="font-size:40px; margin-bottom:10px;">📁</div>
            <div style="font-weight:700; color:var(--tx);">Tap to select CDSL XLS file</div>
            <div style="font-size:10px; color:var(--tx3); margin-top:8px;">CDSL Easiest → Portfolio → Equity Summary Details → Download XLS</div>
            <input type="file" id="file-input" hidden onchange="handleFileSelect(event)" accept=".xls,.xlsx,.csv">
        </div>
        <div id="file-status" style="font-family:var(--mono); font-size:12px; margin-bottom:20px; color:var(--ac);"></div>
        
        <div id="import-actions" style="display:none; gap:10px;">
            <button class="import-btn" style="background:#222; color:#fff;" onclick="commitImport(true)">✓ Import (Replace All)</button>
            <button class="import-btn" onclick="commitImport(false)">+ Append to Existing</button>
        </div>
    `;

    ov.classList.add('on');
    panel.classList.add('on');
    log("Import Panel Opened");
};

/**
 * Parser: Handles the file reading
 */
window.handleFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const status = document.getElementById('file-status');
    status.innerHTML = `⏳ Reading ${file.name}...`;
    log(`Reading: ${file.name}`);

    const reader = new FileReader();
    reader.onload = (event) => {
        const raw = event.target.result;
        
        // CDSL XLS files are often Tab-Separated or CSV
        // We split by newline and look for rows that look like stock data
        const lines = raw.split(/\r?\n/);
        const parsed = [];

        lines.forEach(line => {
            // Split by Tab or Comma
            const cols = line.split(/\t|,/);
            
            // Heuristic: CDSL rows usually have an ISIN (12 chars starting with IN)
            // and a Quantity/Price. We look for columns that match that pattern.
            const isin = cols.find(c => c.trim().length === 12 && c.trim().startsWith('IN'));
            
            if (isin) {
                // Usually: ISIN is col 0, Symbol col 1, Qty col 2, Price col 3
                // We'll be flexible: find the numbers in the row
                const numbers = cols.map(c => parseFloat(c.replace(/,/g, ''))).filter(n => !isNaN(n) && n > 0);
                
                if (numbers.length >= 2) {
                    parsed.push({
                        isin: isin.trim(),
                        qty: numbers[0], // First positive number is usually Qty
                        price: numbers[1], // Second is usually Price/Value
                        sym: window.ISIN_MAP ? window.ISIN_MAP[isin.trim()] : "Unknown"
                    });
                }
            }
        });

        if (parsed.length > 0) {
            window.PENDING_DATA = parsed;
            status.innerHTML = `✅ Found ${parsed.length} stocks in file.`;
            document.getElementById('import-actions').style.display = 'grid';
            document.getElementById('import-actions').style.gridTemplateColumns = '1fr 1fr';
            log(`Success: Parsed ${parsed.length} entries`);
        } else {
            status.innerHTML = `❌ No valid stock data found in file.`;
            log("Error: Parser found 0 rows");
        }
    };
    reader.readAsText(file);
};

/**
 * Committer: Writes data to Portfolio
 */
window.commitImport = (replaceAll) => {
    if (!window.PENDING_DATA) {
        toast("Nothing to import - paste data first");
        return;
    }

    if (replaceAll) {
        S.portfolio = [...window.PENDING_DATA];
    } else {
        // Append logic
        window.PENDING_DATA.forEach(newItem => {
            const idx = S.portfolio.findIndex(p => p.isin === newItem.isin);
            if (idx > -1) {
                // Simple update: Add qty, keep new price
                S.portfolio[idx].qty += newItem.qty;
                S.portfolio[idx].avg = newItem.price; 
            } else {
                S.portfolio.push(newItem);
            }
        });
    }

    // Save to LocalStorage
    localStorage.setItem('soya_portfolio', JSON.stringify(S.portfolio));
    
    // UI Feedback
    toast(replaceAll ? "Portfolio Reset!" : "Portfolio Appended!");
    log(`Committed ${window.PENDING_DATA.length} stocks.`);
    
    if (typeof render === 'function') render();
    closePanel();
};
