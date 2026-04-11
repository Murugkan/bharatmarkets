/**
 * app-engine.js — Core Data Engine
 *
 * Source files (all in repo root, served via GitHub Pages):
 *   unified-symbols.json  — master stock dictionary
 *   fundamentals.json     — financial data keyed by ticker
 *   prices.json           — live price data keyed by ticker
 *
 * unified-symbols.json schema:
 *   { updated, count, symbols: [ { ticker, name, isin, sector, industry, type, source, qty?, avg? } ] }
 *
 * Flow:
 *   Fetch all three → join on ticker → compute PNL/cost/weight → write IndexedDB → hydrate MASTER_DATA → render UI
 */

// ── Database config ──────────────────────────────────────────
var DB_NAME       = 'BharatEngineDB';
var DB_VER        = 1;
var STORE_UNIFIED = 'UnifiedStocks';
var STORE_LEDGER  = 'ExclusionLedger';

// ── Global in-memory array (source of truth for UI) ─────────
var MASTER_DATA = [];

// ── Debug log (visible in UI — essential for iPhone/no devtools) ──
var _engineLogs = [];
function engineLog(msg, level) {
    var ts  = new Date().toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
    var lvl = level || 'info';
    var entry = '[' + ts + '] ' + msg;
    _engineLogs.push({ msg: entry, level: lvl });
    console.log('[Engine]', msg);

    var panel = document.getElementById('engine-debug-log');
    if (panel) {
        var colors = { info: '#8eb0d0', ok: '#00e896', warn: '#ffbf47', err: '#ff4d6d' };
        var div = document.createElement('div');
        div.style.color = colors[lvl] || '#8eb0d0';
        div.style.fontFamily = 'monospace';
        div.style.fontSize   = '11px';
        div.style.lineHeight = '1.6';
        div.textContent = entry;
        panel.appendChild(div);
        panel.scrollTop = panel.scrollHeight;
    }
}

// ── 1. Open IndexedDB ────────────────────────────────────────
function initEngineDB() {
    return new Promise(function(resolve, reject) {
        var req = indexedDB.open(DB_NAME, DB_VER);
        req.onupgradeneeded = function(e) {
            var db = e.target.result;
            if (!db.objectStoreNames.contains(STORE_UNIFIED))
                db.createObjectStore(STORE_UNIFIED, { keyPath: 'sym' });
            if (!db.objectStoreNames.contains(STORE_LEDGER))
                db.createObjectStore(STORE_LEDGER, { keyPath: 'sym' });
        };
        req.onsuccess = function(e) { resolve(e.target.result); };
        req.onerror   = function(e) { reject(e.target.error); };
    });
}

// ── 2. Fetch all three source files ─────────────────────────
function fetchSourceFiles() {
    engineLog('Fetching source files...', 'info');
    var t = '?t=' + Date.now();
    return Promise.all([
        fetch('./unified-symbols.json' + t).then(function(r) {
            if (!r.ok) throw new Error('unified-symbols.json HTTP ' + r.status);
            return r.json();
        }),
        fetch('./fundamentals.json' + t).then(function(r) {
            if (!r.ok) throw new Error('fundamentals.json HTTP ' + r.status);
            return r.json();
        }),
        fetch('./prices.json' + t).then(function(r) {
            if (!r.ok) throw new Error('prices.json HTTP ' + r.status);
            return r.json();
        })
    ]);
}

