/**
 * app-import.js v2.2 - Enhanced Import Workflow
 * - CSV & XLS parsing (with SheetJS fallback)
 * - Step 7: GitHub PAT sync
 * - Tested CSV parsing
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
    
    // Step indicator
    html += '<div style="margin-bottom:20px;font-size:12px;color:#555;font-family:monospace;">' +
        'Step ' + importState.step + ' of 7: ';
    
    var stepTitles = ['Upload CSV/XLS', 'Manual Entries', 'AI Prompt', 'Paste Response', 'Edit & Validate', 'Save to DB', 'GitHub Sync'];
    html += stepTitles[importState.step - 1];
    html += '</div>';
    
    // Progress bar
    var progress = (importState.step / 7) * 100;
    html += '<div style="width:100%;height:4px;background:#111;border-radius:2px;margin-bottom:20px;overflow:hidden;">' +
        '<div style="width:' + progress + '%;height:100%;background:#00ff88;"></div></div>';
    
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
    
    // Modal
    var modal = document.getElementById('import-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'import-modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.8);z-index:9000;display:flex;align-items:center;justify-content:center;overflow-y:auto;';
        document.body.appendChild(modal);
    }
    
    modal.innerHTML = '<div style="background:#000;border:1px solid #222;border-radius:12px;padding:20px;max-height:90vh;overflow-y:auto;width:90%;max-width:900px;margin:20px;">' +
        html + 
        '<div style="margin-top:20px;display:flex;gap:10px;justify-content:flex-end;">' +
        '<button onclick="closeImportModal()" style="padding:10px 20px;background:#333;border:none;color:#fff;border-radius:6px;cursor:pointer;">Cancel</button>' +
        (importState.step > 1 ? '<button onclick="prevImportStep()" style="padding:10px 20px;background:#444;border:none;color:#fff;border-radius:6px;cursor:pointer;">← Back</button>' : '') +
        (importState.step < 7 ? '<button onclick="nextImportStep()" style="padding:10px 20px;background:#00ff88;border:none;color:#000;border-radius:6px;cursor:pointer;font-weight:bold;">Next →</button>' : '') +
        '</div></div>';
    
    modal.style.display = 'flex';
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 1: Upload CSV/XLS
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep1() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Upload CSV or XLS File</h3>' +
        '<p style="margin:10px 0;color:#888;font-size:12px;">' +
        'Format: Name, Symbol, QTY, AVG (QTY & AVG optional)<br>' +
        'Supports: CSV, TXT, XLS, XLSX' +
        '</p>' +
        '<div style="margin:15px 0;padding:20px;border:2px dashed #222;border-radius:8px;text-align:center;cursor:pointer;background:#050505;" onclick="document.getElementById(\'file-input\').click()">' +
        '<div style="font-size:32px;margin-bottom:10px;">📁</div>' +
        '<div style="color:#fff;font-weight:bold;">Click to upload CSV/XLS</div>' +
        '</div>' +
        '<input type="file" id="file-input" accept=".csv,.txt,.xls,.xlsx" style="display:none;" onchange="handleImportFile(this.files[0])">' +
        '<div id="file-status" style="margin:10px 0;font-size:12px;color:#666;"></div>' +
        '<div id="step1-preview" style="margin:10px 0;"></div>' +
        '</div>';
}

function handleImportFile(file) {
    if (!file) return;
    var status = document.getElementById('file-status');
    status.innerHTML = '<span style="color:#ffb347;">⏳ Reading...</span>';
    
    var ext = file.name.split('.').pop().toLowerCase();
    
    if (ext === 'csv' || ext === 'txt') {
        // Plain CSV
        var reader = new FileReader();
        reader.onload = function(e) {
            try {
                processImportCSV(e.target.result);
                status.innerHTML = '<span style="color:#00ff88;">✅ Loaded</span>';
            } catch(err) {
                status.innerHTML = '<span style="color:#ff6b85;">❌ Error: ' + err.message + '</span>';
            }
        };
        reader.onerror = function() {
            status.innerHTML = '<span style="color:#ff6b85;">❌ File read error</span>';
        };
        reader.readAsText(file);
    } else if (ext === 'xls' || ext === 'xlsx') {
        // XLS/XLSX - load SheetJS
        loadSheetJS(function() {
            var reader = new FileReader();
            reader.onload = function(e) {
                try {
                    var wb = XLSX.read(e.target.result, {type: 'binary'});
                    var ws = wb.Sheets[wb.SheetNames[0]];
                    var csv = XLSX.utils.sheet_to_csv(ws);
                    processImportCSV(csv);
                    status.innerHTML = '<span style="color:#00ff88;">✅ Loaded</span>';
                } catch(err) {
                    status.innerHTML = '<span style="color:#ff6b85;">❌ Error: ' + err.message + '</span>';
                }
            };
            reader.onerror = function() {
                status.innerHTML = '<span style="color:#ff6b85;">❌ File read error</span>';
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
            '<span style="color:#ffb347;">⚠️ XLS support unavailable, convert to CSV</span>';
    };
    document.head.appendChild(s);
}

function processImportCSV(csvText) {
    var lines = csvText.split(/\r?\n/).filter(function(l) { return l.trim().length > 0; });
    if (lines.length < 1) throw new Error('Empty file');
    
    importState.stocks = [];
    
    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (!line) continue;
        
        // Simple CSV parse: split by comma
        var parts = line.split(',').map(function(p) { return p.trim(); });
        if (!parts[0]) continue;
        
        // Skip header
        if (parts[0].toLowerCase().includes('name') || parts[0].toLowerCase().includes('stock')) {
            continue;
        }
        
        importState.stocks.push({
            name: parts[0] || '',
            symbol: parts[1] || '',
            qty: parts[2] ? parseFloat(parts[2]) : null,
            avg: parts[3] ? parseFloat(parts[3]) : null,
            type: (parts[2] && parseFloat(parts[2]) > 0) ? 'PORTFOLIO' : 'WATCHLIST',
            isin: '',
            sector: '',
            industry: '',
            status: ''
        });
    }
    
    showImportUI();
    renderStep1Preview();
}

function renderStep1Preview() {
    if (importState.stocks.length === 0) return;
    
    var html = '<table style="width:100%;border-collapse:collapse;font-size:11px;margin:10px 0;border:1px solid #111;border-radius:4px;overflow:hidden;">' +
        '<tr style="background:#111;"><th style="padding:8px;text-align:left;color:#00ff88;">Name</th>' +
        '<th style="padding:8px;color:#00ff88;">Symbol</th><th style="padding:8px;color:#00ff88;">Type</th>' +
        '<th style="padding:8px;color:#00ff88;">QTY</th><th style="padding:8px;color:#00ff88;">AVG</th></tr>';
    
    var pCount = 0, wCount = 0;
    importState.stocks.forEach(function(s) {
        if (s.type === 'PORTFOLIO') pCount++; else wCount++;
        html += '<tr style="border-bottom:1px solid #111;"><td style="padding:6px;">' + s.name + '</td>' +
            '<td style="padding:6px;color:#00ff88;">' + s.symbol + '</td>' +
            '<td style="padding:6px;color:' + (s.type === 'PORTFOLIO' ? '#00ff88' : '#ffb347') + ';">' + s.type + '</td>' +
            '<td style="padding:6px;text-align:right;">' + (s.qty || '-') + '</td>' +
            '<td style="padding:6px;text-align:right;">' + (s.avg ? '₹' + s.avg.toFixed(2) : '-') + '</td></tr>';
    });
    
    html += '</table><div style="font-size:11px;color:#00ff88;margin-top:10px;">✅ ' + importState.stocks.length + 
        ' stocks (' + pCount + ' portfolio, ' + wCount + ' watchlist)</div>';
    
    document.getElementById('step1-preview').innerHTML = html;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 2: Manual Entries
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep2() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Add Manual Entries</h3>' +
        '<p style="margin:10px 0;color:#888;font-size:12px;">Format: Name,Symbol,QTY,AVG (one per line)</p>' +
        '<textarea id="manual-entries" style="width:100%;height:120px;padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;font-size:11px;border-radius:4px;"></textarea>' +
        '<div style="margin:10px 0;"><button onclick="addManualEntries()" style="padding:8px 16px;background:#00ff88;color:#000;border:none;border-radius:4px;cursor:pointer;font-weight:bold;">+ Add</button></div>' +
        '<div id="step2-count" style="font-size:11px;color:#888;"></div>' +
        '</div>';
}

function addManualEntries() {
    var text = document.getElementById('manual-entries').value;
    if (!text.trim()) return;
    
    text.split('\n').forEach(function(line) {
        if (!line.trim()) return;
        var parts = line.split(',').map(function(p) { return p.trim(); });
        if (!parts[0]) return;
        
        importState.stocks.push({
            name: parts[0],
            symbol: parts[1] || '',
            qty: parts[2] ? parseFloat(parts[2]) : null,
            avg: parts[3] ? parseFloat(parts[3]) : null,
            type: (parts[2] && parseFloat(parts[2]) > 0) ? 'PORTFOLIO' : 'WATCHLIST',
            isin: '',
            sector: '',
            industry: '',
            status: ''
        });
    });
    
    document.getElementById('manual-entries').value = '';
    document.getElementById('step2-count').innerHTML = '<span style="color:#00ff88;">✅ Total: ' + importState.stocks.length + '</span>';
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 3: AI Prompt
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep3() {
    var symbols = importState.stocks.map(function(s) { return s.symbol; }).filter(function(s) { return s.length > 0; }).join(', ');
    
    var prompt = 'Get ISIN, sector, industry for these Indian stocks (NSE/BSE):\n' + symbols + 
        '\n\nFormat: Symbol|ISIN|Sector|Industry\nExample:\nHDFCBANK|INE040A01034|Banking|Financial Services';
    
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">AI Prompt</h3>' +
        '<p style="margin:10px 0;color:#888;font-size:12px;">Copy & paste to ChatGPT/Claude</p>' +
        '<textarea id="ai-prompt" readonly style="width:100%;height:150px;padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;font-size:10px;border-radius:4px;resize:none;">' + prompt + '</textarea>' +
        '<button onclick="copyPrompt()" style="margin:10px 0;padding:8px 16px;background:#00ff88;color:#000;border:none;border-radius:4px;cursor:pointer;font-weight:bold;">📋 Copy</button>' +
        '</div>';
}

function copyPrompt() {
    document.getElementById('ai-prompt').select();
    document.execCommand('copy');
    alert('Copied!');
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 4: Paste Response
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep4() {
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Paste AI Response</h3>' +
        '<p style="margin:10px 0;color:#888;font-size:12px;">Format: Symbol|ISIN|Sector|Industry</p>' +
        '<textarea id="ai-response" style="width:100%;height:150px;padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;font-size:11px;border-radius:4px;"></textarea>' +
        '<button onclick="parseAIResponse()" style="margin:10px 0;padding:8px 16px;background:#00ff88;color:#000;border:none;border-radius:4px;cursor:pointer;font-weight:bold;">Parse</button>' +
        '<div id="step4-result" style="margin:10px 0;font-size:11px;"></div>' +
        '</div>';
}

function parseAIResponse() {
    var text = document.getElementById('ai-response').value;
    var matched = 0;
    
    text.split('\n').forEach(function(line) {
        if (!line.includes('|')) return;
        var parts = line.split('|').map(function(p) { return p.trim(); });
        
        var stock = importState.stocks.find(function(s) { return s.symbol === parts[0]; });
        if (stock) {
            stock.isin = parts[1] || '';
            stock.sector = parts[2] || '';
            stock.industry = parts[3] || '';
            stock.status = 'matched';
            matched++;
        }
    });
    
    importState.stocks.forEach(function(s) { if (!s.status) s.status = 'AI_GEN'; });
    
    document.getElementById('step4-result').innerHTML = '<span style="color:#00ff88;">✅ Matched ' + matched + '/' + importState.stocks.length + '</span>';
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 5: Edit & Validate
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep5() {
    var html = '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Review & Edit</h3>' +
        '<div style="overflow-x:auto;border:1px solid #111;border-radius:4px;margin:10px 0;">' +
        '<table style="width:100%;border-collapse:collapse;font-size:10px;">' +
        '<tr style="background:#111;"><th style="padding:6px;text-align:left;color:#00ff88;">Name</th>' +
        '<th style="padding:6px;color:#00ff88;">Symbol</th><th style="padding:6px;color:#00ff88;">ISIN</th>' +
        '<th style="padding:6px;color:#00ff88;">Qty</th><th style="padding:6px;color:#00ff88;">Avg</th>' +
        '<th style="padding:6px;color:#00ff88;">Type</th><th style="padding:6px;color:#00ff88;"></th></tr>';
    
    importState.stocks.forEach(function(s, i) {
        var color = s.status === 'matched' ? '#00ff88' : '#ffb347';
        html += '<tr style="border-bottom:1px solid #111;"><td style="padding:6px;">' + s.name + '</td>' +
            '<td style="padding:6px;color:#00ff88;">' + s.symbol + '</td>' +
            '<td style="padding:6px;color:' + color + ';font-size:9px;">' + (s.isin || '-') + '</td>' +
            '<td style="padding:6px;text-align:right;cursor:pointer;" onclick="editStock(' + i + ',\'qty\')">' + (s.qty || '-') + '</td>' +
            '<td style="padding:6px;text-align:right;cursor:pointer;" onclick="editStock(' + i + ',\'avg\')">' + (s.avg ? s.avg.toFixed(2) : '-') + '</td>' +
            '<td style="padding:6px;cursor:pointer;color:' + (s.type === 'PORTFOLIO' ? '#00ff88' : '#ffb347') + ';" onclick="toggleType(' + i + ')">' + s.type + '</td>' +
            '<td style="padding:6px;"><button onclick="deleteStock(' + i + ')" style="background:#ff6b85;color:#fff;border:none;padding:2px 6px;border-radius:3px;cursor:pointer;font-size:9px;">Del</button></td></tr>';
    });
    
    html += '</table></div></div>';
    return html;
}

function editStock(i, field) {
    var val = importState.stocks[i][field];
    var newVal = prompt('Edit ' + field + ':', val || '');
    if (newVal !== null) {
        importState.stocks[i][field] = newVal ? parseFloat(newVal) : null;
        showImportUI();
    }
}

function toggleType(i) {
    importState.stocks[i].type = importState.stocks[i].type === 'PORTFOLIO' ? 'WATCHLIST' : 'PORTFOLIO';
    showImportUI();
}

function deleteStock(i) {
    if (confirm('Delete ' + importState.stocks[i].name + '?')) {
        importState.stocks.splice(i, 1);
        showImportUI();
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 6: Save to DB
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep6() {
    var pCount = importState.stocks.filter(function(s) { return s.type === 'PORTFOLIO'; }).length;
    var wCount = importState.stocks.filter(function(s) { return s.type === 'WATCHLIST'; }).length;
    
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">Save to Database</h3>' +
        '<div style="margin:15px 0;padding:15px;background:#111;border-left:3px solid #00ff88;border-radius:4px;color:#00ff88;font-size:12px;">' +
        '✅ Portfolio: ' + pCount + '<br>📌 Watchlist: ' + wCount + '<br>Storage: IndexedDB / UnifiedStocks' +
        '</div>' +
        '<button onclick="saveToIndexedDB()" style="padding:10px 20px;background:#00ff88;color:#000;border:none;border-radius:4px;cursor:pointer;font-weight:bold;">💾 Save</button>' +
        '<div id="step6-status" style="margin:15px 0;font-size:12px;"></div>' +
        '</div>';
}

function saveToIndexedDB() {
    var status = document.getElementById('step6-status');
    status.innerHTML = '<span style="color:#ffb347;">⏳ Saving...</span>';
    
    try {
        var req = indexedDB.open('BharatEngineDB', 1);
        req.onerror = function() { status.innerHTML = '<span style="color:#ff6b85;">❌ DB Error</span>'; };
        req.onsuccess = function(e) {
            var db = e.target.result;
            try {
                var tx = db.transaction('UnifiedStocks', 'readwrite');
                var store = tx.objectStore('UnifiedStocks');
                store.clear();
                
                importState.stocks.forEach(function(s) {
                    store.put({
                        sym: s.symbol,
                        name: s.name,
                        isin: s.isin,
                        sector: s.sector,
                        industry: s.industry,
                        type: s.type,
                        qty: s.qty,
                        avg: s.avg,
                        source: 'manual'
                    });
                });
                
                tx.oncomplete = function() {
                    status.innerHTML = '<span style="color:#00ff88;">✅ Saved ' + importState.stocks.length + ' stocks</span>';
                };
                tx.onerror = function() { status.innerHTML = '<span style="color:#ff6b85;">❌ Save Error</span>'; };
            } catch(err) {
                status.innerHTML = '<span style="color:#ff6b85;">❌ ' + err.message + '</span>';
            }
        };
    } catch(err) {
        status.innerHTML = '<span style="color:#ff6b85;">❌ ' + err.message + '</span>';
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 7: GitHub Sync with PAT
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep7() {
    var ghConfigured = (S && S.settings && S.settings.ghToken && S.settings.ghToken.trim()) ? true : false;
    
    return '<div style="padding:20px;background:#0a0a0a;border:1px solid #111;border-radius:8px;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:14px;">GitHub Sync (Optional)</h3>' +
        '<p style="margin:10px 0;color:#888;font-size:12px;">' +
        'Sync portfolio to GitHub and trigger auto-price update via GitHub Actions' +
        '</p>' +
        '<div style="margin:15px 0;padding:15px;background:#111;border-radius:4px;border-left:3px solid ' + 
        (ghConfigured ? '#00ff88' : '#ffb347') + ';color:' + (ghConfigured ? '#00ff88' : '#ffb347') + ';font-size:12px;">' +
        (ghConfigured ? '✅ GitHub PAT configured' : '⚠️ GitHub PAT not configured') +
        '</div>' +
        (ghConfigured ? 
            '<button onclick="syncToGitHub()" style="padding:10px 20px;background:#00ff88;color:#000;border:none;border-radius:4px;cursor:pointer;font-weight:bold;">🚀 Sync to GitHub</button>' :
            '<div style="color:#888;font-size:12px;">Configure GitHub PAT in Settings to enable</div>'
        ) +
        '<div id="step7-status" style="margin:15px 0;font-size:12px;"></div>' +
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

// Navigation
function nextImportStep() {
    if (importState.step === 1 && importState.stocks.length === 0) {
        alert('Add stocks first');
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
    var m = document.getElementById('import-modal');
    if (m) m.style.display = 'none';
    importState = { step: 1, stocks: [], aiResponse: null };
}
