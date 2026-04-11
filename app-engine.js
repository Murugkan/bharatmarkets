/**
 * app-engine.js — Final Version with Forced Debug Window
 */

var DB_NAME       = 'BharatEngineDB';
var DB_VER        = 1;
var STORE_UNIFIED = 'UnifiedStocks';
var MASTER_DATA   = [];
var _engineLogs   = [];

// ── 1. Forced Debug Window (Created immediately on script load) ──
function createDebugWindow() {
    if (document.getElementById('engine-debug-window')) return;
    
    var win = document.createElement('div');
    win.id = 'engine-debug-window';
    // Style forced to be visible over all other elements
    win.style.cssText = 'position:fixed; bottom:0; left:0; right:0; height:30vh; background:#050505; color:#00e896; z-index:999999; border-top:2px solid #00e896; display:flex; flex-direction:column; font-family:monospace;';
    
    win.innerHTML = `
        <div style="background:#111; padding:10px; display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #333;">
            <span style="font-weight:bold; letter-spacing:1px;">ENGINE MONITOR ACTIVE</span>
            <button onclick="this.parentElement.parentElement.style.display='none'" style="background:#333; color:#fff; border:1px solid #555; padding:4px 10px; border-radius:4px; font-size:10px;">Hide</button>
        </div>
        <div id="engine-debug-content" style="flex:1; overflow-y:auto; padding:12px; font-size:11px; line-height:1.5;"></div>
    `;
    document.body.appendChild(win);
    engineLog('Monitor initialized.', 'ok');
}

function engineLog(msg, level) {
    var ts = new Date().toLocaleTimeString('en-IN', { hour12: false });
    var lvl = level || 'info';
    var entry = '[' + ts + '] ' + msg;
    _engineLogs.push({ msg: entry, level: lvl });

    var panel = document.getElementById('engine-debug-content');
    if (panel) {
        var div = document.createElement('div');
        var colors = { info: '#8eb0d0', ok: '#00e896', warn: '#ffbf47', err: '#ff4d6d' };
        div.style.color = colors[lvl] || '#8eb0d0';
        div.style.marginBottom = '4px';
        div.textContent = entry;
        panel.appendChild(div);
        panel.scrollTop = panel.scrollHeight;
    }
}

// ── 2. Data Logic ───────────────────────────────────────────
function buildUnifiedRecords(uData, fData, pData) {
    var symbols      = uData.symbols || (Array.isArray(uData) ? uData : []);
    var fundamentals = fData.stocks  || fData || {};
    var prices       = pData.quotes  || pData || {};

    engineLog('Mapping data for ' + symbols.length + ' symbols...');

    return symbols.filter(function(s) {
        var tk = s.ticker || s.symbol;
        return tk && tk !== '?' && !/^SGB|GOLDBOND/i.test(tk);
    }).map(function(s) {
        var tk = s.ticker || s.symbol;
        var f  = fundamentals[tk] || {};
        var p  = prices[tk] || {};
        var ltp = p.ltp || f.ltp || 0;
        
        return {
            sym: tk,
            name: s.name || f.name || tk,
            qty: s.qty || 0,
            avg: s.avg || 0,
            ltp: ltp,
            marketValue: (s.qty || 0) * ltp,
            cost: (s.qty || 0) * (s.avg || 0),
            category: s.type || s.category || 'portfolio'
        };
    });
}

// ── 3. Orchestrator ─────────────────────────────────────────
function runEngineSync() {
    createDebugWindow();
    engineLog('Starting engine sync...', 'info');

    var req = indexedDB.open(DB_NAME, DB_VER);
    req.onupgradeneeded = function(e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains(STORE_UNIFIED)) db.createObjectStore(STORE_UNIFIED, { keyPath: 'sym' });
    };

    req.onsuccess = function(e) {
        var db = e.target.result;
        var t = '?t=' + Date.now();
        
        Promise.all([
            fetch('./unified-symbols.json' + t).then(r => r.json()),
            fetch('./fundamentals.json' + t).then(r => r.json()),
            fetch('./prices.json' + t).then(r => r.json())
        ]).then(function(res) {
            MASTER_DATA = buildUnifiedRecords(res[0], res[1], res[2]);
            
            var tx = db.transaction(STORE_UNIFIED, 'readwrite');
            var store = tx.objectStore(STORE_UNIFIED);
            store.clear().onsuccess = function() {
                MASTER_DATA.forEach(r => store.put(r));
            };

            tx.oncomplete = function() {
                engineLog('Sync Complete: ' + MASTER_DATA.length + ' stocks.', 'ok');
                if (typeof render === 'function') render();
                window.dispatchEvent(new CustomEvent('engine-updated'));
            };
        }).catch(err => engineLog('Fetch Error: ' + err.message, 'err'));
    };
}

// Ensure execution
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', runEngineSync);
} else {
    runEngineSync();
}