// ── 3. Join all three files and compute derived fields ───────
function buildUnifiedRecords(uData, fData, pData) {
    var symbols      = uData.symbols || uData || [];
    var fundamentals = fData.stocks  || {};
    var prices       = pData.quotes  || {};

    engineLog('Raw symbols: ' + symbols.length + ' | Fund: ' + Object.keys(fundamentals).length + ' | Prices: ' + Object.keys(prices).length, 'info');

    // Filter out unresolved (ticker = "?") and skip SGB/bonds
    var resolved = symbols.filter(function(s) {
        if (!s.ticker || s.ticker === '?' || s.ticker === '') return false;
        if (/^SGB|GOLDBOND/i.test(s.ticker)) return false;
        return true;
    });

    engineLog('Resolved: ' + resolved.length + ' | Skipped: ' + (symbols.length - resolved.length), resolved.length > 0 ? 'ok' : 'warn');

    // Total market value for weight calculation
    var totalMV = 0;
    resolved.forEach(function(s) {
        var p   = prices[s.ticker]       || {};
        var f   = fundamentals[s.ticker] || {};
        var ltp = p.ltp || f.ltp || 0;
        totalMV += ltp * (s.qty || 0);
    });

    engineLog('Total MV: Rs ' + (totalMV / 100000).toFixed(2) + 'L', 'info');

    return resolved.map(function(s) {
        var f   = fundamentals[s.ticker] || {};
        var p   = prices[s.ticker]       || {};

        var ltp         = p.ltp  || f.ltp  || 0;
        var qty         = s.qty  || 0;
        var avg         = s.avg  || 0;
        var cost        = qty * avg;
        var marketValue = qty * ltp;
        var pnl         = marketValue - cost;
        var pnlPct      = cost > 0 ? (pnl / cost) * 100 : 0;
        var weight      = totalMV > 0 ? (marketValue / totalMV) * 100 : 0;
        var ath         = f.ath || p.w52h || 0;
        var athDist     = ath > 0 ? ((ath - ltp) / ath) * 100 : 0;

        return {
            // Identity — from unified-symbols.json
            sym:        s.ticker,
            name:       s.name       || f.name  || '',
            isin:       s.isin       || '',
            sector:     s.sector     || f.sector || s.industry || '',
            industry:   s.industry   || '',
            category:   s.type       || s.category || 'portfolio',
            source:     s.source     || '',

            // Position — from unified-symbols.json
            qty:        qty,
            avg:        avg,

            // Fundamentals — from fundamentals.json
            pe:         f.pe         || null,
            fwd_pe:     f.fwd_pe     || null,
            pb:         f.pb         || null,
            eps:        f.eps        || null,
            bv:         f.bv         || null,
            roe:        f.roe        || null,
            roce:       f.roce       || null,
            opm_pct:    f.opm_pct    || null,
            npm_pct:    f.npm_pct    || null,
            gpm_pct:    f.gpm_pct    || null,
            mcap:       f.mcap       || null,
            sales:      f.sales      || null,
            ebitda:     f.ebitda     || null,
            cfo:        f.cfo        || null,
            debt_eq:    f.debt_eq    || null,
            div_yield:  f.div_yield  || null,
            beta:       f.beta       || null,
            prom_pct:   f.prom_pct   || null,
            fii_pct:    f.fii_pct    || null,
            dii_pct:    f.dii_pct    || null,
            public_pct: f.public_pct || null,
            w52h:       f.w52h       || p.w52h  || null,
            w52l:       f.w52l       || p.w52l  || null,
            w52_pct:    f.w52_pct    || null,
            ath:        ath          || null,
            ath_pct:    f.ath_pct    || null,
            signal:     f.signal     || '',
            pos:        f.pos        || 0,
            neg:        f.neg        || 0,
            quarterly:  f.quarterly  || [],
            chg5d:      f.chg5d      || null,

            // Prices — from prices.json
            ltp:        ltp,
            prev:       p.prev       || f.prev  || 0,
            change:     p.change     || 0,
            chg1d:      p.changePct  || f.chg1d || 0,
            open:       p.open       || 0,
            high:       p.high       || 0,
            low:        p.low        || 0,
            vol:        p.vol        || 0,

            // Computed by engine
            cost:        cost,
            marketValue: marketValue,
            pnl:         pnl,
            pnlPct:      pnlPct,
            weight:      weight,
            athDist:     athDist,
        };
    });
}

// ── 4. Write to IndexedDB ────────────────────────────────────
function writeToIndexedDB(db, records) {
    return new Promise(function(resolve, reject) {
        var tx    = db.transaction(STORE_UNIFIED, 'readwrite');
        var store = tx.objectStore(STORE_UNIFIED);

        var clearReq = store.clear();
        clearReq.onsuccess = function() {
            records.forEach(function(r) { store.put(r); });
        };

        tx.oncomplete = function() {
            engineLog('DB written — ' + records.length + ' records', 'ok');
            resolve();
        };
        tx.onerror = function() {
            engineLog('DB write error: ' + tx.error, 'err');
            reject(tx.error);
        };
    });
}

// ── 5. Hydrate MASTER_DATA from IndexedDB ────────────────────
function hydrateMasterData(db) {
    return new Promise(function(resolve, reject) {
        var tx  = db.transaction(STORE_UNIFIED, 'readonly');
        var req = tx.objectStore(STORE_UNIFIED).getAll();
        req.onsuccess = function(e) {
            MASTER_DATA = e.target.result || [];
            engineLog('MASTER_DATA: ' + MASTER_DATA.length + ' stocks', 'ok');
            resolve(MASTER_DATA);
        };
        req.onerror = function(e) {
            engineLog('Hydration error: ' + e.target.error, 'err');
            reject(e.target.error);
        };
    });
}

// ── 6. Main Sync Orchestrator ─────────────────────────────────
function runEngineSync() {
    var db;
    engineLog('=== Engine Sync Start ===', 'info');
    if (typeof showToast === 'function') showToast('Engine syncing...');

    return initEngineDB()
        .then(function(openedDB) {
            db = openedDB;
            engineLog('IndexedDB ready', 'ok');
            return fetchSourceFiles();
        })
        .then(function(results) {
            engineLog('All files fetched', 'ok');
            var records = buildUnifiedRecords(results[0], results[1], results[2]);
            if (!records.length) engineLog('WARNING: 0 records — check ticker fields in unified-symbols.json', 'warn');
            return writeToIndexedDB(db, records);
        })
        .then(function() {
            return hydrateMasterData(db);
        })
        .then(function(data) {
            engineLog('=== Sync Complete: ' + data.length + ' stocks ===', 'ok');
            if (typeof showToast === 'function') showToast('Synced — ' + data.length + ' stocks');
            if (typeof render === 'function') render();
            else window.dispatchEvent(new CustomEvent('engine-updated'));
        })
        .catch(function(err) {
            engineLog('SYNC FAILED: ' + err.message, 'err');
            if (typeof showToast === 'function') showToast('Sync failed: ' + err.message);
        });
}

