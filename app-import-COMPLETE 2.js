/**
 * app-import.js - Complete Import Module
 * Full wizard + refactored parsing (no redundancy, clean code)
 * Supports: CDSL XLS/CSV, Tab-separated, Manual entry
 * Lines: ~500 (vs original 701)
 */

let parsedHoldings = [];

// ────────────── PANEL CONTROL ──────────────

function openPanel() {
  document.getElementById('ov').classList.add('on');
  document.getElementById('import-panel').classList.add('on');
}

function closePanel() {
  document.getElementById('ov').classList.remove('on');
  document.getElementById('import-panel').classList.remove('on');
}

function openImport() {
  parsedHoldings = [];
  document.getElementById('import-panel-body').innerHTML = renderImportPanel();
  openPanel();
}

// ────────────── UI RENDERING ──────────────

function renderImportPanel() {
  return `
  <style>
  .imp-tabs{display:flex;gap:0;border-bottom:2px solid var(--b2);margin-bottom:14px;}
  .imp-tab{flex:1;padding:9px 6px;text-align:center;font-size:11px;font-weight:700;
    font-family:'Syne',sans-serif;cursor:pointer;color:var(--tx3);
    border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .15s;}
  .imp-tab.on{color:var(--ac);border-bottom-color:var(--ac);}
  .imp-pane{display:none;} .imp-pane.on{display:block;}
  .file-drop{border:2px dashed var(--b2);border-radius:12px;padding:28px 16px;
    text-align:center;cursor:pointer;transition:all .2s;background:var(--s1);}
  .file-drop:hover,.file-drop.drag{border-color:var(--ac);background:rgba(249,115,22,.06);}
  .file-drop input[type=file]{display:none;}
  .file-drop-icon{font-size:32px;margin-bottom:8px;}
  .file-drop-title{font-size:13px;font-weight:700;color:var(--tx);font-family:'Syne',sans-serif;margin-bottom:4px;}
  .file-drop-sub{font-size:10px;color:var(--tx3);line-height:1.6;}
  .file-drop-sub b{color:var(--gr2);}
  .imp-fmt{background:var(--bg);border:1px solid var(--b1);border-radius:8px;
    padding:10px 12px;font-size:9px;color:var(--tx3);line-height:1.9;
    font-family:var(--mono);margin-bottom:12px;}
  .imp-report{margin-top:10px;border-radius:8px;overflow:hidden;font-size:10px;}
  .imp-report-row{padding:6px 10px;border-bottom:1px solid var(--b1);display:flex;gap:8px;align-items:flex-start;}
  .imp-report-sym{font-family:var(--mono);font-weight:700;min-width:90px;color:var(--tx1);}
  .imp-report-reason{color:var(--tx3);}
  </style>

  <div class="imp-tabs">
    <div class="imp-tab on" id="itab-file" onclick="switchImpTab('file')">📁 CDSL XLS</div>
    <div class="imp-tab" id="itab-paste" onclick="switchImpTab('paste')">📋 CDSL Text</div>
    <div class="imp-tab" id="itab-manual" onclick="switchImpTab('manual')">✏ Manual</div>
  </div>

  <div class="imp-pane on" id="ipane-file">
    <div class="file-drop" id="file-drop-zone"
      onclick="document.getElementById('file-input').click()"
      ondragover="event.preventDefault();this.classList.add('drag')"
      ondragleave="this.classList.remove('drag')"
      ondrop="handleFileDrop(event)"
      style="cursor:pointer">
      <input type="file" id="file-input" accept=".xls,.xlsx,.csv,.txt,.tsv" style="display:none"
        onchange="handleFileSelect(this.files[0])">
      <div class="file-drop-icon">📂</div>
      <div class="file-drop-title">Tap to select CDSL XLS file</div>
      <div class="file-drop-sub">
        <b>CDSL Easiest → Portfolio → Equity Summary Details → Download XLS</b><br>
        Supports: XLS, XLSX, CSV, TSV (tab-separated)
      </div>
    </div>
    <div id="file-status" style="margin-top:10px;font-size:10px;color:var(--tx3);font-family:var(--mono);min-height:20px;word-wrap:break-word;overflow-wrap:break-word"></div>
    <div id="imp-report" style="display:none;margin-top:8px"></div>
  </div>

  <div class="imp-pane" id="ipane-paste">
    <div class="imp-fmt">
      <b class="u-gr2">How to get this:</b><br>
      CDSL Easiest → Statement → Holdings → Select All → Copy → Paste below<br><br>
      <b class="u-yw2">Format:</b><br>
      INE040A01034 HDFC BANK LIMITED - EQ Beneficiary 84 68628.00<br><br>
      <b class="u-rd2">⚠ No avg buy price in this format</b> — use XLS tab for full data
    </div>
    <textarea class="import-textarea" id="import-ta"
      placeholder="Paste CDSL statement text here…&#10;&#10;INE040A01034 HDFC BANK LIMITED - EQ Beneficiary 84 68628"
      oninput="liveParseImport(this.value)" rows="9"></textarea>
  </div>

  <div class="imp-pane" id="ipane-manual">
    <div class="imp-fmt">
      <b class="u-gr2">Format:</b>  SYMBOL, QTY, AVG_BUY<br>
      One stock per line. AVG_BUY is optional.<br><br>
      <b class="u-bl2">Examples:</b><br>
      RELIANCE, 10, 2450<br>
      HDFCBANK, 84, 817.50<br>
      TATAPOWER, 100<br><br>
      <b class="u-tx3">Find your symbol:</b> use NSE website or Screener.in
    </div>
    <textarea class="import-textarea" id="import-ta-manual"
      placeholder="RELIANCE, 10, 2450&#10;HDFCBANK, 84, 817&#10;TATAPOWER, 100, 385"
      oninput="liveParseImport(this.value,'manual')" rows="9"></textarea>
  </div>

  <div class="import-err" id="import-err"></div>
  <div class="import-preview" id="import-preview">
    <div class="import-preview-title" id="import-preview-title">Preview</div>
    <div id="import-preview-rows"></div>
  </div>
  `;
}

