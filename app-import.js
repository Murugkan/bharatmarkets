/**
 * app-import.js - Enhanced Import Workflow (FULLY FIXED)
 * Step 1: FIXED CSV/XLSX parsing with validation
 * Step 7: FIXED with PAT config UI, status display, JSON preview, and confirmation
 */

var importState = {
    step: 1,
    stocks: [],
    aiResponse: null
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// MAIN: Open Import Workflow
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function openImportWorkflow() {
    importState.step = 1;
    importState.stocks = [];
    document.body.classList.add('modal-open');
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
    
    // Find column indices - more flexible matching
    var nameIdx = -1;
    var qtyIdx = -1;
    var avgIdx = -1;
    
    for (var i = 0; i < headerParts.length; i++) {
        var h = headerParts[i];
        if (h.includes('name') || h.includes('stock')) nameIdx = i;
        if (h.includes('qty') || h.includes('quantity') || h.includes('shares')) qtyIdx = i;
        if (h.includes('avg') || h.includes('average') || h.includes('price') || h.includes('cost')) avgIdx = i;
    }
    
    // Default to first 3 columns if headers not found
    if (nameIdx === -1) nameIdx = 0;
    if (qtyIdx === -1 && headerParts.length > 1) qtyIdx = 1;
    if (avgIdx === -1 && headerParts.length > 2) avgIdx = 2;
    
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
        
        // Skip header rows
        if (name.toLowerCase().includes('name') || name.toLowerCase().includes('stock')) continue;
        
        var qty = null;
        var avg = null;
        
        if (qtyIdx >= 0 && qtyIdx < parts.length) {
            var qtyVal = parseFloat(parts[qtyIdx]);
            if (!isNaN(qtyVal) && qtyVal > 0) qty = qtyVal;
        }
        
        if (avgIdx >= 0 && avgIdx < parts.length) {
            var avgVal = parseFloat(parts[avgIdx]);
            if (!isNaN(avgVal) && avgVal > 0) avg = avgVal;
        }
        
        // Skip duplicates
        if (seen.has(name)) continue;
        seen.add(name);
        
        // Add stock if has valid name and at least one of qty/avg
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
    
    var prompt = 'For these Indian company names, get ISIN code, Sector, and Industry.\n\n' +
        'Company Names:\n' +
        names + '\n\n' +
        '⚠️ CRITICAL OUTPUT FORMAT (no extra spaces, pipe separated):\n\n' +
        'Name|ISIN|Sector|Industry\n' +
        'HDFC Bank Limited|INE040A01034|Banking|Financial Services\n' +
        'Reliance Industries Limited|INE002A01015|Energy|Oil & Gas\n' +
        '\n' +
        'Rules:\n' +
        '• Match EXACT company names (case-insensitive)\n' +
        '• Get ISIN code (format: INE + 10 chars)\n' +
        '• No spaces around pipe (|) characters\n' +
        '• Output ONLY the table, no extra text';
    
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Generate AI Prompt</h3>' +
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
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Paste AI Response</h3>' +
        '<textarea id="ai-response" style="width:100%;height:200px;' +
        'padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;' +
        'font-size:11px;border-radius:6px;resize:vertical;" ' +
        'placeholder="Name|ISIN|Sector|Industry&#10;HDFC Bank Limited|INE040A01034|Banking|Financial Services" ' +
        'onpaste="setTimeout(function() { autoParseAIResponse(); }, 100)" ' +
        'onchange="autoParseAIResponse()"></textarea>' +
        '<div id="step4-status" style="margin:10px 0;font-size:12px;"></div>' +
        '</div>';
}

function autoParseAIResponse() {
    var response = document.getElementById('ai-response').value;
    if (!response.trim() || !response.includes('|')) return;
    if (!response.includes('INE') && !response.toLowerCase().includes('name')) return;
    parseAIResponse();
}

function parseAIResponse() {
    var response = document.getElementById('ai-response').value;
    if (!response.trim()) {
        alert('Please paste AI response');
        return;
    }
    
    var lines = response.split(/\r?\n/).filter(function(l) { return l.trim(); });
    var matched = 0;
    
    lines.forEach(function(line) {
        if (!line.includes('|')) return;
        var parts = line.split('|');
        if (parts.length < 4) return;
        
        var name = parts[0].trim();
        var isin = parts[1].trim();
        var sector = parts[2].trim();
        var industry = parts[3].trim();
        
        if (name.toLowerCase() === 'name' || name.toLowerCase() === 'symbol') return;
        
        var stock = importState.stocks.find(function(s) { 
            return s.name.toLowerCase().trim() === name.toLowerCase().trim(); 
        });
        
        if (stock) {
            stock.isin = isin;
            stock.sector = sector;
            stock.industry = industry;
            stock.status = 'matched';
            matched++;
        }
    });
    
    importState.stocks.forEach(function(s) {
        if (!s.status) s.status = 'AI_GENERATED';
    });
    
    var status = document.getElementById('step4-status');
    status.innerHTML = '<div style="color:#00ff88;font-weight:bold;">✅ Matched ' + matched + '/' + 
        importState.stocks.length + ' stocks</div>';
    
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
        var statusColor = stock.status === 'matched' ? '#00ff88' : '#ffb347';
        var statusIcon = stock.status === 'matched' ? '✅' : '⚠️';
        
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
            '<button onclick="deleteStock(' + idx + ')" style="background:#ff6b85;color:#fff;border:none;padding:2px 4px;border-radius:2px;cursor:pointer;font-size:8px;">✕</button>' +
            '</td></tr>';
    });
    
    html += '</table></div>' +
        '<div style="margin:10px 0;font-size:11px;color:#888;">' +
        'Total: ' + importState.stocks.length + ' stocks' +
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
    if (confirm('Delete ' + importState.stocks[idx].name + '?')) {
        importState.stocks.splice(idx, 1);
        showImportUI();
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 6: Save to IndexedDB
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep6() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Save to Database</h3>' +
        '<div style="margin:15px 0;padding:15px;background:#111;border-radius:8px;border-left:3px solid #00ff88;' +
        'color:#00ff88;font-size:12px;">' +
        '<div>✅ Portfolio: ' + importState.stocks.filter(function(s) { return s.type === 'PORTFOLIO'; }).length + ' stocks</div>' +
        '<div>📌 Watchlist: ' + importState.stocks.filter(function(s) { return s.type === 'WATCHLIST'; }).length + ' stocks</div>' +
        '</div>' +
        '<button onclick="saveToIndexedDB()" style="padding:12px 24px;background:#00ff88;' +
        'color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:14px;">' +
        '💾 Save All to DB</button>' +
        '<div id="step6-status" style="margin:15px 0;font-size:12px;"></div>' +
        '</div>';
}

