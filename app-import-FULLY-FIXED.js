/**
 * app-import.js - Import Workflow (FULLY FIXED)
 * Step 1: File loading working (drag/drop + click)
 * Step 7: PAT management with upload/append/clear/load options
 */

var importState = {
    step: 1,
    stocks: [],
    aiResponse: null
};

function openImportWorkflow() {
    importState.step = 1;
    importState.stocks = [];
    showImportUI();
}

function showImportUI() {
    var html = '<div id="import-wizard" style="padding:20px;background:#0a0a0a;border-radius:12px;max-width:900px;">';
    
    html += '<div style="margin-bottom:10px;font-size:12px;color:#555;font-family:monospace;">Step ' + importState.step + ' of 7: ';
    var stepTitles = ['Upload CSV/XLS', 'Manual Entries', 'AI Prompt', 'Paste Response', 'Edit & Validate', 'Save to DB', 'Post to GitHub'];
    html += stepTitles[importState.step - 1] + '</div>';
    
    html += '<div style="margin-bottom:15px;display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap;">' +
        '<button onclick="closeImportModal()" style="padding:8px 16px;background:#333;border:none;color:#fff;border-radius:6px;cursor:pointer;font-size:12px;">Cancel</button>' +
        (importState.step > 1 ? '<button onclick="prevImportStep()" style="padding:8px 16px;background:#444;border:none;color:#fff;border-radius:6px;cursor:pointer;font-size:12px;">← Back</button>' : '') +
        (importState.step < 7 ? '<button onclick="nextImportStep()" style="padding:8px 16px;background:#00ff88;border:none;color:#000;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">Next →</button>' : 
        '<button onclick="closeImportModal()" style="padding:8px 16px;background:#00ff88;border:none;color:#000;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">Close ✓</button>') +
        '</div>';
    
    var progress = (importState.step / 7) * 100;
    html += '<div style="width:100%;height:4px;background:#111;border-radius:2px;margin-bottom:20px;overflow:hidden;"><div style="width:' + progress + '%;height:100%;background:#00ff88;"></div></div>';
    
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
    
    var modal = document.getElementById('import-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'import-modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:9000;display:flex;align-items:center;justify-content:center;overflow-y:auto;';
        document.body.appendChild(modal);
    }
    
    modal.innerHTML = '<div style="background:#000;border:1px solid #222;border-radius:12px;padding:20px;max-height:90vh;overflow-y:auto;width:90%;max-width:900px;margin:20px;">' + html + '</div>';
    modal.style.display = 'flex';
    
    // Initialize file input after DOM is ready
    setTimeout(function() {
        initializeFileInput();
    }, 100);
}

function initializeFileInput() {
    var dropZone = document.getElementById('drop-zone');
    var fileInput = document.getElementById('file-input');
    
    if (!dropZone || !fileInput) return;
    
    // Click handler
    dropZone.onclick = function(e) {
        e.preventDefault();
        e.stopPropagation();
        fileInput.click();
    };
    
    // Drag handlers
    dropZone.ondragover = function(e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.style.background = '#1a1a1a';
        dropZone.style.borderColor = '#00ff88';
    };
    
    dropZone.ondragleave = function(e) {
        e.preventDefault();
        dropZone.style.background = '#050505';
        dropZone.style.borderColor = '#222';
    };
    
    dropZone.ondrop = function(e) {
        e.preventDefault();
        e.stopPropagation();
        dropZone.style.background = '#050505';
        dropZone.style.borderColor = '#222';
        
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            processFile(e.dataTransfer.files[0]);
        }
    };
    
    // File input change handler
    fileInput.onchange = function(e) {
        if (e.target.files && e.target.files.length > 0) {
            processFile(e.target.files[0]);
        }
    };
}

