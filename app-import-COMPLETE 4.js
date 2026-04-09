/**
 * app-import.js - 7-Step Portfolio Import Wizard
 * Step 1: Upload (data.html) → Steps 2-7: Modal Wizard
 * Final: Auto-sync to GitHub unified-symbols.json using PAT
 */

var importState = {
    step: 2,
    stocks: [],
    aiResponse: null
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 1: Upload CSV/XLS
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function handleFileImport(file) {
    if (!file) return;
    console.log('FILE SELECTED:', file.name);
    var ext = file.name.split('.').pop().toLowerCase();
    var status = document.getElementById('step1-status');
    console.log('FILE TYPE:', ext);
    
    if (ext === 'csv' || ext === 'txt' || ext === 'tsv') {
        console.log('CSV/TSV PARSING STARTED');
        var reader = new FileReader();
        reader.onload = function(e) {
            try {
                console.log('READING FILE...');
                parseCSV(e.target.result);
                console.log('STOCKS LOADED:', importState.stocks.length);
                status.innerHTML = '✅ Loaded: ' + importState.stocks.length + ' stocks';
                renderStep1Preview();
                console.log('BUTTON SHOWN');
            } catch(err) {
                console.error('PARSE ERROR:', err.message);
                status.innerHTML = '❌ ' + err.message;
            }
        };
        reader.readAsText(file);
    } else if (ext === 'xls' || ext === 'xlsx') {
        console.log('XLS/XLSX PARSING STARTED');
        if (!window.XLSX) {
            console.error('XLSX NOT LOADED');
            status.innerHTML = '❌ Excel library not loaded. Use CSV.';
            return;
        }
        console.log('XLSX LIBRARY AVAILABLE');
        var reader = new FileReader();
        reader.onload = function(e) {
            try {
                console.log('READING XLS FILE...');
                var wb = XLSX.read(new Uint8Array(e.target.result), {type: 'array'});
                var rows = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], {header: 1});
                console.log('ROWS FROM XLS:', rows.length);
                parseRows(rows);
                console.log('STOCKS LOADED:', importState.stocks.length);
                status.innerHTML = '✅ Loaded: ' + importState.stocks.length + ' stocks';
                renderStep1Preview();
                console.log('BUTTON SHOWN');
            } catch(err) {
                console.error('PARSE ERROR:', err.message);
                status.innerHTML = '❌ ' + err.message;
            }
        };
        reader.readAsArrayBuffer(file);
    } else {
        console.error('UNSUPPORTED FILE TYPE:', ext);
        status.innerHTML = '❌ Use CSV or Excel files';
    }
}