function saveToIndexedDB() {
    if (importState.stocks.length === 0) {
        alert('No stocks to save');
        return;
    }
    
    var status = document.getElementById('step6-status');
    status.innerHTML = '<span style="color:#ffb347;">⏳ Saving...</span>';
    
    try {
        var request = indexedDB.open('BharatEngineDB', 1);
        
        request.onerror = function() {
            status.innerHTML = '<span style="color:#ff6b85;">❌ Database error</span>';
        };
        
        request.onsuccess = function(e) {
            var db = e.target.result;
            var tx = db.transaction('UnifiedStocks', 'readwrite');
            var store = tx.objectStore('UnifiedStocks');
            
            store.clear();
            
            importState.stocks.forEach(function(stock) {
                var record = {
                    sym: stock.symbol || stock.name.substring(0, 10),
                    name: stock.name,
                    isin: stock.isin,
                    sector: stock.sector,
                    industry: stock.industry,
                    type: stock.type,
                    qty: stock.qty,
                    avg: stock.avg,
                    source: 'manual'
                };
                store.put(record);
            });
            
            tx.oncomplete = function() {
                status.innerHTML = '<span style="color:#00ff88;">✅ Saved ' + importState.stocks.length + ' stocks</span>';
                
                setTimeout(function() {
                    importState.step = 7;
                    showImportUI();
                }, 800);
            };
            
            tx.onerror = function() {
                status.innerHTML = '<span style="color:#ff6b85;">❌ Save failed</span>';
            };
        };
    } catch(err) {
        status.innerHTML = '<span style="color:#ff6b85;">❌ Error: ' + err.message + '</span>';
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 7: Post to GitHub - PROPER UI WITH CONFIG & CONFIRMATION
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep7() {
    var ghPAT = localStorage.getItem('ghPAT') || '';
    var ghUser = localStorage.getItem('ghUser') || '';
    var ghRepo = localStorage.getItem('ghRepo') || '';
    var isPATConfigured = ghPAT && ghUser && ghRepo;
    
    var html = '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:16px;">🚀 Post to GitHub</h3>';
    
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
        var sym = stock.symbol || generateSymbol(stock.name);
        unifiedData.symbols.push({
            sym: sym,
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
    
    // Build JSON
    var unifiedData = {
        updated: new Date().toISOString(),
        count: importState.stocks.length,
        symbols: []
    };
    
    importState.stocks.forEach(function(stock) {
        var sym = stock.symbol || generateSymbol(stock.name);
        unifiedData.symbols.push({
            sym: sym,
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
    
    // Get current SHA
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
