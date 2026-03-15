// BharatMarkets Price Updater for Scriptable  v2.1
// ─────────────────────────────────────────────────
// Setup:
//   1. Put this file AND index.html in iCloud Drive / Scriptable /
//   2. Run from the Scriptable app
//   3. After it finishes, re-upload index.html to GitHub Pages
// ─────────────────────────────────────────────────

const HTML_FILE  = "index.html";
const TIMEOUT    = 8;    // seconds per request
const BATCH_SIZE = 10;   // parallel requests per batch
const BATCH_DELAY_MS = 300; // ms between batches

// ── Yahoo Finance symbol overrides ───────────────
// Standard format is SYMBOL.NS — add overrides only for
// stocks that Yahoo lists under a different ticker.
const OVERRIDES = {
  // Hyphens & special chars
  "MCDOWELL-N":    "MCDOWELL-N.NS",
  "BAJAJ_AUTO":    "BAJAJ-AUTO.NS",
  "M_M":           "M&M.NS",
  // Stocks that fail with standard .NS suffix → try these
  "BBOX":          "BLACKBOX.NS",
  "MAPMYINDIA":    "MAPMYINDIA.NS",
  "BLACKBUCK":     "BLACKBUCK.NS",
  "ROSSELLTECH":   "ROSSELLTECH.NS",
  "SHREEREFRI":    "SHREEREFRI.NS",
  "QUALPOWER":     "QUALPOWER.NS",
  "TRUALT":        "TRUALT.NS",
  "TITANBIOTE":    "TITANBIOTE.NS",
  "SANDUMA":       "SANDUMA.NS",
  "CAPNUM":        "CAPNUM.NS",
  "AZADINDIA":     "AZADINDIA.NS",
  "REVATHI":       "REVATHI.NS",
  "INTERARCH":     "INTERARCH.NS",
  "VIKRAMSOLAR":   "VIKRAMSOLAR.NS",
  "KPENERGI":      "KPENERGI.NS",
  "KWALYPH":       "KWALYPH.NS",
  "MBENGINEERING": "MBENGINEERING.NS",
  "HIGHENERGYB":   "HIGHENERGYB.NS",
  "HINDRECTIF":    "HINDRECTIF.NS",
  "GRAUERWEIL":    "GRAUERWEIL.NS",
  "SKMEPEX":       "SKMEPEX.NS",
  "VENTIVE":       "VENTIVE.NS",
  "SAGILITY":      "SAGILITY.NS",
  "IDEAFORGE":     "IDEAFORGE.NS",
};

// ── UI helpers ────────────────────────────────────
const table = new UITable();
table.showSeparators = true;

function clearTable() {
  table.removeAllRows();
}

function addRow(title, subtitle, color) {
  const row = new UITableRow();
  row.height = subtitle ? 56 : 40;
  const cell = row.addText(title, subtitle || "");
  cell.titleFont = Font.mediumSystemFont(13);
  cell.subtitleFont = Font.systemFont(11);
  if (color) cell.titleColor = color;
  table.addRow(row);
}

function addHeader(text) {
  const row = new UITableRow();
  row.isHeader = true;
  row.height = 44;
  const cell = row.addText(text);
  cell.titleFont = Font.boldSystemFont(14);
  table.addRow(row);
}

function refreshUI() {
  if (!config.runsInApp) return;
  table.reload();
}

function sleep(ms) {
  return new Promise(resolve => {
    const t = new Timer();
    t.timeInterval = ms / 1000;
    t.schedule(() => resolve());
  });
}

// ── Read file ─────────────────────────────────────
const fm = FileManager.iCloud();
const dir = fm.documentsDirectory();
const filePath = fm.joinPath(dir, HTML_FILE);

clearTable();
addHeader("BharatMarkets Price Updater");
addRow("Checking file…", "", Color.gray());
if (config.runsInApp) table.present(false);

if (!fm.fileExists(filePath)) {
  clearTable();
  addHeader("File Not Found");
  addRow(HTML_FILE + " not found",
         "Put index.html in iCloud Drive / Scriptable /", Color.red());
  refreshUI();
  Script.complete();
}

if (!fm.isFileDownloaded(filePath)) {
  clearTable();
  addHeader("Downloading from iCloud…");
  addRow("Please wait", "", Color.orange());
  refreshUI();
  await fm.downloadFileFromiCloud(filePath);
}

let html = fm.readString(filePath);

// ── Extract symbols from STOCKS_SLIM ─────────────
const slimStartIdx = html.indexOf("const STOCKS_SLIM=[");
const slimEndIdx   = html.indexOf("const STOCKS=expandStocks", slimStartIdx);

if (slimStartIdx < 0 || slimEndIdx < 0) {
  clearTable();
  addHeader("Wrong File");
  addRow("Cannot find STOCKS_SLIM",
         "Is this the BharatMarkets index.html?", Color.red());
  refreshUI();
  Script.complete();
}

const slimBlock = html.slice(slimStartIdx, slimEndIdx);
const symRegex  = /symbol:"([^"]+)"/g;
const symbols   = [];
const seen      = new Set();
let m;
while ((m = symRegex.exec(slimBlock)) !== null) {
  if (!seen.has(m[1])) { seen.add(m[1]); symbols.push(m[1]); }
}

