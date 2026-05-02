/**
 * app-import.js - Enhanced Import Workflow
 * 7-step stock data import with CSV/Excel parsing, validation, and GitHub integration
 * 
 * Code Style:
 * - Uses var for compatibility with older browsers
 * - Mix of single and double quotes for flexibility in HTML generation
 * - Configuration constants defined in CONFIG object at top
 * - Organized into logical sections with clear dividers
 * 
 * FUNCTION GROUPS:
 * 1. Constants & State (CONFIG, importState)
 * 2. File Import (handleFileImport, openImportWorkflow, showImportUI)
 * 3. Step Rendering (renderStep1-7)
 * 4. CSV Processing (processImportCSV, handleDrop, loadSheetJS)
 * 5. Data Editing (editCell, deleteStock, attachDeleteListeners)
 * 6. Database Operations (saveToIndexedDB, saveAndContinue)
 * 7. GitHub Integration (postToGitHub, setImportMode)
 * 8. Utilities (showCustomConfirm, closeImportModal, navigation)
 */

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// CONSTANTS & CONFIGURATION
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

var CONFIG = {
    TOTAL_STEPS: 6,
    DATABASE_NAME: "OnyxPortfolioDB",
    DATABASE_VERSION: 8,
    STORE_NAME: "Stocks",
    MODAL_Z_INDEX: 9000,
    STEP_TITLES: [
        "📤 Upload CSV/XLS",
        "✏️ Manual Entries (Opt)",
        "🤖 AI Prompt (Opt)",
        "📋 Paste Response",
        "📝 Edit & Validate",
        "💾 Post to GitHub"
    ],
    COLORS: {
        SUCCESS: "#00ff88",
        ERROR: "#ff6b85",
        WARNING: "#ffb347",
        DARK_BG: "#0a0a0a",
        DARKER_BG: "#050505",
        BORDER: "#111",
        BORDER_LIGHT: "#222",
        BORDER_ACCENT: "#333",
        TEXT_MUTED: "#555",
        TEXT_DIM: "#888"
    }
};

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STATE MANAGEMENT
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


var importState = {
    step: 1,
    stocks: [],
    aiResponse: null,
    importMode: "append"
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
        alert("❌ Error opening import wizard. Please refresh and try again.");
    }
}

