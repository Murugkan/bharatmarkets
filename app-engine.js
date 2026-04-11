/**
 * app-engine.js — Final Core Data Engine
 */

// ── Configuration & State ─────────────────────────────────────
var DB_NAME       = 'BharatEngineDB';
var DB_VER        = 1;
var STORE_UNIFIED = 'UnifiedStocks';
var STORE_LEDGER  = 'ExclusionLedger';
var MASTER_DATA   = [];
var _engineLogs   = [];

// ── 1. Debug Window System ───────────────────────────────────
function engineLog(msg, level) {
    var ts = new Date().toLocaleTimeString('en-IN', { hour12: false });
    var lvl = level || 'info';
    var entry = '[' + ts + '] ' + msg;
    _engineLogs.push({ msg: entry, level: lvl });
    console.log('[Engine]', msg);

    var panel = document.getElementById('engine-debug-content');
    if (panel) {
        var colors = { info: '#8eb0d0', ok: '#00e896', warn: '#ffbf47', err: '#ff4d6d' };
        var div = document.createElement('div');
        div.style.cssText = 'color:' + (colors[lvl] || '#8eb0d0') + '; border-bottom:1px solid #1a1a1a; padding:4px 0;';
        div.textContent = entry;
        panel.appendChild(div);
        panel.scrollTop = panel.scrollHeight;
    }
}

function createDebugWindow() {
    if (document.getElementById('engine-debug-window')) return;
    var win = document.createElement('div');
    win.id = 'engine-debug-window';
    win.style.cssText = 'position:fixed;bottom:0;left:0;right:0;height:25vh;background:#0a0a0a;color:#eee;font-family:monospace;font-size:10px;z-index:10000;border-top:2px solid #333;display:flex;flex-direction:column;';
    win.innerHTML = `
        <div style="background:#222;padding:5px 10px;display:flex;justify-content:space-between;align-items:center;font-weight:bold;">
            <span>BHARAT ENGINE LOGS</span>
            <button onclick="this.parentElement.parentElement.remove()" style="background:#444;color:white;border:none;padding:2px 8px;border-radius:3px;">✕ Close</button>
        </div>
        <div id="engine-debug-content" style="flex:1;overflow-y:auto;padding:10px;"></div>
    `;
    document.body.appendChild(win);
}

// ── 2. Data Processing & Join Logic ──────────────────────────
function buildUnifiedRecords(uData, fData, pData) {
    // FIX: Fallback for varied JSON structures
    var symbols      = uData.symbols || (Array.isArray(uData) ? uData : []);
    var fundamentals = fData.stocks  || fData || {};
    var prices       = pData.quotes  || pData || {};

    engineLog('Files: Symbols(' + symbols.length + ') Fundamentals(' + Object.keys(fundamentals).length + ') Prices(' + Object.keys(prices).length + ')');

    // Filter and Resolve Tickers
    var resolved = symbols.filter(function(s) {
        var tk = s.ticker || s.symbol; 
        if (!tk || tk === '?' || tk === '') return false;
        if (/^SGB|GOLDBOND/i.test(tk)) return false;
        if (!s.ticker) s.ticker = tk; 
        return true;
    });

    var totalMV = 0;
    resolved.forEach(function(s) {
        var p = prices[s.ticker] || {};
        totalMV += (p.ltp || 0) * (s.qty || 0);
    });

    return resolved.map(function(s) {
        var f   = fundamentals[s.ticker] || {};
        var p   = prices[s.ticker]       || {};
        var ltp = p.ltp || f.ltp || 0;
        var qty = s.qty || 0;
        var avg = s.avg || 0;
        var cost = qty * avg;
        var mv   = qty * ltp;

        return {
            sym:        s.ticker,
            name:       s.name || f.name || s.ticker,
            qty:        qty,
            avg:        avg,
            ltp:        ltp,
            marketValue: mv,
            cost:       cost,
            pnl:        mv - cost,
            pnlPct:     cost > 0 ? ((mv - cost) / cost) * 100 : 0,
            weight:     totalMV > 0 ? (mv / totalMV) * 100 : 0,
            category:   s.type || s.category || 'portfolio',
            sector:     s.sector || f.sector || '',
            signal:     f.signal || '',
            pe:         f.pe || null
        };
    });
}

// ── 3. Main Orchestrator ─────────────────────────────────────
function runEngineSync() {
    createDebugWindow();
    engineLog('=== Sync Start ===', 'info');

    var db;
    var req = indexedDB.open(DB_NAME, DB_VER);
    
    req.onupgradeneeded = function(e) {
        var d = e.target.result;
        if (!d.objectStoreNames.contains(STORE_UNIFIED)) d.createObjectStore(STORE_UNIFIED, { keyPath: 'sym' });
    };

    req.onsuccess = function(e) {
        db = e.target.result;
        var t = '?t=' + Date.now();
        
        Promise.all([
            fetch('./unified-symbols.json' + t).then(r => r.json()),
            fetch('./fundamentals.json' + t).then(r => r.json()),
            fetch('./prices.json' + t).then(r => r.json())
        ]).then(function(res) {
            MASTER_DATA = buildUnifiedRecords(res[0], res[1], res[2]);
            
            // Update IndexedDB Cache
            var tx = db.transaction(STORE_UNIFIED, 'readwrite');
            var store = tx.objectStore(STORE_UNIFIED);
            store.clear().onsuccess = function() {
                MASTER_DATA.forEach(r => store.put(r));
            };

            tx.oncomplete = function() {
                engineLog('Sync Success: ' + MASTER_DATA.length + ' stocks', 'ok');
                // Trigger UI Render
                if (typeof render === 'function') render();
                window.dispatchEvent(new CustomEvent('engine-updated'));
            };
        }).catch(err => engineLog('Fetch Error: ' + err.message, 'err'));
    };
}

// Initial Run
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', runEngineSync);
} else {
    runEngineSync();
}