function parseCSV(text) {
    var lines = text.split('\n');
    var cleaned = [];
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (line.length > 0) cleaned.push(line);
    }
    
    if (cleaned.length < 2) throw new Error('File is empty');
    
    var delimiter = cleaned[0].indexOf('\t') >= 0 ? '\t' : ',';
    var headerLine = cleaned[0].split(delimiter);
    var headers = [];
    for (var i = 0; i < headerLine.length; i++) {
        headers.push(headerLine[i].toLowerCase().trim());
    }
    
    var nameIdx = -1, qtyIdx = -1, avgIdx = -1;
    for (var i = 0; i < headers.length; i++) {
        if (headers[i].indexOf('name') >= 0 || headers[i].indexOf('stock') >= 0) nameIdx = i;
        if (headers[i].indexOf('qty') >= 0 || headers[i].indexOf('quantity') >= 0) qtyIdx = i;
        if (headers[i].indexOf('avg') >= 0 || headers[i].indexOf('price') >= 0) avgIdx = i;
    }
    
    if (nameIdx === -1) nameIdx = 0;
    if (qtyIdx === -1) qtyIdx = 1;
    if (avgIdx === -1) avgIdx = 2;
    
    var stocks = [];
    for (var i = 1; i < cleaned.length; i++) {
        var parts = cleaned[i].split(delimiter);
        for (var j = 0; j < parts.length; j++) {
            parts[j] = parts[j].trim().replace(/['"₹₨]/g, '');
        }
        
        if (!parts[nameIdx]) continue;
        if (parts[nameIdx].toLowerCase().indexOf('name') >= 0) continue;
        
        var qty = parseFloat(parts[qtyIdx]) || 0;
        var avg = parseFloat(parts[avgIdx]) || 0;
        
        if (parts[nameIdx] && (qty || avg)) {
            stocks.push({
                name: parts[nameIdx],
                qty: qty,
                avg: avg,
                isin: '',
                sector: '',
                industry: '',
                type: 'PORTFOLIO'
            });
        }
    }
    
    if (stocks.length === 0) throw new Error('No valid stocks found');
    importState.stocks = stocks;
}

function parseRows(rows) {
    if (rows.length < 2) throw new Error('No data in file');
    
    var headerRow = rows[0];
    var headers = [];
    for (var i = 0; i < headerRow.length; i++) {
        headers.push(String(headerRow[i]).toLowerCase().trim());
    }
    
    var nameIdx = -1, qtyIdx = -1, avgIdx = -1;
    for (var i = 0; i < headers.length; i++) {
        if (headers[i].indexOf('name') >= 0 || headers[i].indexOf('stock') >= 0) nameIdx = i;
        if (headers[i].indexOf('qty') >= 0 || headers[i].indexOf('quantity') >= 0) qtyIdx = i;
        if (headers[i].indexOf('avg') >= 0 || headers[i].indexOf('price') >= 0 || headers[i].indexOf('cost') >= 0) avgIdx = i;
    }
    
    if (nameIdx === -1) nameIdx = 0;
    if (qtyIdx === -1) qtyIdx = 1;
    if (avgIdx === -1) avgIdx = 2;
    
    var stocks = [];
    for (var i = 1; i < rows.length; i++) {
        var r = rows[i];
        if (!r || !r[nameIdx]) continue;
        
        var name = String(r[nameIdx]).trim();
        if (!name || name.length === 0) continue;
        
        var qtyStr = String(r[qtyIdx] || '').replace(/[₹₨$€,]/g, '').trim();
        var avgStr = String(r[avgIdx] || '').replace(/[₹₨$€,]/g, '').trim();
        
        var qty = parseFloat(qtyStr) || 0;
        var avg = parseFloat(avgStr) || 0;
        
        if (name && (qty || avg)) {
            stocks.push({
                name: name,
                qty: qty,
                avg: avg,
                isin: '',
                sector: '',
                industry: '',
                type: 'PORTFOLIO'
            });
        }
    }
    
    if (stocks.length === 0) throw new Error('No valid stocks found');
    importState.stocks = stocks;
}

function renderStep1Preview() {
    if (importState.stocks.length === 0) return;
    var html = '<table style="width:100%;font-size:10px;border-collapse:collapse;margin:10px 0;"><tr style="background:#111;"><th style="padding:6px;text-align:left;">Stock</th><th style="padding:6px;text-align:right;">QTY</th><th style="padding:6px;text-align:right;">AVG</th></tr>';
    
    for (var i = 0; i < importState.stocks.length; i++) {
        var s = importState.stocks[i];
        html += '<tr style="border-bottom:1px solid #111;"><td style="padding:6px;">' + s.name.substring(0, 25) + '</td><td style="padding:6px;text-align:right;">' + (s.qty || '-') + '</td><td style="padding:6px;text-align:right;">₹' + (s.avg ? s.avg.toFixed(2) : '-') + '</td></tr>';
    }
    
    html += '</table>';
    document.getElementById('step1-preview').innerHTML = html;
    document.getElementById('wizard-start').style.display = 'block';
}

function startWizardFromStep2() {
    if (importState.stocks.length === 0) {
        alert('Please upload a file first');
        return;
    }
    openWizardModal();
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// WIZARD MODAL (Steps 2-7)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function openWizardModal() {
    importState.step = 2;
    document.body.classList.add('modal-open');
    showWizardUI();
}

function showWizardUI() {
    var progress = (importState.step / 7) * 100;
    var stepTitles = ['', '', 'Manual Entries', 'AI Prompt', 'Paste Response', 'Edit & Validate', 'Save to DB', 'GitHub Sync'];
    
    var html = '<div style="padding:20px;background:#0a0a0a;border-radius:12px;max-width:900px;">' +
        '<div style="margin-bottom:10px;font-size:12px;color:#555;">Step ' + importState.step + ' of 7: ' + stepTitles[importState.step] + '</div>' +
        '<div style="display:flex;gap:8px;margin-bottom:15px;justify-content:flex-end;flex-wrap:wrap;">' +
        '<button onclick="closeWizard()" style="padding:8px 16px;background:#333;border:none;color:#fff;border-radius:6px;cursor:pointer;font-size:12px;">Cancel</button>';
    
    if (importState.step > 2) {
        html += '<button onclick="prevStep()" style="padding:8px 16px;background:#444;border:none;color:#fff;border-radius:6px;cursor:pointer;font-size:12px;">← Back</button>';
    }
    
    if (importState.step < 7) {
        html += '<button onclick="nextStep()" style="padding:8px 16px;background:#00ff88;border:none;color:#000;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">Next →</button>';
    } else {
        html += '<button onclick="closeWizard()" style="padding:8px 16px;background:#00ff88;border:none;color:#000;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">Done ✓</button>';
    }
    
    html += '</div>' +
        '<div style="width:100%;height:4px;background:#111;border-radius:2px;margin-bottom:20px;overflow:hidden;"><div style="width:' + progress + '%;height:100%;background:#00ff88;transition:width 0.3s;"></div></div>';
    
    switch(importState.step) {
        case 2: html += renderStep2(); break;
        case 3: html += renderStep3(); break;
        case 4: html += renderStep4(); break;
        case 5: html += renderStep5(); break;
        case 6: html += renderStep6(); break;
        case 7: html += renderStep7(); break;
    }
    
    html += '</div>';
    
    var modal = document.getElementById('wizard-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'wizard-modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.95);z-index:9000;display:flex;align-items:center;justify-content:center;overflow-y:auto;';
        document.body.appendChild(modal);
    }
    modal.innerHTML = '<div style="background:#000;border:1px solid #222;border-radius:12px;padding:30px;max-height:90vh;overflow-y:auto;width:95%;max-width:900px;margin:20px auto;">' + html + '</div>';
}

