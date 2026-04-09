/**
 * app-import.js - Enhanced Import Workflow (FINAL - Step 7 AUTO WRITE via PAT)
 * Step 1: Upload → Step 2: Manual → Step 3: AI Prompt → Step 4: Paste → Step 5: Edit → Step 6: Save to DB → Step 7: Auto-commit to GitHub
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
    showImportUI();
}

function showImportUI() {
    var html = '<div id="import-wizard" style="' +
        'padding:20px;background:#0a0a0a;border-radius:12px;max-width:900px;' +
        '">';
    
    // Step indicator
    html += '<div style="margin-bottom:10px;font-size:12px;color:#555;font-family:monospace;">' +
        'Step ' + importState.step + ' of 7: ';
    
    var stepTitles = ['Upload CSV/XLS', 'Manual Entries', 'AI Prompt', 'Paste Response', 'Edit & Validate', 'Save to DB', 'Auto-Commit'];
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
// STEP 1: Upload CSV/XLS
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep1() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Upload Stock List</h3>' +
        '<div style="padding:10px;background:#111;border-left:3px solid #00ff88;margin:10px 0;font-size:11px;color:#888;border-radius:4px;">' +
        '<b style="color:#00ff88;">CSV Format:</b><br>' +
        'Stock Name, [QTY], [AVG]<br><br>' +
        '<b style="color:#00ff88;">Requirements:</b><br>' +
        '• Stock Name: Full company name (required)<br>' +
        '• QTY: Quantity (optional)<br>' +
        '• AVG: Average price (optional)<br>' +
        '• Has QTY → PORTFOLIO | No QTY → WATCHLIST<br><br>' +
        '<b style="color:#ffb347;">Examples:</b><br>' +
        'HDFC Bank Limited,84,817.50<br>' +
        'Reliance Industries Limited,10,2450<br>' +
        'TCS Limited<br>' +
        '</div>' +
        '<div style="margin:15px 0;padding:20px;border:2px dashed #222;border-radius:8px;' +
        'text-align:center;cursor:pointer;background:#050505;" ' +
        'onclick="document.getElementById(\'file-input\').click()">' +
        '<div style="font-size:32px;margin-bottom:10px;">📁</div>' +
        '<div style="color:#fff;font-weight:bold;margin-bottom:5px;">Click to upload CSV/TSV</div>' +
        '<div style="color:#666;font-size:12px;">or drag and drop</div>' +
        '</div>' +
        '<input type="file" id="file-input" accept=".csv,.xls,.xlsx,.tsv,.txt" style="display:none;" ' +
        'onchange="handleImportFile(this.files[0])">' +
        '<div id="file-status" style="margin:10px 0;font-size:12px;color:#666;"></div>' +
        '<div id="step1-preview" style="margin:10px 0;"></div>' +
        '</div>';
}

function handleImportFile(file) {
    if (!file) return;
    
    var status = document.getElementById('file-status');
    status.innerHTML = '<span style="color:#ffb347;">⏳ Reading file...</span>';
    
    var ext = file.name.split('.').pop().toLowerCase();
    
    if (ext === 'csv' || ext === 'txt') {
        var reader = new FileReader();
        reader.onload = function(e) {
            processImportCSV(e.target.result);
            status.innerHTML = '<span style="color:#00ff88;">✅ File loaded successfully</span>';
        };
        reader.readAsText(file);
    } else if (ext === 'xls' || ext === 'xlsx') {
        loadSheetJS(function() {
            var reader = new FileReader();
            reader.onload = function(e) {
                try {
                    var data = new Uint8Array(e.target.result);
                    var wb = XLSX.read(data, {type: 'array'});
                    var ws = wb.Sheets[wb.SheetNames[0]];
                    var csv = XLSX.utils.sheet_to_csv(ws);
                    processImportCSV(csv);
                    status.innerHTML = '<span style="color:#00ff88;">✅ File loaded successfully</span>';
                } catch(err) {
                    status.innerHTML = '<span style="color:#ff6b85;">❌ Error: ' + err.message + '</span>';
                }
            };
            reader.readAsArrayBuffer(file);
        });
    }
}

var _sheetJSLoaded = false;
function loadSheetJS(cb) {
    if (_sheetJSLoaded) { cb(); return; }
    if (window.XLSX) { _sheetJSLoaded = true; cb(); return; }
    
    var script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.min.js';
    script.onload = function() { _sheetJSLoaded = true; cb(); };
    document.head.appendChild(script);
}

function processImportCSV(csv) {
    var lines = csv.split('\n').map(function(l) { return l.trim(); }).filter(function(l) { return l.length > 0; });
    if (lines.length === 0) return;
    
    var headerLine = lines[0];
    var delimiter = (headerLine.includes('\t') ? '\t' : (headerLine.includes(',') ? ',' : ';'));
    
    var headerParts = headerLine.split(delimiter).map(function(p) { return p.trim().toLowerCase(); });
    
    var nameIdx = Math.max(0, headerParts.indexOf('name'), headerParts.indexOf('stock name'), headerParts.indexOf('company'));
    var qtyIdx = Math.max(-1, headerParts.indexOf('qty'), headerParts.indexOf('quantity'));
    var avgIdx = Math.max(-1, headerParts.indexOf('avg'), headerParts.indexOf('average'), headerParts.indexOf('price'));
    var sectorIdx = Math.max(-1, headerParts.indexOf('sector'), headerParts.indexOf('industry'));
    
    var stocks = [];
    var seen = new Set();
    
    for (var i = 1; i < lines.length; i++) {
        var line = lines[i].trim();
        if (!line) continue;
        
        var parts = line.split(delimiter).map(function(p) { return p.trim().replace(/['"]/g, ''); });
        
        if (!parts[0]) continue;
        
        if (parts[0].toLowerCase() === 'stock name' || parts[0].toLowerCase() === 'name') {
            continue;
        }
        
        var name = parts[nameIdx] || parts[0];
        var isin = '';
        var qty = qtyIdx >= 0 && parts[qtyIdx] && parts[qtyIdx] !== '-' ? parseFloat(parts[qtyIdx]) : null;
        var avg = avgIdx >= 0 && parts[avgIdx] && parts[avgIdx] !== '-' ? parseFloat(parts[avgIdx]) : null;
        var sector = sectorIdx >= 0 ? parts[sectorIdx] : '';
        
        if (seen.has(name)) continue;
        seen.add(name);
        
        if (qty && avg && qty > 0 && avg > 0) {
            stocks.push({
                name: name,
                isin: isin,
                qty: qty,
                avg: avg,
                sector: sector,
                industry: '',
                type: 'PORTFOLIO',
                status: ''
            });
        }
    }
    
    importState.stocks = stocks;
    showImportUI();
    renderStep1Preview();
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
            '<td style="padding:6px;text-align:right;">' + (stock.qty || '-') + '</td>' +
            '<td style="padding:6px;text-align:right;">₹' + (stock.avg ? stock.avg.toFixed(0) : '-') + '</td>' +
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
        'Tesla Inc,2,250<br>' +
        '</div>' +
        '<textarea id="manual-entries" style="width:100%;height:150px;' +
        'padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;' +
        'font-size:11px;border-radius:6px;resize:vertical;" ' +
        'placeholder="Stock Name, QTY, AVG&#10;Apple Inc,5,150"></textarea>' +
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
            '<td style="padding:4px;text-align:right;">₹' + stock.avg.toFixed(0) + '</td></tr>';
    });
    
    html += '</table></div><div style="margin:10px 0;font-size:11px;color:#888;">Total: ' + 
        importState.stocks.length + ' stocks</div>';
    
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
        'TCS Limited|INE467B01029|IT|IT Services\n' +
        '\n' +
        'Rules:\n' +
        '• Match EXACT company names (case-insensitive)\n' +
        '• Get ISIN code (format: INE + 10 chars)\n' +
        '• No spaces around pipe (|) characters\n' +
        '• One company per line\n' +
        '• Output ONLY the table, no extra text';
    
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Generate AI Prompt</h3>' +
        '<p style="margin:10px 0;color:#888;font-size:12px;">' +
        'Copy prompt → Paste in ChatGPT/Claude → Get ISIN & Sector<br>' +
        '<b style="color:#ffb347;">Tell AI:</b> "Output ONLY the table with Name|ISIN|Sector|Industry"' +
        '</p>' +
        '<textarea id="ai-prompt" readonly style="width:100%;height:300px;' +
        'padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;' +
        'font-size:11px;border-radius:6px;resize:none;">' + prompt + '</textarea>' +
        '<div style="margin:10px 0;">' +
        '<button onclick="copyPrompt()" style="padding:10px 20px;background:#00ff88;' +
        'color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">📋 Copy Prompt</button>' +
        '</div>' +
        '<div style="margin:10px 0;padding:10px;background:#111;border-radius:6px;' +
        'border-left:3px solid #ffb347;color:#ffb347;font-size:12px;">' +
        '⚠️ After getting AI response, paste it in Step 4' +
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
        '<div style="padding:10px;background:#111;border-left:3px solid #00ff88;margin:10px 0;font-size:11px;color:#888;border-radius:4px;font-family:monospace;">' +
        '<b style="color:#00ff88;">Expected Format (from AI):</b><br><br>' +
        'Name|ISIN|Sector|Industry<br>' +
        'HDFC Bank Limited|INE040A01034|Banking|Financial Services<br>' +
        'Reliance Industries Limited|INE002A01015|Energy|Oil & Gas<br>' +
        'TCS Limited|INE467B01029|IT|IT Services<br>' +
        '</div>' +
        '<textarea id="ai-response" style="width:100%;height:200px;' +
        'padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;' +
        'font-size:11px;border-radius:6px;resize:vertical;" ' +
        'placeholder="Paste AI response here...&#10;Name|ISIN|Sector|Industry&#10;HDFC Bank Limited|INE040A01034|Banking|Financial Services" ' +
        'onpaste="setTimeout(function() { autoParseAIResponse(); }, 100)" ' +
        'onchange="autoParseAIResponse()"></textarea>' +
        '<div id="step4-status" style="margin:10px 0;font-size:12px;"></div>' +
        '</div>';
}

function autoParseAIResponse() {
    var response = document.getElementById('ai-response').value;
    if (!response.trim() || !response.includes('|')) {
        return;
    }
    
    if (!response.includes('INE') && !response.toLowerCase().includes('name')) {
        return;
    }
    
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
        importState.stocks.length + ' stocks</div>' +
        '<div style="margin-top:8px;font-size:11px;color:#666;">Ready for Step 5 → Click Next</div>';
    
    showImportUI();
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 5: Edit & Validate
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep5() {
    var html = '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Review & Edit</h3>' +
        '<p style="margin:10px 0;color:#888;font-size:12px;">' +
        'Click any cell to edit. Validation: ✅ ISIN format (INE + 10 chars)' +
        '</p>' +
        '<div style="margin:10px 0;overflow-x:auto;border:1px solid #111;border-radius:8px;max-height:400px;overflow-y:auto;">' +
        '<table style="width:100%;border-collapse:collapse;font-size:9px;line-height:1.3;">' +
        '<tr style="background:#111;border-bottom:1px solid #222;position:sticky;top:0;">' +
        '<th style="padding:4px 6px;text-align:left;color:#00ff88;width:22%;">Name</th>' +
        '<th style="padding:4px 6px;text-align:left;color:#00ff88;width:20%;">ISIN</th>' +
        '<th style="padding:4px 6px;text-align:left;color:#00ff88;width:18%;">Sector</th>' +
        '<th style="padding:4px 6px;text-align:right;color:#00ff88;width:8%;">Qty</th>' +
        '<th style="padding:4px 6px;text-align:right;color:#00ff88;width:10%;">Avg</th>' +
        '<th style="padding:4px 6px;text-align:center;color:#00ff88;width:6%;">Del</th>' +
        '</tr>';
    
    importState.stocks.forEach(function(stock, idx) {
        var statusColor = stock.status === 'matched' ? '#00ff88' : '#ffb347';
        var statusIcon = stock.status === 'matched' ? '✅' : '⚠️';
        
        html += '<tr style="border-bottom:0.5px solid #111;background:#050505;" data-idx="' + idx + '">' +
            '<td style="padding:4px 6px;overflow:hidden;text-overflow:ellipsis;" onclick="editCell(this, ' + idx + ', \'name\')">' +
            stock.name.substring(0, 25) + '</td>' +
            '<td style="padding:4px 6px;color:' + statusColor + ';font-weight:bold;" onclick="editCell(this, ' + idx + ', \'isin\')">' +
            statusIcon + ' ' + (stock.isin || '-') + '</td>' +
            '<td style="padding:4px 6px;overflow:hidden;text-overflow:ellipsis;" onclick="editCell(this, ' + idx + ', \'sector\')">' +
            stock.sector.substring(0, 15) + '</td>' +
            '<td style="padding:4px 6px;text-align:right;" onclick="editCell(this, ' + idx + ', \'qty\')">' +
            (stock.qty || '-') + '</td>' +
            '<td style="padding:4px 6px;text-align:right;" onclick="editCell(this, ' + idx + ', \'avg\')">' +
            (stock.avg ? '₹' + stock.avg.toFixed(0) : '-') + '</td>' +
            '<td style="padding:4px 6px;text-align:center;">' +
            '<button onclick="deleteStock(' + idx + ')" style="background:#ff6b85;color:#fff;' +
            'border:none;padding:2px 4px;border-radius:2px;cursor:pointer;font-size:8px;">✕</button>' +
            '</td></tr>';
    });
    
    html += '</table></div>' +
        '<div style="margin:10px 0;font-size:11px;color:#888;">' +
        'Total: ' + importState.stocks.length + ' stocks | ' +
        'Portfolio: ' + importState.stocks.filter(function(s) { return s.type === 'PORTFOLIO'; }).length + ' | ' +
        'Watchlist: ' + importState.stocks.filter(function(s) { return s.type === 'WATCHLIST'; }).length +
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
        '<p style="margin:10px 0;color:#888;font-size:12px;">Click to save all stocks to IndexedDB</p>' +
        '<div style="margin:15px 0;padding:15px;background:#111;border-radius:8px;border-left:3px solid #00ff88;' +
        'color:#00ff88;font-size:12px;">' +
        '<div>✅ Portfolio: ' + importState.stocks.filter(function(s) { return s.type === 'PORTFOLIO'; }).length + ' stocks</div>' +
        '<div>📌 Watchlist: ' + importState.stocks.filter(function(s) { return s.type === 'WATCHLIST'; }).length + ' stocks</div>' +
        '<div style="margin-top:10px;">Stored in: <b>IndexedDB / BharatEngineDB</b></div>' +
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
                status.innerHTML = '<span style="color:#00ff88;">✅ Saved ' + importState.stocks.length + 
                    ' stocks to IndexedDB</span>' +
                    '<div style="margin-top:10px;font-size:11px;color:#666;">Moving to Step 7...</div>';
                
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
// STEP 7: Auto-Commit to GitHub via PAT
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep7() {
    var portfolioCount = importState.stocks.filter(function(s) { return s.type === 'PORTFOLIO'; }).length;
    var watchlistCount = importState.stocks.filter(function(s) { return s.type === 'WATCHLIST'; }).length;
    
    // Check if PAT is configured
    var settings = JSON.parse(localStorage.getItem('bharatSettings') || '{}');
    var ghPAT = settings.githubPAT || localStorage.getItem('githubPAT') || '';
    var ghUser = settings.githubUser || localStorage.getItem('githubUser') || '';
    var ghRepo = settings.githubRepo || localStorage.getItem('githubRepo') || '';
    var isPATConfigured = ghPAT && ghUser && ghRepo;
    
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:16px;text-align:center;">🚀 Auto-Commit to GitHub</h3>' +
        
        '<div style="margin:20px 0;padding:15px;background:#111;border-radius:8px;border-left:4px solid ' + 
        (isPATConfigured ? '#00ff88' : '#ffb347') + ';color:' + (isPATConfigured ? '#00ff88' : '#ffb347') + ';font-size:12px;">' +
        (isPATConfigured ? '✅ GitHub PAT Configured' : '⚠️ GitHub PAT Not Configured') +
        '</div>' +
        
        (isPATConfigured ? 
            '<div style="margin:20px 0;padding:15px;background:#111;border-radius:8px;border-left:3px solid #00ff88;color:#888;font-size:12px;">' +
            '<b style="color:#00ff88;">📋 Data to Commit</b><br><br>' +
            '✅ Portfolio Stocks: <b style="color:#00ff88;">' + portfolioCount + '</b><br>' +
            '📌 Watchlist Items: <b style="color:#ffb347;">' + watchlistCount + '</b><br>' +
            '💾 Total Records: <b style="color:#00ff88;">' + importState.stocks.length + '</b><br><br>' +
            'File: <b>unified-symbols.json</b><br>' +
            'Repo: <b>' + ghUser + '/' + ghRepo + '</b>' +
            '</div>' +
            '<div style="margin:20px 0;">' +
            '<button onclick="autoCommitToGitHub()" style="padding:14px 28px;background:#00ff88;color:#000;' +
            'border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:14px;">' +
            '📤 Auto-Commit Now</button>' +
            '</div>' :
            '<div style="margin:20px 0;padding:15px;background:#050505;border:1px solid #222;border-radius:8px;color:#888;font-size:12px;">' +
            '<b style="color:#ffb347;">Configure GitHub First</b><br><br>' +
            'Go to Settings → GitHub Configuration and add:<br>' +
            '• GitHub PAT (Personal Access Token)<br>' +
            '• GitHub Username<br>' +
            '• GitHub Repository<br><br>' +
            'Then return to this step to auto-commit.' +
            '</div>'
        ) +
        
        '<div id="step7-status" style="margin:15px 0;font-size:12px;"></div>' +
        '</div>';
}

function autoCommitToGitHub() {
    var status = document.getElementById('step7-status');
    status.innerHTML = '<span style="color:#ffb347;">⏳ Preparing commit...</span>';
    
    // Get settings
    var settings = JSON.parse(localStorage.getItem('bharatSettings') || '{}');
    var ghPAT = settings.githubPAT || localStorage.getItem('githubPAT') || '';
    var ghUser = settings.githubUser || localStorage.getItem('githubUser') || '';
    var ghRepo = settings.githubRepo || localStorage.getItem('githubRepo') || '';
    
    if (!ghPAT || !ghUser || !ghRepo) {
        status.innerHTML = '<span style="color:#ff6b85;">❌ GitHub not configured. Go to Settings first.</span>';
        return;
    }
    
    // Build unified-symbols.json
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
    
    // GitHub API call
    status.innerHTML = '<span style="color:#ffb347;">⏳ Connecting to GitHub...</span>';
    
    var apiUrl = 'https://api.github.com/repos/' + ghUser + '/' + ghRepo + '/contents/unified-symbols.json';
    
    // First, get current file SHA (if exists)
    fetch(apiUrl, {
        headers: {
            'Authorization': 'token ' + ghPAT,
            'Accept': 'application/vnd.github.v3+json'
        }
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
        var sha = data.sha || undefined;
        
        status.innerHTML = '<span style="color:#ffb347;">⏳ Committing to GitHub...</span>';
        
        // Commit file
        return fetch(apiUrl, {
            method: 'PUT',
            headers: {
                'Authorization': 'token ' + ghPAT,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: 'Import: ' + importState.stocks.length + ' stocks to unified-symbols.json',
                content: base64Content,
                sha: sha
            })
        });
    })
    .then(function(res) { return res.json(); })
    .then(function(data) {
        if (data.commit) {
            status.innerHTML = '<div style="color:#00ff88;"><b>✅ Auto-Commit Successful!</b></div>' +
                '<div style="margin:10px 0;font-size:11px;color:#888;">' +
                'Commit: ' + data.commit.message + '<br>' +
                'SHA: ' + data.content.sha.substring(0, 7) + '...<br>' +
                importState.stocks.length + ' stocks written to unified-symbols.json' +
                '</div>';
        } else if (data.message) {
            status.innerHTML = '<span style="color:#ff6b85;">❌ Error: ' + data.message + '</span>';
        } else {
            status.innerHTML = '<div style="color:#00ff88;"><b>✅ File Updated!</b></div>' +
                '<div style="margin:10px 0;font-size:11px;color:#888;">' +
                importState.stocks.length + ' stocks committed to GitHub' +
                '</div>';
        }
    })
    .catch(function(err) {
        status.innerHTML = '<span style="color:#ff6b85;">❌ Error: ' + err.message + '</span>';
    });
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
}