function renderStep1() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">📁 Upload Stock List</h3>' +
        '<div style="padding:10px;background:#111;border-left:3px solid #00ff88;margin:10px 0;font-size:11px;color:#888;border-radius:4px;">' +
        '<b style="color:#00ff88;">Format:</b> Name, Quantity, Average Price<br>' +
        '<b style="color:#ffb347;">Example:</b> HDFC Bank Limited,84,817.50<br>' +
        'Supports: CSV, Excel, TSV, Text files' +
        '</div>' +
        '<div id="drop-zone" style="margin:15px 0;padding:30px;border:2px dashed #333;border-radius:8px;text-align:center;background:#050505;cursor:pointer;transition:all 0.3s;">' +
        '<div style="font-size:40px;margin-bottom:10px;">📤</div>' +
        '<div style="color:#fff;font-weight:bold;margin-bottom:5px;">Click or drag files here</div>' +
        '<div style="color:#666;font-size:12px;">CSV, Excel, TSV files supported</div>' +
        '</div>' +
        '<input type="file" id="file-input" accept=".csv,.xls,.xlsx,.tsv,.txt" style="display:none;">' +
        '<div id="file-status" style="margin:10px 0;font-size:12px;"></div>' +
        '<div id="step1-preview"></div>' +
        '</div>';
}

function processFile(file) {
    if (!file) return;
    
    console.log('File selected:', file.name, 'Size:', file.size, 'Type:', file.type);
    
    var status = document.getElementById('file-status');
    if (!status) {
        console.error('Status element not found');
        return;
    }
    
    status.innerHTML = '<span style="color:#ffb347;">⏳ Reading: ' + file.name + '</span>';
    
    var ext = file.name.split('.').pop().toLowerCase();
    
    if (ext === 'csv' || ext === 'txt' || ext === 'tsv') {
        var reader = new FileReader();
        
        reader.onload = function(e) {
            try {
                console.log('CSV loaded, bytes:', e.target.result.length);
                var csv = e.target.result;
                parseAndLoadCSV(csv);
                status.innerHTML = '<span style="color:#00ff88;">✅ Loaded ' + importState.stocks.length + ' stocks</span>';
                renderStep1Preview();
            } catch(err) {
                console.error('Parse error:', err);
                status.innerHTML = '<span style="color:#ff6b85;">❌ ' + err.message + '</span>';
            }
        };
        
        reader.onerror = function(err) {
            console.error('Read error:', err);
            status.innerHTML = '<span style="color:#ff6b85;">❌ Error reading file</span>';
        };
        
        reader.readAsText(file);
        
    } else if (ext === 'xls' || ext === 'xlsx') {
        status.innerHTML = '<span style="color:#ffb347;">⏳ Loading Excel library...</span>';
        loadXLSX(function() {
            var reader = new FileReader();
            
            reader.onload = function(e) {
                try {
                    console.log('Excel loaded, bytes:', e.target.result.byteLength);
                    var data = new Uint8Array(e.target.result);
                    var wb = XLSX.read(data, {type: 'array'});
                    
                    if (!wb || !wb.SheetNames || wb.SheetNames.length === 0) {
                        throw new Error('No sheets found in Excel file');
                    }
                    
                    var ws = wb.Sheets[wb.SheetNames[0]];
                    var csv = XLSX.utils.sheet_to_csv(ws);
                    console.log('Excel converted to CSV');
                    parseAndLoadCSV(csv);
                    status.innerHTML = '<span style="color:#00ff88;">✅ Loaded ' + importState.stocks.length + ' stocks</span>';
                    renderStep1Preview();
                } catch(err) {
                    console.error('Excel error:', err);
                    status.innerHTML = '<span style="color:#ff6b85;">❌ ' + err.message + '</span>';
                }
            };
            
            reader.onerror = function(err) {
                console.error('Excel read error:', err);
                status.innerHTML = '<span style="color:#ff6b85;">❌ Error reading Excel file</span>';
            };
            
            reader.readAsArrayBuffer(file);
        });
    } else {
        status.innerHTML = '<span style="color:#ff6b85;">❌ Unsupported file type</span>';
    }
}

var xlsxLoaded = false;
function loadXLSX(cb) {
    if (xlsxLoaded || window.XLSX) {
        xlsxLoaded = true;
        cb();
        return;
    }
    
    var script = document.createElement('script');
    script.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.min.js';
    script.onload = function() {
        xlsxLoaded = true;
        cb();
    };
    script.onerror = function() {
        alert('Failed to load Excel library');
    };
    document.head.appendChild(script);
}

