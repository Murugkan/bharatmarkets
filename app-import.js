/**
 * app-import.js - Enhanced Import Workflow (FULLY FIXED)
 * Step 1: FIXED CSV/XLSX parsing with validation
 * Step 7: FIXED with PAT config UI, status display, JSON preview, and confirmation
 */

var debugLog = [];

function addDebugLog(msg) {
    debugLog.push(msg);
    var el = document.getElementById('debug-log');
    if (el) {
        el.textContent = debugLog.join('\n');
        el.scrollTop = el.scrollHeight;
    }
    console.log(msg);
}

function clearDebugLog() {
    debugLog = [];
}

var importState = {
    step: 1,
    stocks: [],
    aiResponse: null,
    importMode: 'append'
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// FILE IMPORT HANDLER
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function handleFileImport(file) {
    if (!file) return;
    
    var status = document.getElementById('step1-status');
    status.innerHTML = '<span style="color:#ffb347;">⏳ Reading file...</span>';
    
    var ext = file.name.split('.').pop().toLowerCase();
    
    if (ext === 'csv' || ext === 'txt' || ext === 'tsv') {
        var reader = new FileReader();
        reader.onload = function(e) {
            try {
                processImportCSV(e.target.result);
                status.innerHTML = '<span style="color:#00ff88;">✅ File parsed successfully</span>';
                renderStep1Preview();
                showImportUI();
                openImportWorkflow();
            } catch(err) {
                status.innerHTML = '<span style="color:#ff6b85;">❌ Parse error: ' + err.message + '</span>';
            }
        };
        reader.onerror = function() {
            status.innerHTML = '<span style="color:#ff6b85;">❌ Error reading file</span>';
        };
        reader.readAsText(file);
    } else if (ext === 'xls' || ext === 'xlsx') {
        loadSheetJS(function() {
            var reader = new FileReader();
            reader.onload = function(e) {
                try {
                    var data = new Uint8Array(e.target.result);
                    var wb = XLSX.read(data, {type: 'array'});
                    
                    if (!wb || !wb.SheetNames || wb.SheetNames.length === 0) {
                        throw new Error('No sheets found in Excel file');
                    }
                    
                    var ws = wb.Sheets[wb.SheetNames[0]];
                    if (!ws) {
                        throw new Error('Cannot read first sheet');
                    }
                    
                    var csv = XLSX.utils.sheet_to_csv(ws);
                    processImportCSV(csv);
                    status.innerHTML = '<span style="color:#00ff88;">✅ Excel file parsed successfully</span>';
                    renderStep1Preview();
                    showImportUI();
                    openImportWorkflow();
                } catch(err) {
                    status.innerHTML = '<span style="color:#ff6b85;">❌ Excel error: ' + err.message + '</span>';
                }
            };
            reader.onerror = function() {
                status.innerHTML = '<span style="color:#ff6b85;">❌ Error reading Excel file</span>';
            };
            reader.readAsArrayBuffer(file);
        });
    } else {
        status.innerHTML = '<span style="color:#ff6b85;">❌ Unsupported file type. Use CSV or Excel.</span>';
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// MAIN: Open Import Workflow
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function openImportWorkflow() {
    try {
        importState.step = 1;
        importState.stocks = [];
        document.body.classList.add('modal-open');
        showImportUI();
    } catch(err) {
        console.error('❌ Error in openImportWorkflow:', err.message);
        console.error('Stack:', err.stack);
        alert('❌ Error opening import wizard: ' + err.message);
    }
}

function showImportUI() {
    try {
        var html = '<div id="import-wizard" style="' +
            'padding:20px;background:#0a0a0a;border-radius:12px;max-width:900px;' +
            '">';
        
        // Step indicator
        html += '<div style="margin-bottom:10px;font-size:12px;color:#555;font-family:monospace;">' +
            'Step ' + importState.step + ' of 7: ';
        
        var stepTitles = ['Upload CSV/XLS', 'Manual Entries (Opt)', 'AI Prompt (Opt)', 'Paste Response', 'Edit & Validate', 'Save to DB (Opt)', 'Post to GitHub'];
        html += stepTitles[importState.step - 1];
        html += '</div>';
        
        // TOP BUTTONS - no scrolling needed
        html += '<div style="margin-bottom:15px;display:flex;gap:8px;justify-content:flex-end;">' +
            '<button onclick="closeImportModal()" style="padding:8px 16px;background:#333;border:none;color:#fff;' +
            'border-radius:6px;cursor:pointer;font-size:12px;">Cancel</button>' +
            (importState.step > 1 ? '<button onclick="prevImportStep()" style="padding:8px 16px;background:#444;' +
            'border:none;color:#fff;border-radius:6px;cursor:pointer;font-size:12px;">← Back</button>' : '') +
            (importState.step < 7 ? '<button onclick="nextImportStep()" style="padding:8px 16px;background:#00ff88;' +
            'border:none;color:#000;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">Next →</button>' : 
            '<button onclick="closeImportModal()" style="padding:8px 16px;background:#00ff88;' +
            'border:none;color:#000;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">Close ✓</button>') +
            '</div>';
        
        // Progress bar
        var progress = (importState.step / 7) * 100;
        html += '<div style="width:100%;height:4px;background:#111;border-radius:2px;margin-bottom:20px;overflow:hidden;">' +
            '<div style="width:' + progress + '%;height:100%;background:#00ff88;"></div>' +
            '</div>';
        
        switch(importState.step) {
            case 1: html += renderStep1(); break;
            case 2: html += renderStep2(); break;
            case 3: html += renderStep3(); break;
            case 4: html += renderStep4(); break;
            case 5: html += renderStep5(); break;
            case 6: html += renderStep6(); break;
            case 7: html += renderStep7(); break;
        }
        
        html += '</div>';
        
        // Show modal
        var modal = document.getElementById('import-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'import-modal';
            modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);' +
                'z-index:9000;display:flex;align-items:center;justify-content:center;overflow-y:auto;';
            document.body.appendChild(modal);
        }
        
        modal.innerHTML = '<div style="background:#000;border:1px solid #222;border-radius:12px;' +
            'padding:20px;max-height:90vh;overflow-y:auto;width:90%;max-width:900px;margin:20px;">' +
            html + 
            '</div>';
        
        modal.style.display = 'flex';
        
        // Attach delete button listeners if on step 5
        if (importState.step === 5) {
            attachDeleteListeners();
        }
        
        // Initialize step 7 button styles if showing step 7
        if (importState.step === 7) {
            setTimeout(function() {
                setImportMode(importState.importMode);
            }, 100);
        }
    } catch(err) {
        console.error('❌ Error in showImportUI:', err.message);
        console.error('Stack:', err.stack);
        alert('❌ Error rendering UI: ' + err.message);
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 1: Upload CSV/XLS - FIXED PARSING
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep1() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Upload Stock List</h3>' +
        '<div style="padding:10px;background:#111;border-left:3px solid #00ff88;margin:10px 0;font-size:11px;color:#888;border-radius:4px;">' +
        '<b style="color:#00ff88;">CSV/Excel Format:</b><br>' +
        'Stock Name, Quantity, Average Price<br><br>' +
        '<b style="color:#00ff88;">Examples:</b><br>' +
        'HDFC Bank Limited,84,817.50<br>' +
        'Reliance Industries Limited,10,2450<br>' +
        'TCS Limited,50,3200<br>' +
        '</div>' +
        '<div style="margin:15px 0;padding:20px;border:2px dashed #222;border-radius:8px;' +
        'text-align:center;cursor:pointer;background:#050505;position:relative;" ' +
        'id="drop-zone" onclick="document.getElementById(\'file-input\').click()" ondrop="handleDrop(event)" ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)">' +
        '<div style="font-size:32px;margin-bottom:10px;">📁</div>' +
        '<div style="color:#fff;font-weight:bold;margin-bottom:5px;">Click to upload or drag & drop</div>' +
        '<div style="color:#666;font-size:12px;">CSV or Excel files</div>' +
        '</div>' +
        '<input type="file" id="file-input" accept=".csv,.xls,.xlsx,.tsv,.txt" style="display:none;" ' +
        'onchange="handleImportFile(this.files[0])">' +
        '<div id="file-status" style="margin:10px 0;font-size:12px;color:#666;"></div>' +
        '<div id="step1-preview" style="margin:10px 0;"></div>' +
        '</div>';
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('drop-zone').style.background = '#050505';
    if (e.dataTransfer.files.length > 0) {
        handleImportFile(e.dataTransfer.files[0]);
    }
}

function handleDragOver(e) {
    e.preventDefault();
    document.getElementById('drop-zone').style.background = '#111';
}

function handleDragLeave(e) {
    document.getElementById('drop-zone').style.background = '#050505';
}

function handleImportFile(file) {
    if (!file) return;
    
    var status = document.getElementById('file-status');
    status.innerHTML = '<span style="color:#ffb347;">⏳ Reading file...</span>';
    
    var ext = file.name.split('.').pop().toLowerCase();
    
    if (ext === 'csv' || ext === 'txt' || ext === 'tsv') {
        var reader = new FileReader();
        reader.onload = function(e) {
            try {
                processImportCSV(e.target.result);
                status.innerHTML = '<span style="color:#00ff88;">✅ File parsed successfully</span>';
                renderStep1Preview();
            } catch(err) {
                status.innerHTML = '<span style="color:#ff6b85;">❌ Parse error: ' + err.message + '</span>';
            }
        };
        reader.onerror = function() {
            status.innerHTML = '<span style="color:#ff6b85;">❌ Error reading file</span>';
        };
        reader.readAsText(file);
    } else if (ext === 'xls' || ext === 'xlsx') {
        loadSheetJS(function() {
            var reader = new FileReader();
            reader.onload = function(e) {
                try {
                    var data = new Uint8Array(e.target.result);
                    var wb = XLSX.read(data, {type: 'array'});
                    
                    if (!wb || !wb.SheetNames || wb.SheetNames.length === 0) {
                        throw new Error('No sheets found in Excel file');
                    }
                    
                    var ws = wb.Sheets[wb.SheetNames[0]];
                    if (!ws) {
                        throw new Error('Cannot read first sheet');
                    }
                    
                    var csv = XLSX.utils.sheet_to_csv(ws);
                    processImportCSV(csv);
                    status.innerHTML = '<span style="color:#00ff88;">✅ Excel file parsed successfully</span>';
                    renderStep1Preview();
                } catch(err) {
                    status.innerHTML = '<span style="color:#ff6b85;">❌ Excel error: ' + err.message + '</span>';
                }
            };
            reader.onerror = function() {
                status.innerHTML = '<span style="color:#ff6b85;">❌ Error reading Excel file</span>';
            };
            reader.readAsArrayBuffer(file);
        });
    } else {
        status.innerHTML = '<span style="color:#ff6b85;">❌ Unsupported file type. Use CSV or Excel.</span>';
    }
}

var _sheetJSLoaded = false;
function loadSheetJS(cb) {
    if (_sheetJSLoaded) { cb(); return; }
    if (window.XLSX) { _sheetJSLoaded = true; cb(); return; }
    
    var script = document.createElement('script');
    // Try primary CDN first
    script.src = 'https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js';
    
    script.onload = function() { 
        _sheetJSLoaded = true; 
        cb(); 
    };
    
    script.onerror = function() { 
        // Fallback to secondary CDN
        var script2 = document.createElement('script');
        script2.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.min.js';
        script2.onload = function() { _sheetJSLoaded = true; cb(); };
        script2.onerror = function() { 
            var status = document.getElementById('file-status');
            if (status) status.innerHTML = '<span style="color:#ffb347;">⚠️ Excel support unavailable - use CSV instead</span>';
            // Still continue with CSV support
            cb();
        };
        document.head.appendChild(script2);
    };
    
    document.head.appendChild(script);
}

function processImportCSV(csv) {
    var lines = csv.split('\n').map(function(l) { return l.trim(); }).filter(function(l) { return l.length > 0; });
    
    if (lines.length === 0) {
        throw new Error('File is empty');
    }
    
    var headerLine = lines[0];
    var delimiter = ',';
    
    if (headerLine.includes('\t')) delimiter = '\t';
    else if (headerLine.includes(';')) delimiter = ';';
    
    var headerParts = headerLine.split(delimiter).map(function(p) { return p.trim().toLowerCase(); });
    
    // Find column indices - robust matching
    var nameIdx = -1;
    var qtyIdx = -1;
    var avgIdx = -1;
    var isinIdx = -1;
    var sectorIdx = -1;
    
    clearDebugLog();
    addDebugLog("Headers: " + headerParts.join(" | "));
    
    for (var i = 0; i < headerParts.length; i++) {
        var h = headerParts[i];
        
        // Stock Name / Symbol / Ticker
        if (!nameIdx && (h === 'stock name' || h === 'symbol' || h === 'ticker' || 
            h === 'name' || (h.includes('stock') && h.includes('name')))) {
            nameIdx = i;
            addDebugLog("✓ Name @ [" + i + "]: " + h);
        }
        
        // Quantity - various forms but not "value"
        if (qtyIdx === -1 && (h === 'quantity' || h === 'qty' || h === 'shares' || 
            h.includes('quantity') || h.includes('qty')) && !h.includes('value')) {
            qtyIdx = i;
            addDebugLog("✓ Qty @ [" + i + "]: " + h);
        }
        
        // Average Price / Cost Price - flexible matching
        if (avgIdx === -1 && ((h.includes('average') || h.includes('avg') || h.includes('cost')) && 
            (h.includes('price') || h.includes('cost')))) {
            avgIdx = i;
            addDebugLog("✓ Avg @ [" + i + "]: " + h);
        }
        
        // ISIN
        if (isinIdx === -1 && h === 'isin') {
            isinIdx = i;
            addDebugLog("✓ ISIN @ [" + i + "]: " + h);
        }
        
        // Sector
        if (sectorIdx === -1 && (h === 'sector' || h === 'sector name' || h.includes('sector'))) {
            sectorIdx = i;
            addDebugLog("✓ Sector @ [" + i + "]: " + h);
        }
    }
    
    // Smarter fallback detection based on column count
    if (nameIdx === -1) {
        nameIdx = 0;
        addDebugLog("Fallback: Name @ [0]");
    }
    
    // If Qty not found, look for numeric columns after name
    if (qtyIdx === -1) {
        for (var i = nameIdx + 1; i < headerParts.length; i++) {
            var h = headerParts[i];
            if (h.includes('qty') || h.includes('quantity') || h.includes('shares')) {
                qtyIdx = i;
                addDebugLog("Fallback: Found Qty @ [" + i + "]");
                break;
            }
        }
        if (qtyIdx === -1 && headerParts.length > 3) {
            qtyIdx = 3;  // Common position in broker exports
            addDebugLog("Fallback: Qty @ [3]");
        }
    }
    
    // If Avg not found, look after Qty
    if (avgIdx === -1) {
        for (var i = nameIdx + 1; i < headerParts.length; i++) {
            var h = headerParts[i];
            if (h.includes('average') || h.includes('avg') || (h.includes('cost') && h.includes('price'))) {
                avgIdx = i;
                addDebugLog("Fallback: Found Avg @ [" + i + "]");
                break;
            }
        }
        if (avgIdx === -1 && headerParts.length > 4) {
            avgIdx = 4;  // Common position in broker exports
            addDebugLog("Fallback: Avg @ [4]");
        }
    }
    
    addDebugLog("Final: Name[" + nameIdx + "], Qty[" + qtyIdx + "], Avg[" + avgIdx + "]");
    
    var stocks = [];
    var seen = new Set();
    
    for (var i = 1; i < lines.length; i++) {
        var line = lines[i].trim();
        if (!line) continue;
        
        var parts = line.split(delimiter).map(function(p) { 
            return p.trim().replace(/['"]/g, '').replace(/[₹₨]/g, '');
        });
        
        if (!parts[0] || parts[0].length === 0) continue;
        
        var name = parts[nameIdx] || parts[0];
        
        // Skip header rows and empty names
        if (name.toLowerCase().includes('name') || name.toLowerCase().includes('stock') || 
            name.toLowerCase().includes('symbol') || name.length === 0) continue;
        
        var qty = null;
        var avg = null;
        var isin = null;
        var sector = null;
        
        // Extract Quantity
        if (qtyIdx >= 0 && qtyIdx < parts.length) {
            var qtyVal = parseFloat(parts[qtyIdx]);
            if (!isNaN(qtyVal) && qtyVal > 0) qty = qtyVal;
        }
        
        // Extract Average Price
        if (avgIdx >= 0 && avgIdx < parts.length) {
            var avgVal = parseFloat(parts[avgIdx]);
            if (!isNaN(avgVal) && avgVal > 0) avg = avgVal;
        }
        
        // Extract ISIN if available
        if (isinIdx >= 0 && isinIdx < parts.length) {
            isin = parts[isinIdx] || null;
        }
        
        // Extract Sector if available
        if (sectorIdx >= 0 && sectorIdx < parts.length) {
            sector = parts[sectorIdx] || null;
        }
        
        // Log first 3 rows for debugging
        if (i <= 3) {
            addDebugLog("Row" + i + ": " + name + " | Qty=" + qty + " | Avg=" + (avg ? avg.toFixed(2) : "null"));
        }
        
        // Skip duplicates
        if (seen.has(name)) continue;
        seen.add(name);
        
        // Add stock if has valid name and at least one of qty/avg
        if (name && (qty !== null || avg !== null)) {
            stocks.push({
                name: name,
                isin: isin || '',
                qty: qty || 0,
                avg: avg || 0,
                sector: sector || '',
                industry: '',
                type: qty !== null ? 'PORTFOLIO' : 'WATCHLIST',
                status: ''
            });
        }
    }
    
    if (stocks.length === 0) {
        throw new Error('No valid stocks found. Ensure file has Name and Quantity or Price.');
    }
    
    importState.stocks = stocks;
    showImportUI();
}

function renderStep1Preview() {
    if (importState.stocks.length === 0) return;
    
    var html = '<div style="margin:15px 0;border:1px solid #222;border-radius:8px;overflow:auto;max-height:300px;">' +
        '<table style="width:100%;border-collapse:collapse;font-size:11px;">' +
        '<tr style="background:#111;border-bottom:1px solid #222;position:sticky;top:0;">' +
        '<th style="padding:6px;text-align:left;color:#00ff88;">Stock Name</th>' +
        '<th style="padding:6px;text-align:right;color:#00ff88;">QTY</th>' +
        '<th style="padding:6px;text-align:right;color:#00ff88;">AVG</th>' +
        '</tr>';
    
    importState.stocks.forEach(function(stock) {
        html += '<tr style="border-bottom:1px solid #111;">' +
            '<td style="padding:6px;">' + stock.name.substring(0, 30) + '</td>' +
            '<td style="padding:6px;text-align:right;">' + stock.qty + '</td>' +
            '<td style="padding:6px;text-align:right;">₹' + stock.avg.toFixed(2) + '</td>' +
            '</tr>';
    });
    
    html += '</table></div>' +
        '<div id="debug-log" style="margin:10px 0;padding:10px;background:#000;border:1px solid #333;border-radius:4px;' +
        'font-family:monospace;font-size:10px;color:#888;max-height:120px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;"></div>' +
        '<div style="margin:10px 0;font-size:11px;color:#00ff88;">' +
        '✅ Loaded: ' + importState.stocks.length + ' stocks' +
        '</div>';
    
    document.getElementById('step1-preview').innerHTML = html;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 2: Manual Entries
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep2() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Add Manual Entries (OPTIONAL)</h3>' +
        '<div style="padding:10px;background:#111;border-left:3px solid #00ff88;margin:10px 0;font-size:11px;color:#888;border-radius:4px;">' +
        '<b style="color:#00ff88;">Format (one per line):</b><br>' +
        'Stock Name, QTY, AVG<br><br>' +
        '<b style="color:#ffb347;">Examples:</b><br>' +
        'Apple Inc,5,150<br>' +
        'Google LLC,3,2800<br>' +
        '</div>' +
        '<textarea id="manual-entries" style="width:100%;height:150px;' +
        'padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;' +
        'font-size:11px;border-radius:6px;resize:vertical;" ' +
        'placeholder="Stock Name, QTY, AVG"></textarea>' +
        '<div style="margin:10px 0;">' +
        '<button onclick="addManualEntries()" style="padding:10px 20px;background:#00ff88;' +
        'color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">Add Entries</button>' +
        '</div>' +
        '<div id="step2-preview"></div>' +
        '</div>';
}

function addManualEntries() {
    var textarea = document.getElementById('manual-entries');
    var entries = textarea.value.split('\n').filter(function(l) { return l.trim().length > 0; });
    
    entries.forEach(function(entry) {
        var parts = entry.split(',').map(function(p) { return p.trim(); });
        if (parts.length >= 3) {
            var name = parts[0];
            var qty = parseFloat(parts[1]);
            var avg = parseFloat(parts[2]);
            
            if (name && qty && avg && !importState.stocks.find(function(s) { return s.name === name; })) {
                importState.stocks.push({
                    name: name,
                    isin: '',
                    qty: qty,
                    avg: avg,
                    sector: '',
                    industry: '',
                    type: 'PORTFOLIO',
                    status: ''
                });
            }
        }
    });
    
    textarea.value = '';
    showImportUI();
    renderStep2Preview();
}

function renderStep2Preview() {
    if (importState.stocks.length === 0) return;
    
    var html = '<div style="margin:15px 0;border:1px solid #222;border-radius:8px;overflow:auto;max-height:250px;">' +
        '<table style="width:100%;border-collapse:collapse;font-size:10px;">' +
        '<tr style="background:#111;border-bottom:1px solid #222;position:sticky;top:0;">' +
        '<th style="padding:4px;text-align:left;color:#00ff88;">Name</th>' +
        '<th style="padding:4px;text-align:right;color:#00ff88;">QTY</th>' +
        '<th style="padding:4px;text-align:right;color:#00ff88;">AVG</th>' +
        '</tr>';
    
    importState.stocks.forEach(function(stock) {
        html += '<tr style="border-bottom:1px solid #111;"><td style="padding:4px;">' + stock.name.substring(0, 20) + '</td>' +
            '<td style="padding:4px;text-align:right;">' + stock.qty + '</td>' +
            '<td style="padding:4px;text-align:right;">₹' + stock.avg.toFixed(2) + '</td></tr>';
    });
    
    html += '</table></div>';
    document.getElementById('step2-preview').innerHTML = html;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 3: Generate AI Prompt
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep3() {
    var names = importState.stocks.map(function(s) { return s.name; }).join('\n');
    
    var prompt = 'For these Indian company names, get NSE Ticker, ISIN code, Sector, and Industry.\n\n' +
        'Company Names:\n' +
        names + '\n\n' +
        '⚠️ CRITICAL OUTPUT FORMAT (comma-separated, no extra spaces):\n\n' +
        'Name,Ticker,ISIN,Sector,Industry\n' +
        'HDFC Bank Limited,HDFCBANK,INE040A01034,Banking,Financial Services\n' +
        'Reliance Industries Limited,RELIANCE,INE002A01015,Energy,Oil & Gas\n' +
        '\n' +
        'Rules:\n' +
        '• Match EXACT company names (case-insensitive)\n' +
        '• Get NSE Ticker (e.g., HDFCBANK, RELIANCE, TATAPOWER)\n' +
        '• Get ISIN code (format: INE + 10 chars)\n' +
        '• Use comma as delimiter - NO spaces around commas\n' +
        '• Output ONLY the table, no extra text';
    
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Generate AI Prompt (OPTIONAL)</h3>' +
        '<p style="margin:10px 0;color:#888;font-size:12px;">' +
        'Copy prompt → Paste in ChatGPT/Claude → Get ISIN & Sector' +
        '</p>' +
        '<textarea id="ai-prompt" readonly style="width:100%;height:300px;' +
        'padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;' +
        'font-size:11px;border-radius:6px;resize:none;">' + prompt + '</textarea>' +
        '<div style="margin:10px 0;">' +
        '<button onclick="copyPrompt()" style="padding:10px 20px;background:#00ff88;' +
        'color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">📋 Copy Prompt</button>' +
        '</div>' +
        '</div>';
}

function copyPrompt() {
    var prompt = document.getElementById('ai-prompt');
    prompt.select();
    document.execCommand('copy');
    alert('✅ Prompt copied to clipboard!');
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 4: Paste AI Response
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep4() {
    var hasStocks = importState.stocks && importState.stocks.length > 0;
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">📋 Paste Additional Data (MANDATORY)</h3>' +
        '<div style="padding:10px;background:#1a2a0a;border-left:3px solid #ffb347;margin:10px 0;font-size:11px;color:#888;border-radius:4px;">' +
        '<b style="color:#ffb347;">⚠️ REQUIRED:</b><br>' +
        'Paste data with Ticker, ISIN, Sector for each stock from Step 1.' +
        '</div>' +
        
        '<div style="margin:10px 0;font-size:11px;color:#666;">' +
        '<b>Format (any delimiter):</b><br>' +
        '&bull; Comma: Stock Name,Ticker,ISIN,Sector<br>' +
        '&bull; Tab: Stock Name\tTicker\tISIN\tSector<br>' +
        '<b>Example:</b><br>' +
        'HDFC Bank,HDFCBANK,INE040A01034,Banking<br>' +
        'Reliance,RIL,INE002A01018,Oil & Gas' +
        '</div>' +
        
        '<textarea id="ai-response" style="width:100%;height:180px;' +
        'padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;' +
        'font-size:11px;border-radius:6px;resize:vertical;" ' +
        'placeholder="Paste data here - copy from Excel/CSV/AI response"></textarea>' +
        
        '<button onclick="manuallyParseStep4()" style="margin-top:10px;padding:8px 16px;background:#ffb347;' +
        'color:#000;border:none;border-radius:4px;cursor:pointer;font-weight:bold;">📌 Parse Pasted Data</button>' +
        
        '<div id="step4-status" style="margin:10px 0;font-size:12px;">' + 
        (hasStocks ? '<span style="color:#00ff88;">✅ ' + importState.stocks.length + ' stocks from Step 1</span>' : 
                     '<span style="color:#ff6b85;">❌ No stocks from Step 1 - Go back to Step 1</span>') +
        '</div>' +
        '</div>';
}

function manuallyParseStep4() {
    var response = document.getElementById('ai-response').value;
    
    if (!importState.stocks || importState.stocks.length === 0) {
        alert('❌ No stocks from Step 1. Go back and upload CSV file first.');
        return;
    }
    
    if (!response.trim()) {
        alert('❌ Please paste data in the textarea first');
        return;
    }
    
    // Detect delimiter
    if (response.includes('\t')) {
        parseAIResponse('\t');
    } else if (response.includes(',')) {
        parseAIResponse(',');
    } else if (response.includes(';')) {
        parseAIResponse(';');
    } else if (response.includes('|')) {
        parseAIResponse('|');
    } else {
        alert('❌ Could not detect delimiter. Use comma, tab, semicolon, or pipe.');
        return;
    }
}

function autoParseAIResponse() {
    // This won't be called - user uses the button instead
    // Kept for compatibility
}

function parseAIResponse(delimiter) {
    var response = document.getElementById('ai-response').value;
    if (!response.trim() || !importState.stocks || importState.stocks.length === 0) {
        return;
    }
    
    var lines = response.split(/\r?\n/).filter(function(l) { return l.trim().length > 0; });
    var matched = 0;
    
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (line.length === 0) continue;
        
        var parts = line.split(delimiter).map(function(p) { return p.trim(); });
        if (parts.length < 1) continue;
        
        var name = parts[0];
        
        // Skip header rows
        if (name.toLowerCase() === 'name' || name.toLowerCase() === 'stock name' || 
            name.toLowerCase() === 'ticker' || name.toLowerCase() === 'symbol') continue;
        
        // Find matching stock from Step 1
        var stock = importState.stocks.find(function(s) { 
            return s.name && s.name.toLowerCase().trim() === name.toLowerCase().trim(); 
        });
        
        if (stock) {
            // Enrich with additional data
            if (parts[1]) stock.ticker = parts[1];
            if (parts[2]) stock.isin = parts[2];
            if (parts[3]) stock.sector = parts[3];
            if (parts[4]) stock.industry = parts[4];
            stock.status = 'enriched';
            matched++;
        }
    }
    
    var status = document.getElementById('step4-status');
    if (status) {
        if (matched > 0) {
            status.innerHTML = '<div style="color:#00ff88;font-weight:bold;">✅ Enriched ' + matched + '/' + 
                importState.stocks.length + ' stocks</div>';
        } else {
            status.innerHTML = '<div style="color:#ffb347;">⚠️ No matching stocks found</div>';
        }
    }
    
    showImportUI();
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 5: Edit & Validate
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep5() {
    var html = '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Review & Edit</h3>' +
        '<div style="margin:10px 0;overflow-x:auto;border:1px solid #111;border-radius:8px;max-height:400px;overflow-y:auto;">' +
        '<table style="width:100%;border-collapse:collapse;font-size:9px;line-height:1.3;">' +
        '<tr style="background:#111;border-bottom:1px solid #222;position:sticky;top:0;">' +
        '<th style="padding:4px 6px;text-align:left;color:#00ff88;">Name</th>' +
        '<th style="padding:4px 6px;text-align:left;color:#00ff88;">ISIN</th>' +
        '<th style="padding:4px 6px;text-align:left;color:#00ff88;">Sector</th>' +
        '<th style="padding:4px 6px;text-align:right;color:#00ff88;">Qty</th>' +
        '<th style="padding:4px 6px;text-align:right;color:#00ff88;">Avg</th>' +
        '<th style="padding:4px 6px;text-align:center;color:#00ff88;">Del</th>' +
        '</tr>';
    
    importState.stocks.forEach(function(stock, idx) {
        var statusColor = stock.status === 'enriched' ? '#00ff88' : '#ffb347';
        var statusIcon = stock.status === 'enriched' ? '✅' : '⚠️';
        
        html += '<tr style="border-bottom:0.5px solid #111;background:#050505;">' +
            '<td style="padding:4px 6px;" onclick="editCell(this, ' + idx + ', \'name\')">' +
            stock.name.substring(0, 25) + '</td>' +
            '<td style="padding:4px 6px;color:' + statusColor + ';font-weight:bold;" onclick="editCell(this, ' + idx + ', \'isin\')">' +
            statusIcon + ' ' + (stock.isin || '-') + '</td>' +
            '<td style="padding:4px 6px;" onclick="editCell(this, ' + idx + ', \'sector\')">' +
            (stock.sector || '-') + '</td>' +
            '<td style="padding:4px 6px;text-align:right;" onclick="editCell(this, ' + idx + ', \'qty\')">' +
            stock.qty + '</td>' +
            '<td style="padding:4px 6px;text-align:right;" onclick="editCell(this, ' + idx + ', \'avg\')">' +
            '₹' + stock.avg.toFixed(2) + '</td>' +
            '<td style="padding:4px 6px;text-align:center;">' +
            '<button class="step5-delete-btn" data-idx="' + idx + '" onclick="deleteStock(' + idx + '); return false;" style="background:#ff6b85;color:#fff;border:none;padding:2px 4px;border-radius:2px;cursor:pointer;font-size:8px;">✕</button>' +
            '</td></tr>';
    });
    
    html += '</table></div>' +
        '<div style="margin:15px 0;font-size:11px;color:#888;">' +
        'Total: ' + importState.stocks.length + ' stocks' +
        '</div>' +
        '<div style="display:flex;gap:10px;margin-top:15px;">' +
        '<button onclick="importState.step = 4; showImportUI();" style="flex:1;padding:10px;background:#444;color:#fff;border:none;border-radius:6px;cursor:pointer;">← Back</button>' +
        '<button onclick="saveAndContinue();" style="flex:1;padding:10px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">Save & Continue →</button>' +
        '</div>' +
        '</div>';
    
    return html;
}

function editCell(cell, idx, field) {
    var stock = importState.stocks[idx];
    var currentValue = stock[field] || '';
    var newValue = prompt('Edit ' + field + ':', currentValue);
    
    if (newValue !== null) {
        if (field === 'qty' || field === 'avg') {
            stock[field] = newValue ? parseFloat(newValue) : null;
        } else {
            stock[field] = newValue;
        }
        showImportUI();
    }
}

function deleteStock(idx) {
    showDebugLog('🗑️ deleteStock(' + idx + ') called');
    
    // Validate index
    if (typeof idx !== 'number' || idx < 0 || idx >= importState.stocks.length) {
        showDebugLog('❌ Invalid stock index: ' + idx);
        console.error('Invalid stock index:', idx);
        return;
    }
    
    var stock = importState.stocks[idx];
    if (!stock || !stock.name) {
        showDebugLog('❌ Stock not found at index ' + idx);
        console.error('Stock not found at index', idx);
        return;
    }
    
    var stockName = stock.name;
    showDebugLog('🗑️ Deleting: ' + stockName);
    
    if (confirm('🗑️ Delete: ' + stockName + '?')) {
        showDebugLog('✅ User confirmed delete');
        importState.stocks.splice(idx, 1);
        showDebugLog('✅ Removed from array. Remaining: ' + importState.stocks.length);
        
        // Force UI refresh
        setTimeout(function() {
            showDebugLog('🔄 Re-rendering UI...');
            showImportUI();
            attachDeleteListeners();
            showDebugLog('✅ UI refreshed');
        }, 50);
    } else {
        showDebugLog('⚠️ User cancelled delete');
    }
}

// Attach event listeners to delete buttons
function attachDeleteListeners() {
    setTimeout(function() {
        var deleteButtons = document.querySelectorAll('.step5-delete-btn');
        showDebugLog('📌 Found ' + deleteButtons.length + ' delete buttons');
        
        deleteButtons.forEach(function(btn, i) {
            // Remove old listener
            btn.removeEventListener('click', handleDeleteClick);
            
            // Add new listener
            btn.addEventListener('click', handleDeleteClick);
            
            if (i === 0) {
                showDebugLog('✅ Attached listeners to delete buttons');
            }
        });
    }, 100);
}

function handleDeleteClick(e) {
    e.preventDefault();
    e.stopPropagation();
    
    var idx = parseInt(this.getAttribute('data-idx'));
    showDebugLog('🖱️ Delete button clicked: index=' + idx);
    deleteStock(idx);
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 6: Save to IndexedDB
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep6() {
    // Step 6 removed - save happens automatically in Step 5
    return '';
}

function saveToIndexedDB(callback) {
    // Save to IndexedDB with callback for chaining
    showDebugLog('💾 saveToIndexedDB() - Saving ' + importState.stocks.length + ' stocks');
    
    if (importState.stocks.length === 0) {
        showDebugLog('⚠️ No stocks to save');
        if (callback) callback(false);
        return;
    }
    
    try {
        // Use correct database that index.html uses
        var request = indexedDB.open('OnyxPortfolioDB', 8);
        showDebugLog('📂 Opening database: OnyxPortfolioDB v8');
        
        request.onerror = function() {
            console.error('❌ Database error');
            showDebugLog('❌ Database open error: ' + request.error);
            if (callback) callback(false);
        };
        
        request.onsuccess = function(e) {
            var db = e.target.result;
            showDebugLog('✅ Database opened');
            
            var tx = db.transaction('Stocks', 'readwrite');
            var store = tx.objectStore('Stocks');
            showDebugLog('📝 Transaction started on Stocks store');
            
            // Append to existing data (don't clear)
            var savedCount = 0;
            importState.stocks.forEach(function(stock, idx) {
                var record = {
                    SYM: stock.ticker || stock.symbol || stock.name.substring(0, 10),
                    NAME: stock.name,
                    ISIN: stock.isin || '',
                    SECTOR: stock.sector || '',
                    INDUSTRY: stock.industry || '',
                    TYPE: (stock.type || 'PORTFOLIO').toUpperCase(),
                    QTY: parseFloat(stock.qty) || 0,
                    AVG: parseFloat(stock.avg) || 0,
                    source: 'import'
                };
                
                if (idx === 0) {
                    showDebugLog('First record to save: SYM=' + record.SYM + ', QTY=' + record.QTY + ', AVG=' + record.AVG);
                }
                
                store.put(record);
                savedCount++;
            });
            
            showDebugLog('📤 Queued ' + savedCount + ' records for save');
            
            tx.oncomplete = function() {
                showDebugLog('✅ Transaction complete - ' + savedCount + ' stocks saved!');
                if (callback) callback(true);
            };
            
            tx.onerror = function() {
                console.error('❌ Transaction error:', tx.error);
                showDebugLog('❌ Transaction error: ' + (tx.error ? tx.error.name : 'unknown'));
                if (callback) callback(false);
            };
        };
    } catch(err) {
        console.error('Error:', err.message);
        showDebugLog('❌ Exception: ' + err.message);
        if (callback) callback(false);
    }
}

// New function: Save and continue to Step 7
function saveAndContinue() {
    console.log('🔵 saveAndContinue() called');
    console.log('Stocks to save:', importState.stocks);
    console.log('First stock:', importState.stocks[0]);
    
    var btn = document.querySelector('button[onclick="saveAndContinue()"]');
    if (btn) btn.disabled = true;
    
    showDebugLog('📝 Saving ' + importState.stocks.length + ' stocks...');
    
    saveToIndexedDB(function(success) {
        if (success) {
            console.log('✅ Save successful');
            showDebugLog('✅ Save successful! Moving to Step 7...');
            importState.step = 7;
            showImportUI();
            attachDeleteListeners();
        } else {
            console.error('❌ Save failed');
            showDebugLog('❌ Save failed - check first stock:' + JSON.stringify(importState.stocks[0]));
            if (btn) btn.disabled = false;
        }
    });
}

// Add debug log to page
function showDebugLog(message) {
    var debugDiv = document.getElementById('debug-log');
    if (!debugDiv) {
        debugDiv = document.createElement('div');
        debugDiv.id = 'debug-log';
        debugDiv.style.cssText = 'position:fixed;bottom:80px;left:10px;right:10px;background:#111;' +
            'border:1px solid #00ff88;color:#00ff88;padding:10px;font-size:11px;' +
            'max-height:200px;overflow-y:auto;z-index:10000;border-radius:6px;font-family:monospace;';
        document.body.appendChild(debugDiv);
    }
    var timestamp = new Date().toLocaleTimeString();
    debugDiv.innerHTML += '[' + timestamp + '] ' + message + '<br>';
    debugDiv.scrollTop = debugDiv.scrollHeight;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 7: Post to GitHub - PROPER UI WITH CONFIG & CONFIRMATION
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep7() {
    var ghPAT = localStorage.getItem('ghPAT') || '';
    var ghUser = localStorage.getItem('ghUser') || '';
    var ghRepo = localStorage.getItem('ghRepo') || '';
    var isPATConfigured = ghPAT && ghUser && ghRepo;
    
    // Calculate counts
    var portfolioCount = importState.stocks.filter(function(s) { 
        return (s.type || '').toUpperCase() === 'PORTFOLIO'; 
    }).length;
    var watchlistCount = importState.stocks.filter(function(s) { 
        return (s.type || '').toUpperCase() === 'WATCHLIST'; 
    }).length;
    
    var html = '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 15px 0;color:#00ff88;font-size:16px;">✅ Saved to Database</h3>';
    
    // Add counts display
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:15px;margin:15px 0;">' +
        '<div style="background:#001a00;padding:15px;border-radius:8px;border:1px solid #00ff88;text-align:center;">' +
            '<div style="font-size:28px;color:#00ff88;font-weight:bold;">' + portfolioCount + '</div>' +
            '<div style="font-size:12px;color:#888;margin-top:8px;">Portfolio Stocks</div>' +
        '</div>' +
        '<div style="background:#1a0000;padding:15px;border-radius:8px;border:1px solid #ff6b85;text-align:center;">' +
            '<div style="font-size:28px;color:#ff6b85;font-weight:bold;">' + watchlistCount + '</div>' +
            '<div style="font-size:12px;color:#888;margin-top:8px;">Watchlist Stocks</div>' +
        '</div>' +
    '</div>';
    
    html += '<div style="margin:15px 0;padding:12px;background:#111;border-radius:8px;border-left:3px solid #00ff88;color:#00ff88;font-size:12px;">' +
        '✅ Data saved to IndexedDB. Ready for portfolio view!' +
    '</div>';
    
    html += '<h4 style="margin:20px 0 10px 0;color:#ffb347;font-size:14px;">📤 Optional: Backup to GitHub</h4>';
    
    // PAT Configuration Section
    html += '<div style="margin:15px 0;padding:15px;background:#111;border-radius:8px;border-left:3px solid ' + 
        (isPATConfigured ? '#00ff88' : '#ffb347') + ';">' +
        '<div style="color:' + (isPATConfigured ? '#00ff88' : '#ffb347') + ';font-weight:bold;margin-bottom:10px;">' +
        (isPATConfigured ? '✅ GitHub Configured' : '⚠️ Configure GitHub') +
        '</div>';
    
    if (isPATConfigured) {
        html += '<div style="font-size:11px;color:#888;">' +
            'User: <b>' + ghUser + '</b><br>' +
            'Repo: <b>' + ghRepo + '</b><br>' +
            'PAT: <b>' + ghPAT.substring(0, 10) + '...</b>' +
            '</div>' +
            '<button onclick="toggleGitHubConfig()" style="margin-top:10px;padding:8px 16px;background:#444;' +
            'color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:11px;">Edit Config</button>';
    } else {
        html += '<div id="github-config" style="display:none;margin-bottom:10px;">';
        html += '<div style="margin:8px 0;">' +
            '<label style="color:#888;font-size:11px;">GitHub PAT:</label><br>' +
            '<input type="password" id="ghPAT" placeholder="ghp_xxxxxxxxxxxxx" style="width:100%;padding:8px;' +
            'background:#000;border:1px solid #222;color:#fff;border-radius:4px;font-family:monospace;font-size:11px;margin-top:4px;' +
            'box-sizing:border-box;">' +
            '</div>';
        html += '<div style="margin:8px 0;">' +
            '<label style="color:#888;font-size:11px;">GitHub User:</label><br>' +
            '<input type="text" id="ghUser" placeholder="murugkan" style="width:100%;padding:8px;' +
            'background:#000;border:1px solid #222;color:#fff;border-radius:4px;font-size:11px;margin-top:4px;' +
            'box-sizing:border-box;">' +
            '</div>';
        html += '<div style="margin:8px 0;">' +
            '<label style="color:#888;font-size:11px;">GitHub Repo:</label><br>' +
            '<input type="text" id="ghRepo" placeholder="bharatmarkets" style="width:100%;padding:8px;' +
            'background:#000;border:1px solid #222;color:#fff;border-radius:4px;font-size:11px;margin-top:4px;' +
            'box-sizing:border-box;">' +
            '</div>';
        html += '<button onclick="saveGitHubConfig()" style="margin-top:10px;padding:8px 16px;background:#00ff88;' +
            'color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:11px;">Save Config</button>' +
            '</div>' +
            '<button onclick="toggleGitHubConfig()" style="padding:8px 16px;background:#444;color:#fff;' +
            'border:none;border-radius:6px;cursor:pointer;font-size:11px;">Configure GitHub</button>';
    }
    
    html += '</div>';
    
    // Append vs Replace Option
    html += '<div style="margin:15px 0;padding:15px;background:#050505;border:1px solid #222;border-radius:8px;">' +
        '<div style="color:#00ff88;font-weight:bold;margin-bottom:10px;">📥 Import Mode</div>' +
        '<div style="display:flex;gap:10px;">' +
        '<button onclick="setImportMode(\'append\')" id="btn-append" style="flex:1;padding:10px;' +
        'background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;' +
        'font-size:12px;">➕ APPEND to Portfolio</button>' +
        '<button onclick="setImportMode(\'replace\')" id="btn-replace" style="flex:1;padding:10px;' +
        'background:#333;color:#fff;border:none;border-radius:6px;cursor:pointer;font-weight:bold;' +
        'font-size:12px;">🔄 REPLACE Portfolio</button>' +
        '</div>' +
        '<div style="margin-top:8px;font-size:10px;color:#888;">' +
        '<b>APPEND:</b> Add new stocks to existing portfolio<br>' +
        '<b>REPLACE:</b> Clear portfolio and import fresh' +
        '</div>' +
        '</div>';
    
    // Data Summary
    if (isPATConfigured) {
        html += '<div style="margin:15px 0;padding:15px;background:#050505;border:1px solid #222;border-radius:8px;' +
            'font-size:12px;color:#888;">' +
            '<b style="color:#00ff88;">📊 Data to Post:</b><br><br>' +
            '<div style="display:flex;justify-content:space-around;margin:10px 0;">' +
            '<div>✅ Portfolio<br><b style="color:#00ff88;font-size:14px;">' + 
            importState.stocks.filter(function(s) { return s.type === 'PORTFOLIO'; }).length + '</b></div>' +
            '<div>📌 Watchlist<br><b style="color:#ffb347;font-size:14px;">' + 
            importState.stocks.filter(function(s) { return s.type === 'WATCHLIST'; }).length + '</b></div>' +
            '<div>💾 Total<br><b style="color:#00ff88;font-size:14px;">' + importState.stocks.length + '</b></div>' +
            '</div>' +
            '<div style="margin-top:10px;padding-top:10px;border-top:1px solid #333;font-size:11px;">' +
            'File: <b>unified-symbols.json</b><br>' +
            'Each stock includes: sym, name, isin, sector, industry, type, source' +
            '</div>' +
            '</div>';
        
        // JSON Preview
        html += '<button onclick="toggleJSONPreview()" style="padding:10px 20px;background:#444;color:#fff;' +
            'border:none;border-radius:6px;cursor:pointer;font-size:12px;margin-bottom:10px;">' +
            '📋 Preview JSON</button>';
        
        html += '<div id="json-preview" style="display:none;margin:10px 0;padding:10px;background:#000;' +
            'border:1px solid #222;border-radius:6px;max-height:300px;overflow-y:auto;font-size:9px;' +
            'font-family:monospace;color:#0f0;"></div>';
        
        // Post Button
        html += '<button onclick="postToGitHub()" style="padding:12px 24px;background:#00ff88;color:#000;' +
            'border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:14px;width:100%;' +
            'margin-top:15px;">📤 Post to GitHub</button>';
    }
    
    html += '<div id="step7-status" style="margin:15px 0;font-size:12px;"></div>';
    html += '</div>';
    
    return html;
}

function toggleGitHubConfig() {
    var configDiv = document.getElementById('github-config');
    if (configDiv) {
        configDiv.style.display = configDiv.style.display === 'none' ? 'block' : 'none';
    }
}

function saveGitHubConfig() {
    var pat = document.getElementById('ghPAT').value;
    var user = document.getElementById('ghUser').value;
    var repo = document.getElementById('ghRepo').value;
    
    if (!pat || !user || !repo) {
        alert('Please fill all fields');
        return;
    }
    
    localStorage.setItem('ghPAT', pat);
    localStorage.setItem('ghUser', user);
    localStorage.setItem('ghRepo', repo);
    
    alert('✅ GitHub configuration saved!');
    showImportUI();
}

function toggleJSONPreview() {
    var preview = document.getElementById('json-preview');
    if (preview.style.display === 'none') {
        preview.style.display = 'block';
        generateJSONPreview();
    } else {
        preview.style.display = 'none';
    }
}

function generateJSONPreview() {
    var unifiedData = {
        updated: new Date().toISOString(),
        count: importState.stocks.length,
        symbols: []
    };
    
    importState.stocks.forEach(function(stock) {
        var ticker = stock.ticker || '?';
        unifiedData.symbols.push({
            ticker: ticker,
            name: stock.name,
            isin: stock.isin,
            sector: stock.sector,
            industry: stock.industry,
            type: stock.type.toLowerCase(),
            source: 'import'
        });
    });
    
    unifiedData.symbols.sort(function(a, b) {
        return a.ticker.localeCompare(b.ticker);
    });
    
    var jsonString = JSON.stringify(unifiedData, null, 2);
    var preview = document.getElementById('json-preview');
    preview.innerHTML = jsonString.replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function generateSymbol(name) {
    var words = name.split(' ');
    var sym = '';
    words.forEach(function(w) {
        if (w.length > 0 && w[0] !== '&') {
            sym += w[0].toUpperCase();
        }
    });
    return sym.substring(0, 10);
}

function setImportMode(mode) {
    importState.importMode = mode;
    
    // Update button styles
    var btnAppend = document.getElementById('btn-append');
    var btnReplace = document.getElementById('btn-replace');
    
    if (mode === 'append') {
        btnAppend.style.background = '#00ff88';
        btnAppend.style.color = '#000';
        btnReplace.style.background = '#333';
        btnReplace.style.color = '#fff';
    } else {
        btnAppend.style.background = '#333';
        btnAppend.style.color = '#fff';
        btnReplace.style.background = '#00ff88';
        btnReplace.style.color = '#000';
    }
}

function postToGitHub() {
    var ghPAT = localStorage.getItem('ghPAT');
    var ghUser = localStorage.getItem('ghUser');
    var ghRepo = localStorage.getItem('ghRepo');
    
    if (!ghPAT || !ghUser || !ghRepo) {
        alert('GitHub not configured');
        return;
    }
    
    if (!confirm('Post ' + importState.stocks.length + ' stocks (' + importState.importMode.toUpperCase() + ' mode) to unified-symbols.json?')) {
        return;
    }
    
    var status = document.getElementById('step7-status');
    status.innerHTML = '<span style="color:#ffb347;">⏳ Preparing data...</span>';
    
    // Build JSON based on import mode
    var unifiedData = {
        updated: new Date().toISOString(),
        count: importState.stocks.length,
        symbols: []
    };
    
    // In REPLACE mode, start fresh; in APPEND mode, we'll merge later
    var stocksToSave = importState.stocks;
    
    if (importState.importMode === 'replace') {
        // Clear all existing stocks - just use new stocks
        stocksToSave = importState.stocks;
        unifiedData.count = stocksToSave.length;
    } else {
        // APPEND mode - will merge with existing (handled in GitHub fetch)
        // For now just save the new stocks
        unifiedData.count = stocksToSave.length;
    }
    
    stocksToSave.forEach(function(stock) {
        var ticker = stock.ticker || '?';
        unifiedData.symbols.push({
            ticker: ticker,
            name: stock.name,
            isin: stock.isin,
            sector: stock.sector,
            industry: stock.industry,
            type: stock.type.toLowerCase(),
            source: 'import',
            qty: stock.qty || 0,
            avg: stock.avg || 0
        });
    });
    
    unifiedData.symbols.sort(function(a, b) {
        return a.ticker.localeCompare(b.ticker);
    });
    
    var jsonContent = JSON.stringify(unifiedData, null, 2);
    var base64Content = btoa(unescape(encodeURIComponent(jsonContent)));
    
    status.innerHTML = '<span style="color:#ffb347;">⏳ Connecting to GitHub...</span>';
    
    var apiUrl = 'https://api.github.com/repos/' + ghUser + '/' + ghRepo + '/contents/unified-symbols.json';
    
    // Get current SHA and optionally existing data (for APPEND mode)
    fetch(apiUrl, {
        headers: {
            'Authorization': 'token ' + ghPAT,
            'Accept': 'application/vnd.github.v3+json'
        }
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
        var sha = data.sha || undefined;
        var finalData = unifiedData;
        
        // In APPEND mode, fetch and merge existing data
        if (importState.importMode === 'append' && data.content) {
            try {
                var existingContent = atob(data.content);
                var existingData = JSON.parse(existingContent);
                
                if (existingData.symbols) {
                    // Create map of new stocks by ticker
                    var newTickers = {};
                    unifiedData.symbols.forEach(function(s) {
                        newTickers[s.ticker] = s;
                    });
                    
                    // Keep existing stocks that aren't being replaced
                    var mergedSymbols = existingData.symbols.filter(function(existing) {
                        return !newTickers[existing.ticker];
                    });
                    
                    // Add new stocks
                    mergedSymbols = mergedSymbols.concat(unifiedData.symbols);
                    
                    // Update final data
                    finalData.symbols = mergedSymbols;
                    finalData.count = mergedSymbols.length;
                }
            } catch(e) {
                console.log('Could not parse existing data, will replace:', e);
            }
        }
        
        // Sort by ticker
        finalData.symbols.sort(function(a, b) {
            return a.ticker.localeCompare(b.ticker);
        });
        
        var jsonContent = JSON.stringify(finalData, null, 2);
        var base64Content = btoa(unescape(encodeURIComponent(jsonContent)));
        
        status.innerHTML = '<span style="color:#ffb347;">⏳ Posting to GitHub...</span>';
        
        return fetch(apiUrl, {
            method: 'PUT',
            headers: {
                'Authorization': 'token ' + ghPAT,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: importState.importMode.toUpperCase() + ': ' + importState.stocks.length + ' stocks',
                content: base64Content,
                sha: sha
            })
        });
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
        if (data.commit && data.commit.sha) {
            status.innerHTML = '<div style="color:#00ff88;"><b>✅ Posted Successfully!</b></div>' +
                '<div style="margin:10px 0;font-size:11px;color:#888;">' +
                'Mode: <b>' + importState.importMode.toUpperCase() + '</b><br>' +
                'Message: ' + data.commit.message + '<br>' +
                'SHA: ' + data.commit.sha.substring(0, 10) + '...<br>' +
                'File: ' + data.content.name + '<br><br>' +
                '<b style="color:#00ff88;">' + importState.stocks.length + ' stocks imported</b>' +
                '</div>';
        } else {
            status.innerHTML = '<span style="color:#ff6b85;">❌ Error: ' + (data.message || 'Unknown error') + '</span>';
        }
    })
    .catch(function(err) {
        status.innerHTML = '<span style="color:#ff6b85;">❌ Error: ' + err.message + '</span>';
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Navigation & Cleanup
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function nextImportStep() {
    if (importState.step < 7) {
        importState.step++;
        showImportUI();
    }
}

function prevImportStep() {
    if (importState.step > 1) {
        importState.step--;
        showImportUI();
    }
}

function closeImportModal() {
    var modal = document.getElementById('import-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    document.body.classList.remove('modal-open');
}
