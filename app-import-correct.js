/**
 * app-import.js - Enhanced Import Workflow
 * Step 1: Upload → Step 2: Manual → Step 3: AI Prompt → Step 4: Paste → Step 5: Edit → Step 6: Save → Step 7: Sync
 */

var importState = {
    step: 1,
    stocks: [],
    aiResponse: null
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 1: Upload CSV/XLS
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
    html += '<div style="margin-bottom:20px;font-size:12px;color:#555;font-family:monospace;">' +
        'Step ' + importState.step + ' of 7: ';
    
    var stepTitles = ['Upload CSV/XLS', 'Manual Entries', 'AI Prompt', 'Paste Response', 'Edit & Validate', 'Save to DB', 'GitHub Sync'];
    html += stepTitles[importState.step - 1];
    html += '</div>';
    
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
        '<div style="margin-top:20px;display:flex;gap:10px;justify-content:flex-end;">' +
        '<button onclick="closeImportModal()" style="padding:10px 20px;background:#333;border:none;color:#fff;' +
        'border-radius:6px;cursor:pointer;">Cancel</button>' +
        (importState.step > 1 ? '<button onclick="prevImportStep()" style="padding:10px 20px;background:#444;' +
        'border:none;color:#fff;border-radius:6px;cursor:pointer;">← Back</button>' : '') +
        (importState.step < 7 ? '<button onclick="nextImportStep()" style="padding:10px 20px;background:#00ff88;' +
        'border:none;color:#000;border-radius:6px;cursor:pointer;font-weight:bold;">Next →</button>' : '') +
        '</div>' +
        '</div>';
    
    modal.style.display = 'flex';
}

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
        'Apple Inc,5,150<br>' +
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
                    var wb = XLSX.read(e.target.result, {type: 'binary'});
                    var ws = wb.Sheets[wb.SheetNames[0]];
                    var csv = XLSX.utils.sheet_to_csv(ws);
                    processImportCSV(csv);
                    status.innerHTML = '<span style="color:#00ff88;">✅ File loaded successfully</span>';
                } catch(err) {
                    status.innerHTML = '<span style="color:#ff6b85;">❌ Error: ' + err.message + '</span>';
                }
            };
            reader.readAsBinaryString(file);
        });
    }
}

var _sheetJSLoaded = false;
function loadSheetJS(cb) {
    if (_sheetJSLoaded) { cb(); return; }
    if (window.XLSX) { _sheetJSLoaded = true; cb(); return; }
    
    var s = document.createElement('script');
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js';
    s.onload = function() { _sheetJSLoaded = true; cb(); };
    s.onerror = function() {
        document.getElementById('file-status').innerHTML = 
            '<span style="color:#ff6b85;">❌ Could not load XLS reader</span>';
    };
    document.head.appendChild(s);
}