function switchImpTab(tab) {
  ['file', 'paste', 'manual'].forEach(t => {
    const tab_el = document.getElementById('itab-' + t);
    const pane_el = document.getElementById('ipane-' + t);
    if (tab_el) tab_el.classList.toggle('on', t === tab);
    if (pane_el) pane_el.classList.toggle('on', t === tab);
  });
}

// ────────────── FILE UPLOAD ──────────────

function handleFileDrop(e) {
  e.preventDefault();
  const zone = document.getElementById('file-drop-zone');
  if (zone) zone.classList.remove('drag');
  if (e.dataTransfer.files.length > 0) {
    handleFileSelect(e.dataTransfer.files[0]);
  }
}

function handleFileSelect(file) {
  if (!file) return;
  const status = document.getElementById('file-status');
  if (!status) return;

  status.innerHTML = `<span class="u-yw2">⏳ Reading ${file.name}…</span>`;
  const ext = file.name.split('.').pop().toLowerCase();

  // XLS/XLSX - use SheetJS library
  if (ext === 'xls' || ext === 'xlsx') {
    loadSheetJS(() => {
      const reader = new FileReader();
      reader.onload = (e) => {
        try {
          const wb = XLSX.read(e.target.result, { type: 'binary' });
          const ws = wb.Sheets[wb.SheetNames[0]];
          const csv = XLSX.utils.sheet_to_csv(ws);
          processImportText(csv, file.name, status);
        } catch (err) {
          status.innerHTML = `<span class="u-rd2">✗ Could not read XLS: ${err.message}</span>`;
        }
      };
      reader.onerror = () => {
        status.innerHTML = `<span class="u-rd2">✗ Error reading file</span>`;
      };
      reader.readAsBinaryString(file);
    });
    return;
  }

  // CSV / TXT / TSV
  const reader = new FileReader();
  reader.onload = (e) => processImportText(e.target.result, file.name, status);
  reader.onerror = () => {
    status.innerHTML = `<span class="u-rd2">✗ Could not read file</span>`;
  };
  reader.readAsText(file);
}

let _sheetJSLoaded = false;
function loadSheetJS(cb) {
  if (_sheetJSLoaded) { cb(); return; }
  if (window.XLSX) { _sheetJSLoaded = true; cb(); return; }

  const s = document.createElement('script');
  s.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js';
  s.onload = () => { _sheetJSLoaded = true; cb(); };
  s.onerror = () => {
    const status = document.getElementById('file-status');
    if (status) {
      status.innerHTML = '<span class="u-rd2">✗ Could not load XLS reader — try saving as CSV first</span>';
    }
  };
  document.head.appendChild(s);
}

// ────────────── PARSE HELPERS ──────────────

function detectDelimiter(line) {
  const tabs = (line.match(/\t/g) || []).length;
  const semis = (line.match(/;/g) || []).length;
  const commas = (line.match(/,/g) || []).length;
  if (tabs >= commas && tabs >= semis && tabs > 0) return '\t';
  if (semis > commas && semis > 0) return ';';
  return ',';
}

function parseNum(str) {
  if (!str) return 0;
  const num = parseFloat(String(str).replace(/,/g, ''));
  return isNaN(num) ? 0 : num;
}

function cleanStr(str) {
  if (!str) return '';
  return String(str).replace(/^"|"$/g, '').trim();
}

