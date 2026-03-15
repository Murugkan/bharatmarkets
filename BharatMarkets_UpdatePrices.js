// BharatMarkets Price Updater for Scriptable
// Setup: put this file and index.html in iCloud Drive / Scriptable /
// Run from Scriptable app - fetches NSE prices and updates index.html

const HTML_FILE = "index.html";
const DELAY_MS = 350;
const TIMEOUT = 10;

const OVERRIDES = {
  "MCDOWELL-N": "MCDOWELL-N.NS",
  "BAJAJ_AUTO": "BAJAJ-AUTO.NS",
  "M_M": "M&M.NS",
};

// UI
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

function sleep(ms) {
  return new Promise(resolve => {
    let t = new Timer();
    t.timeInterval = ms / 1000;
    t.schedule(() => resolve());
  });
}

// Read file
const fm = FileManager.iCloud();
const dir = fm.documentsDirectory();
const filePath = fm.joinPath(dir, HTML_FILE);

clearTable();
addHeader("BharatMarkets Price Updater");

if (!fm.fileExists(filePath)) {
  clearTable();
  addHeader("File Not Found");
  addRow(HTML_FILE + " not found", "Put index.html in iCloud Drive / Scriptable /", Color.red());
  if (config.runsInApp) await table.present();
  Script.complete();
}

if (!fm.isFileDownloaded(filePath)) {
  addRow("Downloading from iCloud...", "", Color.orange());
  if (config.runsInApp) table.present(false);
  await fm.downloadFileFromiCloud(filePath);
}

let html = fm.readString(filePath);

// Extract symbols
const slimStartIdx = html.indexOf("const STOCKS_SLIM=[");
const slimEndIdx = html.indexOf("const STOCKS=expandStocks", slimStartIdx);
if (slimStartIdx < 0 || slimEndIdx < 0) {
  clearTable();
  addHeader("Wrong File");
  addRow("Could not find STOCKS_SLIM", "Is this the BharatMarkets index.html?", Color.red());
  if (config.runsInApp) await table.present();
  Script.complete();
}

const slimBlock = html.slice(slimStartIdx, slimEndIdx);
const symRegex = /symbol:"([^"]+)"/g;
const symbols = [];
const seen = new Set();
let m;
while ((m = symRegex.exec(slimBlock)) !== null) {
  if (!seen.has(m[1])) { seen.add(m[1]); symbols.push(m[1]); }
}

clearTable();
addHeader("Fetching " + symbols.length + " NSE Stocks");
addRow("Starting...", new Date().toLocaleTimeString(), Color.gray());
if (config.runsInApp) table.present(false);

// Fetch prices
let updated = 0;
let errors = 0;
const prices = {};

for (let i = 0; i < symbols.length; i++) {
  const sym = symbols[i];
  const yahooSym = OVERRIDES[sym] || (sym + ".NS");
  const url = "https://query1.finance.yahoo.com/v8/finance/chart/" + encodeURIComponent(yahooSym) + "?interval=1d&range=1d";

  try {
    const req = new Request(url);
    req.timeoutInterval = TIMEOUT;
    req.headers = {
      "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
      "Accept": "application/json"
    };

    const data = await req.loadJSON();
    const result = data && data.chart && data.chart.result && data.chart.result[0];
    const meta = result && result.meta;
    const ltp = (meta && (meta.regularMarketPrice || meta.previousClose)) || 0;
    const prev = (meta && (meta.previousClose || meta.chartPreviousClose)) || ltp;

    if (ltp > 0) {
      const chg = prev > 0 ? Math.round((ltp - prev) / prev * 10000) / 100 : 0;
      prices[sym] = {
        ltp: Math.round(ltp * 100) / 100,
        prev: Math.round(prev * 100) / 100,
        change: chg
      };
      updated++;
      const arrow = chg >= 0 ? "+" : "";
      clearTable();
      addHeader("Fetching " + (i + 1) + "/" + symbols.length);
      addRow(sym + "  Rs." + ltp.toFixed(2), arrow + chg.toFixed(2) + "%  |  " + updated + " updated", chg >= 0 ? Color.green() : Color.red());
      addRow("Progress: " + Math.round((i + 1) / symbols.length * 100) + "%", (symbols.length - i - 1) + " remaining", Color.gray());
      if (config.runsInApp) table.present(false);
    } else {
      errors++;
    }
  } catch (e) {
    errors++;
  }

  if (i < symbols.length - 1) {
    await sleep(DELAY_MS);
  }
}

// Update HTML
let newSlim = slimBlock;

for (const sym of Object.keys(prices)) {
  const p = prices[sym];
  const symPat = 'symbol:"' + sym + '"';
  const symPos = newSlim.indexOf(symPat);
  if (symPos < 0) continue;

  let depth = 0;
  let endPos = symPos;
  for (let k = symPos; k < Math.min(symPos + 2000, newSlim.length); k++) {
    if (newSlim[k] === "{") depth++;
    else if (newSlim[k] === "}") {
      depth--;
      if (depth < 0) { endPos = k; break; }
    }
  }

  let entry = newSlim.slice(symPos, endPos);
  entry = entry.replace(/(ltp:)([-\d.]+)/, "$1" + p.ltp);
  entry = entry.replace(/(prev:)([-\d.]+)/, "$1" + p.prev);
  entry = entry.replace(/(change:)([-\d.]+)/, "$1" + p.change);
  newSlim = newSlim.slice(0, symPos) + entry + newSlim.slice(endPos);
}

const ts = new Date().toLocaleString("en-IN", {
  day: "2-digit", month: "short", year: "numeric",
  hour: "2-digit", minute: "2-digit", hour12: true
});
const tsComment = "/* PRICES_UPDATED: " + ts + " */";
let newHtml = html.replace(/\/\* PRICES_UPDATED:[^*]*\*\/\n?/g, "");
newHtml = newHtml.replace("const STOCKS_SLIM=[", tsComment + "\nconst STOCKS_SLIM=[");
newHtml = newHtml.replace(slimBlock, newSlim);

fm.writeString(filePath, newHtml);

// Done
clearTable();
addHeader("Done!");
addRow(updated + " stocks updated", ts, Color.green());
if (errors > 0) addRow(errors + " failed", "These keep previous prices", Color.orange());
addRow("Next step", "Open index.html from Files app in Safari", Color.blue());
if (config.runsInApp) await table.present();

Script.complete();
