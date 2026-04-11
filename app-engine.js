/**
 * app-engine.js — Core Data Engine
 */

var DB_NAME       = 'BharatEngineDB';
var DB_VER        = 1;
var STORE_UNIFIED = 'UnifiedStocks';
var STORE_LEDGER  = 'ExclusionLedger';
var MASTER_DATA   = [];
var _engineLogs   = [];

function engineLog(msg, level) {
    var ts = new Date().toLocaleTimeString('en-IN', { hour12: false });
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
        div.style.fontSize = '11px';
        div.textContent = entry;
        panel.appendChild(div);
        panel.scrollTop = panel.scrollHeight;
    }
}

function initEngineDB() {
    return new Promise(function(resolve, reject) {
        var req = indexedDB.open(DB_NAME, DB_VER);
        req.onupgradeneeded = function(e) {
            var db = e.target.result;
            if (!db.objectStoreNames.contains(STORE_UNIFIED)) db.createObjectStore(STORE_UNIFIED, { keyPath: 'sym' });
            if (!db.objectStoreNames.contains(STORE_LEDGER)) db.createObjectStore(STORE_LEDGER, { keyPath: 'sym' });
        };
        req.onsuccess = function(e) { resolve(e.target.result); };
        req.onerror = function(e) { reject(e.target.error); };
    });
}

function fetchSourceFiles() {
    engineLog('Fetching source files...', 'info');
    var t = '?t=' + Date.now();
    return Promise.all([
        fetch('./unified-symbols.json' + t).then(function(r) { if (!r.ok) throw new Error('Symbols fetch failed'); return r.json(); }),
        fetch('./fundamentals.json' + t).then(function(r) { if (!r.ok) throw new Error('Fund fetch failed'); return r.json(); }),
        fetch('./prices.json' + t).then(function(r) { if (!r.ok) throw new Error('Prices fetch failed'); return r.json(); })
    ]);
}

function buildUnifiedRecords(uData, fData, pData) {
    // Fix for blank table: Support both 'symbols' key and direct arrays
    var symbols = uData.symbols || (Array.isArray(uData) ? uData : []);
    var fundamentals = fData.stocks || fData || {};
    var prices = pData.quotes || pData || {};

    engineLog('Raw symbols: ' + symbols.length, 'info');

    var resolved = symbols.filter(function(s) {
        var tickerKey = s.ticker || s.symbol; 
        if (!tickerKey || tickerKey === '?' || tickerKey === '') return false;
        if (/^SGB|GOLDBOND/i.test(tickerKey)) return false;
        if (!s.ticker) s.ticker = tickerKey; 
        return true;
    });

    var totalMV = 0;
    resolved.forEach(function(s) {
        var p = prices[s.ticker] || {};
        var ltp = p.ltp || 0;
        totalMV += ltp * (s.qty || 0);
    });

    return resolved.map(function(s) {
        var f = fundamentals[s.ticker] || {};
        var p = prices[s.ticker] || {};
        var ltp = p.ltp || f.ltp || 0;
        var cost = (s.qty || 0) * (s.avg || 0);
        var marketValue = (s.qty || 0) * ltp;

        return {
            sym: s.ticker,
            name: s.name || f.name || '',
            sector: s.sector || f.sector || '',
            category: s.type || s.category || 'portfolio',
            qty: s.qty || 0,
            avg: s.avg || 0,
            ltp: ltp,
            cost: cost,
            marketValue: marketValue,
            pnl: marketValue - cost,
            pnlPct: cost > 0 ? ((marketValue - cost) / cost) * 100 : 0,
            weight: totalMV > 0 ? (marketValue / totalMV) * 100 : 0
        };
    });
}

function writeToIndexedDB(db, records) {
    return new Promise(function(resolve, reject) {
        var tx = db.transaction(STORE_UNIFIED, 'readwrite');
        var store = tx.objectStore(STORE_UNIFIED);
        store.clear().onsuccess = function() {
            records.forEach(function(r) { store.put(r); });
        };
        tx.oncomplete = function() { resolve(); };
        tx.onerror = function() { reject(tx.error); };
    });
}

function runEngineSync() {
    engineLog('=== Sync Start ===', 'info');
    return initEngineDB()
        .then(function(db) {
            return fetchSourceFiles().then(function(res) {
                var records = buildUnifiedRecords(res[0], res[1], res[2]);
                return writeToIndexedDB(db, records).then(function() {
                    MASTER_DATA = records;
                    engineLog('Sync Complete: ' + records.length + ' stocks', 'ok');
                    if (typeof render === 'function') render();
                });
            });
        })
        .catch(function(err) { engineLog('Error: ' + err.message, 'err'); });
}

function showEngineDebug() {
    var overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.9);padding:20px;color:white;overflow:y-auto;';
    overlay.innerHTML = '<h3>Engine Logs</h3><button onclick="this.parentElement.remove()">Close</button><hr>';
    _engineLogs.forEach(function(l) {
        overlay.innerHTML += '<div style="font-family:monospace;margin-bottom:5px;">' + l.msg + '</div>';
    });
    document.body.appendChild(overlay);
}
