/**
 * app-engine.js — Final Execution Version
 * Fixes: Data Mapping, Syntax Errors, and Mobile UI Rendering
 */

// ── Global Configuration ──────────────────────────────────────
var DB_NAME       = 'BharatEngineDB';
var DB_VER        = 1;
var STORE_UNIFIED = 'UnifiedStocks';
var MASTER_DATA   = [];
var _engineLogs   = [];

// ── 1. The Auto-Debug Window ──────────────────────────────────
function engineLog(msg, level) {
    var ts = new Date().toLocaleTimeString('en-IN', { hour12: false });
    var lvl = level || 'info';
    var entry = '[' + ts + '] ' + msg;
    _engineLogs.push({ msg: entry, level: lvl });

    var panel = document.getElementById('engine-debug-content');
    if (panel) {
        var colors = { info: '#8eb0d0', ok: '#00e896', warn: '#ffbf47', err: '#ff4d6d' };
        var div = document.createElement('div');
        div.style.cssText = 'color:' + (colors[lvl] || '#8eb0d0') + '; border-bottom:1px solid #1a1a1a; padding:4px 0; font-family:monospace;';
        div.textContent = entry;
        panel.appendChild(div);
        panel.scrollTop = panel.scrollHeight;
    }
}

function createDebugWindow() {
    if (document.getElementById('engine-debug-window')) return;
    var win = document.createElement('div');
    win.id = 'engine-debug-window';
    win.style.cssText = 'position:fixed;bottom:0;left:0;right:0;height:25vh;background:#0a0a0a;color:#eee;z-index:10000;border-top:2px solid #333;display:flex;flex-direction:column;';
    win.innerHTML = `
        <div style="background:#222;padding:8px;display:flex;justify-content:space-between;align-items:center;font-size:12px;font-weight:bold;font-family:sans-serif;">
            <span>ENGINE DATA MONITOR</span>
            <button onclick="this.parentElement.parentElement.remove()" style="background:#444;color:white;border:none;padding:4px 10px;border-radius:4px;">✕ Close</button>
        </div>
        <div id="engine-debug-content" style="flex:1;overflow-y:auto;padding:10px;font-size:11px;"></div>
    `;
    document.body.appendChild(win);
}

// ── 2. The Universal Mapper (Fixes the "❌" Issue) ────────────
function buildUnifiedRecords(uData, fData, pData) {
    // Handle different JSON structures
    var symbols      = uData.symbols || (Array.isArray(uData) ? uData : []);
    var fundamentals = fData.stocks  || fData || {};
    var prices       = pData.quotes  || pData || {};

    engineLog('Data Loaded: ' + symbols.length + ' stocks found.');

    return symbols.filter(function(s) {
        var tk = s.ticker || s.symbol;
        return tk && tk !== '?' && !/^SGB|GOLDBOND/i.test(tk);
    }).map(function(s) {
        var tk  = s.ticker || s.symbol;
        var f   = fundamentals[tk] || {};
        var p   = prices[tk] || {};
        
        // Log mapping failure for specific stocks
        if (!f.pe && !p.ltp) engineLog('No data link for: ' + tk, 'warn');

        var ltp = p.ltp || f.ltp || 0;
        var qty = s.qty || 0;
        var avg = s.avg || 0;

        return {
            sym:      tk,
            name:     s.name || f.name || tk,
            category: s.type || s.category || 'portfolio',
            qty:      qty,
            avg:      avg,
            ltp:      ltp,
            marketValue: qty * ltp,
            cost:     qty * avg,
            pnl:      (qty * ltp) - (qty * avg),
            pnlPct:   (qty * avg) > 0 ? (((qty * ltp) - (qty * avg)) / (qty * avg)) * 100 : 0,
            pe:       f.pe || null,
            signal:   f.signal || '',
            sector:   s.sector || f.sector || ''
        };
    });
}

// ── 3. The Orchestrator ───────────────────────────────────────
function runEngineSync() {
    createDebugWindow();
    engineLog('=== Initializing Engine ===', 'info');

    var req = indexedDB.open(DB_NAME, DB_VER);
    req.onupgradeneeded = function(e) {
        e.target.result.createObjectStore(STORE_UNIFIED, { keyPath: 'sym' });
    };

    req.onsuccess = function(e) {
        var db = e.target.result;
        var t  = '?t=' + Date.now();
        
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
                engineLog('Sync Success: ' + MASTER_DATA.length + ' stocks merged', 'ok');
                if (typeof render === 'function') render();
                window.dispatchEvent(new CustomEvent('engine-updated'));
            };
        }).catch(err => engineLog('Critical Error: ' + err.message, 'err'));
    };
}

// Auto-Launch
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', runEngineSync);
} else {
    runEngineSync();
}
