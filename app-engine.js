/**
 * app-engine.js — Core Data Engine with Integrated Debug Window
 */

// ── Configuration & State ─────────────────────────────────────
var DB_NAME       = 'BharatEngineDB';
var DB_VER        = 1;
var STORE_UNIFIED = 'UnifiedStocks';
var STORE_LEDGER  = 'ExclusionLedger';
var MASTER_DATA   = [];
var _engineLogs   = [];

// ── 1. Enhanced Logging System ───────────────────────────────
function engineLog(msg, level) {
    var ts = new Date().toLocaleTimeString('en-IN', { hour12: false });
    var lvl = level || 'info';
    var entry = '[' + ts + '] ' + msg;
    _engineLogs.push({ msg: entry, level: lvl });
    console.log('[Engine]', msg);

    // Update the UI log panel if it exists
    var panel = document.getElementById('engine-debug-content');
    if (panel) {
        var colors = { info: '#8eb0d0', ok: '#00e896', warn: '#ffbf47', err: '#ff4d6d' };
        var div = document.createElement('div');
        div.style.color = colors[lvl] || '#8eb0d0';
        div.style.borderBottom = '1px solid #1a1a1a';
        div.style.padding = '4px 0';
        div.textContent = entry;
        panel.appendChild(div);
        panel.scrollTop = panel.scrollHeight;
    }
}

// ── 2. The Debug Window (UI) ──────────────────────────────────
function createDebugWindow() {
    if (document.getElementById('engine-debug-window')) return;

    var win = document.createElement('div');
    win.id = 'engine-debug-window';
    win.style.cssText = 'position:fixed;bottom:0;left:0;right:0;height:30vh;background:#0a0a0a;color:#eee;font-family:monospace;font-size:11px;z-index:10000;border-top:2px solid #333;display:flex;flex-direction:column;';
    
    win.innerHTML = `
        <div style="background:#222;padding:5px 10px;display:flex;justify-content:space-between;align-items:center;font-weight:bold;border-bottom:1px solid #444;">
            <span>BHARAT ENGINE DEBUG</span>
            <button onclick="this.parentElement.parentElement.remove()" style="background:#444;color:white;border:none;padding:2px 8px;border-radius:3px;cursor:pointer;">Close</button>
        </div>
        <div id="engine-debug-content" style="flex:1;overflow-y:auto;padding:10px;white-space:pre-wrap;"></div>
    `;
    document.body.appendChild(win);
}

// ── 3. Database & Fetch Logic ────────────────────────────────
function initEngineDB() {
    return new Promise(function(resolve, reject) {
        var req = indexedDB.open(DB_NAME, DB_VER);
        req.onupgradeneeded = function(e) {
            var db = e.target.result;
            if (!db.objectStoreNames.contains(STORE_UNIFIED)) db.createObjectStore(STORE_UNIFIED, { keyPath: 'sym' });
        };
        req.onsuccess = function(e) { resolve(e.target.result); };
        req.onerror = function(e) { reject(e.target.error); };
    });
}

function buildUnifiedRecords(uData, fData, pData) {
    var symbols      = uData.symbols || (Array.isArray(uData) ? uData : []);
    var fundamentals = fData.stocks  || fData || {};
    var prices       = pData.quotes  || pData || {};

    engineLog('Files Loaded: Symbols(' + symbols.length + ') Fund(' + Object.keys(fundamentals).length + ') Prices(' + Object.keys(prices).length + ')');

    var resolved = symbols.filter(function(s) {
        var tk = s.ticker || s.symbol; 
        if (!tk || tk === '?' || tk === '') return false;
        if (!s.ticker) s.ticker = tk; 
        return true;
    });

    engineLog('Resolved Stocks: ' + resolved.length, resolved.length > 0 ? 'ok' : 'err');

    return resolved.map(function(s) {
        var f = fundamentals[s.ticker] || {};
        var p = prices[s.ticker] || {};
        var ltp = p.ltp || f.ltp || 0;
        return {
            sym: s.ticker,
            name: s.name || f.name || s.ticker,
            qty: s.qty || 0,
            avg: s.avg || 0,
            ltp: ltp,
            marketValue: (s.qty || 0) * ltp,
            category: s.type || s.category || 'portfolio'
        };
    });
}

// ── 4. Orchestrator ──────────────────────────────────────────
function runEngineSync() {
    createDebugWindow();
    engineLog('=== Starting Sync ===', 'info');

    initEngineDB().then(function(db) {
        var t = '?t=' + Date.now();
        return Promise.all([
            fetch('./unified-symbols.json' + t).then(r => r.json()),
            fetch('./fundamentals.json' + t).then(r => r.json()),
            fetch('./prices.json' + t).then(r => r.json())
        ]).then(function(res) {
            MASTER_DATA = buildUnifiedRecords(res[0], res[1], res[2]);
            
            // Cache to DB
            var tx = db.transaction(STORE_UNIFIED, 'readwrite');
            var store = tx.objectStore(STORE_UNIFIED);
            store.clear().onsuccess = function() {
                MASTER_DATA.forEach(r => store.put(r));
            };

            tx.oncomplete = function() {
                engineLog('Sync Success! ' + MASTER_DATA.length + ' records.', 'ok');
                if (typeof render === 'function') render();
            };
        });
    }).catch(function(err) {
        engineLog('SYNC FAILED: ' + err.message, 'err');
    });
}

// Start automatically
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', runEngineSync);
} else {
    runEngineSync();
}