function cleanSymbol(name, isin) {
  if (typeof ISIN_MAP !== 'undefined' && ISIN_MAP[isin]) {
    return ISIN_MAP[isin];
  }
  return name.replace(/[^A-Z0-9&\-]/g, '').slice(0, 12).toUpperCase();
}

function isValidISIN(isin) {
  return /^IN[A-Z0-9]{10,12}$/.test(isin);
}

function shouldSkipStock(name, isin) {
  const skipPatterns = /ETF|BOND|GOLDBOND|SGB|SBI ETF|MIRAEAMC|FUND|GOVERNMENT/i;
  return skipPatterns.test(name) || (isin && /^INF/.test(isin));
}

// ────────────── PARSING LOGIC ──────────────

function parsePortfolioText(text) {
  const results = [];
  const seen = new Set();

  // Detect if CDSL export format
  const isCDSL = /Stock Name.*ISIN.*Sector.*Quantity.*Average Cost/i.test(text.slice(0, 500)) ||
                 /ISIN.*Sector.*Quantity.*Average Cost/i.test(text.slice(0, 500));

  if (isCDSL) {
    // ────── CDSL PARSER ──────
    const lines = text.replace(/\r/g, '').split('\n');
    const delimiter = detectDelimiter(lines[0] || '');

    // Find header row
    let headerIdx = -1, headers = [];
    for (let i = 0; i < Math.min(10, lines.length); i++) {
      const lower = lines[i].toLowerCase();
      if (lower.includes('stock name') && lower.includes('isin') && lower.includes('quantity')) {
        headerIdx = i;
        headers = lines[i].split(delimiter).map(h => cleanStr(h).toLowerCase());
        break;
      }
    }

    if (headerIdx < 0) return results;

    // Find columns
    let nameIdx = -1, isinIdx = -1, sectorIdx = -1, qtyIdx = -1, avgIdx = -1, ltpIdx = -1;
    for (let i = 0; i < headers.length; i++) {
      const h = headers[i];
      if (nameIdx === -1 && (h.includes('stock name') || h.includes('name'))) nameIdx = i;
      if (isinIdx === -1 && h.includes('isin')) isinIdx = i;
      if (sectorIdx === -1 && h.includes('sector')) sectorIdx = i;
      if (qtyIdx === -1 && h.includes('quantity')) qtyIdx = i;
      if (avgIdx === -1 && (h.includes('average cost') || h.includes('avg'))) avgIdx = i;
      if (ltpIdx === -1 && (h.includes('current market price') || h.includes('ltp'))) ltpIdx = i;
    }

    // Fallback to standard positions
    if (nameIdx < 0) nameIdx = 0;
    if (isinIdx < 0) isinIdx = 1;
    if (sectorIdx < 0) sectorIdx = 2;
    if (qtyIdx < 0) qtyIdx = 3;
    if (avgIdx < 0) avgIdx = 4;
    if (ltpIdx < 0) ltpIdx = 6;

    // Parse data rows
    for (let i = headerIdx + 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line || line.length < 2) continue;

      const cols = line.split(delimiter).map(c => cleanStr(c));
      if (cols.length < 2) continue;

      const name = cols[nameIdx] || '';
      const isin = cols[isinIdx] || '';
      const sector = cols[sectorIdx] || '';
      const qtyRaw = cols[qtyIdx] || '';
      const avgRaw = cols[avgIdx] || '';
      const ltpRaw = cols[ltpIdx] || '';

      if (!name || !isin) continue;
      if (name.toLowerCase().includes('stock name')) continue;
      if (seen.has(isin)) continue;
      if (shouldSkipStock(name, isin)) continue;
      if (!isValidISIN(isin)) continue;

      const qty = Math.round(parseNum(qtyRaw));
      const avgBuy = Math.round(parseNum(avgRaw) * 100) / 100;
      const ltp = Math.round(parseNum(ltpRaw) * 100) / 100;

      if (qty <= 0) continue;

      seen.add(isin);
      results.push({
        sym: cleanSymbol(name, isin),
        isin,
        name,
        sector: sector || 'Diversified',
        qty,
        avgBuy,
        ltp,
        change: 0
      });
    }
    return results;
  }

  // ────── GENERIC/MANUAL PARSER ──────
  const lines = text.replace(/\r/g, '').split('\n').map(l => l.trim()).filter(l => l.length > 2);

  for (const line of lines) {
    if (/^(symbol|name|isin|qty|quantity|avg|average|price|stock)/i.test(line)) continue;

    const delim = line.includes('\t') ? '\t' : line.includes(';') ? ';' : line.includes('|') ? '|' : ',';
    const parts = line.split(delim).map(p => cleanStr(p)).filter(Boolean);

    if (parts.length < 2) continue;

    let sym = parts[0].toUpperCase().replace(/[^A-Z0-9&\-]/g, '').replace(/\.NS$/, '');
    const numbers = parts.map(p => parseNum(p)).filter(n => n > 0 && n < 1e10);
    const qty = numbers.length > 0 ? Math.round(numbers[0]) : 0;
    const avgBuy = numbers.length > 1 ? Math.round(numbers[1] * 100) / 100 : 0;

    if (!sym || qty <= 0) continue;
    if (seen.has(sym)) continue;

    seen.add(sym);
    results.push({
      sym,
      isin: '',
      name: sym,
      sector: 'Diversified',
      qty,
      avgBuy,
      ltp: 0,
      change: 0
    });
  }

  return results;
}