function showImportUI() {
    try {
        var html = '<div id="import-wizard" style="' +
            'padding:8px;background:#0a0a0a;border-radius:0;margin:0;' +
            '">';
        
        // Step indicator - BRIGHT TITLE
        html += '<div style="margin-bottom:15px;font-size:18px;font-weight:bold;color:#00ff88;">' +
            'Step ' + importState.step + ' of ' + CONFIG.TOTAL_STEPS + ' — ';
        
        html += CONFIG.STEP_TITLES[importState.step - 1];
        html += '</div>';
        
        // TOP BUTTONS - no scrolling needed
        html += '<div style="margin-bottom:15px;display:flex;gap:4px;justify-content:flex-end;">' +
            '<button onclick="closeImportModal()" style="padding:8px 16px;background:#333;border:none;color:#fff;' +
            'border-radius:6px;cursor:pointer;font-size:12px;">Cancel</button>' +
            (importState.step > 1 ? '<button onclick="prevImportStep()" style="padding:8px 16px;background:#444;' +
            'border:none;color:#fff;border-radius:6px;cursor:pointer;font-size:12px;">← Back</button>' : '') +
            (importState.step < CONFIG.TOTAL_STEPS ? '<button onclick="nextImportStep()" style="padding:8px 16px;background:#00ff88;' +
            'border:none;color:#000;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">Next →</button>' : 
            '<button onclick="closeImportModal()" style="padding:8px 16px;background:#00ff88;' +
            'border:none;color:#000;border-radius:6px;cursor:pointer;font-weight:bold;font-size:12px;">Close ✓</button>') +
            '</div>';
        
        // Progress bar
        var progress = (importState.step / CONFIG.TOTAL_STEPS) * 100;
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
            'padding:8px;max-height:90vh;overflow-y:auto;width:100%;margin:0;box-sizing:border-box;">' +
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
        alert("❌ Error rendering UI. Please refresh and try again.");
    }
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 1: Upload CSV/XLS - FIXED PARSING
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep1() {
    return '<div style="padding:8px;background:#0a0a0a;border:1px solid #111;border-radius:0;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:16px;font-weight:bold;">📤 Upload Stock List</h3>' +
        '<div style="padding:10px;background:#111;border-left:3px solid #00ff88;margin:6px 0;font-size:12px;color:#ccc;border-radius:4px;">' +
        '<b style="color:#00ff88;">Format:</b> Stock Name, Qty (optional), Avg Price (optional)<br>' +
        '<b style="color:#00ff88;">Example:</b> HDFC Bank,84,817.50 or just HDFC Bank<br>' +
        '</div>' +
        '<div style="margin:8px 0;padding:10px;border:2px dashed #222;border-radius:8px;' +
        'text-align:center;cursor:pointer;background:#050505;position:relative;" ' +
        'id="drop-zone" onclick="document.getElementById(\'file-input\').click()" ondrop="handleDrop(event)" ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)">' +
        '<div style="font-size:32px;margin-bottom:10px;">📁</div>' +
        '<div style="color:#fff;font-weight:bold;margin-bottom:5px;">Click to upload or drag & drop</div>' +
        '<div style="color:#666;font-size:12px;">CSV or Excel files</div>' +
        '</div>' +
        '<input type="file" id="file-input" accept=".csv,.xls,.xlsx,.tsv,.txt" style="display:none;" ' +
        'onchange="handleImportFile(this.files[0])">' +
        '<div id="file-status" style="margin:6px 0;font-size:12px;color:#666;"></div>' +
        '<div id="step1-preview" style="margin:6px 0;"></div>' +
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
    
    // Find column indices
    var nameIdx = -1;
    var qtyIdx = -1;
    var avgIdx = -1;
    var sectorIdx = -1;
    
    for (var i = 0; i < headerParts.length; i++) {
        var h = headerParts[i];
        
        // Stock Name / Symbol / Ticker
        if (!nameIdx && (h === 'stock name' || h === 'symbol' || h === 'ticker' || 
            h === 'name' || (h.includes('stock') && h.includes('name')))) {
            nameIdx = i;
        }
        
        // Quantity - various forms but not "value"
        if (qtyIdx === -1 && (h === 'quantity' || h === 'qty' || h === 'shares' || 
            h.includes('quantity') || h.includes('qty')) && !h.includes('value')) {
            qtyIdx = i;
        }
        
        // Average Price / Cost Price - flexible matching
        if (avgIdx === -1 && ((h.includes('average') || h.includes('avg') || h.includes('cost')) && 
            (h.includes('price') || h.includes('cost')))) {
            avgIdx = i;
        }
        
        // Sector
        if (sectorIdx === -1 && (h === 'sector' || h === 'sector name' || h.includes('sector'))) {
            sectorIdx = i;
        }
    }
    
    // Smarter fallback detection based on column count
    if (nameIdx === -1) {
        nameIdx = 0;
    }
    
    // If Qty not found, look for numeric columns after name
    if (qtyIdx === -1) {
        for (var i = nameIdx + 1; i < headerParts.length; i++) {
            var h = headerParts[i];
            if (h.includes('qty') || h.includes('quantity') || h.includes('shares')) {
                qtyIdx = i;
                break;
            }
        }
        if (qtyIdx === -1 && headerParts.length > 3) {
            qtyIdx = 3;  // Common position in broker exports
        }
    }
    
    // If Avg not found, look after Qty
    if (avgIdx === -1) {
        for (var i = nameIdx + 1; i < headerParts.length; i++) {
            var h = headerParts[i];
            if (h.includes('average') || h.includes('avg') || (h.includes('cost') && h.includes('price'))) {
                avgIdx = i;
                break;
            }
        }
        if (avgIdx === -1 && headerParts.length > 4) {
            avgIdx = 4;  // Common position in broker exports
        }
    }
    
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
        
        // Extract Sector if available
        if (sectorIdx >= 0 && sectorIdx < parts.length) {
            sector = parts[sectorIdx] || null;
        }
        
        // Skip duplicates
        if (seen.has(name)) continue;
        seen.add(name);
        
        // Add stock if has valid name and at least one of qty/avg
        if (name && (qty !== null || avg !== null)) {
            stocks.push({
                name: name,
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
    
    var html = '<div style="margin:8px 0;border:1px solid #222;border-radius:8px;overflow:auto;max-height:300px;">' +
        '<table style="width:100%;border-collapse:collapse;font-size:11px;">' +
        '<tr style="background:#111;border-bottom:1px solid #222;position:sticky;top:0;">' +
        '<th style="padding:6px;text-align:left;color:#00ff88;">Stock Name</th>' +
        '<th style="padding:6px;text-align:right;color:#00ff88;">QTY</th>' +
        '<th style="padding:6px;text-align:right;color:#00ff88;">AVG</th>' +
        '</tr>';
    
    importState.stocks.forEach(function(stock) {
        html += '<tr style="border-bottom:1px solid #111;">' +
            '<td style="padding:6px;">' + stock.name.substring(0, 40) + '</td>' +
            '<td style="padding:6px;text-align:right;">' + stock.qty + '</td>' +
            '<td style="padding:6px;text-align:right;">₹' + stock.avg.toFixed(2) + '</td>' +
            '</tr>';
    });
    
    html += '</table></div>' +
        '<div style="margin:6px 0;font-size:11px;color:#00ff88;">' +
        '✅ Loaded: ' + importState.stocks.length + ' holdings' +
        '</div>';
    
    document.getElementById('step1-preview').innerHTML = html;
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 2: Manual Entries
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep2() {
    var existingCount = importState.stocks.length;
    return '<div style="padding:8px;background:#0a0a0a;border:1px solid #111;border-radius:0;">' +
        '<div style="display:flex;gap:6px;margin-bottom:15px;align-items:center;">' +
        '<button onclick="addManualEntries()" style="padding:8px 16px;background:#00ff88;' +
        'color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">➕ Add Entries</button>' +
        '<span id="step2-status" style="font-size:12px;color:#888;">Total: ' + existingCount + ' stocks</span>' +
        '</div>' +
        
        '<div style="padding:10px;background:#111;border-left:3px solid #00ff88;margin:6px 0;font-size:12px;color:#ccc;border-radius:4px;">' +
        '<b style="color:#00ff88;">Format:</b> Name, Qty (opt), Avg (opt) - One per line<br>' +
        '<b style="color:#ffb347;">Example:</b> Apple,5,150 or Google (watchlist)<br>' +
        '</div>' +
        
        '<textarea id="manual-entries" style="width:100%;height:150px;' +
        'padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;' +
        'font-size:11px;border-radius:6px;resize:vertical;" ' +
        'placeholder="Stock Name,QTY,AVG or just Stock Name"></textarea>' +
        
        '<div id="step2-message" style="margin:6px 0;font-size:12px;color:#888;"></div>' +
        '<div id="step2-preview"></div>' +
        '</div>';
}

function addManualEntries() {
    var textarea = document.getElementById("manual-entries");
    var entries = textarea.value.split("\n").filter(function(l) { return l.trim().length > 0; });
    var addedCount = 0;
    var duplicateCount = 0;
    
    entries.forEach(function(entry) {
        var parts = entry.split(",").map(function(p) { return p.trim(); });
        var name = parts[0];
        
        if (!name) return;
        
        if (importState.stocks.find(function(s) { return s.name === name; })) {
            duplicateCount++;
            return;
        }
        
        var qty = parts.length > 1 && parts[1] ? parseFloat(parts[1]) : null;
        var avg = parts.length > 2 && parts[2] ? parseFloat(parts[2]) : null;
        
        importState.stocks.push({
            name: name,
            isin: "",
            qty: qty,
            avg: avg,
            sector: "",
            industry: "",
            type: (qty && avg) ? "PORTFOLIO" : "WATCHLIST",
            status: ""
        });
        addedCount++;
    });
    
    textarea.value = "";
    
    // Update message and status
    var message = document.getElementById("step2-message");
    var status = document.getElementById("step2-status");
    
    if (addedCount > 0) {
        message.innerHTML = '<span style="color:#00ff88;">✅ Added ' + addedCount + ' stock(s)</span>';
    } else if (duplicateCount > 0) {
        message.innerHTML = '<span style="color:#ffb347;">⚠️ ' + duplicateCount + ' duplicate(s) skipped</span>';
    } else if (entries.length > 0) {
        message.innerHTML = '<span style="color:#ffb347;">⚠️ No valid entries</span>';
    }
    
    if (status) {
        status.innerHTML = 'Total: ' + importState.stocks.length + ' stocks';
    }
    
    showImportUI();
    renderStep2Preview();
}

function renderStep2Preview() {
    if (importState.stocks.length === 0) return;
    
    var html = '<div style="margin:8px 0;border:1px solid #222;border-radius:8px;overflow:auto;max-height:250px;">' +
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
    // Check if stocks exist
    if (!importState.stocks || importState.stocks.length === 0) {
        return '<div style="padding:8px;background:#0a0a0a;border:1px solid #111;border-radius:0;">' +
            '<div style="padding:15px;background:#1a0000;border-left:3px solid #ff6b85;border-radius:4px;margin:8px 0;">' +
            '<b style="color:#ff6b85;">⚠️ No Stocks Added</b><br>' +
            '<span style="font-size:12px;color:#ccc;margin-top:8px;display:block;">' +
            'Please go back and either:<br>' +
            '• Upload a CSV file in Step 1, OR<br>' +
            '• Add manual entries in Step 2<br>' +
            'Then return to this step.' +
            '</span>' +
            '</div>' +
            '</div>';
    }
    
    
    var inputData = importState.stocks.map(function(s) { 
        return s.name;
    }).join("\n");
    
    var prompt = "TASK: Extract NSE/BSE Ticker, ISIN, Sector, Industry for Indian financial instruments.\n\n" +
        "INPUT:\n" + inputData + "\n\n" +
        "STEP 0: NORMALIZE INPUT\n" +
        "- Convert to UPPERCASE\n" +
        "- Expand: LTD→LIMITED, L→LIMITED, IND→INDIA, TECH→TECHNOLOGIES\n" +
        "- Remove extra spaces & special characters\n" +
        "- Resolve truncated names using fuzzy matching\n\n" +
        "STEP 1: CLASSIFY INSTRUMENT TYPE\n" +
        "- EQUITY (company stock)\n" +
        "- ETF (contains 'ETF')\n" +
        "- MUTUAL FUND (contains 'AMC')\n" +
        "- SOVEREIGN BOND (contains 'GOLD', '%', 'SGB')\n" +
        "- CORPORATE BOND / NCD\n" +
        "- SME / UNLISTED\n" +
        "- UNKNOWN\n\n" +
        "STEP 2: DATA EXTRACTION (TYPE-WISE)\n" +
        "EQUITY: NSE ticker, ISIN (INE format), Sector, Industry\n" +
        "ETF: ETF ticker, ISIN (INF format), Sector=ETF, Industry=index\n" +
        "MUTUAL FUND: Ticker=NA, ISIN (INF format), Sector=Mutual Fund, Industry=scheme\n" +
        "SOVEREIGN BOND: Ticker=NA, ISIN (INE format), Sector=Government Securities\n" +
        "CORPORATE BOND: Ticker=NA, ISIN mandatory, Sector=issuer sector\n" +
        "SME/UNLISTED: ticker or ISIN if available, else UNKNOWN\n\n" +
        "STEP 3: SEARCH FALLBACK (MANDATORY)\n" +
        "If not found internally, search:\n" +
        "1. '[NAME] NSE ticker ISIN'\n" +
        "2. '[NAME] BSE code ISIN'\n" +
        "3. '[NAME] ETF ISIN'\n" +
        "4. '[NAME] mutual fund ISIN AMFI'\n" +
        "5. '[NAME] SGB series RBI ISIN'\n" +
        "6. '[NAME] renamed OR delisted OR merged'\n\n" +
        "STEP 4: DATA SOURCE PRIORITY\n" +
        "1. NSE India (primary)\n" +
        "2. BSE India\n" +
        "3. AMFI (mutual funds)\n" +
        "4. RBI (SGB)\n" +
        "5. Official company filings\n\n" +
        "STEP 5: VALIDATION RULES\n" +
        "- NSE ticker must exactly match official symbol\n" +
        "- ISIN format: Equity/Bonds→INE##########, ETF/MF→INF##########\n" +
        "- Do NOT guess missing data\n" +
        "- Prefer NSE over BSE\n" +
        "- If multiple matches→choose primary listed\n\n" +
        "STEP 6: OUTPUT FORMAT (STRICT, NO EXTRA SPACES)\n" +
        "Name,Ticker,ISIN,Sector,Industry,InstrumentType\n" +
        "- Ticker not applicable → NA\n" +
        "- ISIN not found → UNKNOWN\n" +
        "- Return ALL entries (no omissions)\n\n" +
        "EXAMPLES:\n" +
        "2.50%GOLDBONDS2032SR-IV,NA,IN0020230184,Government Securities,Sovereign Gold Bond,SOVEREIGN BOND\n" +
        "SBI ETF NIFTY 50,NIFTYBEES,INF200KA1FS1,ETF,Nifty 50 Index,ETF\n" +
        "INDIAN BRIGHT STEEL,AZAD,INE02PY01013,Industrials,Engineering,EQUITY\n";
    
    return '<div style="padding:8px;background:#0a0a0a;border:1px solid #111;border-radius:0;">' +
        '<div style="margin-bottom:8px;font-size:12px;color:#888;">' +
        'Total stocks: <span style="color:#00ff88;font-weight:bold;">' + importState.stocks.length + '</span>' +
        '</div>' +
        
        '<div style="margin-bottom:15px;">' +
        '<button onclick="copyPrompt()" style="padding:8px 16px;background:#00ff88;' +
        'color:#000;border:none;border-radius:6px;cursor:pointer;font-weight:bold;">📋 Copy Prompt</button>' +
        '</div>' +
        
        '<div style="padding:10px;background:#1a2a0a;border-left:3px solid #ffb347;margin:6px 0;font-size:12px;color:#ccc;border-radius:4px;">' +
        'Copy → Paste in ChatGPT/Claude → Copy response → Paste in Step 4' +
        '</div>' +
        
        '<textarea id="ai-prompt" readonly style="width:100%;height:220px;' +
        'padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;' +
        'font-size:11px;border-radius:6px;resize:none;">' + prompt + '</textarea>' +
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
    var textarea = document.getElementById("ai-response");
    var hasResponse = textarea && textarea.value.trim().length > 0;
    var stockCount = importState.stocks ? importState.stocks.length : 0;
    
    return '<div style="padding:8px;background:#0a0a0a;border:1px solid #111;border-radius:0;">' +
        '<div style="margin-bottom:8px;font-size:12px;">' +
        '<span id="step4-status">' + 
        (hasResponse ? '<span style="color:#00ff88;">✅ Data pasted. Click Next to parse & enrich.</span>' : 
                      '<span style="color:#888;">Paste data for ' + stockCount + ' stocks below</span>') +
        '</span>' +
        '</div>' +
        
        '<div style="padding:10px;background:#1a2a0a;border-left:3px solid #ffb347;margin:6px 0;font-size:12px;color:#ccc;border-radius:4px;">' +
        '<b style="color:#ffb347;">Paste:</b> Name, Ticker, ISIN, Sector (any delimiter)' +
        '</div>' +
        
        '<textarea id="ai-response" style="width:100%;height:350px;' +
        'padding:10px;background:#000;border:1px solid #222;color:#fff;font-family:monospace;' +
        'font-size:11px;border-radius:6px;resize:vertical;" ' +
        'placeholder="Paste here..."></textarea>' +
        
        '<div id="step4-result" style="margin:6px 0;font-size:12px;color:#00ff88;"></div>' +
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
    var result = document.getElementById('step4-result');
    if (status) {
        if (matched > 0) {
            status.innerHTML = '<span style="color:#00ff88;font-weight:bold;">✅ ' + matched + '/' + importState.stocks.length + '</span>';
            if (result) {
                result.innerHTML = '✅ Enriched ' + matched + ' stocks with Ticker, ISIN, Sector';
            }
        } else {
            status.innerHTML = '<span style="color:#ffb347;">⚠️ No matches</span>';
            if (result) {
                result.innerHTML = '⚠️ No stocks matched. Check names and data format.';
            }
        }
    }
    
    showImportUI();
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 5: Edit & Validate
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep5() {
    var html = '<div style="padding:8px;background:#0a0a0a;border:1px solid #111;border-radius:0;">' +
        '<h3 style="margin:0 0 10px 0;color:#00ff88;font-size:16px;font-weight:bold;">📝 Edit & Validate</h3>' +
        '<div style="margin:6px 0;overflow-x:auto;border:1px solid #111;border-radius:8px;max-height:500px;overflow-y:auto;">' +
        '<table style="width:100%;border-collapse:collapse;font-size:9px;line-height:1.3;">' +
        '<tr style="background:#222;border-bottom:1px solid #333;position:sticky;top:0;">' +
        '<th style="padding:6px;text-align:left;color:#00ff88;cursor:pointer;user-select:none;" onclick="sortStocks(\'name\')">▼ Name</th>' +
        '<th style="padding:6px;text-align:left;color:#00ff88;cursor:pointer;user-select:none;" onclick="sortStocks(\'isin\')">▼ ISIN</th>' +
        '<th style="padding:6px;text-align:left;color:#00ff88;cursor:pointer;user-select:none;" onclick="sortStocks(\'sector\')">▼ Sector</th>' +
        '<th style="padding:6px;text-align:right;color:#00ff88;cursor:pointer;user-select:none;" onclick="sortStocks(\'qty\')">▼ Qty</th>' +
        '<th style="padding:6px;text-align:right;color:#00ff88;cursor:pointer;user-select:none;" onclick="sortStocks(\'avg\')">▼ Avg</th>' +
        '<th style="padding:6px;text-align:center;color:#00ff88;">Del</th>' +
        '</tr>';
    
    importState.stocks.forEach(function(stock, idx) {
        var statusColor = stock.status === "enriched" ? "#00ff88" : "#ffb347";
        var statusIcon = stock.status === "enriched" ? "✅" : "⚠️";
        var typeLabel = stock.type === "PORTFOLIO" ? "P" : "W";
        var typeColor = stock.type === "PORTFOLIO" ? "#00ff88" : "#ffb347";
        
        html += '<tr style="border-bottom:0.5px solid #111;background:#050505;">' +
            '<td style="padding:4px 6px;cursor:pointer;" onclick="editCell(this, ' + idx + ', \'name\')">' +
            stock.name.substring(0, 20) + ' <span style="color:' + typeColor + ';">[' + typeLabel + ']</span></td>' +
            '<td style="padding:4px 6px;color:' + statusColor + ';font-weight:bold;cursor:pointer;" onclick="editCell(this, ' + idx + ', \'isin\')">' +
            statusIcon + ' ' + (stock.isin || '-') + '</td>' +
            '<td style="padding:4px 6px;cursor:pointer;" onclick="editCell(this, ' + idx + ', \'sector\')">' +
            (stock.sector || '-') + '</td>' +
            '<td style="padding:4px 6px;text-align:right;cursor:pointer;" onclick="editCell(this, ' + idx + ', \'qty\')">' +
            (stock.qty ? stock.qty : '-') + '</td>' +
            '<td style="padding:4px 6px;text-align:right;cursor:pointer;" onclick="editCell(this, ' + idx + ', \'avg\')">' +
            (stock.avg ? '₹' + stock.avg.toFixed(2) : '-') + '</td>' +
            '<td style="padding:4px 6px;text-align:center;">' +
            '<button class="step5-delete-btn" data-idx="' + idx + '" style="background:#ff6b85;color:#fff;border:none;padding:2px 4px;border-radius:2px;cursor:pointer;font-size:8px;">✕</button>' +
            '</td></tr>';
    });
    
    html += '</table></div>' +
        '<div style="margin:8px 0;font-size:12px;color:#ccc;">' +
        'Total: ' + importState.stocks.length + ' stocks (P=Portfolio, W=Watchlist)' +
        '</div>' +
        '</div>';
    
    return html;
}

function sortStocks(field) {
    if (!importState.stocks || importState.stocks.length === 0) {
        return;
    }
    
    importState.stocks.sort(function(a, b) {
        var aVal = a[field];
        var bVal = b[field];
        
        // Handle null/undefined
        if (aVal === null || aVal === undefined) aVal = "";
        if (bVal === null || bVal === undefined) bVal = "";
        
        if (typeof aVal === "string" && typeof bVal === "string") {
            return aVal.localeCompare(bVal);
        } else {
            // Convert to number for numeric fields
            var aNum = parseFloat(aVal) || 0;
            var bNum = parseFloat(bVal) || 0;
            return aNum - bNum;
        }
    });
    
    showImportUI();
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
    // Validate index
    if (typeof idx !== 'number' || idx < 0 || idx >= importState.stocks.length) {
        return;
    }
    
    var stock = importState.stocks[idx];
    if (!stock || !stock.name) {
        return;
    }
    
    var stockName = stock.name;
    
    // Use custom confirmation instead of confirm() (works better on mobile)
    showCustomConfirm('Delete: ' + stockName + '?', function(confirmed) {
        if (confirmed) {
            importState.stocks.splice(idx, 1);
            
            // Force UI refresh
            setTimeout(function() {
                showImportUI();
                attachDeleteListeners();
            }, 50);
        }
    });
}

// Custom confirmation dialog (works on mobile)
function showCustomConfirm(message, callback) {
    var dialogDiv = document.createElement('div');
    dialogDiv.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:100%;' +
        'background:rgba(0,0,0,0.8);z-index:99999;display:flex;align-items:center;justify-content:center;';
    
    var contentDiv = document.createElement('div');
    contentDiv.style.cssText = 'background:#0a0a0a;border:2px solid #00ff88;border-radius:8px;' +
        'padding:10px;max-width:300px;text-align:center;color:#fff;';
    
    contentDiv.innerHTML = '<div style="margin-bottom:15px;font-size:14px;color:#00ff88;">' + message + '</div>' +
        '<div style="display:flex;gap:6px;">' +
            '<button id="confirm-yes" style="flex:1;padding:10px;background:#00ff88;color:#000;border:none;' +
                'border-radius:6px;font-weight:bold;cursor:pointer;">Yes, Delete</button>' +
            '<button id="confirm-no" style="flex:1;padding:10px;background:#444;color:#fff;border:none;' +
                'border-radius:6px;cursor:pointer;">Cancel</button>' +
        '</div>';
    
    dialogDiv.appendChild(contentDiv);
    document.body.appendChild(dialogDiv);
    
    document.getElementById('confirm-yes').onclick = function() {
        document.body.removeChild(dialogDiv);
        callback(true);
    };
    
    document.getElementById('confirm-no').onclick = function() {
        document.body.removeChild(dialogDiv);
        callback(false);
    };
}

// Attach event listeners to delete buttons
function attachDeleteListeners() {
    setTimeout(function() {
        var deleteButtons = document.querySelectorAll('.step5-delete-btn');
        
        deleteButtons.forEach(function(btn, i) {
            // Remove old listener
            btn.removeEventListener('click', handleDeleteClick);
            
            // Add new listener
            btn.addEventListener('click', handleDeleteClick);
        });
    }, 100);
}

function handleDeleteClick(e) {
    e.preventDefault();
    e.stopPropagation();
    
    var idx = parseInt(this.getAttribute('data-idx'));
    deleteStock(idx);
}


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 6: Post to GitHub (Save + GitHub Backup)
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function saveToIndexedDB(callback) {
    // Save to IndexedDB with callback for chaining
    
    if (importState.stocks.length === 0) {
        if (callback) callback(false);
        return;
    }
    
    try {
        // Use correct database that index.html uses
        var request = indexedDB.open(CONFIG.DATABASE_NAME, CONFIG.DATABASE_VERSION);
        
        request.onerror = function() {
            if (callback) callback(false);
        };
        
        request.onsuccess = function(e) {
            var db = e.target.result;
            
            var tx = db.transaction(CONFIG.STORE_NAME, "readwrite");
            var store = tx.objectStore(CONFIG.STORE_NAME);
            
            // Append to existing data (don't clear)
            var savedCount = 0;
            var skippedCount = 0;
            var skipped = [];
            
            importState.stocks.forEach(function(stock, idx) {
                // Validate ticker
                var ticker = stock.ticker || stock.symbol;
                if (!ticker || ticker === '') {
                    ticker = stock.name ? stock.name.substring(0, 10) : null;
                }
                
                if (!ticker || ticker === '' || ticker === '?') {
                    skipped.push(stock.name || 'unnamed');
                    skippedCount++;
                    return;  // Skip invalid record
                }
                
                var record = {
                    ticker: ticker,
                    name: stock.name || '',
                    isin: stock.isin || '',
                    sector: stock.sector || '',
                    industry: stock.industry || '',
                    type: (stock.type || 'portfolio').toLowerCase(),
                    qty: parseFloat(stock.qty) || 0,
                    avg: parseFloat(stock.avg) || 0,
                    source: 'import',
                    userDataUpdatedAt: new Date().toISOString()
                };
                
                // Final validation
                if (!record.ticker) {
                    skipped.push(record.name || 'unnamed');
                    skippedCount++;
                    return;
                }
                
                store.put(record);
                savedCount++;
            });
            
            tx.oncomplete = function() {
                if (callback) callback(true);
            };
            
            tx.onerror = function() {
                if (callback) callback(false);
            };
        };
    } catch(err) {
        if (callback) callback(false);
    }
}

// Save and continue to Step 7
function saveAndContinue() {
    var btn = document.querySelector("button[onclick=\"saveAndContinue()\"]");
    if (btn) btn.disabled = true;
    
    saveToIndexedDB(function(success) {
        if (success) {
            importState.step = 7;
            showImportUI();
            attachDeleteListeners();
        } else {
            if (btn) btn.disabled = false;
        }
    });
}


// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// STEP 7: Post to GitHub - PROPER UI WITH CONFIG & CONFIRMATION
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function renderStep6() {
    // Try MULTIPLE sources to get PAT (in order of preference)
    var ghPAT = localStorage.getItem("ghPAT") || 
                localStorage.getItem("github_pat") || 
                sessionStorage.getItem("ghPAT") ||
                sessionStorage.getItem("github_pat") || "";
    
    var ghUser = localStorage.getItem("ghUser") || 
                 localStorage.getItem("github_user") || 
                 sessionStorage.getItem("ghUser") ||
                 sessionStorage.getItem("github_user") || "";
    
    var ghRepo = localStorage.getItem("ghRepo") || 
                 localStorage.getItem("github_repo") || 
                 sessionStorage.getItem("ghRepo") ||
                 sessionStorage.getItem("github_repo") || "";
    
    // Only consider it configured if ALL THREE fields have values
    var isPATConfigured = (ghPAT && ghPAT.trim() !== "") && 
                         (ghUser && ghUser.trim() !== "") && 
                         (ghRepo && ghRepo.trim() !== "");
    
    // Calculate portfolio vs watchlist based on qty/avg fields
    var portfolioCount = 0;
    var watchlistCount = 0;
    
    importState.stocks.forEach(function(s) {
        if ((s.qty && s.qty !== null && s.qty !== "") && (s.avg && s.avg !== null && s.avg !== "")) {
            portfolioCount++;
            s.type = "PORTFOLIO";
        } else {
            watchlistCount++;
            s.type = "WATCHLIST";
        }
    });
    
    var html = '<div style="padding:8px;background:#0a0a0a;border:1px solid #111;border-radius:0;">' +
        '<h3 style="margin:0 0 15px 0;color:#00ff88;font-size:16px;font-weight:bold;">💾 Save & Backup to GitHub (Step 6)</h3>';
    
    // Add counts display
    html += '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:8px 0;">' +
        '<div style="background:#001a00;padding:15px;border-radius:8px;border:1px solid #00ff88;text-align:center;">' +
            '<div style="font-size:28px;color:#00ff88;font-weight:bold;">' + portfolioCount + '</div>' +
            '<div style="font-size:12px;color:#ccc;margin-top:8px;">Portfolio</div>' +
        '</div>' +
        '<div style="background:#1a0000;padding:15px;border-radius:8px;border:1px solid #ff6b85;text-align:center;">' +
            '<div style="font-size:28px;color:#ff6b85;font-weight:bold;">' + watchlistCount + '</div>' +
            '<div style="font-size:12px;color:#ccc;margin-top:8px;">Watchlist</div>' +
        '</div>' +
    '</div>';
    
    html += '<div style="margin:8px 0;padding:12px;background:#111;border-radius:8px;border-left:3px solid #00ff88;color:#ccc;font-size:12px;">' +
        '✅ Ready to save & optionally backup to GitHub' +
    '</div>';
    
    html += '<h4 style="margin:20px 0 10px 0;color:#ffb347;font-size:14px;font-weight:bold;">📤 GitHub Backup (Optional)</h4>';
    
    // PAT Configuration Section
    html += '<div style="margin:8px 0;padding:15px;background:#111;border-radius:8px;border-left:3px solid ' + 
        (isPATConfigured ? '#00ff88' : '#ffb347') + ';">' +
        '<div style="color:' + (isPATConfigured ? '#00ff88' : '#ffb347') + ';font-weight:bold;margin-bottom:10px;">' +
        (isPATConfigured ? '✅ GitHub Configured' : '⚠️ Configure GitHub (Optional)') +
        '</div>';
    
    if (isPATConfigured) {
        var maskedPAT = ghPAT.substring(0, 4) + "..." + ghPAT.substring(ghPAT.length - 4);
        html += '<div style="font-size:11px;color:#ccc;margin-bottom:10px;">' +
            'User: <b>' + ghUser + '</b><br>' +
            'Repo: <b>' + ghRepo + '</b><br>' +
            'PAT: <b>' + maskedPAT + '</b>' +
            '</div>' +
            '<button onclick="editGitHubConfig()" style="padding:8px 16px;background:#ffb347;color:#000;' +
            'border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:11px;">✏️ Edit PAT</button>';
    }
    
    // Config form (always show if not configured OR if editing)
    html += '<div id="github-config-form" style="' + (isPATConfigured ? 'display:none;' : '') + 'margin-top:10px;">';
    html += '<div style="margin:8px 0;">' +
        '<label style="color:#ccc;font-size:11px;">GitHub PAT:</label><br>' +
        '<input type="password" id="ghPAT" value="' + ghPAT + '" placeholder="ghp_xxxxxxxxxxxxx" style="width:100%;padding:8px;' +
        'background:#000;border:1px solid #222;color:#fff;border-radius:4px;font-family:monospace;font-size:11px;margin-top:4px;' +
        'box-sizing:border-box;">' +
        '</div>';
    html += '<div style="margin:8px 0;">' +
        '<label style="color:#ccc;font-size:11px;">GitHub User:</label><br>' +
        '<input type="text" id="ghUser" value="' + ghUser + '" placeholder="username" style="width:100%;padding:8px;' +
        'background:#000;border:1px solid #222;color:#fff;border-radius:4px;font-size:11px;margin-top:4px;' +
        'box-sizing:border-box;">' +
        '</div>';
    html += '<div style="margin:8px 0;">' +
        '<label style="color:#ccc;font-size:11px;">GitHub Repo:</label><br>' +
        '<input type="text" id="ghRepo" value="' + ghRepo + '" placeholder="repo-name" style="width:100%;padding:8px;' +
        'background:#000;border:1px solid #222;color:#fff;border-radius:4px;font-size:11px;margin-top:4px;' +
        'box-sizing:border-box;">' +
        '</div>';
    html += '<div style="display:flex;gap:4px;margin-top:10px;">' +
        '<button onclick="saveGitHubConfig()" style="flex:1;padding:8px 16px;background:#00ff88;color:#000;' +
        'border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:11px;">✅ Save</button>' +
        '<button onclick="cancelGitHubEdit()" style="flex:1;padding:8px 16px;background:#444;color:#fff;' +
        'border:none;border-radius:6px;cursor:pointer;font-size:11px;">Cancel</button>' +
        '</div>' +
        '</div>';
    
    html += '</div>';
    
    // Append vs Replace Option
    html += '<div style="margin:8px 0;padding:15px;background:#050505;border:1px solid #222;border-radius:8px;">' +
        '<div style="color:#00ff88;font-weight:bold;margin-bottom:10px;">📥 Import Mode</div>' +
        '<div style="display:flex;gap:6px;">' +
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
        html += '<div style="margin:8px 0;padding:15px;background:#050505;border:1px solid #222;border-radius:8px;' +
            'font-size:12px;color:#888;">' +
            '<b style="color:#00ff88;">📊 Data to Post:</b><br><br>' +
            '<div style="display:flex;justify-content:space-around;margin:6px 0;">' +
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
        
        html += '<div id="json-preview" style="display:none;margin:6px 0;padding:10px;background:#000;' +
            'border:1px solid #222;border-radius:6px;max-height:300px;overflow-y:auto;font-size:9px;' +
            'font-family:monospace;color:#0f0;"></div>';
        
        // Post Button
        html += '<button onclick="postToGitHub()" style="padding:12px 24px;background:#00ff88;color:#000;' +
            'border:none;border-radius:6px;cursor:pointer;font-weight:bold;font-size:14px;width:100%;' +
            'margin-top:15px;">📤 Post to GitHub</button>';
    }
    
    html += '<div id="step7-status" style="margin:8px 0;font-size:12px;"></div>';
    html += '</div>';
    
    return html;
}

function toggleGitHubConfig() {
    var configDiv = document.getElementById('github-config');
    if (configDiv) {
        configDiv.style.display = configDiv.style.display === 'none' ? 'block' : 'none';
    }
}

function editGitHubConfig() {
    var form = document.getElementById('github-config-form');
    if (form) {
        form.style.display = 'block';
    }
}

function cancelGitHubEdit() {
    var form = document.getElementById('github-config-form');
    var ghPAT = localStorage.getItem('ghPAT') || '';
    if (form && ghPAT) {
        form.style.display = 'none';
    }
}

function saveGitHubConfig() {
    var pat = document.getElementById("ghPAT").value;
    var user = document.getElementById("ghUser").value;
    var repo = document.getElementById("ghRepo").value;
    
    if (!pat || !user || !repo) {
        alert("⚠️ Please fill all fields");
        return;
    }
    
    // Save to both localStorage AND sessionStorage for persistence
    localStorage.setItem("ghPAT", pat);
    localStorage.setItem("ghUser", user);
    localStorage.setItem("ghRepo", repo);
    
    // Also save with alternate keys for compatibility
    localStorage.setItem("github_pat", pat);
    localStorage.setItem("github_user", user);
    localStorage.setItem("github_repo", repo);
    
    // Also save to sessionStorage as fallback
    sessionStorage.setItem("ghPAT", pat);
    sessionStorage.setItem("ghUser", user);
    sessionStorage.setItem("ghRepo", repo);
    
    alert("✅ GitHub configuration saved!");
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
                // Continue with append mode if parse fails
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
                '<div style="margin:6px 0;font-size:11px;color:#888;">' +
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
    if (importState.step < CONFIG.TOTAL_STEPS) {
        // Auto-parse when going from step 4 to step 5
        if (importState.step === 4) {
            var response = document.getElementById('ai-response').value;
            if (!response.trim()) {
                alert('❌ Please paste data first');
                return;
            }
            manuallyParseStep4();
            importState.step++;
            showImportUI();
        }
        // Auto-save to DB when going from step 5 to step 6
        else if (importState.step === 5) {
            saveToIndexedDB(function(success) {
                if (success) {
                    importState.step++;
                    showImportUI();
                } else {
                    alert("❌ Failed to save to database. Please try again.");
                }
            });
        } else {
            importState.step++;
            showImportUI();
        }
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