function parseAndLoadCSV(csv) {
    var lines = csv.split('\n').map(l => l.trim()).filter(l => l.length > 0);
    
    if (lines.length === 0) throw new Error('File is empty');
    
    var headerLine = lines[0];
    var delimiter = ',';
    if (headerLine.includes('\t')) delimiter = '\t';
    else if (headerLine.includes(';')) delimiter = ';';
    
    var headers = headerLine.split(delimiter).map(h => h.trim().toLowerCase());
    
    var nameIdx = -1, qtyIdx = -1, avgIdx = -1;
    for (var i = 0; i < headers.length; i++) {
        if (headers[i].includes('name') || headers[i].includes('stock') || headers[i].includes('company')) nameIdx = i;
        if (headers[i].includes('qty') || headers[i].includes('quantity') || headers[i].includes('shares')) qtyIdx = i;
        if (headers[i].includes('avg') || headers[i].includes('average') || headers[i].includes('price') || headers[i].includes('cost')) avgIdx = i;
    }
    
    if (nameIdx < 0) nameIdx = 0;
    if (qtyIdx < 0 && headers.length > 1) qtyIdx = 1;
    if (avgIdx < 0 && headers.length > 2) avgIdx = 2;
    
    var stocks = [];
    var seen = new Set();
    
    for (var i = 1; i < lines.length; i++) {
        var parts = lines[i].split(delimiter).map(p => p.trim().replace(/['"₹₨]/g, ''));
        
        if (!parts[0]) continue;
        
        var name = parts[nameIdx] || parts[0];
        if (name.toLowerCase().includes('name') || name.toLowerCase().includes('stock')) continue;
        
        var qty = qtyIdx >= 0 && qtyIdx < parts.length ? parseFloat(parts[qtyIdx]) : null;
        var avg = avgIdx >= 0 && avgIdx < parts.length ? parseFloat(parts[avgIdx]) : null;
        
        if (isNaN(qty) || qty <= 0) qty = null;
        if (isNaN(avg) || avg <= 0) avg = null;
        
        if (seen.has(name)) continue;
        
        if (name && qty && avg) {
            seen.add(name);
            stocks.push({
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
    
    if (stocks.length === 0) {
        throw new Error('No valid data found. Ensure file has: Name, Quantity, Average Price');
    }
    
    importState.stocks = stocks;
}

function renderStep1Preview() {
    if (importState.stocks.length === 0) return;
    
    var html = '<div style="margin:15px 0;border:1px solid #222;border-radius:8px;overflow:auto;max-height:300px;">' +
        '<table style="width:100%;border-collapse:collapse;font-size:11px;">' +
        '<tr style="background:#111;border-bottom:1px solid #222;position:sticky;top:0;">' +
        '<th style="padding:8px;text-align:left;color:#00ff88;">Stock Name</th>' +
        '<th style="padding:8px;text-align:right;color:#00ff88;width:60px;">QTY</th>' +
        '<th style="padding:8px;text-align:right;color:#00ff88;width:80px;">AVG</th>' +
        '</tr>';
    
    importState.stocks.forEach(function(stock) {
        html += '<tr style="border-bottom:1px solid #111;">' +
            '<td style="padding:8px;">' + stock.name.substring(0, 35) + '</td>' +
            '<td style="padding:8px;text-align:right;">' + stock.qty + '</td>' +
            '<td style="padding:8px;text-align:right;">₹' + stock.avg.toFixed(2) + '</td>' +
            '</tr>';
    });
    
    html += '</table></div>' +
        '<div style="margin:10px 0;font-size:11px;color:#00ff88;font-weight:bold;">✅ ' + importState.stocks.length + ' stocks loaded successfully</div>';
    
    var preview = document.getElementById('step1-preview');
    if (preview) preview.innerHTML = html;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 2: Manual Entries
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep2() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Add Manual Entries</h3>' +
        '<textarea id="manual-entries" style="width:100%;height:120px;padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;font-size:11px;border-radius:6px;resize:vertical;box-sizing:border-box;" placeholder="Stock Name, QTY, AVG&#10;Apple Inc,5,150"></textarea>' +
        '<button onclick="addManualEntries()" style="margin-top:10px;padding:10px 20px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">Add Entries</button>' +
        '<div id="step2-preview" style="margin-top:10px;"></div>' +
        '</div>';
}

function addManualEntries() {
    var textarea = document.getElementById('manual-entries');
    var entries = textarea.value.split('\n').filter(l => l.trim());
    
    entries.forEach(entry => {
        var parts = entry.split(',').map(p => p.trim());
        if (parts.length >= 3) {
            var name = parts[0];
            var qty = parseFloat(parts[1]);
            var avg = parseFloat(parts[2]);
            
            if (name && qty > 0 && avg > 0 && !importState.stocks.find(s => s.name === name)) {
                importState.stocks.push({
                    name, isin: '', qty, avg, sector: '', industry: '', type: 'PORTFOLIO', status: ''
                });
            }
        }
    });
    
    textarea.value = '';
    showImportUI();
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 3: AI Prompt
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep3() {
    var names = importState.stocks.map(s => s.name).join('\n');
    var prompt = `For these Indian company names, get ISIN code, Sector, and Industry.

Company Names:
${names}

⚠️ CRITICAL OUTPUT FORMAT (pipe separated, no extra spaces):

Name|ISIN|Sector|Industry
HDFC Bank Limited|INE040A01034|Banking|Financial Services

Rules:
• Match EXACT company names
• Get ISIN code (INE + 10 chars)
• No spaces around pipe (|)
• Output ONLY the table`;
    
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Generate AI Prompt</h3>' +
        '<textarea id="ai-prompt" readonly style="width:100%;height:250px;padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;font-size:11px;border-radius:6px;resize:none;box-sizing:border-box;">' + prompt + '</textarea>' +
        '<button onclick="copyToClipboard(document.getElementById(\'ai-prompt\'))" style="margin-top:10px;padding:10px 20px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">📋 Copy</button>' +
        '</div>';
}

function copyToClipboard(elem) {
    elem.select();
    document.execCommand('copy');
    alert('✅ Copied to clipboard!');
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 4: Paste AI Response
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep4() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Paste AI Response</h3>' +
        '<textarea id="ai-response" style="width:100%;height:200px;padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;font-size:11px;border-radius:6px;resize:vertical;box-sizing:border-box;" ' +
        'placeholder="Name|ISIN|Sector|Industry&#10;HDFC Bank Limited|INE040A01034|Banking|Financial Services" ' +
        'onpaste="setTimeout(() => parseAIResponse(), 100)"></textarea>' +
        '<div id="step4-status" style="margin:10px 0;font-size:12px;"></div>' +
        '</div>';
}

function parseAIResponse() {
    var response = document.getElementById('ai-response').value;
    if (!response.trim()) return;
    
    var lines = response.split('\n').filter(l => l.trim() && l.includes('|'));
    var matched = 0;
    
    lines.forEach(line => {
        var parts = line.split('|');
        if (parts.length < 4) return;
        
        var name = parts[0].trim();
        if (name.toLowerCase() === 'name') return;
        
        var stock = importState.stocks.find(s => s.name.toLowerCase() === name.toLowerCase());
        if (stock) {
            stock.isin = parts[1].trim();
            stock.sector = parts[2].trim();
            stock.industry = parts[3].trim();
            stock.status = 'matched';
            matched++;
        }
    });
    
    importState.stocks.forEach(s => { if (!s.status) s.status = 'pending'; });
    
    var status = document.getElementById('step4-status');
    if (status) {
        status.innerHTML = '<div style="color:#00ff88;">✅ Matched ' + matched + '/' + importState.stocks.length + ' stocks</div>';
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 5: Edit & Validate
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep5() {
    var html = '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Review & Edit</h3>' +
        '<div style="overflow-x:auto;border:1px solid #111;border-radius:8px;max-height:400px;overflow-y:auto;"><table style="width:100%;border-collapse:collapse;font-size:10px;">' +
        '<tr style="background:#111;border-bottom:1px solid #222;position:sticky;top:0;">' +
        '<th style="padding:6px;text-align:left;color:#00ff88;">Name</th>' +
        '<th style="padding:6px;color:#00ff88;">ISIN</th>' +
        '<th style="padding:6px;color:#00ff88;">Sector</th>' +
        '<th style="padding:6px;text-align:right;color:#00ff88;">Qty</th>' +
        '<th style="padding:6px;text-align:right;color:#00ff88;">Avg</th>' +
        '<th style="padding:6px;">🗑️</th></tr>';
    
    importState.stocks.forEach((stock, idx) => {
        var icon = stock.status === 'matched' ? '✅' : '⚠️';
        html += `<tr style="border-bottom:1px solid #111;">
            <td style="padding:6px;cursor:pointer;" onclick="editCell(${idx}, 'name')">${stock.name.substring(0, 25)}</td>
            <td style="padding:6px;color:${stock.status === 'matched' ? '#00ff88' : '#ffb347'};cursor:pointer;" onclick="editCell(${idx}, 'isin')">${icon} ${stock.isin || '-'}</td>
            <td style="padding:6px;cursor:pointer;" onclick="editCell(${idx}, 'sector')">${stock.sector || '-'}</td>
            <td style="padding:6px;text-align:right;cursor:pointer;" onclick="editCell(${idx}, 'qty')">${stock.qty}</td>
            <td style="padding:6px;text-align:right;cursor:pointer;" onclick="editCell(${idx}, 'avg')">₹${stock.avg.toFixed(2)}</td>
            <td style="padding:6px;"><button onclick="deleteStock(${idx})" style="background:#ff6b85;color:#fff;border:none;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:10px;">✕</button></td>
        </tr>`;
    });
    
    html += '</table></div>' +
        '<div style="margin:10px 0;font-size:11px;color:#888;">Total: ' + importState.stocks.length + ' stocks</div>' +
        '</div>';
    
    return html;
}

function editCell(idx, field) {
    var stock = importState.stocks[idx];
    var val = prompt(`Edit ${field}:`, stock[field] || '');
    if (val !== null) {
        stock[field] = field === 'qty' || field === 'avg' ? parseFloat(val) : val;
        showImportUI();
    }
}

function deleteStock(idx) {
    if (confirm(`Delete ${importState.stocks[idx].name}?`)) {
        importState.stocks.splice(idx, 1);
        showImportUI();
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 6: Save to DB
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep6() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Save to Database</h3>' +
        '<div style="padding:15px;background:#111;border-radius:8px;margin:15px 0;border-left:3px solid #00ff88;">' +
        '<div style="color:#00ff88;">✅ Portfolio: ' + importState.stocks.length + ' stocks</div>' +
        '</div>' +
        '<button onclick="saveToIndexedDB()" style="padding:12px 24px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">💾 Save to DB</button>' +
        '<div id="step6-status" style="margin:15px 0;font-size:12px;"></div>' +
        '</div>';
}

function saveToIndexedDB() {
    var status = document.getElementById('step6-status');
    status.innerHTML = '<span style="color:#ffb347;">⏳ Saving...</span>';
    
    var req = indexedDB.open('BharatEngineDB', 1);
    req.onsuccess = function(e) {
        var db = e.target.result;
        var tx = db.transaction('UnifiedStocks', 'readwrite');
        var store = tx.objectStore('UnifiedStocks');
        store.clear();
        
        importState.stocks.forEach(stock => {
            store.put({
                sym: stock.name.substring(0, 10).toUpperCase(),
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
            status.innerHTML = '<span style="color:#00ff88;">✅ Saved ' + importState.stocks.length + ' stocks</span>';
            setTimeout(() => {
                importState.step = 7;
                showImportUI();
            }, 800);
        };
    };
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 7: Post to GitHub - PAT MANAGEMENT
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep7() {
    var pat = localStorage.getItem('ghPAT') || '';
    var user = localStorage.getItem('ghUser') || '';
    var repo = localStorage.getItem('ghRepo') || '';
    var isConfigured = pat && user && repo;
    
    var html = '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:16px;">🚀 Post to GitHub</h3>';
    
    // PAT Configuration Section
    html += '<div style="padding:15px;background:#111;border-radius:8px;margin:15px 0;border-left:3px solid ' + 
        (isConfigured ? '#00ff88' : '#ffb347') + ';">' +
        '<div style="color:' + (isConfigured ? '#00ff88' : '#ffb347') + ';font-weight:bold;margin-bottom:10px;">' +
        (isConfigured ? '✅ GitHub Configured' : '⚠️ Not Configured') +
        '</div>';
    
    if (isConfigured) {
        html += '<div style="font-size:11px;color:#888;margin-bottom:10px;line-height:1.6;">' +
            '<div>User: <b style="color:#00ff88;">' + user + '</b></div>' +
            '<div>Repo: <b style="color:#00ff88;">' + repo + '</b></div>' +
            '<div>PAT: <b style="color:#00ff88;">' + pat.substring(0, 10) + '...</b></div>' +
            '</div>' +
            '<div style="display:flex;gap:8px;flex-wrap:wrap;">' +
            '<button onclick="showPATForm()" style="padding:8px 12px;background:#444;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:11px;">✏️ Edit</button>' +
            '<button onclick="appendPATForm()" style="padding:8px 12px;background:#444;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:11px;">➕ Append</button>' +
            '<button onclick="clearPAT()" style="padding:8px 12px;background:#ff6b85;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:11px;">🗑️ Clear</button>' +
            '</div>';
    } else {
        html += '<div id="pat-form" style="background:#000;padding:12px;border-radius:6px;margin-bottom:10px;">' +
            '<div style="margin:8px 0;"><label style="color:#888;font-size:11px;">GitHub PAT:</label>' +
            '<input type="password" id="pat-input" placeholder="ghp_xxxxxxxxxxxxx" style="width:100%;padding:8px;background:#050505;border:1px solid #222;color:#fff;border-radius:4px;font-family:monospace;font-size:11px;margin-top:4px;box-sizing:border-box;"></div>' +
            '<div style="margin:8px 0;"><label style="color:#888;font-size:11px;">GitHub User:</label>' +
            '<input type="text" id="user-input" placeholder="murugkan" style="width:100%;padding:8px;background:#050505;border:1px solid #222;color:#fff;border-radius:4px;font-size:11px;margin-top:4px;box-sizing:border-box;"></div>' +
            '<div style="margin:8px 0;"><label style="color:#888;font-size:11px;">GitHub Repo:</label>' +
            '<input type="text" id="repo-input" placeholder="bharatmarkets" style="width:100%;padding:8px;background:#050505;border:1px solid #222;color:#fff;border-radius:4px;font-size:11px;margin-top:4px;box-sizing:border-box;"></div>' +
            '<div style="display:flex;gap:8px;margin-top:10px;">' +
            '<button onclick="savePAT()" style="padding:8px 12px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:11px;">✅ Save</button>' +
            '<button onclick="hidePATForm()" style="padding:8px 12px;background:#444;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:11px;">✕ Cancel</button>' +
            '</div>' +
            '</div>' +
            '<button onclick="showPATForm()" style="padding:8px 12px;background:#444;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:11px;">⚙️ Configure</button>';
    }
    
    html += '</div>';
    
    if (isConfigured) {
        html += '<div style="padding:15px;background:#050505;border:1px solid #222;border-radius:8px;margin:15px 0;font-size:12px;color:#888;">' +
            '<b style="color:#00ff88;">📊 Data Summary:</b><br><br>' +
            '<div style="display:flex;justify-content:space-around;"><div>Total Stocks<br><b style="color:#00ff88;font-size:16px;">' + importState.stocks.length + '</b></div></div>' +
            '</div>';
        
        html += '<button onclick="toggleJSONPreview()" style="padding:10px 20px;background:#444;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:12px;margin-bottom:10px;width:100%;box-sizing:border-box;">📋 Preview JSON</button>';
        html += '<div id="json-preview" style="display:none;padding:10px;background:#000;border:1px solid #222;border-radius:6px;max-height:250px;overflow-y:auto;font-size:9px;font-family:monospace;color:#0f0;margin-bottom:10px;"></div>';
        html += '<button onclick="postToGitHub()" style="padding:12px 24px;background:#00ff88;color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:14px;width:100%;box-sizing:border-box;">📤 Post to GitHub</button>';
    }
    
    html += '<div id="step7-status" style="margin:15px 0;font-size:12px;"></div></div>';
    return html;
}

function showPATForm() {
    document.getElementById('pat-form').style.display = 'block';
    document.getElementById('pat-input').value = localStorage.getItem('ghPAT') || '';
    document.getElementById('user-input').value = localStorage.getItem('ghUser') || '';
    document.getElementById('repo-input').value = localStorage.getItem('ghRepo') || '';
}

function hidePATForm() {
    document.getElementById('pat-form').style.display = 'none';
}

function appendPATForm() {
    showPATForm();
    document.getElementById('pat-input').focus();
}

function savePAT() {
    var pat = document.getElementById('pat-input').value;
    var user = document.getElementById('user-input').value;
    var repo = document.getElementById('repo-input').value;
    
    if (!pat || !user || !repo) {
        alert('❌ Fill all fields');
        return;
    }
    
    localStorage.setItem('ghPAT', pat);
    localStorage.setItem('ghUser', user);
    localStorage.setItem('ghRepo', repo);
    alert('✅ Saved!');
    showImportUI();
}

function clearPAT() {
    if (confirm('Clear GitHub config?')) {
        localStorage.removeItem('ghPAT');
        localStorage.removeItem('ghUser');
        localStorage.removeItem('ghRepo');
        alert('✅ Cleared!');
        showImportUI();
    }
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
    var data = {
        updated: new Date().toISOString(),
        count: importState.stocks.length,
        symbols: importState.stocks.map(s => ({
            sym: (s.name.split(' ')[0] || 'SYM').substring(0, 10).toUpperCase(),
            name: s.name,
            isin: s.isin,
            sector: s.sector,
            industry: s.industry,
            type: s.type.toLowerCase(),
            source: 'import'
        })).sort((a, b) => a.sym.localeCompare(b.sym))
    };
    
    var preview = document.getElementById('json-preview');
    preview.innerHTML = JSON.stringify(data, null, 2).replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function postToGitHub() {
    var pat = localStorage.getItem('ghPAT');
    var user = localStorage.getItem('ghUser');
    var repo = localStorage.getItem('ghRepo');
    
    if (!pat || !user || !repo) {
        alert('❌ Not configured');
        return;
    }
    
    if (!confirm(`📤 Post ${importState.stocks.length} stocks to GitHub?`)) return;
    
    var status = document.getElementById('step7-status');
    status.innerHTML = '<span style="color:#ffb347;">⏳ Preparing...</span>';
    
    var data = {
        updated: new Date().toISOString(),
        count: importState.stocks.length,
        symbols: importState.stocks.map(s => ({
            sym: (s.name.split(' ')[0] || 'SYM').substring(0, 10).toUpperCase(),
            name: s.name,
            isin: s.isin,
            sector: s.sector,
            industry: s.industry,
            type: s.type.toLowerCase(),
            source: 'import'
        })).sort((a, b) => a.sym.localeCompare(b.sym))
    };
    
    var content = btoa(unescape(encodeURIComponent(JSON.stringify(data, null, 2))));
    var url = `https://api.github.com/repos/${user}/${repo}/contents/unified-symbols.json`;
    
    status.innerHTML = '<span style="color:#ffb347;">⏳ Connecting...</span>';
    
    fetch(url, {
        headers: { 'Authorization': `token ${pat}`, 'Accept': 'application/vnd.github.v3+json' }
    })
    .then(r => r.json())
    .then(d => {
        status.innerHTML = '<span style="color:#ffb347;">⏳ Posting...</span>';
        return fetch(url, {
            method: 'PUT',
            headers: { 'Authorization': `token ${pat}`, 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: `Import: ${importState.stocks.length} stocks`, content, sha: d.sha })
        });
    })
    .then(r => r.json())
    .then(d => {
        if (d.commit) {
            status.innerHTML = '<div style="color:#00ff88;"><b>✅ Posted!</b><br><br>' +
                '<span style="color:#888;font-size:11px;">SHA: ' + d.commit.sha.substring(0, 10) + '...<br>' +
                importState.stocks.length + ' stocks written</span></div>';
        } else {
            status.innerHTML = '<span style="color:#ff6b85;">❌ ' + (d.message || 'Error') + '</span>';
        }
    })
    .catch(e => {
        status.innerHTML = '<span style="color:#ff6b85;">❌ ' + e.message + '</span>';
    });
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// Navigation
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
    if (modal) modal.style.display = 'none';
}