// ────────────── TEXT PROCESSING ──────────────

function processImportText(text, filename, statusEl) {
  parsedHoldings = parsePortfolioText(text);

  if (parsedHoldings.length) {
    if (statusEl) {
      statusEl.innerHTML = `<span class="u-gr2">✓ ${filename} — ${parsedHoldings.length} holdings detected</span>`;
    }
    showImportPreview();
  } else {
    if (statusEl) {
      statusEl.innerHTML = `<span class="u-rd2">✗ No holdings found in ${filename} — check format</span>`;
    }
  }
}

function liveParseImport(text, mode) {
  parsedHoldings = parsePortfolioText(text);
  const preEl = document.getElementById('import-preview');
  const errEl = document.getElementById('import-err');

  if (!text.trim()) {
    if (preEl) preEl.style.display = 'none';
    if (errEl) errEl.style.display = 'none';
    return;
  }

  if (!parsedHoldings.length) {
    if (errEl) {
      errEl.textContent = 'No valid holdings detected. Check format.';
      errEl.style.display = 'block';
    }
    if (preEl) preEl.style.display = 'none';
    return;
  }

  if (errEl) errEl.style.display = 'none';
  showImportPreview();
}

function showImportPreview() {
  const preEl = document.getElementById('import-preview');
  const preRows = document.getElementById('import-preview-rows');
  const preTitle = document.getElementById('import-preview-title');

  if (!preEl || !preRows) return;

  preTitle.textContent = `✓ ${parsedHoldings.length} holdings detected`;
  preRows.innerHTML = parsedHoldings.slice(0, 10).map(h => `
    <div style="display:flex;justify-content:space-between;align-items:center;
      padding:5px 0;border-bottom:1px solid var(--b1);font-size:10px">
      <div>
        <span style="font-family:var(--mono);font-weight:700;color:var(--tx)">${h.sym}</span>
        <span style="color:var(--tx3);margin-left:6px;font-size:8px">${h.isin || ''}</span>
      </div>
      <div style="display:flex;gap:10px;font-family:var(--mono)">
        <span>×${h.qty}</span>
        <span style="color:${h.avgBuy > 0 ? 'var(--gr2)' : 'var(--mu)'}">
          ${h.avgBuy > 0 ? '₹' + h.avgBuy.toFixed(2) : 'avg?'}
        </span>
        ${h.ltp > 0 ? `<span class="u-tx3">@₹${h.ltp.toFixed(1)}</span>` : ''}
      </div>
    </div>`).join('') +
    (parsedHoldings.length > 10
      ? `<div style="font-size:9px;color:var(--mu);padding:5px 0">+${parsedHoldings.length - 10} more…</div>`
      : '');

  preEl.style.display = 'block';
}

// ────────────── SAVE/IMPORT ──────────────

function applyImport(mode) {
  if (!parsedHoldings || !parsedHoldings.length) {
    alert('No holdings to import');
    return;
  }

  // Save to IndexedDB
  openDB('BharatEngineDB', 1, (db) => {
    const tx = db.transaction('UnifiedStocks', 'readwrite');
    const store = tx.objectStore('UnifiedStocks');

    if (mode === 'replace') {
      store.clear();
    }

    parsedHoldings.forEach(h => {
      store.put({
        sym: h.sym,
        name: h.name,
        isin: h.isin,
        sector: h.sector,
        qty: h.qty,
        avgBuy: h.avgBuy,
        ltp: h.ltp,
        source: 'import'
      });
    });

    tx.oncomplete = () => {
      alert(`✓ Imported ${parsedHoldings.length} holdings!`);
      closePanel();
      // Trigger data refresh
      if (typeof runEngineSync === 'function') {
        runEngineSync();
      }
    };

    tx.onerror = () => {
      alert('Error saving to database');
    };
  });
}

function openDB(dbName, version, cb) {
  const req = indexedDB.open(dbName, version);
  req.onupgradeneeded = (e) => {
    const db = e.target.result;
    if (!db.objectStoreNames.contains('UnifiedStocks')) {
      db.createObjectStore('UnifiedStocks', { keyPath: 'sym' });
    }
  };
  req.onsuccess = () => cb(req.result);
  req.onerror = () => alert('Database error');
}
