/**
 * app-import.js - Enhanced Import Workflow (FULLY ENHANCED)
 * Step 1: FIXED CSV/TSV/XLS parsing with intelligent column detection
 * Handles: Comma-separated, Tab-separated, Multi-word headers
 * FIXED: Column matching for StockName, Quantity, AverageCostPrice format
 */

var importState = {
    step: 1,
    stocks: [],
    aiResponse: null,
    debugInfo: ''  // Track parsing info for troubleshooting
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// MAIN: Open Import Workflow
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function openImportWorkflow() {
    importState.step = 1;
    importState.stocks = [];
    importState.debugInfo = '';
    showImportUI();
}

function showImportUI() {
    var html = '<div id="import-wizard" style="' +
        'padding:20px;background:#0a0a0a;border-radius:12px;max-width:900px;' +
        '">';
    
    // Step indicator
    html += '<div style="margin-bottom:10px;font-size:12px;color:#555;font-family:monospace;">' +
        'Step ' + importState.step + ' of 7: ';
    
    var stepTitles = ['Upload CSV/XLS', 'Manual Entries', 'AI Prompt', 'Paste Response', 'Edit & Validate', 'Save to DB', 'Post to GitHub'];
    html += stepTitles[importState.step - 1];
    html += '</div>';
    
    // TOP BUTTONS
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
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 1: Upload CSV/TSV/XLS - ENHANCED PARSING
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep1() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Upload Stock List</h3>' +
        '<div style="padding:10px;background:#111;border-left:3px solid #00ff88;margin:10px 0;font-size:11px;color:#888;border-radius:4px;">' +
        '<b style="color:#00ff88;">Supported Formats:</b><br>' +
        '✓ CSV (comma-separated)<br>' +
        '✓ TSV (tab-separated)<br>' +
        '✓ Excel XLS/XLSX<br>' +
        '✓ TXT files<br><br>' +
        '<b style="color:#00ff88;">Required Columns:</b><br>' +
        'Stock Name + (Quantity OR Average Price)<br><br>' +
        '<b style="color:#ffb347;">Column names can include:</b><br>' +
        'StockName, Symbol, Name, Quantity, Qty, Shares, AverageCostPrice, Average, Cost, Price<br>' +
        '</div>' +
        '<div style="margin:15px 0;padding:20px;border:2px dashed #222;border-radius:8px;' +
        'text-align:center;cursor:pointer;background:#050505;position:relative;" ' +
        'id="drop-zone" onclick="document.getElementById(\'file-input\').click();" ondrop="handleDrop(event)" ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)">' +
        '<div style="font-size:32px;margin-bottom:10px;">📁</div>' +
        '<div style="color:#fff;font-weight:bold;margin-bottom:5px;">Click to upload or drag & drop</div>' +
        '<div style="color:#666;font-size:12px;">CSV, TSV, Excel, or TXT files</div>' +
        '</div>' +
        '<input type="file" id="file-input" accept=".csv,.xls,.xlsx,.tsv,.txt" style="display:none;" ' +
        'onchange="handleImportFile(this.files[0])">' +
        '<div id="file-status" style="margin:10px 0;font-size:12px;color:#666;"></div>' +
        '<div id="step1-preview" style="margin:10px 0;"></div>' +
        '<div id="step1-debug" style="margin:10px 0;padding:10px;background:#000;border:1px solid #222;border-radius:6px;font-size:9px;font-family:monospace;color:#666;display:none;"></div>' +
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
                processImportCSV(e.target.result, file.name);
                status.innerHTML = '<span style="color:#00ff88;">✅ File parsed successfully</span>';
                renderStep1Preview();
            } catch(err) {
                var errMsg = err.message.split('\n\nDEBUG INFO:');
                var mainError = errMsg[0];
                var debugInfo = errMsg[1] ? '\n\nDEBUG INFO:' + errMsg[1] : '';
                status.innerHTML = '<span style="color:#ff6b85;">❌ Parse error: ' + mainError + '</span>' +
                    (debugInfo ? '<div style="margin-top:10px;padding:8px;background:#000;border:1px solid #222;border-radius:4px;font-size:9px;font-family:monospace;color:#666;white-space:pre-wrap;overflow-x:auto;">' + debugInfo.replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</div>' : '');
            }
        };
        reader.onerror = function() {
            status.innerHTML = '<span style="color:#ff6b85;">❌ Error reading file</span>';
        };
        reader.readAsText(file);
    } else if (ext === 'xls' || ext === 'xlsx') {
        loadSheetJS(function(success) {
            if (!success) {
                status.innerHTML = '<span style="color:#ff6b85;">❌ Failed to load Excel library. Using alternative method...</span>';
                // Try to process as text anyway
                var reader = new FileReader();
                reader.onload = function(e) {
                    status.innerHTML = '<span style="color:#ffb347;">⚠️ Excel file detected but library unavailable. Please convert to CSV and try again.</span>';
                };
                reader.readAsText(file);
                return;
            }
            
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
                    processImportCSV(csv, file.name);
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
        status.innerHTML = '<span style="color:#ff6b85;">❌ Unsupported file type. Use CSV, TSV, Excel, or TXT.</span>';
    }
}

var _sheetJSLoaded = false;
function loadSheetJS(cb) {
    if (_sheetJSLoaded) { cb(true); return; }
    if (window.XLSX) { _sheetJSLoaded = true; cb(true); return; }
    
    var script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.min.js';
    script.onload = function() { 
        _sheetJSLoaded = true; 
        cb(true); 
    };
    script.onerror = function() { 
        cb(false);  // Return false instead of alert
    };
    document.head.appendChild(script);
}

function processImportCSV(csv, filename) {
    var lines = csv.split('\n').map(function(l) { return l.trim(); }).filter(function(l) { return l.length > 0; });
    
    if (lines.length === 0) {
        throw new Error('File is empty');
    }
    
    // Auto-detect delimiter
    var headerLine = lines[0];
    var delimiter = ',';
    var delimCount = {',': 0, '\t': 0, ';': 0};
    
    if (headerLine.includes('\t')) delimiter = '\t';
    else if (headerLine.includes(';')) delimiter = ';';
    
    importState.debugInfo = 'File: ' + filename + '\n' +
        'Delimiter: ' + (delimiter === '\t' ? 'TAB' : delimiter) + '\n' +
        'Total lines: ' + lines.length + '\n';
    
    var headerParts = headerLine.split(delimiter).map(function(p) { return p.trim().toLowerCase(); });
    
    importState.debugInfo += 'Header columns: ' + headerParts.length + '\n';
    importState.debugInfo += 'Headers: ' + headerParts.join(' | ') + '\n\n';
    
    // Find column indices - EXPLICIT matching for YOUR exact file format
    var nameIdx = -1;
    var qtyIdx = -1;
    var avgIdx = -1;
    
    for (var i = 0; i < headerParts.length; i++) {
        var h = headerParts[i];
        
        // Match EXACT column names from your file
        if (h === 'stockname') nameIdx = i;
        if (h === 'quantity') qtyIdx = i;
        if (h === 'averagecostprice') avgIdx = i;
    }
    
    // FALLBACK: If exact match fails, try partial matching
    if (nameIdx === -1) {
        for (var i = 0; i < headerParts.length; i++) {
            var h = headerParts[i];
            if (h.indexOf('stock') !== -1 || h.indexOf('name') !== -1) {
                nameIdx = i;
                break;
            }
        }
    }
    
    if (qtyIdx === -1) {
        for (var i = 0; i < headerParts.length; i++) {
            var h = headerParts[i];
            if (h.indexOf('qty') !== -1 || h.indexOf('quantity') !== -1 || h.indexOf('shares') !== -1) {
                qtyIdx = i;
                break;
            }
        }
    }
    
    if (avgIdx === -1) {
        for (var i = 0; i < headerParts.length; i++) {
            var h = headerParts[i];
            if (h.indexOf('averagecost') !== -1 || h.indexOf('avg') !== -1 || h.indexOf('price') !== -1) {
                avgIdx = i;
                break;
            }
        }
    }
    
    // Default to first 3 columns if still not found
    if (nameIdx === -1) nameIdx = 0;
    if (qtyIdx === -1) qtyIdx = 1;
    if (avgIdx === -1) avgIdx = 2;
    
    importState.debugInfo += 'Column mapping:\n' +
        '  Name: Column ' + (nameIdx + 1) + ' (' + headerParts[nameIdx] + ')\n' +
        '  Qty:  Column ' + (qtyIdx + 1) + ' (' + (headerParts[qtyIdx] || 'NOT FOUND') + ')\n' +
        '  Avg:  Column ' + (avgIdx + 1) + ' (' + (headerParts[avgIdx] || 'NOT FOUND') + ')\n\n';
    
    var stocks = [];
    var seen = new Set();
    var skipped = 0;
    var skipReasons = {};
    
    for (var i = 1; i < lines.length; i++) {
        var line = lines[i].trim();
        if (!line) continue;
        
        var parts = line.split(delimiter).map(function(p) { 
            return p.trim().replace(/['"]/g, '').replace(/[₹₨]/g, '');
        });
        
        if (!parts[0] || parts[0].length === 0) continue;
        
        var name = parts[nameIdx] || parts[0];
        
        // Skip header rows
        if (name.toLowerCase().includes('name') || name.toLowerCase().includes('stock')) continue;
        
        var qty = null;
        var avg = null;
        
        // Parse Quantity
        if (qtyIdx >= 0 && qtyIdx < parts.length && parts[qtyIdx]) {
            var qtyVal = parseFloat(parts[qtyIdx]);
            if (!isNaN(qtyVal) && qtyVal > 0) qty = qtyVal;
        }
        
        // Parse Average Price
        if (avgIdx >= 0 && avgIdx < parts.length && parts[avgIdx]) {
            var avgVal = parseFloat(parts[avgIdx]);
            if (!isNaN(avgVal) && avgVal > 0) avg = avgVal;
        }
        
        // Skip duplicates
        if (seen.has(name)) {
            skipped++;
            skipReasons['duplicate'] = (skipReasons['duplicate'] || 0) + 1;
            continue;
        }
        seen.add(name);
        
        // Add stock if has valid name AND (qty OR avg)
        if (name && (qty || avg)) {
            stocks.push({
                name: name,
                isin: '',
                qty: qty || 0,
                avg: avg || 0,
                sector: '',
                industry: '',
                type: 'PORTFOLIO',
                status: ''
            });
        } else {
            skipped++;
            if (qty && avg) {
                skipReasons['invalid'] = (skipReasons['invalid'] || 0) + 1;
            } else {
                skipReasons['no_data'] = (skipReasons['no_data'] || 0) + 1;
            }
        }
    }
    
    importState.debugInfo += 'Parsing results:\n' +
        '  Loaded: ' + stocks.length + ' stocks\n' +
        '  Skipped: ' + skipped + ' rows\n';
    
    for (var reason in skipReasons) {
        importState.debugInfo += '    - ' + reason + ': ' + skipReasons[reason] + '\n';
    }
    
    if (stocks.length === 0) {
        var debugMsg = '\n\nDEBUG INFO:\n' + importState.debugInfo + '\nColumn mapping:\n' +
            '  Name: Column ' + (nameIdx + 1) + ' (' + headerParts[nameIdx] + ')\n' +
            '  Qty:  Column ' + (qtyIdx + 1) + ' (' + (headerParts[qtyIdx] || 'NOT FOUND') + ')\n' +
            '  Avg:  Column ' + (avgIdx + 1) + ' (' + (headerParts[avgIdx] || 'NOT FOUND') + ')';
        throw new Error('No valid stocks found (skipped: ' + skipped + '). Check column names match: Stock Name, Quantity/Shares, Average Price/Cost' + debugMsg);
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
        '<th style="padding:6px;text-align:right;color:#00ff88;">AVG PRICE</th>' +
        '</tr>';
    
    importState.stocks.forEach(function(stock) {
        var qtyDisplay = stock.qty > 0 ? stock.qty : '<span style="color:#ffb347;">—</span>';
        var avgDisplay = stock.avg > 0 ? '₹' + stock.avg.toFixed(2) : '<span style="color:#ffb347;">—</span>';
        
        html += '<tr style="border-bottom:1px solid #111;">' +
            '<td style="padding:6px;">' + stock.name.substring(0, 35) + '</td>' +
            '<td style="padding:6px;text-align:right;">' + qtyDisplay + '</td>' +
            '<td style="padding:6px;text-align:right;">' + avgDisplay + '</td>' +
            '</tr>';
    });
    
    html += '</table></div>' +
        '<div style="margin:10px 0;font-size:11px;color:#00ff88;">' +
        '✅ Loaded: ' + importState.stocks.length + ' stocks' +
        '</div>' +
        '<div style="margin:10px 0;">' +
        '<button onclick="toggleDebugInfo()" style="padding:6px 12px;background:#333;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:10px;">🔍 Debug Info</button>' +
        '</div>';
    
    document.getElementById('step1-preview').innerHTML = html;
}

function toggleDebugInfo() {
    var debug = document.getElementById('step1-debug');
    if (debug.style.display === 'none') {
        debug.style.display = 'block';
        debug.innerHTML = importState.debugInfo.replace(/\n/g, '<br>');
    } else {
        debug.style.display = 'none';
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 2: Manual Entries
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep2() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Add Manual Entries</h3>' +
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
            var qty = parseFloat(parts[1]) || 0;
            var avg = parseFloat(parts[2]) || 0;
            
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
    });
    
    showImportUI();
    nextImportStep();
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 3-7: Remaining steps
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep3() {
    var prompt = 'Please identify these stocks and provide ISIN, Sector, Industry for each:\n\n';
    importState.stocks.forEach(function(s, i) {
        prompt += (i + 1) + '. ' + s.name + '\n';
    });
    prompt += '\nRespond in this exact format:\n' +
        '1. ISIN|Sector|Industry\n' +
        '2. ISIN|Sector|Industry\n' +
        '... etc\n';
    
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">AI Enrichment Prompt</h3>' +
        '<div style="padding:10px;background:#000;border:1px solid #222;border-radius:6px;font-size:11px;color:#0f0;font-family:monospace;max-height:300px;overflow-y:auto;white-space:pre-wrap;word-wrap:break-word;margin:10px 0;">' +
        prompt +
        '</div>' +
        '<div style="margin:10px 0;">' +
        '<button onclick="copyPrompt()" style="padding:10px 20px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">📋 Copy Prompt</button>' +
        '</div>' +
        '</div>';
}

function copyPrompt() {
    var prompt = 'Please identify these stocks and provide ISIN, Sector, Industry for each:\n\n';
    importState.stocks.forEach(function(s, i) {
        prompt += (i + 1) + '. ' + s.name + '\n';
    });
    prompt += '\nRespond in this exact format:\n1. ISIN|Sector|Industry\n2. ISIN|Sector|Industry\n... etc\n';
    
    navigator.clipboard.writeText(prompt).then(function() {
        alert('✅ Prompt copied! Paste in ChatGPT or Claude');
    });
}

function renderStep4() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Paste AI Response</h3>' +
        '<textarea id="ai-response" style="width:100%;height:200px;padding:10px;background:#000;' +
        'border:1px solid #222;color:#fff;font-family:monospace;font-size:11px;border-radius:6px;resize:vertical;" ' +
        'placeholder="Paste the AI response here..."></textarea>' +
        '<div style="margin:10px 0;">' +
        '<button onclick="parseAIResponse()" style="padding:10px 20px;background:#00ff88;' +
        'color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">Parse Response</button>' +
        '</div>' +
        '<div id="step4-status" style="margin:10px 0;font-size:12px;"></div>' +
        '</div>';
}

function parseAIResponse() {
    var textarea = document.getElementById('ai-response');
    var response = textarea.value.trim();
    
    if (!response) {
        alert('Please paste the AI response');
        return;
    }
    
    var lines = response.split('\n').filter(function(l) { return l.trim().length > 0; });
    var updated = 0;
    
    lines.forEach(function(line, idx) {
        var match = line.match(/^\d+\.\s*(.+?)\|(.+?)\|(.+)$/);
        if (match && idx < importState.stocks.length) {
            importState.stocks[idx].isin = match[1].trim();
            importState.stocks[idx].sector = match[2].trim();
            importState.stocks[idx].industry = match[3].trim();
            updated++;
        }
    });
    
    document.getElementById('step4-status').innerHTML = '<span style="color:#00ff88;">✅ Updated ' + updated + ' stocks</span>';
    nextImportStep();
}

function renderStep5() {
    var html = '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Edit & Validate</h3>' +
        '<div style="margin:15px 0;border:1px solid #222;border-radius:8px;overflow:auto;max-height:400px;">' +
        '<table style="width:100%;border-collapse:collapse;font-size:10px;">' +
        '<tr style="background:#111;border-bottom:1px solid #222;position:sticky;top:0;">' +
        '<th style="padding:4px;text-align:left;color:#00ff88;">Stock Name</th>' +
        '<th style="padding:4px;text-align:center;color:#00ff88;">Type</th>' +
        '<th style="padding:4px;text-align:right;color:#00ff88;">Action</th>' +
        '</tr>';
    
    importState.stocks.forEach(function(stock, idx) {
        html += '<tr style="border-bottom:1px solid #111;">' +
            '<td style="padding:4px;">' + stock.name.substring(0, 20) + '</td>' +
            '<td style="padding:4px;text-align:center;">' +
            '<select id="type' + idx + '" style="background:#000;color:#fff;border:1px solid #333;padding:2px 4px;border-radius:3px;font-size:9px;">' +
            '<option value="PORTFOLIO"' + (stock.type === 'PORTFOLIO' ? ' selected' : '') + '>Portfolio</option>' +
            '<option value="WATCHLIST"' + (stock.type === 'WATCHLIST' ? ' selected' : '') + '>Watchlist</option>' +
            '</select>' +
            '</td>' +
            '<td style="padding:4px;text-align:right;">' +
            '<button onclick="deleteStock(' + idx + ')" style="padding:2px 6px;background:#ff6b85;color:#fff;border:none;border-radius:3px;cursor:pointer;font-size:9px;">Delete</button>' +
            '</td>' +
            '</tr>';
    });
    
    html += '</table></div>' +
        '<div style="margin:10px 0;font-size:11px;color:#888;">Total: ' + importState.stocks.length + ' stocks</div>' +
        '</div>';
    
    return html;
}

function deleteStock(idx) {
    importState.stocks.splice(idx, 1);
    showImportUI();
}

function renderStep6() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Save to Database</h3>' +
        '<div style="padding:10px;background:#111;border-left:3px solid #00ff88;margin:10px 0;font-size:11px;color:#888;border-radius:4px;">' +
        'This will save your ' + importState.stocks.length + ' stocks to the local database (IndexedDB).' +
        '</div>' +
        '<button onclick="saveToIndexedDB()" style="padding:12px 24px;background:#00ff88;color:#000;' +
        'border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:14px;width:100%;margin-bottom:10px;">💾 Save to DB</button>' +
        '<div id="step6-status" style="margin:10px 0;font-size:12px;"></div>' +
        '</div>';
}

function saveToIndexedDB() {
    if (!importState.stocks || importState.stocks.length === 0) {
        alert('No stocks to save');
        return;
    }
    
    openDB('BharatEngineDB', 1, function(db) {
        var tx = db.transaction('UnifiedStocks', 'readwrite');
        var store = tx.objectStore('UnifiedStocks');
        
        importState.stocks.forEach(function(stock) {
            store.put({
                sym: stock.name.toUpperCase().substring(0, 10),
                name: stock.name,
                isin: stock.isin,
                sector: stock.sector,
                industry: stock.industry,
                type: stock.type,
                qty: stock.qty,
                avg: stock.avg,
                source: 'import'
            });
        });
        
        tx.oncomplete = function() {
            document.getElementById('step6-status').innerHTML = 
                '<span style="color:#00ff88;">✅ Saved ' + importState.stocks.length + ' stocks to database!</span>';
        };
        
        tx.onerror = function() {
            document.getElementById('step6-status').innerHTML = 
                '<span style="color:#ff6b85;">❌ Database error: ' + tx.error + '</span>';
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
    req.onerror = function() { alert('DB error'); };
}

function renderStep7() {
    var hasGH = localStorage.getItem('ghPAT') && localStorage.getItem('ghUser') && localStorage.getItem('ghRepo');
    
    var html = '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">GitHub Sync (Optional)</h3>';
    
    if (!hasGH) {
        html += '<div style="padding:10px;background:#111;border-left:3px solid #ffb347;margin:10px 0;font-size:11px;color:#ffb347;border-radius:4px;">' +
            '⚠️ GitHub not configured. Configure below to enable sync.' +
            '</div>';
        html += '<button onclick="toggleGitHubConfig()" style="padding:10px 20px;background:#444;color:#fff;' +
            'border:none;border-radius:6px;cursor:pointer;font-size:12px;margin-bottom:10px;">⚙️ Configure GitHub</button>';
        
        html += '<div id="github-config" style="display:none;padding:15px;background:#111;border:1px solid #222;border-radius:6px;margin:10px 0;">' +
            '<div style="margin-bottom:10px;">' +
            '<label style="color:#00ff88;font-size:11px;display:block;margin-bottom:4px;">GitHub PAT (Personal Access Token)</label>' +
            '<input type="password" id="ghPAT" style="width:100%;padding:6px;background:#000;border:1px solid #222;color:#fff;border-radius:4px;font-size:11px;" placeholder="ghp_...">' +
            '</div>' +
            '<div style="margin-bottom:10px;">' +
            '<label style="color:#00ff88;font-size:11px;display:block;margin-bottom:4px;">GitHub Username</label>' +
            '<input type="text" id="ghUser" style="width:100%;padding:6px;background:#000;border:1px solid #222;color:#fff;border-radius:4px;font-size:11px;" placeholder="your-username">' +
            '</div>' +
            '<div style="margin-bottom:10px;">' +
            '<label style="color:#00ff88;font-size:11px;display:block;margin-bottom:4px;">Repository Name</label>' +
            '<input type="text" id="ghRepo" style="width:100%;padding:6px;background:#000;border:1px solid #222;color:#fff;border-radius:4px;font-size:11px;" placeholder="bharatmarkets">' +
            '</div>' +
            '<button onclick="saveGitHubConfig()" style="padding:8px 16px;background:#00ff88;color:#000;' +
            'border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:11px;">Save Config</button>' +
            '</div>';
    } else {
        html += '<div style="padding:10px;background:#111;border-left:3px solid #00ff88;margin:10px 0;font-size:11px;color:#00ff88;border-radius:4px;">' +
            '✅ GitHub configured<br>' +
            'User: ' + localStorage.getItem('ghUser') + '<br>' +
            'Repo: ' + localStorage.getItem('ghRepo') +
            '</div>';
        html += '<button onclick="toggleGitHubConfig()" style="padding:10px 20px;background:#444;color:#fff;' +
            'border:none;border-radius:6px;cursor:pointer;font-size:12px;margin-bottom:10px;">✏️ Edit Config</button>';
        
        html += '<button onclick="toggleJSONPreview()" style="padding:10px 20px;background:#444;color:#fff;' +
            'border:none;border-radius:6px;cursor:pointer;font-size:12px;margin-bottom:10px;">' +
            '📋 Preview JSON</button>';
        
        html += '<div id="json-preview" style="display:none;margin:10px 0;padding:10px;background:#000;' +
            'border:1px solid #222;border-radius:6px;max-height:300px;overflow-y:auto;font-size:9px;' +
            'font-family:monospace;color:#0f0;"></div>';
        
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
        unifiedData.symbols.push({
            sym: stock.name.toUpperCase().substring(0, 10),
            name: stock.name,
            isin: stock.isin,
            sector: stock.sector,
            industry: stock.industry,
            type: stock.type.toLowerCase(),
            source: 'import'
        });
    });
    
    unifiedData.symbols.sort(function(a, b) {
        return a.sym.localeCompare(b.sym);
    });
    
    var jsonString = JSON.stringify(unifiedData, null, 2);
    var preview = document.getElementById('json-preview');
    preview.innerHTML = jsonString.replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function postToGitHub() {
    var ghPAT = localStorage.getItem('ghPAT');
    var ghUser = localStorage.getItem('ghUser');
    var ghRepo = localStorage.getItem('ghRepo');
    
    if (!ghPAT || !ghUser || !ghRepo) {
        alert('GitHub not configured');
        return;
    }
    
    if (!confirm('Post ' + importState.stocks.length + ' stocks to unified-symbols.json?')) {
        return;
    }
    
    var status = document.getElementById('step7-status');
    status.innerHTML = '<span style="color:#ffb347;">⏳ Preparing data...</span>';
    
    var unifiedData = {
        updated: new Date().toISOString(),
        count: importState.stocks.length,
        symbols: []
    };
    
    importState.stocks.forEach(function(stock) {
        unifiedData.symbols.push({
            sym: stock.name.toUpperCase().substring(0, 10),
            name: stock.name,
            isin: stock.isin,
            sector: stock.sector,
            industry: stock.industry,
            type: stock.type.toLowerCase(),
            source: 'import'
        });
    });
    
    unifiedData.symbols.sort(function(a, b) {
        return a.sym.localeCompare(b.sym);
    });
    
    var jsonContent = JSON.stringify(unifiedData, null, 2);
    var base64Content = btoa(unescape(encodeURIComponent(jsonContent)));
    
    status.innerHTML = '<span style="color:#ffb347;">⏳ Connecting to GitHub...</span>';
    
    var apiUrl = 'https://api.github.com/repos/' + ghUser + '/' + ghRepo + '/contents/unified-symbols.json';
    
    fetch(apiUrl, {
        headers: {
            'Authorization': 'token ' + ghPAT,
            'Accept': 'application/vnd.github.v3+json'
        }
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
        var sha = data.sha || undefined;
        
        status.innerHTML = '<span style="color:#ffb347;">⏳ Posting to GitHub...</span>';
        
        return fetch(apiUrl, {
            method: 'PUT',
            headers: {
                'Authorization': 'token ' + ghPAT,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: 'Import: ' + importState.stocks.length + ' stocks',
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
                'Message: ' + data.commit.message + '<br>' +
                'SHA: ' + data.commit.sha.substring(0, 10) + '...<br>' +
                'File: ' + data.content.name + '<br><br>' +
                '<b style="color:#00ff88;">' + importState.stocks.length + ' stocks written to GitHub</b>' +
                '</div>';
        } else {
            status.innerHTML = '<span style="color:#ff6b85;">❌ Error: ' + (data.message || 'Unknown error') + '</span>';
        }
    })
    .catch(function(err) {
        status.innerHTML = '<span style="color:#ff6b85;">❌ Error: ' + err.message + '</span>';
    });
}

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
}