function renderStep2() {
    return '<div><h3 style="color:#00ff88;margin-bottom:10px;">Add Manual Entries</h3>' +
        '<textarea id="manual-ta" style="width:100%;height:150px;padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;font-size:11px;border-radius:6px;resize:vertical;" placeholder="SYMBOL QTY AVG (one per line)"></textarea>' +
        '<div style="margin:10px 0;"><button onclick="addManualEntries()" style="width:100%;padding:10px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">Add Entries</button></div>' +
        '</div>';
}

function addManualEntries() {
    var ta = document.getElementById('manual-ta');
    var lines = ta.value.split('\n');
    
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (line.length === 0) continue;
        
        var parts = line.split(/[\s,]+/);
        var filtered = [];
        for (var j = 0; j < parts.length; j++) {
            if (parts[j].length > 0) filtered.push(parts[j]);
        }
        
        if (filtered.length >= 2) {
            importState.stocks.push({
                name: filtered[0].toUpperCase(),
                qty: parseFloat(filtered[1]) || 0,
                avg: parseFloat(filtered[2]) || 0,
                isin: '',
                sector: '',
                industry: '',
                type: 'PORTFOLIO'
            });
        }
    }
    
    nextStep();
}

function renderStep3() {
    return '<div><h3 style="color:#00ff88;margin-bottom:10px;">Generate AI Prompt</h3>' +
        '<div style="background:#050505;border:1px solid #222;padding:12px;border-radius:6px;font-size:11px;color:#888;margin-bottom:15px;max-height:300px;overflow-y:auto;font-family:monospace;">' +
        '<b style="color:#00ff88;">Copy this prompt and paste into Claude:</b><br><br>' +
        'I have a portfolio with ' + importState.stocks.length + ' stocks. Please enrich with ISIN, Sector, Industry in JSON format. Return only valid JSON.' +
        '</div>' +
        '<p style="font-size:11px;color:#666;">After getting Claude response, come back to Step 4.</p>' +
        '</div>';
}

function renderStep4() {
    return '<div><h3 style="color:#00ff88;margin-bottom:10px;">Paste AI Response</h3>' +
        '<textarea id="ai-response-ta" style="width:100%;height:180px;padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;font-size:10px;border-radius:6px;resize:vertical;" placeholder="Paste JSON from Claude here..."></textarea>' +
        '<div id="step4-status" style="margin:10px 0;font-size:11px;color:#666;"></div>' +
        '<div style="margin:10px 0;"><button onclick="parseAIResponse()" style="width:100%;padding:10px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">Parse & Continue</button></div>' +
        '</div>';
}

function parseAIResponse() {
    var ta = document.getElementById('ai-response-ta');
    var text = ta.value.trim();
    var status = document.getElementById('step4-status');
    
    if (!text) {
        status.innerHTML = '⚠️ Empty response. Skipping AI enrichment.';
        setTimeout(function() { nextStep(); }, 1500);
        return;
    }
    
    try {
        var data = JSON.parse(text);
        if (!Array.isArray(data)) data = [data];
        
        for (var i = 0; i < data.length; i++) {
            var item = data[i];
            for (var j = 0; j < importState.stocks.length; j++) {
                var stock = importState.stocks[j];
                if (stock.name.toUpperCase() === item.name.toUpperCase()) {
                    stock.isin = item.isin || '';
                    stock.sector = item.sector || '';
                    stock.industry = item.industry || '';
                }
            }
        }
        
        status.innerHTML = '✅ Enriched ' + data.length + ' stocks';
        setTimeout(function() { nextStep(); }, 1500);
    } catch(e) {
        status.innerHTML = '❌ Invalid JSON: ' + e.message;
    }
}

