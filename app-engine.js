/**
 * app-engine.js — Recovery Mode
 */

// 1. ABSOLUTE FORCE DEBUG (Runs first, no dependencies)
var debugDiv = document.createElement('div');
debugDiv.id = 'emergency-log';
debugDiv.style.cssText = 'position:fixed;top:0;left:0;width:100%;height:150px;background:red;color:white;z-index:1000000;overflow:auto;font-family:monospace;padding:10px;font-size:12px;display:block !important;';
debugDiv.innerHTML = '<b>ENGINE STATUS: SCRIPT DETECTED</b><br>';
document.body.appendChild(debugDiv);

function quickLog(m) {
    debugDiv.innerHTML += '<div>> ' + m + '</div>';
    console.log(m);
}

// 2. CORE DATA
var MASTER_DATA = [];

function runSync() {
    quickLog("Starting Fetch...");
    var t = "?v=" + Date.now();
    
    Promise.all([
        fetch('./unified-symbols.json' + t).then(function(r){ return r.json(); }),
        fetch('./fundamentals.json' + t).then(function(r){ return r.json(); }),
        fetch('./prices.json' + t).then(function(r){ return r.json(); })
    ]).then(function(res) {
        quickLog("Files loaded.");
        
        var symbols = res[0].symbols || res[0];
        var funds = res[1].stocks || res[1];
        var prices = res[2].quotes || res[2];

        MASTER_DATA = symbols.map(function(s) {
            var tk = s.ticker || s.symbol;
            var f = funds[tk] || {};
            var p = prices[tk] || {};
            return {
                sym: tk,
                name: s.name || tk,
                qty: s.qty || 0,
                avg: s.avg || 0,
                ltp: p.ltp || f.ltp || 0,
                category: s.type || s.category || 'portfolio'
            };
        });

        quickLog("Total Stocks: " + MASTER_DATA.length);
        
        if (typeof render === 'function') {
            render();
            quickLog("Table updated.");
        } else {
            quickLog("UI Error: render() missing.");
        }
        
        // Hide red box if successful after 5 seconds
        setTimeout(function(){ debugDiv.style.background = 'black'; }, 5000);

    }).catch(function(err) {
        quickLog("CRITICAL ERROR: " + err.message);
    });
}

// 3. START
runSync();
