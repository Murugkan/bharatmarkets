/**
 * app-engine.js — Emergency Recovery Version
 */

// 1. Force the Debug Window to appear IMMEDIATELY
(function createImmediateDebug() {
    var win = document.createElement('div');
    win.id = 'engine-debug-window';
    win.style.cssText = 'position:fixed; bottom:0; left:0; right:0; height:30vh; background:#000; color:#0f0; z-index:999999; border-top:2px solid #0f0; font-family:monospace; padding:10px; overflow-y:auto; font-size:12px;';
    win.innerHTML = '<b>--- ENGINE LOGS ---</b><div id="debug-inner"></div>';
    document.body.appendChild(win);
})();

function log(m) {
    console.log(m);
    var target = document.getElementById('debug-inner');
    if(target) target.innerHTML += '<div>' + m + '</div>';
}

log("Script loaded successfully.");

// 2. Global State
var MASTER_DATA = [];

// 3. The Core Logic
async function runEngineSync() {
    log("Starting Sync...");
    try {
        const t = "?v=" + Date.now();
        log("Fetching files...");
        
        const [uRes, fRes, pRes] = await Promise.all([
            fetch('./unified-symbols.json' + t).then(r => r.json()),
            fetch('./fundamentals.json' + t).then(r => r.json()),
            fetch('./prices.json' + t).then(r => r.json())
        ]);

        log("Files received. Processing...");

        const symbols = uRes.symbols || uRes;
        const fundamentals = fRes.stocks || fRes;
        const prices = pRes.quotes || pRes;

        MASTER_DATA = symbols.map(s => {
            const tk = s.ticker || s.symbol;
            const f = fundamentals[tk] || {};
            const p = prices[tk] || {};
            return {
                sym: tk,
                name: s.name || tk,
                qty: s.qty || 0,
                avg: s.avg || 0,
                ltp: p.ltp || f.ltp || 0,
                category: s.type || s.category || 'portfolio'
            };
        });

        log("Sync Complete: " + MASTER_DATA.length + " stocks.");
        
        // Trigger the table update
        if (typeof render === 'function') {
            render();
            log("UI Render triggered.");
        } else {
            log("Warning: render() function not found in other scripts.");
        }

    } catch (e) {
        log("CRITICAL ERROR: " + e.message);
    }
}

// Start
runEngineSync();