function renderStep5() {
    var html = '<div><h3 style="color:#00ff88;margin-bottom:10px;">Edit & Validate</h3>' +
        '<div style="max-height:400px;overflow-y:auto;">';
    
    for (var i = 0; i < importState.stocks.length; i++) {
        var stock = importState.stocks[i];
        html += '<div style="padding:10px;background:#050505;margin:8px 0;border:1px solid #222;border-radius:6px;">' +
            '<input type="text" value="' + stock.name.replace(/"/g, '&quot;') + '" style="width:100%;padding:6px;background:#000;color:#fff;border:1px solid #333;border-radius:3px;margin-bottom:6px;font-size:11px;" onchange="importState.stocks[' + i + '].name=this.value">' +
            '<div style="display:flex;gap:6px;font-size:11px;">' +
            '<input type="number" value="' + stock.qty + '" placeholder="QTY" style="flex:1;padding:6px;background:#000;color:#fff;border:1px solid #333;border-radius:3px;" onchange="importState.stocks[' + i + '].qty=parseFloat(this.value)">' +
            '<input type="number" value="' + stock.avg + '" placeholder="AVG" step="0.01" style="flex:1;padding:6px;background:#000;color:#fff;border:1px solid #333;border-radius:3px;" onchange="importState.stocks[' + i + '].avg=parseFloat(this.value)">' +
            '<input type="text" value="' + (stock.isin || '').replace(/"/g, '&quot;') + '" placeholder="ISIN" style="flex:1;padding:6px;background:#000;color:#fff;border:1px solid #333;border-radius:3px;" onchange="importState.stocks[' + i + '].isin=this.value">' +
            '</div>' +
            '<div style="display:flex;gap:6px;margin-top:6px;font-size:10px;">' +
            '<select style="flex:1;padding:6px;background:#000;color:#fff;border:1px solid #333;border-radius:3px;" onchange="importState.stocks[' + i + '].type=this.value"><option value="PORTFOLIO">PORTFOLIO</option><option value="WATCHLIST">WATCHLIST</option></select>' +
            '<button onclick="deleteStock(' + i + ')" style="padding:6px 10px;background:#ff6b85;color:#fff;border:none;border-radius:3px;cursor:pointer;font-size:10px;">Delete</button>' +
            '</div>' +
            '</div>';
    }
    
    html += '</div></div>';
    return html;
}

function deleteStock(idx) {
    importState.stocks.splice(idx, 1);
    showWizardUI();
}

function renderStep6() {
    return '<div><h3 style="color:#00ff88;margin-bottom:10px;">Save to Database</h3>' +
        '<p style="font-size:11px;color:#888;margin-bottom:15px;">Ready to save ' + importState.stocks.length + ' stocks to browser database</p>' +
        '<button onclick="saveToIndexedDB()" style="width:100%;padding:12px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">💾 Save Now</button>' +
        '<div id="step6-status" style="margin:15px 0;font-size:11px;"></div>' +
        '</div>';
}

function saveToIndexedDB() {
    var status = document.getElementById('step6-status');
    status.innerHTML = '⏳ Saving...';
    
    openDB('BharatEngineDB', 1, function(db) {
        var tx = db.transaction('UnifiedStocks', 'readwrite');
        var store = tx.objectStore('UnifiedStocks');
        
        for (var i = 0; i < importState.stocks.length; i++) {
            var stock = importState.stocks[i];
            store.put({
                sym: stock.name.toUpperCase(),
                name: stock.name,
                isin: stock.isin,
                qty: stock.qty,
                avg: stock.avg,
                sector: stock.sector,
                industry: stock.industry,
                type: stock.type,
                source: 'import'
            });
        }
        
        tx.oncomplete = function() {
            status.innerHTML = '✅ Saved ' + importState.stocks.length + ' stocks';
            setTimeout(function() { nextStep(); }, 1500);
        };
        
        tx.onerror = function() {
            status.innerHTML = '❌ Error saving to database';
        };
    });
}

function openDB(dbName, version, cb) {
    var req = indexedDB.open(dbName, version);
    req.onupgradeneeded = function(e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains('UnifiedStocks')) {
            db.createObjectStore('UnifiedStocks', {keyPath: 'sym'});
        }
    };
    req.onsuccess = function() { cb(req.result); };
    req.onerror = function() { alert('Database error'); };
}

function renderStep7() {
    return '<div><h3 style="color:#00ff88;margin-bottom:10px;">GitHub Sync</h3>' +
        '<p style="font-size:11px;color:#888;margin-bottom:15px;">Upload to GitHub and update unified-symbols.json</p>' +
        '<button onclick="syncToGitHub()" style="width:100%;padding:12px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">📤 Sync to GitHub</button>' +
        '<div id="step7-status" style="margin:15px 0;font-size:11px;"></div>' +
        '</div>';
}

function syncToGitHub() {
    var status = document.getElementById('step7-status');
    var token = localStorage.getItem('gh_token');
    
    if (!token) {
        status.innerHTML = '⚠️ GitHub PAT not configured. Skipping sync.';
        return;
    }
    
    status.innerHTML = '⏳ Syncing to GitHub...';
    
    var symbols = [];
    for (var i = 0; i < importState.stocks.length; i++) {
        var s = importState.stocks[i];
        symbols.push({
            sym: s.name.toUpperCase(),
            name: s.name,
            isin: s.isin,
            sector: s.sector,
            industry: s.industry,
            qty: s.qty,
            avg: s.avg,
            type: s.type,
            source: 'import'
        });
    }
    
    var unifiedData = {
        updated: new Date().toISOString(),
        count: importState.stocks.length,
        symbols: symbols
    };
    
    var jsonStr = JSON.stringify(unifiedData, null, 2);
    var content = btoa(unescape(encodeURIComponent(jsonStr)));
    var owner = 'murugkan';
    var repo = 'bharatmarkets';
    var path = 'unified-symbols.json';
    var url = 'https://api.github.com/repos/' + owner + '/' + repo + '/contents/' + path;
    
    fetch(url, {
        headers: {'Authorization': 'token ' + token, 'Accept': 'application/vnd.github.v3+json'}
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        return fetch(url, {
            method: 'PUT',
            headers: {'Authorization': 'token ' + token, 'Content-Type': 'application/json'},
            body: JSON.stringify({
                message: 'Import: ' + importState.stocks.length + ' stocks via wizard',
                content: content,
                sha: data.sha || undefined
            })
        });
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.commit) {
            status.innerHTML = '✅ Synced successfully!';
        } else {
            status.innerHTML = '❌ ' + (data.message || 'Sync failed');
        }
    })
    .catch(function(e) {
        status.innerHTML = '❌ ' + e.message;
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Navigation
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function nextStep() {
    if (importState.step < 7) {
        importState.step++;
        showWizardUI();
    }
}

function prevStep() {
    if (importState.step > 2) {
        importState.step--;
        showWizardUI();
    }
}

function closeWizard() {
    var modal = document.getElementById('wizard-modal');
    if (modal) modal.style.display = 'none';
    document.body.classList.remove('modal-open');
    if (typeof loadPortfolioTable === 'function') loadPortfolioTable();
}


function parseCSV(text) {
    var lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    if (lines.length < 2) throw new Error('File is empty or too short');
    
    var delimiter = lines[0].includes('\t') ? '\t' : ',';
    var headers = lines[0].split(delimiter).map(h => h.toLowerCase().trim());
    
    var nameIdx = headers.findIndex(h => h.includes('name') || h.includes('stock'));
    var qtyIdx = headers.findIndex(h => h.includes('qty') || h.includes('quantity'));
    var avgIdx = headers.findIndex(h => h.includes('avg') || h.includes('price'));
    
    if (nameIdx === -1) nameIdx = 0;
    if (qtyIdx === -1) qtyIdx = 1;
    if (avgIdx === -1) avgIdx = 2;
    
    var stocks = [];
    for (var i = 1; i < lines.length; i++) {
        var parts = lines[i].split(delimiter).map(p => p.trim().replace(/['"₹₨]/g, ''));
        if (!parts[nameIdx]) continue;
        if (parts[nameIdx].toLowerCase().includes('name')) continue;
        
        var qty = parseFloat(parts[qtyIdx]) || 0;
        var avg = parseFloat(parts[avgIdx]) || 0;
        
        if (parts[nameIdx] && (qty || avg)) {
            stocks.push({
                name: parts[nameIdx],
                qty: qty,
                avg: avg,
                isin: '',
                sector: '',
                industry: '',
                type: 'PORTFOLIO'
            });
        }
    }
    
    if (stocks.length === 0) throw new Error('No valid stocks found');
    importState.stocks = stocks;
}

function parseRows(rows) {
    if (rows.length < 2) throw new Error('No data in file');
    
    // Detect column indices from header row
    var headerRow = rows[0].map(h => String(h).toLowerCase().trim());
    var nameIdx = headerRow.findIndex(h => h.includes('name') || h.includes('stock'));
    var qtyIdx = headerRow.findIndex(h => h.includes('qty') || h.includes('quantity'));
    var avgIdx = headerRow.findIndex(h => h.includes('avg') || h.includes('price') || h.includes('cost'));
    
    if (nameIdx === -1) nameIdx = 0;
    if (qtyIdx === -1) qtyIdx = 1;
    if (avgIdx === -1) avgIdx = 2;
    
    var stocks = [];
    
    for (var i = 1; i < rows.length; i++) {
        var r = rows[i];
        if (!r || !r[nameIdx]) continue;
        
        var name = String(r[nameIdx]).trim();
        if (!name || name.toLowerCase().includes('name') || name.length === 0) continue;
        
        // Remove currency symbols (₹, $, etc) and parse numbers
        var qtyStr = String(r[qtyIdx] || '').replace(/[₹₨$€,]/g, '').trim();
        var avgStr = String(r[avgIdx] || '').replace(/[₹₨$€,]/g, '').trim();
        
        var qty = parseFloat(qtyStr) || 0;
        var avg = parseFloat(avgStr) || 0;
        
        if (name && (qty || avg)) {
            stocks.push({
                name: name,
                qty: qty,
                avg: avg,
                isin: '',
                sector: '',
                industry: '',
                type: 'PORTFOLIO'
            });
        }
    }
    
    if (stocks.length === 0) throw new Error('No valid stocks found. Ensure file has Stock Name, QTY, and/or Price.');
    importState.stocks = stocks;
}

function renderStep1Preview() {
    if (importState.stocks.length === 0) return;
    var html = '<table style="width:100%;font-size:10px;border-collapse:collapse;margin:10px 0;"><tr style="background:#111;"><th style="padding:6px;text-align:left;">Stock</th><th style="padding:6px;text-align:right;">QTY</th><th style="padding:6px;text-align:right;">AVG</th></tr>';
    importState.stocks.forEach(s => {
        html += '<tr style="border-bottom:1px solid #111;"><td style="padding:6px;">' + s.name.substring(0,25) + '</td><td style="padding:6px;text-align:right;">' + (s.qty || '-') + '</td><td style="padding:6px;text-align:right;">₹' + (s.avg ? s.avg.toFixed(2) : '-') + '</td></tr>';
    });
    html += '</table>';
    document.getElementById('step1-preview').innerHTML = html;
    document.getElementById('wizard-start').style.display = 'block';
}

function startWizardFromStep2() {
    if (importState.stocks.length === 0) {
        alert('Please upload a file first');
        return;
    }
    openWizardModal();
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// WIZARD MODAL (Steps 2-7)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function openWizardModal() {
    importState.step = 2;
    document.body.classList.add('modal-open');
    showWizardUI();
}

function showWizardUI() {
    var progress = (importState.step / 7) * 100;
    var stepTitles = ['', '', 'Manual Entries', 'AI Prompt', 'Paste Response', 'Edit & Validate', 'Save to DB', 'GitHub Sync'];
    
    var html = '<div style="padding:20px;background:#0a0a0a;border-radius:12px;max-width:900px;">' +
        '<div style="margin-bottom:10px;font-size:12px;color:#555;">Step ' + importState.step + ' of 7: ' + stepTitles[importState.step] + '</div>' +
        '<div style="display:flex;gap:8px;margin-bottom:15px;justify-content:flex-end;flex-wrap:wrap;">' +
        '<button onclick="closeWizard()" style="padding:8px 16px;background:#333;border:none;color:#fff;border-radius:6px;cursor:pointer;font-size:12px;">Cancel</button>' +
        (importState.step > 2 ? '<button onclick="prevStep()" style="padding:8px 16px;background:#444;border:none;color:#fff;border-radius:6px;cursor:pointer;font-size:12px;">← Back</button>' : '') +
        (importState.step < 7 ? '<button onclick="nextStep()" style="padding:8px 16px;background:#00ff88;border:none;color:#000;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">Next →</button>' : 
        '<button onclick="closeWizard()" style="padding:8px 16px;background:#00ff88;border:none;color:#000;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">Done ✓</button>') +
        '</div>' +
        '<div style="width:100%;height:4px;background:#111;border-radius:2px;margin-bottom:20px;overflow:hidden;"><div style="width:' + progress + '%;height:100%;background:#00ff88;transition:width 0.3s;"></div></div>';
    
    switch(importState.step) {
        case 2: html += renderStep2(); break;
        case 3: html += renderStep3(); break;
        case 4: html += renderStep4(); break;
        case 5: html += renderStep5(); break;
        case 6: html += renderStep6(); break;
        case 7: html += renderStep7(); break;
    }
    
    html += '</div>';
    
    var modal = document.getElementById('wizard-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'wizard-modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.95);z-index:9000;display:flex;align-items:center;justify-content:center;overflow-y:auto;';
        document.body.appendChild(modal);
    }
    modal.innerHTML = '<div style="background:#000;border:1px solid #222;border-radius:12px;padding:30px;max-height:90vh;overflow-y:auto;width:95%;max-width:900px;margin:20px auto;">' + html + '</div>';
}

function renderStep2() {
    return '<div><h3 style="color:#00ff88;margin-bottom:10px;">Add Manual Entries</h3>' +
        '<textarea id="manual-ta" style="width:100%;height:150px;padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;font-size:11px;border-radius:6px;resize:vertical;" placeholder="SYMBOL QTY AVG (one per line)"></textarea>' +
        '<div style="margin:10px 0;"><button onclick="addManualEntries()" style="width:100%;padding:10px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">Add Entries</button></div>' +
        '</div>';
}

function addManualEntries() {
    var ta = document.getElementById('manual-ta');
    var lines = ta.value.split('\n').filter(l => l.trim().length > 0);
    
    lines.forEach(line => {
        var parts = line.split(/[\s,]+/).filter(p => p.length > 0);
        if (parts.length >= 2) {
            importState.stocks.push({
                name: parts[0].toUpperCase(),
                qty: parseFloat(parts[1]) || 0,
                avg: parseFloat(parts[2]) || 0,
                isin: '',
                sector: '',
                industry: '',
                type: 'PORTFOLIO'
            });
        }
    });
    
    nextStep();
}

function renderStep3() {
    return '<div><h3 style="color:#00ff88;margin-bottom:10px;">Generate AI Prompt</h3>' +
        '<div style="background:#050505;border:1px solid #222;padding:12px;border-radius:6px;font-size:11px;color:#888;margin-bottom:15px;max-height:300px;overflow-y:auto;font-family:monospace;">' +
        '<b style="color:#00ff88;">Copy this prompt and paste into Claude:</b><br><br>' +
        'I have a portfolio with ' + importState.stocks.length + ' stocks. Please enrich with ISIN, Sector, Industry in JSON format:<br><br>' +
        '[' + importState.stocks.slice(0,3).map(s => '{"name":"' + s.name + '","qty":' + s.qty + ',"avg":' + s.avg + '}').join(',') + (importState.stocks.length > 3 ? ',...' : '') + ']<br><br>' +
        'Return only valid JSON with added fields: isin, sector, industry' +
        '</div>' +
        '<p style="font-size:11px;color:#666;">After getting Claude\'s response, come back and paste it in Step 4.</p>' +
        '</div>';
}

function renderStep4() {
    return '<div><h3 style="color:#00ff88;margin-bottom:10px;">Paste AI Response</h3>' +
        '<textarea id="ai-response-ta" style="width:100%;height:180px;padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;font-size:10px;border-radius:6px;resize:vertical;" placeholder="Paste JSON from Claude here..."></textarea>' +
        '<div id="step4-status" style="margin:10px 0;font-size:11px;color:#666;"></div>' +
        '<div style="margin:10px 0;"><button onclick="parseAIResponse()" style="width:100%;padding:10px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">Parse & Continue</button></div>' +
        '</div>';
}

function parseAIResponse() {
    var ta = document.getElementById('ai-response-ta');
    var text = ta.value.trim();
    var status = document.getElementById('step4-status');
    
    if (!text) {
        status.innerHTML = '<span style="color:#ffb347;">⚠️ Empty response. Skipping AI enrichment.</span>';
        setTimeout(() => nextStep(), 1500);
        return;
    }
    
    try {
        var data = JSON.parse(text);
        if (!Array.isArray(data)) data = [data];
        
        data.forEach(item => {
            var stock = importState.stocks.find(s => s.name.toUpperCase() === item.name.toUpperCase());
            if (stock) {
                stock.isin = item.isin || '';
                stock.sector = item.sector || '';
                stock.industry = item.industry || '';
            }
        });
        
        status.innerHTML = '<span style="color:#00ff88;">✅ Enriched ' + data.length + ' stocks</span>';
        setTimeout(() => nextStep(), 1500);
    } catch(e) {
        status.innerHTML = '<span style="color:#ff6b85;">❌ Invalid JSON: ' + e.message + '</span>';
    }
}

function renderStep5() {
    var html = '<div><h3 style="color:#00ff88;margin-bottom:10px;">Edit & Validate</h3>' +
        '<div style="max-height:400px;overflow-y:auto;">';
    
    importState.stocks.forEach((stock, i) => {
        html += '<div style="padding:10px;background:#050505;margin:8px 0;border:1px solid #222;border-radius:6px;">' +
            '<input type="text" value="' + stock.name + '" style="width:100%;padding:6px;background:#000;color:#fff;border:1px solid #333;border-radius:3px;margin-bottom:6px;font-size:11px;" onchange="importState.stocks[' + i + '].name=this.value">' +
            '<div style="display:flex;gap:6px;font-size:11px;">' +
            '<input type="number" value="' + stock.qty + '" placeholder="QTY" style="flex:1;padding:6px;background:#000;color:#fff;border:1px solid #333;border-radius:3px;" onchange="importState.stocks[' + i + '].qty=parseFloat(this.value)">' +
            '<input type="number" value="' + stock.avg + '" placeholder="AVG" step="0.01" style="flex:1;padding:6px;background:#000;color:#fff;border:1px solid #333;border-radius:3px;" onchange="importState.stocks[' + i + '].avg=parseFloat(this.value)">' +
            '<input type="text" value="' + (stock.isin || '') + '" placeholder="ISIN" style="flex:1;padding:6px;background:#000;color:#fff;border:1px solid #333;border-radius:3px;" onchange="importState.stocks[' + i + '].isin=this.value">' +
            '</div>' +
            '<div style="display:flex;gap:6px;margin-top:6px;font-size:10px;">' +
            '<select style="flex:1;padding:6px;background:#000;color:#fff;border:1px solid #333;border-radius:3px;" onchange="importState.stocks[' + i + '].type=this.value"><option value="PORTFOLIO">PORTFOLIO</option><option value="WATCHLIST">WATCHLIST</option></select>' +
            '<button onclick="deleteStock(' + i + ')" style="padding:6px 10px;background:#ff6b85;color:#fff;border:none;border-radius:3px;cursor:pointer;font-size:10px;">Delete</button>' +
            '</div>' +
            '</div>';
    });
    
    html += '</div></div>';
    return html;
}

function deleteStock(idx) {
    importState.stocks.splice(idx, 1);
    showWizardUI();
}

function renderStep6() {
    return '<div><h3 style="color:#00ff88;margin-bottom:10px;">Save to Database</h3>' +
        '<p style="font-size:11px;color:#888;margin-bottom:15px;">Ready to save ' + importState.stocks.length + ' stocks to browser database</p>' +
        '<button onclick="saveToIndexedDB()" style="width:100%;padding:12px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">💾 Save Now</button>' +
        '<div id="step6-status" style="margin:15px 0;font-size:11px;"></div>' +
        '</div>';
}

function saveToIndexedDB() {
    var status = document.getElementById('step6-status');
    status.innerHTML = '<span style="color:#ffb347;">⏳ Saving...</span>';
    
    openDB('BharatEngineDB', 1, function(db) {
        var tx = db.transaction('UnifiedStocks', 'readwrite');
        var store = tx.objectStore('UnifiedStocks');
        
        importState.stocks.forEach(stock => {
            store.put({
                sym: stock.name.toUpperCase(),
                name: stock.name,
                isin: stock.isin,
                qty: stock.qty,
                avg: stock.avg,
                sector: stock.sector,
                industry: stock.industry,
                type: stock.type,
                source: 'import'
            });
        });
        
        tx.oncomplete = function() {
            status.innerHTML = '<span style="color:#00ff88;">✅ Saved ' + importState.stocks.length + ' stocks</span>';
            setTimeout(() => nextStep(), 1500);
        };
        
        tx.onerror = function() {
            status.innerHTML = '<span style="color:#ff6b85;">❌ Error saving to database</span>';
        };
    });
}

function openDB(dbName, version, cb) {
    var req = indexedDB.open(dbName, version);
    req.onupgradeneeded = function(e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains('UnifiedStocks')) {
            db.createObjectStore('UnifiedStocks', {keyPath: 'sym'});
        }
    };
    req.onsuccess = function() { cb(req.result); };
    req.onerror = function() { alert('Database error'); };
}

function renderStep7() {
    return '<div><h3 style="color:#00ff88;margin-bottom:10px;">GitHub Sync</h3>' +
        '<p style="font-size:11px;color:#888;margin-bottom:15px;">Upload to GitHub and update unified-symbols.json</p>' +
        '<button onclick="syncToGitHub()" style="width:100%;padding:12px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">📤 Sync to GitHub</button>' +
        '<div id="step7-status" style="margin:15px 0;font-size:11px;"></div>' +
        '</div>';
}

function syncToGitHub() {
    var status = document.getElementById('step7-status');
    var token = localStorage.getItem('gh_token');
    
    if (!token) {
        status.innerHTML = '<span style="color:#ffb347;">⚠️ GitHub PAT not configured. Skipping sync.</span>';
        return;
    }
    
    status.innerHTML = '<span style="color:#ffb347;">⏳ Syncing to GitHub...</span>';
    
    var unifiedData = {
        updated: new Date().toISOString(),
        count: importState.stocks.length,
        symbols: importState.stocks.map(s => ({
            sym: s.name.toUpperCase(),
            name: s.name,
            isin: s.isin,
            sector: s.sector,
            industry: s.industry,
            qty: s.qty,
            avg: s.avg,
            type: s.type,
            source: 'import'
        }))
    };
    
    var content = btoa(unescape(encodeURIComponent(JSON.stringify(unifiedData, null, 2))));
    var owner = 'murugkan';
    var repo = 'bharatmarkets';
    var path = 'unified-symbols.json';
    var url = 'https://api.github.com/repos/' + owner + '/' + repo + '/contents/' + path;
    
    // Get current SHA
    fetch(url, {
        headers: {'Authorization': 'token ' + token, 'Accept': 'application/vnd.github.v3+json'}
    })
    .then(r => r.json())
    .then(data => {
        return fetch(url, {
            method: 'PUT',
            headers: {'Authorization': 'token ' + token, 'Content-Type': 'application/json'},
            body: JSON.stringify({
                message: 'Import: ' + importState.stocks.length + ' stocks via wizard',
                content: content,
                sha: data.sha || undefined
            })
        });
    })
    .then(r => r.json())
    .then(data => {
        if (data.commit) {
            status.innerHTML = '<span style="color:#00ff88;">✅ Synced successfully!</span><div style="margin-top:10px;font-size:10px;color:#666;">GitHub Actions will fetch prices automatically.</div>';
        } else {
            status.innerHTML = '<span style="color:#ff6b85;">❌ ' + (data.message || 'Sync failed') + '</span>';
        }
    })
    .catch(e => {
        status.innerHTML = '<span style="color:#ff6b85;">❌ ' + e.message + '</span>';
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Navigation
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function nextStep() {
    if (importState.step < 7) {
        importState.step++;
        showWizardUI();
    }
}

function prevStep() {
    if (importState.step > 2) {
        importState.step--;
        showWizardUI();
    }
}

function closeWizard() {
    var modal = document.getElementById('wizard-modal');
    if (modal) modal.style.display = 'none';
    document.body.classList.remove('modal-open');
    if (typeof loadPortfolioTable === 'function') loadPortfolioTable();
}