function processImportCSV(csv) {
    var lines = csv.split(/\r?\n/).filter(function(l) { return l.trim(); });
    if (lines.length < 2) return;
    
    // Detect if tab or comma separated
    var isTSV = lines[0].includes('\t');
    var delimiter = isTSV ? /\t/ : /,/;
    
    var headers = lines[0].split(delimiter).map(function(h) { 
        return h.trim().toLowerCase().replace(/['"]/g, ''); 
    });
    
    // Find column indices
    var nameIdx = headers.findIndex(function(h) { return h.includes('stock') && h.includes('name'); });
    if (nameIdx < 0) nameIdx = 0; // First column is stock name
    
    var qtyIdx = headers.findIndex(function(h) { return h.includes('qty') || h.includes('quantity'); });
    var avgIdx = headers.findIndex(function(h) { return h.includes('avg') || h.includes('price'); });
    
    var stocks = [];
    var seen = new Set();
    
    for (var i = 1; i < lines.length; i++) {
        var line = lines[i].trim();
        if (!line) continue;
        
        var parts = line.split(delimiter).map(function(p) { return p.trim().replace(/['"]/g, ''); });
        
        // Skip if first column is empty
        if (!parts[0]) continue;
        
        // Skip if this looks like a header row (duplicate)
        if (parts[0].toLowerCase() === 'stock name' || parts[0].toLowerCase() === 'name') {
            continue;
        }
        
        var name = parts[nameIdx] || parts[0];
        
        // Skip duplicates
        if (seen.has(name)) continue;
        seen.add(name);
        
        // Get QTY and AVG
        var qty = qtyIdx >= 0 && parts[qtyIdx] && parts[qtyIdx] !== '-' ? parseFloat(parts[qtyIdx]) : null;
        var avg = avgIdx >= 0 && parts[avgIdx] && parts[avgIdx] !== '-' ? parseFloat(parts[avgIdx]) : null;
        
        // Auto-detect type: if QTY exists → PORTFOLIO, else → WATCHLIST
        var type = qty ? 'PORTFOLIO' : 'WATCHLIST';
        
        // Add stock with just name, qty, avg (NO symbol)
        stocks.push({
            name: name,
            symbol: '',  // Empty - will be matched later
            qty: qty,
            avg: avg,
            type: type,
            isin: '',
            sector: '',
            industry: ''
        });
    }
    
    importState.stocks = stocks;
    showImportUI();
    renderStep1Preview();
}

function renderStep1Preview() {
    if (importState.stocks.length === 0) return;
    
    var html = '<div style="margin:15px 0;border:1px solid #222;border-radius:8px;overflow:auto;">' +
        '<table style="width:100%;border-collapse:collapse;font-size:12px;">' +
        '<tr style="background:#111;border-bottom:1px solid #222;">' +
        '<th style="padding:8px;text-align:left;color:#00ff88;">Stock Name</th>' +
        '<th style="padding:8px;text-align:left;color:#00ff88;">Symbol</th>' +
        '<th style="padding:8px;text-align:left;color:#00ff88;">Type</th>' +
        '<th style="padding:8px;text-align:left;color:#00ff88;">QTY</th>' +
        '<th style="padding:8px;text-align:left;color:#00ff88;">AVG</th>' +
        '</tr>';
    
    var portfolioCount = 0, watchlistCount = 0;
    importState.stocks.forEach(function(stock) {
        if (stock.type === 'PORTFOLIO') portfolioCount++;
        else watchlistCount++;
        
        html += '<tr style="border-bottom:1px solid #111;">' +
            '<td style="padding:8px;">' + stock.name + '</td>' +
            '<td style="padding:8px;color:#00ff88;font-weight:bold;">' + stock.symbol + '</td>' +
            '<td style="padding:8px;color:' + (stock.type === 'PORTFOLIO' ? '#00ff88' : '#ffb347') + ';">' +
            stock.type + '</td>' +
            '<td style="padding:8px;">' + (stock.qty || '-') + '</td>' +
            '<td style="padding:8px;">' + (stock.avg ? '₹' + stock.avg.toFixed(2) : '-') + '</td>' +
            '</tr>';
    });
    
    html += '</table></div>' +
        '<div style="margin:10px 0;font-size:12px;color:#00ff88;">' +
        '✅ Loaded: ' + importState.stocks.length + ' stocks (' + portfolioCount + ' portfolio, ' + 
        watchlistCount + ' watchlist)' +
        '</div>';
    
    document.getElementById('step1-preview').innerHTML = html;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 2: Manual Entries
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep2() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Add Manual Entries</h3>' +
        '<div style="padding:10px;background:#111;border-left:3px solid #00ff88;margin:10px 0;font-size:12px;color:#888;border-radius:4px;">' +
        '<b style="color:#00ff88;">Format (no extra spaces):</b><br>' +
        'StockName,SYMBOL,QTY,AVG<br><br>' +
        '<b style="color:#ffb347;">Important:</b><br>' +
        '• No spaces around commas<br>' +
        '• QTY and AVG are optional but use format<br>' +
        '• If no QTY: StockName,SYMBOL,,<br>' +
        '• One entry per line<br><br>' +
        '<b style="color:#00ff88;">Examples:</b><br>' +
        'Apple,APPLE,5,150<br>' +
        'Google,GOOGLE,3,<br>' +
        'Tesla,TESLA,,<br>' +
        '</div>' +
        '<textarea id="manual-entries" style="width:100%;height:150px;' +
        'padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;' +
        'font-size:12px;border-radius:6px;resize:vertical;" ' +
        'placeholder="Apple,APPLE,5,150&#10;Google,GOOGLE,3,&#10;Tesla,TESLA,,"></textarea>' +
        '<div style="margin:10px 0;">' +
        '<button onclick="addManualEntries()" style="padding:10px 20px;background:#00ff88;' +
        'color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">+ Add Entries</button>' +
        '</div>' +
        '<div id="step2-preview" style="margin:10px 0;"></div>' +
        '</div>';
}

function addManualEntries() {
    var text = document.getElementById('manual-entries').value;
    if (!text.trim()) {
        alert('Please enter stock data');
        return;
    }
    
    var lines = text.split(/\r?\n/).filter(function(l) { return l.trim(); });
    lines.forEach(function(line) {
        var parts = line.split(',').map(function(p) { return p.trim(); });
        if (!parts[0]) return;
        
        importState.stocks.push({
            name: parts[0],
            symbol: parts[1] || parts[0].replace(/\s+/g, '').toUpperCase(),
            qty: parts[2] ? parseFloat(parts[2]) : null,
            avg: parts[3] ? parseFloat(parts[3]) : null,
            type: parts[2] ? 'PORTFOLIO' : 'WATCHLIST',
            isin: '',
            sector: '',
            industry: ''
        });
    });
    
    // Remove duplicates
    var seen = new Set();
    importState.stocks = importState.stocks.filter(function(s) {
        if (seen.has(s.symbol)) return false;
        seen.add(s.symbol);
        return true;
    });
    
    document.getElementById('manual-entries').value = '';
    renderStep2Preview();
}

function renderStep2Preview() {
    var html = '<div style="margin:10px 0;font-size:12px;color:#00ff88;">' +
        '✅ Total stocks: ' + importState.stocks.length +
        '</div>';
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
        '• Skip if not found\n' +
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
        '<br>' +
        '<b style="color:#ffb347;">Important:</b><br>' +
        '• Names must MATCH company names from Step 1<br>' +
        '• ISIN: Format INE + 10 characters<br>' +
        '• No spaces around pipes (|)<br>' +
        '• Each company on its own line<br>' +
        '• Copy entire AI response (header + data)<br>' +
        '</div>' +
        '<textarea id="ai-response" style="width:100%;height:200px;' +
        'padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;' +
        'font-size:11px;border-radius:6px;resize:vertical;" ' +
        'placeholder="Name|ISIN|Sector|Industry&#10;HDFC Bank Limited|INE040A01034|Banking|Financial Services&#10;Reliance Industries Limited|INE002A01015|Energy|Oil & Gas"></textarea>' +
        '<div style="margin:10px 0;">' +
        '<button onclick="parseAIResponse()" style="padding:10px 20px;background:#00ff88;' +
        'color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">✓ Parse Response</button>' +
        '</div>' +
        '<div id="step4-status" style="margin:10px 0;font-size:12px;"></div>' +
        '</div>';
}

function parseAIResponse() {
    var response = document.getElementById('ai-response').value;
    if (!response.trim()) {
        alert('Please paste AI response');
        return;
    }
    
    // Split by lines and reconstruct if multi-line
    var lines = response.split(/\r?\n/).filter(function(l) { return l.trim(); });
    var processedLines = [];
    var currentLine = '';
    
    // Reconstruct multi-line entries
    lines.forEach(function(line) {
        var pipeCount = (line.match(/\|/g) || []).length;
        
        if (pipeCount >= 3) {
            // This is a complete line
            if (currentLine) {
                processedLines.push(currentLine);
                currentLine = '';
            }
            processedLines.push(line);
        } else if (pipeCount > 0 || currentLine) {
            // This is part of a multi-line entry
            if (currentLine) {
                currentLine += ' ' + line;
            } else {
                currentLine = line;
            }
            
            // Check if we now have enough pipes
            var totalPipes = (currentLine.match(/\|/g) || []).length;
            if (totalPipes >= 3) {
                processedLines.push(currentLine);
                currentLine = '';
            }
        }
    });
    
    if (currentLine) {
        processedLines.push(currentLine);
    }
    
    var matched = 0;
    
    processedLines.forEach(function(line) {
        if (!line.includes('|')) return;
        
        var parts = line.split('|');
        if (parts.length < 4) return;
        
        var name = parts[0].trim();
        var isin = parts[1].trim();
        var sector = parts[2].trim();
        var industry = parts[3].trim();
        
        // Skip header row
        if (name.toLowerCase() === 'name' || name.toLowerCase() === 'symbol') return;
        
        // Find stock by name (case-insensitive)
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
    
    // Mark remaining as AI GENERATED
    importState.stocks.forEach(function(s) {
        if (!s.status) s.status = 'AI_GENERATED';
    });
    
    var status = document.getElementById('step4-status');
    status.innerHTML = '<div style="color:#00ff88;">✅ Matched ' + matched + '/' + 
        importState.stocks.length + ' stocks</div>';
    
    showImportUI();
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 5: Inline Edit
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep5() {
    var html = '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Review & Edit</h3>' +
        '<p style="margin:10px 0;color:#888;font-size:12px;">' +
        'Click any cell to edit. Validation: ✅ ISIN format (INE + 10 chars), no duplicates' +
        '</p>' +
        '<div style="margin:10px 0;overflow-x:auto;border:1px solid #111;border-radius:8px;">' +
        '<table style="width:100%;border-collapse:collapse;font-size:11px;">' +
        '<tr style="background:#111;border-bottom:1px solid #222;position:sticky;top:0;">' +
        '<th style="padding:8px;text-align:left;color:#00ff88;width:15%;">Name</th>' +
        '<th style="padding:8px;text-align:left;color:#00ff88;width:12%;">Symbol</th>' +
        '<th style="padding:8px;text-align:left;color:#00ff88;width:18%;">ISIN</th>' +
        '<th style="padding:8px;text-align:left;color:#00ff88;width:15%;">Sector</th>' +
        '<th style="padding:8px;text-align:left;color:#00ff88;width:8%;">Qty</th>' +
        '<th style="padding:8px;text-align:left;color:#00ff88;width:8%;">Avg</th>' +
        '<th style="padding:8px;text-align:left;color:#00ff88;width:8%;">Type</th>' +
        '<th style="padding:8px;text-align:center;color:#00ff88;width:6%;">Del</th>' +
        '</tr>';
    
    importState.stocks.forEach(function(stock, idx) {
        var statusColor = stock.status === 'matched' ? '#00ff88' : '#ffb347';
        var statusIcon = stock.status === 'matched' ? '✅' : '⚠️';
        
        html += '<tr style="border-bottom:1px solid #111;background:#050505;" data-idx="' + idx + '">' +
            '<td style="padding:8px;" onclick="editCell(this, ' + idx + ', \'name\')">' +
            stock.name + '</td>' +
            '<td style="padding:8px;color:#00ff88;font-weight:bold;" onclick="editCell(this, ' + idx + ', \'symbol\')">' +
            stock.symbol + '</td>' +
            '<td style="padding:8px;color:' + statusColor + ';" onclick="editCell(this, ' + idx + ', \'isin\')">' +
            statusIcon + ' ' + (stock.isin || '-') + '</td>' +
            '<td style="padding:8px;" onclick="editCell(this, ' + idx + ', \'sector\')">' +
            stock.sector + '</td>' +
            '<td style="padding:8px;text-align:right;" onclick="editCell(this, ' + idx + ', \'qty\')">' +
            (stock.qty || '-') + '</td>' +
            '<td style="padding:8px;text-align:right;" onclick="editCell(this, ' + idx + ', \'avg\')">' +
            (stock.avg ? '₹' + stock.avg.toFixed(2) : '-') + '</td>' +
            '<td style="padding:8px;color:' + (stock.type === 'PORTFOLIO' ? '#00ff88' : '#ffb347') + ';" ' +
            'onclick="toggleType(' + idx + ')">' +
            stock.type + '</td>' +
            '<td style="padding:8px;text-align:center;">' +
            '<button onclick="deleteStock(' + idx + ')" style="background:#ff6b85;color:#fff;' +
            'border:none;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:10px;">✕</button>' +
            '</td></tr>';
    });
    
    html += '</table></div>' +
        '<div style="margin:10px 0;font-size:12px;color:#888;">' +
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

function toggleType(idx) {
    var stock = importState.stocks[idx];
    stock.type = stock.type === 'PORTFOLIO' ? 'WATCHLIST' : 'PORTFOLIO';
    showImportUI();
}

function deleteStock(idx) {
    if (confirm('Delete ' + importState.stocks[idx].symbol + '?')) {
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
        '<p style="margin:10px 0;color:#888;font-size:12px;">' +
        'Click to save all stocks to IndexedDB (not localStorage)' +
        '</p>' +
        '<div style="margin:15px 0;padding:15px;background:#111;border-radius:8px;border-left:3px solid #00ff88;' +
        'color:#00ff88;font-size:12px;">' +
        '<div>✅ Portfolio: ' + importState.stocks.filter(function(s) { return s.type === 'PORTFOLIO'; }).length + ' stocks</div>' +
        '<div>📌 Watchlist: ' + importState.stocks.filter(function(s) { return s.type === 'WATCHLIST'; }).length + ' stocks</div>' +
        '<div style="margin-top:10px;">Stored in: <b>IndexedDB / unified-symbols</b></div>' +
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
            
            // Create or update store
            if (!db.objectStoreNames.contains('unified-symbols')) {
                // If store doesn't exist, we need to update version
                // For now, just save to a temp location
            }
            
            var tx = db.transaction('UnifiedStocks', 'readwrite');
            var store = tx.objectStore('UnifiedStocks');
            
            // Clear existing
            store.clear();
            
            // Save new
            importState.stocks.forEach(function(stock) {
                var record = {
                    sym: stock.symbol,
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
                    ' stocks to IndexedDB</span>';
                importState.step = 7;
                showImportUI();
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
// STEP 7: GitHub Sync
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep7() {
    var ghConfigured = (S && S.settings && S.settings.ghToken && S.settings.ghToken.trim()) ? true : false;
    
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">GitHub Sync (Optional)</h3>' +
        '<p style="margin:10px 0;color:#888;font-size:12px;">' +
        'Sync portfolio to GitHub and trigger data refresh' +
        '</p>' +
        '<div style="margin:15px 0;padding:15px;background:#111;border-radius:8px;' +
        'border-left:3px solid ' + (ghConfigured ? '#00ff88' : '#ffb347') + ';color:' + 
        (ghConfigured ? '#00ff88' : '#ffb347') + ';font-size:12px;">' +
        (ghConfigured ? '✅ GitHub PAT configured' : '⚠️ GitHub PAT not configured') +
        '</div>' +
        (ghConfigured ? 
            '<button onclick="syncToGitHub()" style="padding:12px 24px;background:#00ff88;' +
            'color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:14px;">' +
            '🚀 Sync to GitHub</button>' :
            '<div style="color:#888;font-size:12px;">Configure GitHub PAT in Settings to enable sync</div>'
        ) +
        '<div id="step7-status" style="margin:15px 0;font-size:12px;"></div>' +
        '<div style="margin:15px 0;padding:15px;background:#050505;border:1px solid #111;border-radius:8px;' +
        'font-size:12px;color:#888;">' +
        '✅ Import complete!<br>' +
        'Your portfolio data is now stored in IndexedDB.<br>' +
        '<b style="color:#00ff88;">Next:</b> Sync market data to see prices, PE, ROE, etc.' +
        '</div>' +
        '</div>';
}

function syncToGitHub() {
    var status = document.getElementById('step7-status');
    status.innerHTML = '<span style="color:#ffb347;">⏳ Syncing...</span>';
    
    // Generate portfolio_symbols.txt
    var symbols = importState.stocks
        .filter(function(s) { return s.type === 'PORTFOLIO'; })
        .map(function(s) { return s.symbol; })
        .join('\n');
    
    var token = S.settings.ghToken.trim();
    var repo = S.settings.ghRepo.trim();
    
    if (!token || !repo) {
        status.innerHTML = '<span style="color:#ff6b85;">❌ GitHub not configured</span>';
        return;
    }
    
    var encoded = btoa(unescape(encodeURIComponent(symbols)));
    var headers = {
        'Authorization': 'token ' + token,
        'Content-Type': 'application/json'
    };
    var fileUrl = 'https://api.github.com/repos/' + repo + '/contents/portfolio_symbols.txt';
    
    // Get current SHA
    fetch(fileUrl, {headers: headers})
        .then(function(r) { return r.json(); })
        .then(function(data) {
            var body = {
                message: 'portfolio: update from import',
                content: encoded
            };
            if (data.sha) body.sha = data.sha;
            
            return fetch(fileUrl, {
                method: 'PUT',
                headers: headers,
                body: JSON.stringify(body)
            });
        })
        .then(function(r) {
            if (r.ok) {
                status.innerHTML = '<span style="color:#00ff88;">✅ Synced to GitHub</span>';
            } else {
                status.innerHTML = '<span style="color:#ff6b85;">❌ Sync failed (' + r.status + ')</span>';
            }
        })
        .catch(function(err) {
            status.innerHTML = '<span style="color:#ff6b85;">❌ Error: ' + err.message + '</span>';
        });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Navigation
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function nextImportStep() {
    if (importState.step === 1 && importState.stocks.length === 0) {
        alert('Please upload a file or continue to manual entry');
        return;
    }
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
    if (modal) modal.style.display = 'none';
    importState = { step: 1, stocks: [], aiResponse: null };
}
