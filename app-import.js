/* ================================
   IMPORT WORKFLOW (FULL FIXED)
================================ /

var importState = {
    stocks: []
};

/ ================================
   OPEN IMPORT UI (UNCHANGED)
================================ /
function openImportWorkflow() {
    document.getElementById('file-input').click();
}

/ ================================
   FILE INPUT HANDLER
================================ /
document.addEventListener("DOMContentLoaded", function () {

    var fileInput = document.getElementById("file-input");

    if (!fileInput) {
        fileInput = document.createElement("input");
        fileInput.type = "file";
        fileInput.id = "file-input";
        fileInput.style.display = "none";
        fileInput.onchange = function () {
            handleFile(fileInput.files[0]);
        };
        document.body.appendChild(fileInput);
    }
});

/ ================================
   HANDLE FILE
================================ /
function handleFile(file) {

    if (!file) return;

    var reader = new FileReader();

    reader.onload = function (e) {
        parseCSV(e.target.result);
    };

    reader.readAsText(file);
}

/ ================================
   PARSE CSV (UNCHANGED LOGIC)
================================ /
function parseCSV(csv) {

    var lines = csv.split("\n").filter(l => l.trim());
    var headers = lines[0].split(",");

    var nameIdx = headers.findIndex(h => /name/i.test(h));
    var qtyIdx = headers.findIndex(h => /qty/i.test(h));
    var avgIdx = headers.findIndex(h => /avg/i.test(h));

    importState.stocks = [];

    for (var i = 1; i < lines.length; i++) {

        var cols = lines[i].split(",");

        var name = (cols[nameIdx] || "").trim();
        var qty = parseFloat(cols[qtyIdx]) || 0;
        var avg = parseFloat(cols[avgIdx]) || 0;

        if (!name) continue;

        var ticker = generateSymbol(name);

        importState.stocks.push({
            ticker: ticker,
            name: name,
            qty: qty,
            avg: avg,
            type: "portfolio"
        });
    }

    alert("Parsed: " + importState.stocks.length + " stocks");

    saveToIndexedDB();
}

/ ================================
   SAVE TO DB (CRITICAL FIXED)
================================ /
function saveToIndexedDB() {

    if (!importState.stocks.length) {
        alert("No stocks to save");
        return;
    }

    var request = indexedDB.open('BharatEngineDB', 2);

    request.onupgradeneeded = function (e) {
        var db = e.target.result;

        if (!db.objectStoreNames.contains('UnifiedStocks')) {
            db.createObjectStore('UnifiedStocks', { keyPath: 'sym' });
        }
    };

    request.onsuccess = function (e) {

        var db = e.target.result;
        var tx = db.transaction('UnifiedStocks', 'readwrite');
        var store = tx.objectStore('UnifiedStocks');

        store.clear();

        importState.stocks.forEach(function (stock) {

            var ticker = stock.ticker || generateSymbol(stock.name);

            if (!ticker) return;

            var record = {
                sym: ticker,                          // ✅ FIXED
                ticker: ticker,
                name: stock.name,
                isin: stock.isin || "",
                sector: stock.sector || "",
                industry: stock.industry || "",
                type: (stock.type || "portfolio").toLowerCase(), // ✅ FIXED
                qty: stock.qty || 0,
                avg: stock.avg || 0,
                source: "import"
            };

            store.put(record);
        });

        tx.oncomplete = function () {
            alert("✅ Saved " + importState.stocks.length + " stocks");

            if (typeof loadDQA === "function") {
                loadDQA();   // auto refresh
            }
        };

        tx.onerror = function () {
            alert("❌ Save failed");
        };
    };
}

/ ================================
   SYMBOL GENERATOR (UNCHANGED)
================================ */
function generateSymbol(name) {
    return name
        .split(" ")
        .map(w => w[0])
        .join("")
        .toUpperCase()
        .slice(0, 10);
}
