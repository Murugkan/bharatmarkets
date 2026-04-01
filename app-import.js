function openPanel(){document.getElementById('ov').classList.add('on');document.getElementById('import-panel').classList.add('on');}
function closePanel(){document.getElementById('ov').classList.remove('on');document.getElementById('import-panel').classList.remove('on');}
// PORTFOLIO IMPORT — CDSL XLS, CSV, or manual entry
// Parses holdings, saves, then triggers full data refresh
function openImport(){
  parsedHoldings = [];   // always start fresh
  document.getElementById('import-panel-body').innerHTML=renderImportPanel();
  openPanel();
}

function renderImportPanel(){
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

  <!-- Tabs -->
  <div class="imp-tabs">
    <div class="imp-tab on" id="itab-file" onclick="switchImpTab('file')">📁 CDSL XLS</div>
    <div class="imp-tab" id="itab-paste" onclick="switchImpTab('paste')">📋 CDSL Text</div>
    <div class="imp-tab" id="itab-manual" onclick="switchImpTab('manual')">✏ Manual</div>
  </div>

  <!-- Tab: XLS File Upload -->
  <div class="imp-pane on" id="ipane-file">
    <div class="file-drop" id="file-drop-zone"
      onclick="document.getElementById('file-input').click()"
      ondragover="event.preventDefault();this.classList.add('drag')"
      ondragleave="this.classList.remove('drag')"
      ondrop="handleFileDrop(event)">
      <input type="file" id="file-input" accept=".xls,.xlsx,.csv"
        onchange="handleFileSelect(this.files[0])">
      <div class="file-drop-icon">📂</div>
      <div class="file-drop-title">Tap to select CDSL XLS file</div>
      <div class="file-drop-sub">
        <b>CDSL Easiest → Portfolio → Equity Summary Details → Download XLS</b><br>
        Has: symbol, sector, qty, avg buy price — single file, full import
      </div>
    </div>
    <div id="file-status" style="margin-top:10px;font-size:10px;color:var(--tx3);font-family:var(--mono);min-height:20px"></div>
    <!-- Error/warning report -->
    <div id="imp-report" style="display:none;margin-top:8px"></div>
  </div>

  <!-- Tab: CDSL Text Paste -->
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

  <!-- Tab: Manual Entry -->
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

  <!-- Preview -->
  <div class="import-err" id="import-err"></div>
  <div class="import-preview" id="import-preview">
    <div class="import-preview-title" id="import-preview-title">Preview</div>
    <div id="import-preview-rows"></div>
  </div>

  <button class="import-btn" onclick="applyImport('replace')">✓ Import (Replace All)</button>
  <button class="import-btn" style="background:var(--s2);border:1px solid var(--b2);color:var(--tx2);margin-top:6px"
    onclick="applyImport('append')">+ Append to Existing</button>
  `;
}

function switchImpTab(tab){
  ['file','paste','manual'].forEach(t=>{
    document.getElementById('itab-'+t).classList.toggle('on', t===tab);
    document.getElementById('ipane-'+t).classList.toggle('on', t===tab);
  });
}

// ── File Upload Handler ─────────────────────────────
function handleFileDrop(e){
  e.preventDefault();
  document.getElementById('file-drop-zone').classList.remove('drag');
  const file = e.dataTransfer.files[0];
  if(file) handleFileSelect(file);
}

function handleFileSelect(file){
  if(!file) return;
  const status = document.getElementById('file-status');
  status.innerHTML = `<span class="u-yw2">⏳ Reading ${file.name}…</span>`;

  const ext = file.name.split('.').pop().toLowerCase();

  // XLS/XLSX — use SheetJS (CDN)
  if(ext==='xls'||ext==='xlsx'){
    loadSheetJS(()=>{
      const reader = new FileReader();
      reader.onload = e=>{
        try{
          const wb  = XLSX.read(e.target.result, {type:'binary'});
          const ws  = wb.Sheets[wb.SheetNames[0]];
          const csv = XLSX.utils.sheet_to_csv(ws);
          processImportText(csv, file.name, status);
        } catch(err){
          status.innerHTML = `<span class="u-rd2">✗ Could not read XLS: ${err.message}</span>`;
        }
      };
      reader.readAsBinaryString(file);
    });
    return;
  }

  // CSV / TXT — read as text
  const reader = new FileReader();
  reader.onload = e => processImportText(e.target.result, file.name, status);
  reader.onerror = ()=>{ status.innerHTML='<span class="u-rd2">✗ Could not read file</span>'; };
  reader.readAsText(file);
}

let _sheetJSLoaded = false;
function loadSheetJS(cb){
  if(_sheetJSLoaded){ cb(); return; }
  if(window.XLSX){ _sheetJSLoaded=true; cb(); return; }
  const s = document.createElement('script');
  s.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js';
  s.onload = ()=>{ _sheetJSLoaded=true; cb(); };
  s.onerror = ()=>{
    document.getElementById('file-status').innerHTML=
      '<span class="u-rd2">✗ Could not load XLS reader — try saving as CSV first</span>';
  };
  document.head.appendChild(s);
}

// ── CDSL XLS parser — full import with error/warning report ─────
function parseCDSLXls(csv){
  const imported = [], warnings = [], rejected = [];
  const lines = csv.split(/\r?\n/).map(l=>l.trim()).filter(l=>l.length>0);

  // Find header row
  let headerIdx = -1;
  for(let i=0;i<Math.min(10,lines.length);i++){
    if(/stock name/i.test(lines[i]) && /isin/i.test(lines[i]) && /quantity/i.test(lines[i])){
      headerIdx = i; break;
    }
  }
  if(headerIdx<0){ return {imported,warnings,rejected,error:'Header row not found — check file format'}; }

  const hdrs = lines[headerIdx].split(',').map(h=>h.replace(/"/g,'').trim().toLowerCase());
  const col = k => hdrs.findIndex(h=>h.includes(k));
  const iC  = col('isin'),  nC  = col('stock name'), secC = col('sector');
  const qC  = col('quantity'), avgC = col('average cost'), ltpC = col('current market price');

  for(let i=headerIdx+1; i<lines.length; i++){
    const cols = lines[i].split(',').map(c=>c.replace(/"/g,'').trim());
    if(cols.length < 4) continue;

    const name   = nC>=0   ? cols[nC]   : '';
    const isin   = iC>=0   ? cols[iC]   : '';
    const sector = secC>=0 ? cols[secC] : '';
    const qtyRaw = qC>=0   ? cols[qC]   : '';
    const avgRaw = avgC>=0 ? cols[avgC] : '';
    const ltpRaw = ltpC>=0 ? cols[ltpC] : '';

    if(!name && !isin) continue; // blank row

    // Reject bonds/ETFs/SGBs
    if(/goldbond|sgb|ETF/i.test(isin) || /^INF/.test(isin) || /ETF|Bond|SGB/i.test(name)){
      rejected.push({name:name||isin, reason:'Bond/ETF/SGB — equity only'});
      continue;
    }

    // Reject missing ISIN
    if(!isin || !/^IN[A-Z0-9]{10,12}$/.test(isin)){
      rejected.push({name:name||'(unknown)', reason:'Invalid or missing ISIN'});
      continue;
    }

    const qty    = Math.round(parseFloat(qtyRaw.replace(/,/g,''))||0);
    const avgBuy = Math.round(parseFloat(avgRaw.replace(/,/g,''))*100)/100 || 0;
    const snapLtp= Math.round(parseFloat(ltpRaw.replace(/,/g,''))*100)/100 || 0;

    // Reject zero qty
    if(qty<=0){
      rejected.push({name, reason:'Quantity is 0 or missing'});
      continue;
    }

    // Resolve symbol from ISIN
    let sym = ISIN_MAP[isin] || '';
    if(!sym){
      // Try name match in NSE_DB
      const nameParts = name.toUpperCase().replace(/\s+/g,' ').split(' ').slice(0,2).join(' ');
      const found = NSE_DB.find(s=>s.name.toUpperCase().startsWith(nameParts));
      sym = found ? found.sym : name.replace(/[^A-Z0-9]/g,'').slice(0,12).toUpperCase();
      warnings.push({name, sym, reason:'ISIN not in map — symbol derived from name, may not have live prices'});
    }

    const info = NSE_DB.find(s=>s.sym===sym)||{};
    imported.push({
      sym, isin,
      name:   info.name || name,
      sector: info.sector || sector || 'Diversified',
      qty,
      avgBuy,
      ltp:    snapLtp,   // CDSL snapshot — will be replaced by live fetch
      liveLtp: 0,
      change: 0,
    });
  }
  return {imported, warnings, rejected};
}

function renderImportReport(result, filename){
  const {imported, warnings, rejected, error} = result;
  if(error) return '<div style="color:var(--rd2);padding:8px">❌ '+error+'</div>';

  let html = '<div style="padding:8px 0">';

  // Summary line
  html += '<div style="display:flex;gap:10px;margin-bottom:8px;font-weight:700;font-size:11px">';
  html += '<span class="u-grn">✅ '+imported.length+' imported</span>';
  if(warnings.length) html += '<span class="u-yel">⚠ '+warnings.length+' warnings</span>';
  if(rejected.length) html += '<span class="u-red">❌ '+rejected.length+' rejected</span>';
  html += '</div>';

  // Warnings
  if(warnings.length){
    html += '<div style="background:rgba(245,166,35,.06);border:1px solid rgba(245,166,35,.2);border-radius:6px;margin-bottom:6px">';
    html += '<div style="padding:5px 10px;font-size:9px;font-weight:700;color:#ffbf47;border-bottom:1px solid rgba(245,166,35,.15)">⚠ WARNINGS</div>';
    warnings.forEach(w=>{
      html += '<div class="imp-report-row"><span class="imp-report-sym">'+(w.sym||w.name).slice(0,14)+'</span><span class="imp-report-reason">'+w.reason+'</span></div>';
    });
    html += '</div>';
  }

  // Rejected
  if(rejected.length){
    html += '<div style="background:rgba(255,59,92,.06);border:1px solid rgba(255,59,92,.2);border-radius:6px">';
    html += '<div style="padding:5px 10px;font-size:9px;font-weight:700;color:#ff6b85;border-bottom:1px solid rgba(255,59,92,.15)">❌ REJECTED</div>';
    rejected.forEach(r=>{
      html += '<div class="imp-report-row"><span class="imp-report-sym">'+r.name.slice(0,14)+'</span><span class="imp-report-reason">'+r.reason+'</span></div>';
    });
    html += '</div>';
  }

  html += '</div>';
  return html;
}

function processImportText(text, filename, statusEl){
  // Check if this looks like CDSL XLS (has the known header)
  const isCDSLXls = /stock name.*isin.*sector.*quantity.*average cost/i.test(text.slice(0,500));

  if(isCDSLXls){
    const result = parseCDSLXls(text);
    if(result.error){
      statusEl.innerHTML = '<span class="u-rd2">✗ '+result.error+'</span>';
      return;
    }
    parsedHoldings = result.imported;
    statusEl.innerHTML = '<span class="u-gr2">✓ '+filename+' parsed</span>';
    // Show report
    const rpt = document.getElementById('imp-report');
    if(rpt){ rpt.style.display='block'; rpt.innerHTML=renderImportReport(result, filename); }
    showImportPreview();
  } else {
    // Generic parser (CDSL text or manual CSV)
    parsedHoldings = parsePortfolioText(text);
    const rpt = document.getElementById('imp-report');
    if(rpt) rpt.style.display='none';
    if(parsedHoldings.length){
      statusEl.innerHTML = '<span class="u-gr2">✓ '+filename+' — '+parsedHoldings.length+' holdings detected</span>';
      showImportPreview();
    } else {
      statusEl.innerHTML = '<span class="u-rd2">✗ No holdings found in '+filename+' — check format</span>';
    }
  }
}

let parsedHoldings = [];

function liveParseImport(text, mode){
  parsedHoldings = parsePortfolioText(text);
  const errEl = document.getElementById('import-err');
  const preEl = document.getElementById('import-preview');
  if(!errEl||!preEl) return;

  if(!text.trim()){
    errEl.classList.remove('show');
    preEl.classList.remove('show');
    return;
  }
  if(!parsedHoldings.length){
    errEl.textContent = 'No valid holdings detected. Check format.';
    errEl.classList.add('show');
    preEl.classList.remove('show');
    return;
  }
  errEl.classList.remove('show');
  showImportPreview();
}

function showImportPreview(){
  const preEl    = document.getElementById('import-preview');
  const preRows  = document.getElementById('import-preview-rows');
  const preTitle = document.getElementById('import-preview-title');
  if(!preEl) return;
  preTitle.textContent = `✓ ${parsedHoldings.length} holdings detected`;
  preRows.innerHTML = parsedHoldings.slice(0,10).map(h=>`
    <div style="display:flex;justify-content:space-between;align-items:center;
      padding:5px 0;border-bottom:1px solid var(--b1);font-size:10px">
      <div>
        <span style="font-family:var(--mono);font-weight:700;color:var(--tx)">${h.sym}</span>
        <span style="color:var(--tx3);margin-left:6px;font-size:8px">${h.isin||''}</span>
      </div>
      <div style="display:flex;gap:10px;font-family:var(--mono)">
        <span class="u-bl2">×${h.qty}</span>
        <span style="color:${h.avgBuy>0?'var(--gr2)':'var(--mu)'}">
          ${h.avgBuy>0?'₹'+fmt(h.avgBuy):'avg?'}
        </span>
        ${h.ltp>0?`<span class="u-tx3">@₹${h.ltp.toFixed(1)}</span>`:''}
      </div>
    </div>`).join('') +
    (parsedHoldings.length>10
      ? `<div style="font-size:9px;color:var(--mu);padding:5px 0">+${parsedHoldings.length-10} more…</div>`
      : '');
  preEl.classList.add('show');
}

// Robust multi-format parser
// Multi-format parser: CDSL XLS export, plain CSV, CDSL PDF text
// Priority: CDSL export format → Key:Value → numbered list
function parsePortfolioText(text){
  const results = [];
  const seen    = new Set();

  // ── Detect CDSL XLS/CSV export format ─────────────────────────
  // Header: Stock Name,ISIN,Sector Name,Quantity,Average Cost Price,Value At Cost,
  //         Current Market Price,Current Market Price % Change,Valuation at Current Market Price,
  //         Unrealized Profit/Loss,...
  const isCDSLExport = /Stock Name.*ISIN.*Sector.*Quantity.*Average Cost Price/i.test(text) ||
                       /ISIN.*Sector.*Quantity.*Average Cost/i.test(text);

  if(isCDSLExport){
    // Parse as CSV — split by lines, skip header rows and summary rows
    const lines = text.replace(/\r/g,'').split('\n');
    for(const line of lines){
      const cols = line.split(',').map(c=>c.replace(/^"|"$/g,'').trim());
      // Need at least: name, isin, sector, qty, avgBuy
      if(cols.length < 5) continue;
      const isin = cols[1];
      if(!/^IN[A-Z0-9]{10,12}$/.test(isin)) continue; // must have valid ISIN

      const name    = cols[0].trim();
      const sector  = cols[2].trim();
      const qty     = Math.round(parseFloat(cols[3].replace(/,/g,''))||0);
      const avgBuy  = Math.round(parseFloat(cols[4].replace(/,/g,''))*100)/100 || 0;
      const ltp     = Math.round(parseFloat((cols[6]||'').replace(/,/g,''))*100)/100 || 0;
      const pnl     = parseFloat((cols[9]||'').replace(/,/g,'')) || 0;

      if(!name || qty <= 0 || seen.has(isin)) continue;

      // Skip ETFs and Bonds (no NSE equity symbol)
      if(/ETF|BOND|GOLDBOND|SGB|SBI ETF|MIRAEAMC/i.test(name)) continue;

      // Resolve NSE symbol from ISIN map first, then name
      let sym = ISIN_MAP[isin] || '';
      if(!sym){
        // Try matching name against NSE_DB
        const nameUp = name.toUpperCase();
        const found  = NSE_DB.find(s=>
          nameUp.startsWith(s.name.toUpperCase().slice(0,8)) ||
          s.name.toUpperCase().startsWith(nameUp.slice(0,8))
        );
        sym = found ? found.sym : name.replace(/[^A-Z0-9]/g,'').slice(0,12);
      }

      seen.add(isin);
      const info = NSE_DB.find(s=>s.sym===sym)||{name,sector};
      results.push({
        sym,
        isin,
        cdslName: name,   // original CDSL company name — used for Yahoo search fallback
        name:    info.name || name,
        sector:  info.sector || sector || 'Diversified',
        qty,
        avgBuy,           // ✅ Real avg buy price from CDSL
        ltp,              // Current market price from CDSL
        change:  0,
        pnl,              // Unrealized P&L from CDSL
        cdslImport: true,
      });
    }
    return results;
  }

  // ── Fallback: Plain text / manual paste ────────────────────────
  // Step 1: Join wrapped CDSL lines (ISIN on line 1, Beneficiary on line 2)
  const rawLines = text.replace(/\r/g,'').split('\n').map(l=>l.trim()).filter(l=>l.length>2);
  const joined   = [];
  let i = 0;
  while(i < rawLines.length){
    const cur    = rawLines[i];
    const hasISIN = /\bIN[A-Z0-9]{10,12}\b/.test(cur);
    const hasBen  = /beneficiary/i.test(cur);
    if(hasISIN && !hasBen && i+1 < rawLines.length){
      let merged = cur, j = i+1;
      while(j < rawLines.length && !/beneficiary/i.test(merged)){
        merged = merged + ' ' + rawLines[j]; j++;
      }
      joined.push(merged); i = j;
    } else {
      joined.push(cur); i++;
    }
  }

  for(const line of joined){
    if(/^(symbol|name|isin|sr\.?no|total|date|page|user|holding|demat|client)/i.test(line)) continue;
    if(/saturday|sunday|monday|tuesday|wednesday|thursday|friday/i.test(line)) continue;
    if(/mutual fund|government of india|SGB|sovereign/i.test(line)) continue;
    if(line.length < 5) continue;

    let sym='', isin='', qty=0, avgBuy=0, ltp=0;

    // Pattern 1: CDSL text — has ISIN + Beneficiary
    const cdslMatch = line.match(/\b(IN[A-Z0-9]{10,12})\b/);
    if(cdslMatch){
      isin = cdslMatch[1];
      sym  = ISIN_MAP[isin] || '';
      const benIdx  = line.search(/beneficiary/i);
      const numPart = benIdx >= 0 ? line.slice(benIdx) : line;
      const nums    = [...numPart.matchAll(/[\d,]+\.?\d*/g)]
        .map(m=>parseFloat(m[0].replace(/,/g,'')))
        .filter(n=>n>0&&n<1e10);
      if(nums.length>=2){
        qty = Math.round(nums[0]);
        // CDSL text last number = current market value (qty × LTP)
        // Derive LTP from value/qty — this is the CDSL snapshot price, not avg buy
        // avgBuy is NOT available in CDSL text format — leave as 0
        // But we store the CDSL value/qty as ltp so at least we have a price reference
        const totalVal = nums[nums.length-1];
        ltp = qty>0 ? Math.round(totalVal/qty*100)/100 : 0;
        avgBuy = 0; // CDSL text format does not include avg buy price
        // Note: to get avgBuy, use CDSL XLS/CSV export (Equity_Summary_Details)
      } else if(nums.length===1){
        qty = Math.round(nums[0]);
      }
      if(!sym){
        const nameMatch = line.replace(isin,'')
          .replace(/new\s+fv\s+r[se]\.?\s*[\d./]+\s*/gi,'')
          .replace(/fv\s+r[se]\.?\s*[\d./]+\s*/gi,'')
          .match(/([A-Z][A-Z\s&.()\-]+?(?:LTD\.?|LIMITED|CORP|CO\.?|IND|BANK|POWER|TECH|SOLAR|ENERGY|FINANCE))/i);
        if(nameMatch){
          const nu = nameMatch[1].toUpperCase().replace(/\s+/g,' ').trim();
          const found = NSE_DB.find(s=>
            s.name.toUpperCase().startsWith(nu.split(' ').slice(0,2).join(' ')) ||
            nu.startsWith(s.name.toUpperCase().split(' ').slice(0,2).join(' '))
          );
          sym = found ? found.sym : nu.replace(/[^A-Z0-9]/g,'').slice(0,12);
        }
      }
      if(sym && qty>0 && !seen.has(isin)){
        seen.add(isin);
        const info = NSE_DB.find(s=>s.sym===sym)||{name:sym,sector:'Diversified'};
        results.push({sym,isin,name:info.name||sym,sector:info.sector||'Diversified',
          qty:Math.round(qty),avgBuy,ltp,change:0});
      }
      continue;
    }

    // Pattern 2: CSV / manual — Symbol, Qty, AvgBuy  OR  Symbol, ISIN, Qty, AvgBuy
    const parts = line.split(/[,\t|;]+/).map(p=>p.trim()).filter(Boolean);
    if(parts.length>=2){
      const maybeISIN = parts.find(p=>/^IN[A-Z0-9]{10,12}$/.test(p));
      const maybeSym  = parts[0].toUpperCase().replace(/[^A-Z0-9&\-]/g,'').replace(/\.NS$/,'');
      const nums      = parts.map(p=>parseFloat(p.replace(/[,₹]/g,''))).filter(n=>!isNaN(n)&&n>0);
      isin = maybeISIN || '';
      sym  = isin ? (ISIN_MAP[isin]||maybeSym) : maybeSym;
      if(nums.length>=2){ qty=Math.round(nums[0]); avgBuy=nums[1]; }
      // If 3 numbers and nums[1] looks like a total invested amount (not per-share):
      // heuristic — if nums[1]/nums[0] gives a price < nums[2] then nums[1] is total
      if(nums.length>=3){
        const perShare = nums[1]/Math.max(nums[0],1);
        if(perShare > 1 && perShare < nums[2] * 0.95){
          qty = Math.round(nums[0]);
          avgBuy = Math.round(perShare*100)/100;
        }
      }
      if(sym&&sym.length>=2&&sym.length<=15&&qty>0&&avgBuy>0&&!seen.has(sym)){
        seen.add(sym);
        const info=NSE_DB.find(s=>s.sym===sym)||{name:sym,sector:'Diversified'};
        results.push({sym,isin,name:info.name||sym,sector:info.sector||'Diversified',
          qty:Math.round(qty),avgBuy,ltp:0,change:0});
      }
    }
  }
  return results;
}

// Apply parsed holdings to portfolio, then trigger data refresh
function applyImport(mode){
  if(!parsedHoldings.length){toast('Nothing to import — paste data first');return;}

  // Save avgBuy values keyed by sym AND isin before any changes
  // so they survive both replace and append modes
  const savedAvg = {};
  S.portfolio.forEach(h=>{
    if(h.avgBuy>0){
      if(h.sym)  savedAvg[h.sym]  = h.avgBuy;
      if(h.isin) savedAvg[h.isin] = h.avgBuy;
    }
  });

  if(mode==='replace') S.portfolio=[];
  const existing = new Set(S.portfolio.map(h=>h.sym));
  parsedHoldings.forEach(h=>{
    if(existing.has(h.sym)){
      const idx=S.portfolio.findIndex(p=>p.sym===h.sym);
      if(idx>=0) Object.assign(S.portfolio[idx],h);
    } else {
      S.portfolio.push({...h});
      existing.add(h.sym);
    }
  });

  // Restore avgBuy values that were lost during import
  S.portfolio.forEach(h=>{
    if(!h.avgBuy || h.avgBuy===0){
      const restored = savedAvg[h.sym] || savedAvg[h.isin] || 0;
      if(restored) h.avgBuy = restored;
    }
  });
  savePF();
  closePanel();
  parsedHoldings = [];

  // ── Switch to portfolio tab immediately ───────────────────────
  S.curTab = 'portfolio';
  document.querySelectorAll('.nb').forEach(b=>b.classList.remove('active'));
  const pfBtn = document.querySelector('.nb');
  if(pfBtn) pfBtn.classList.add('active');

  // Set sync status to show live progress in portfolio tab
  S._importStatus = { state:'syncing', msg:'Imported — refreshing data…', ts: Date.now() };
  render();

  // ── Data refresh pipeline (sequential, with visible status) ──
  (async ()=>{
    // Step 1: Clear stale fund cache + reload fundamentals.json
    localStorage.removeItem('fund_cache');
    localStorage.removeItem('fund_cache_ts');
    S._importStatus = { state:'syncing', msg:'Step 1/3 — Loading fundamentals…', ts: Date.now() };
    updateImportStatus();
    await loadFundamentals(true);
    render();

    // Step 2: Fetch live prices
    S._importStatus = { state:'syncing', msg:'Step 2/3 — Fetching live prices…', ts: Date.now() };
    updateImportStatus();
    await refreshPortfolioData();

    // Step 3: Sync to GitHub + trigger Actions
    S._importStatus = { state:'syncing', msg:'Step 3/3 — Syncing to GitHub…', ts: Date.now() };
    updateImportStatus();
    await autoSyncPortfolioSymbols();
  })();
}

// ── Update the status strip in portfolio tab without full re-render ──
function updateImportStatus(){
  const el = document.getElementById('import-status-strip');
  if(el && S._importStatus) el.innerHTML = importStatusHtml();
}

function importStatusHtml(){
  const st = S._importStatus;
  if(!st) return '';
  const col = st.state==='ok'?'#00e896':st.state==='error'?'#ff6b85':'#ffbf47';
  const icon = st.state==='ok'?'✅':st.state==='error'?'❌':'⏳';
  return `<div style="padding:8px 13px;background:rgba(${st.state==='ok'?'0,208,132':st.state==='error'?'255,59,92':'245,166,35'},.08);
    border-bottom:1px solid rgba(${st.state==='ok'?'0,208,132':st.state==='error'?'255,59,92':'245,166,35'},.2);
    font-size:11px;color:${col};font-family:'JetBrains Mono',monospace;display:flex;justify-content:space-between;align-items:center">
    <span>${icon} ${st.msg}</span>
    ${st.state!=='syncing'?`<span class="u-tx3-9">${new Date(st.ts).toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit',hour12:true})}</span>`:'<span class="u-tx3-9">working…</span>'}
  </div>`;
}

// ── Auto-sync portfolio symbols to GitHub after import ────────────
// AUTO-SYNC — commits portfolio_symbols.txt to GitHub
// and triggers 'all' workflow after import (RESOLVE=true confirms symbols via Yahoo)

async function autoSyncPortfolioSymbols(){
  const token = S.settings.ghToken?.trim();
  const repo  = S.settings.ghRepo?.trim();
  if(!token || !repo) return; // silent — user hasn't configured GitHub

  const txt = S.portfolio
    .filter(h=>h.sym)
    .map(h=>h.cdslName ? h.sym+'|'+h.cdslName : h.sym)
    .join('\n');

  const encoded = btoa(unescape(encodeURIComponent(txt)));
  const headers = { 'Authorization':'token '+token, 'Content-Type':'application/json', 'Accept':'application/vnd.github.v3+json' };
  const fileUrl = 'https://api.github.com/repos/'+repo+'/contents/portfolio_symbols.txt';

  try{
    // Get current SHA
    let sha = null;
    const get = await fetch(fileUrl, {headers});
    if(get.ok){ const d = await get.json(); sha = d.sha; }

    // Commit updated portfolio_symbols.txt
    const body = { message:'portfolio: update symbols', content: encoded };
    if(sha) body.sha = sha;
    const put = await fetch(fileUrl, { method:'PUT', headers, body:JSON.stringify(body) });
    if(!put.ok){
      const err = await put.json().catch(()=>({}));
      const msg = 'portfolio_symbols.txt commit failed: '+(err.message||put.status)+' — check PAT has repo scope';
      S.settings._lastSync = Date.now();
      S.settings._lastSyncOk = false;
      S.settings._lastSyncMsg = msg;
      saveSettings();
      S._importStatus = { state:'error', msg, ts: Date.now() };
      updateImportStatus();
      toast('❌ '+msg);
      return;
    }

    // Trigger fundamentals fetch workflow
    await new Promise(r=>setTimeout(r, 1500)); // let commit land
    const wfUrl = 'https://api.github.com/repos/'+repo+'/actions/workflows/fetch-prices.yml/dispatches';
    const wfRes = await fetch(wfUrl, {
      method:'POST', headers,
      body: JSON.stringify({ ref:'main', inputs:{ fetch_type:'all' } })
    });

    if(wfRes.status === 204){
      S.settings._lastSync    = Date.now();
      S.settings._lastSyncOk  = true;
      S.settings._lastSyncMsg = 'Symbols synced + workflow triggered';
      saveSettings();
      S._importStatus = { state:'ok', msg:'Synced ✓ — fundamentals fetching in background (~5 min)', ts: Date.now() };
      updateImportStatus();
    } else if(wfRes.status === 403){
      const msg = 'GitHub PAT needs "workflow" scope — run diagnostic in Watchlist settings';
      S.settings._lastSync    = Date.now();
      S.settings._lastSyncOk  = false;
      S.settings._lastSyncMsg = msg;
      saveSettings();
      S._importStatus = { state:'error', msg: msg, ts: Date.now() };
      updateImportStatus();
    } else if(wfRes.status === 422){
      const msg = 'Workflow not found — check fetch-prices.yml exists in .github/workflows/';
      S._importStatus = { state:'error', msg, ts: Date.now() };
      updateImportStatus();
    } else {
      const e2 = await wfRes.json().catch(()=>({}));
      const msg = 'Workflow trigger failed ('+wfRes.status+'): '+(e2.message||'unknown');
      S._importStatus = { state:'error', msg, ts: Date.now() };
      updateImportStatus();
    }
  } catch(e){
    const msg = 'Sync error: '+e.message;
    S.settings._lastSync    = Date.now();
    S.settings._lastSyncOk  = false;
    S.settings._lastSyncMsg = msg;
    saveSettings();
    S._importStatus = { state:'error', msg, ts: Date.now() };
    updateImportStatus();
  }
}

//  PORTFOLIO TAB — Bloomberg Terminal Style Screener Grid
//  Matches: color-coded rows, dense columns, signal badges

// Refresh state

// Signal logic for each stock
// Color a numeric cell based on value vs threshold