clearTable();
addHeader("Fetching " + symbols.length + " NSE Stocks");
addRow("Starting…", new Date().toLocaleTimeString(), Color.gray());
refreshUI();

// ── Fetch one price from Yahoo Finance ───────────
async function fetchPrice(sym) {
  const yahooSym = OVERRIDES[sym] || (sym + ".NS");
  const url = "https://query1.finance.yahoo.com/v8/finance/chart/"
            + encodeURIComponent(yahooSym)
            + "?interval=1d&range=1d";
  try {
    const req = new Request(url);
    req.timeoutInterval = TIMEOUT;
    req.headers = {
      "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
      "Accept":     "application/json"
    };
    const data = await req.loadJSON();
    const meta = data?.chart?.result?.[0]?.meta;
    const ltp  = (meta?.regularMarketPrice || meta?.previousClose) || 0;
    const prev = (meta?.previousClose || meta?.chartPreviousClose) || ltp;
    if (ltp > 0 && ltp < 10000000) {
      const chg = prev > 0
        ? Math.round((ltp - prev) / prev * 10000) / 100
        : 0;
      return {
        ltp:    Math.round(ltp  * 100) / 100,
        prev:   Math.round(prev * 100) / 100,
        change: chg,
        sym
      };
    }
  } catch(e) {}
  return null;
}

// ── Fetch all in parallel batches ────────────────
let updated = 0;
let errors  = 0;
const prices = {};

for (let b = 0; b < symbols.length; b += BATCH_SIZE) {
  const batch   = symbols.slice(b, b + BATCH_SIZE);
  const results = await Promise.all(batch.map(s => fetchPrice(s)));

  results.forEach((res, j) => {
    if (res) {
      prices[res.sym] = res;
      updated++;
    } else {
      errors++;
    }
  });

  const done    = Math.min(b + BATCH_SIZE, symbols.length);
  const lastRes = results.filter(Boolean).pop();

  clearTable();
  addHeader("Fetching " + done + " / " + symbols.length);
  if (lastRes) {
    addRow(
      lastRes.sym + "  ₹" + lastRes.ltp.toFixed(2),
      (lastRes.change >= 0 ? "+" : "") + lastRes.change.toFixed(2) + "%  ·  " + updated + " updated",
      lastRes.change >= 0 ? Color.green() : Color.red()
    );
  }
  addRow(
    "Progress: " + Math.round(done / symbols.length * 100) + "%",
    (symbols.length - done) + " remaining · " + errors + " failed so far",
    Color.gray()
  );
  refreshUI();

  if (b + BATCH_SIZE < symbols.length) await sleep(BATCH_DELAY_MS);
}

// ── Patch STOCKS_SLIM in the HTML ─────────────────
// Finds each stock entry by symbol and replaces ltp/prev/change in-place.
// Uses brace-depth counting from the symbol position to isolate the entry.

let newSlim = slimBlock;

for (const sym of Object.keys(prices)) {
  const p      = prices[sym];
  const symPat = 'symbol:"' + sym + '"';
  const symPos = newSlim.indexOf(symPat);
  if (symPos < 0) continue;

  // Walk backward to find the opening { of this entry
  let entryStart = symPos;
  for (let k = symPos; k >= Math.max(0, symPos - 5); k--) {
    if (newSlim[k] === "{") { entryStart = k; break; }
  }

  // Walk forward using brace depth to find the closing }
  let depth  = 0;
  let endPos = symPos;
  for (let k = entryStart; k < Math.min(entryStart + 3000, newSlim.length); k++) {
    if      (newSlim[k] === "{") depth++;
    else if (newSlim[k] === "}") {
      depth--;
      if (depth === 0) { endPos = k + 1; break; }
    }
  }

  // Extract and patch the entry
  let entry = newSlim.slice(entryStart, endPos);
  entry = entry.replace(/(,ltp:)([-\d.]+)/,    "$1" + p.ltp);
  entry = entry.replace(/(,prev:)([-\d.]+)/,   "$1" + p.prev);
  entry = entry.replace(/(,change:)([-\d.]+)/, "$1" + p.change);

  newSlim = newSlim.slice(0, entryStart) + entry + newSlim.slice(endPos);
}

// ── Stamp update time & write file ───────────────
const ts = new Date().toLocaleString("en-IN", {
  day:    "2-digit", month: "short", year: "numeric",
  hour:   "2-digit", minute: "2-digit", hour12: true
});
const tsComment = "/* PRICES_UPDATED: " + ts + " */";

let newHtml = html.replace(/\/\* PRICES_UPDATED:[^*]*\*\/\n?/g, "");
newHtml = newHtml.replace("const STOCKS_SLIM=[", tsComment + "\nconst STOCKS_SLIM=[");
newHtml = newHtml.replace(slimBlock, newSlim);

fm.writeString(filePath, newHtml);

// ── Done ──────────────────────────────────────────
clearTable();
addHeader("✅ Done!");
addRow(
  updated + " stocks updated",
  ts,
  Color.green()
);
if (errors > 0) {
  addRow(
    errors + " failed (kept old prices)",
    "Small/unlisted stocks not on Yahoo Finance",
    Color.orange()
  );
}
addRow(
  "⚠️ Next step",
  "Upload index.html to GitHub Pages to go live",
  Color.blue()
);
refreshUI();

Script.complete();