// ── 7. Re-hydrate without re-fetch ───────────────────────────
function rehydrateFromDB() {
    return initEngineDB()
        .then(function(db) { return hydrateMasterData(db); })
        .then(function(data) {
            MASTER_DATA = data;
            if (typeof render === 'function') render();
            return data;
        });
}

// ── 8. UI filter helpers ──────────────────────────────────────
function getPortfolioStocks() {
    return MASTER_DATA.filter(function(s) { return s.category === 'portfolio'; });
}

function getWatchlistStocks() {
    return MASTER_DATA.filter(function(s) { return s.category === 'watchlist'; });
}

// ── 9. Debug overlay — tap anywhere to show on iPhone ────────
function showEngineDebug() {
    var existing = document.getElementById('engine-debug-overlay');
    if (existing) { existing.remove(); return; }

    var overlay = document.createElement('div');
    overlay.id = 'engine-debug-overlay';
    overlay.style.cssText = [
        'position:fixed;inset:0;z-index:9999;',
        'background:rgba(0,0,0,.97);',
        'display:flex;flex-direction:column;',
        'padding:16px;',
        'padding-top:calc(16px + env(safe-area-inset-top));',
        'padding-bottom:calc(16px + env(safe-area-inset-bottom));'
    ].join('');

    var header = document.createElement('div');
    header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-shrink:0;';
    header.innerHTML = [
        '<div style="font-family:monospace;font-size:12px;color:#00e896;font-weight:800;">ENGINE DEBUG</div>',
        '<button onclick="document.getElementById(\'engine-debug-overlay\').remove()" ',
        'style="background:#222;color:#fff;border:1px solid #444;border-radius:6px;padding:6px 14px;font-size:12px;cursor:pointer;">',
        '✕ Close</button>'
    ].join('');

    var stats = document.createElement('div');
    stats.style.cssText = 'font-family:monospace;font-size:11px;color:#00e896;margin-bottom:8px;flex-shrink:0;line-height:1.8;';
    stats.textContent = [
        'MASTER_DATA: ' + MASTER_DATA.length + ' stocks',
        'Portfolio: ' + getPortfolioStocks().length,
        'Watchlist: ' + getWatchlistStocks().length
    ].join(' | ');

    var log = document.createElement('div');
    log.id = 'engine-debug-log';
    log.style.cssText = 'flex:1;overflow-y:auto;background:#02040a;border:1px solid #1e3350;border-radius:6px;padding:10px;margin-bottom:8px;';

    _engineLogs.forEach(function(entry) {
        var colors = { info: '#8eb0d0', ok: '#00e896', warn: '#ffbf47', err: '#ff4d6d' };
        var div = document.createElement('div');
        div.style.color = colors[entry.level] || '#8eb0d0';
        div.style.fontFamily = 'monospace';
        div.style.fontSize = '11px';
        div.style.lineHeight = '1.7';
        div.textContent = entry.msg;
        log.appendChild(div);
    });
    log.scrollTop = log.scrollHeight;

    // Sample first resolved stock
    var sample = document.createElement('div');
    sample.style.cssText = 'font-family:monospace;font-size:10px;color:#8eb0d0;background:#02040a;border:1px solid #1e3350;border-radius:6px;padding:8px;white-space:pre-wrap;word-break:break-all;max-height:160px;overflow-y:auto;flex-shrink:0;';
    if (MASTER_DATA.length > 0) {
        var s = MASTER_DATA[0];
        sample.textContent = 'Sample [0]:\n' +
            'sym='    + s.sym     + ' name=' + (s.name||'').slice(0,20) + '\n' +
            'ltp='    + s.ltp     + ' qty='  + s.qty    + ' avg='    + s.avg    + '\n' +
            'cost='   + s.cost    + ' pnl='  + s.pnl.toFixed(0) + ' pnlPct=' + s.pnlPct.toFixed(2) + '%\n' +
            'sector=' + s.sector  + ' cat='  + s.category + '\n' +
            'signal=' + s.signal  + ' pe='   + s.pe;
    } else {
        sample.textContent = 'No stocks in MASTER_DATA';
    }

    overlay.appendChild(header);
    overlay.appendChild(stats);
    overlay.appendChild(log);
    overlay.appendChild(sample);
    document.body.appendChild(overlay);
}
