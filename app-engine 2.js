/**
 * app-engine.js — Core Data Engine
 *
 * Architecture:
 *   unified-symbols.json  →  master stock dictionary (sym, name, isin, sector, category, qty, avg)
 *   fundamentals.json     →  financial data keyed by sym
 *   prices.json           →  live price data keyed by sym
 *       ↓
 *   Engine joins all three → IndexedDB (UnifiedStocks)
 *       ↓
 *   MASTER_DATA → UI
 */

// ── Database Configuration ──────────────────────────────────
var DB_NAME  = 'BharatEngineDB';
var DB_VER   = 1;
var STORE_UNIFIED = 'UnifiedStocks';
var STORE_LEDGER  = 'ExclusionLedger';

// ── Global in-memory store (hydrated from IndexedDB after sync) ──
var MASTER_DATA = [];

// ── 1. Open IndexedDB ───────────────────────────────────────
function initEngineDB() {
    return new Promise(function(resolve, reject) {
        var req = indexedDB.open(DB_NAME, DB_VER);

        req.onupgradeneeded = function(e) {
            var db = e.target.result;
            if (!db.objectStoreNames.contains(STORE_UNIFIED))
                db.createObjectStore(STORE_UNIFIED, { keyPath: 'sym' });
            if (!db.objectStoreNames.contains(STORE_LEDGER))
                db.createObjectStore(STORE_LEDGER, { keyPath: 'sym' });
        };

        req.onsuccess  = function(e) { resolve(e.target.result); };
        req.onerror    = function(e) { reject(e.target.error); };
    });
}

// ── 2. Fetch all three source files ─────────────────────────
function fetchSourceFiles() {
    return Promise.all([
        fetch('./unified-symbols.json').then(function(r) {
            if (!r.ok) throw new Error('unified-symbols.json not found (' + r.status + ')');
            return r.json();
        }),
        fetch('./fundamentals.json').then(function(r) {
            if (!r.ok) throw new Error('fundamentals.json not found (' + r.status + ')');
            return r.json();
        }),
        fetch('./prices.json').then(function(r) {
            if (!r.ok) throw new Error('prices.json not found (' + r.status + ')');
            return r.json();
        })
    ]);
}

// ── 3. Join data + compute fields ───────────────────────────
function buildUnifiedRecords(symbols, fData, pData) {
    var fundamentals = fData.stocks  || {};
    var prices       = pData.quotes  || {};

    // Compute total market value for weight calculation
    var totalMV = 0;
    symbols.forEach(function(s) {
        var p = prices[s.sym] || {};
        totalMV += (p.ltp || 0) * (s.qty || 0);
    });

    return symbols.map(function(s) {
        var f   = fundamentals[s.sym] || {};
        var p   = prices[s.sym]       || {};

        var ltp         = p.ltp   || f.ltp   || 0;
        var qty         = s.qty   || 0;
        var avg         = s.avg   || 0;
        var cost        = qty * avg;
        var marketValue = qty * ltp;
        var pnl         = marketValue - cost;
        var pnlPct      = cost > 0 ? (pnl / cost) * 100 : 0;
        var weight      = totalMV > 0 ? (marketValue / totalMV) * 100 : 0;
        var athDist     = (f.ath || p.w52h || 0) > 0
                            ? (((f.ath || p.w52h) - ltp) / (f.ath || p.w52h)) * 100
                            : 0;

        return {
            // ── Identity (from unified-symbols.json) ──
            sym:        s.sym,
            name:       s.name       || f.name  || '',
            isin:       s.isin       || '',
            sector:     s.sector     || f.sector || '',
            category:   s.category   || 'portfolio',
            resolved:   s.resolved   || false,

            // ── Position (from unified-symbols.json) ──
            qty:        qty,
            avg:        avg,

            // ── Fundamentals (from fundamentals.json) ──
            pe:         f.pe         || null,
            fwd_pe:     f.fwd_pe     || null,
            pb:         f.pb         || null,
            eps:        f.eps        || null,
            roe:        f.roe        || null,
            roce:       f.roce       || null,
            opm_pct:    f.opm_pct    || null,
            npm_pct:    f.npm_pct    || null,
            gpm_pct:    f.gpm_pct    || null,
            mcap:       f.mcap       || null,
            sales:      f.sales      || null,
            ebitda:     f.ebitda     || null,
            cfo:        f.cfo        || null,
            debt_eq:    f.debt_eq    || null,
            div_yield:  f.div_yield  || null,
            beta:       f.beta       || null,
            bv:         f.bv         || null,
            prom_pct:   f.prom_pct   || null,
            fii_pct:    f.fii_pct    || null,
            dii_pct:    f.dii_pct    || null,
            public_pct: f.public_pct || null,
            w52h:       f.w52h       || p.w52h  || null,
            w52l:       f.w52l       || p.w52l  || null,
            w52_pct:    f.w52_pct    || null,
            ath:        f.ath        || null,
            ath_pct:    f.ath_pct    || null,
            signal:     f.signal     || '',
            pos:        f.pos        || 0,
            neg:        f.neg        || 0,
            quarterly:  f.quarterly  || [],
            chg5d:      f.chg5d      || null,

            // ── Prices (from prices.json) ──
            ltp:        ltp,
            prev:       p.prev       || f.prev   || 0,
            change:     p.change     || 0,
            chg1d:      p.changePct  || f.chg1d  || 0,
            open:       p.open       || 0,
            high:       p.high       || 0,
            low:        p.low        || 0,
            vol:        p.vol        || 0,

            // ── Computed by engine ──
            cost:        cost,
            marketValue: marketValue,
            pnl:         pnl,
            pnlPct:      pnlPct,
            weight:      weight,
            athDist:     athDist,
        };
    });
}

// ── 4. Write records to IndexedDB ───────────────────────────
function writeToIndexedDB(db, records) {
    return new Promise(function(resolve, reject) {
        var tx    = db.transaction(STORE_UNIFIED, 'readwrite');
        var store = tx.objectStore(STORE_UNIFIED);

        // Clear existing data first — ensures deleted symbols are removed
        store.clear();

        records.forEach(function(record) {
            store.put(record);
        });

        tx.oncomplete = function() { resolve(); };
        tx.onerror    = function() { reject(tx.error); };
    });
}

// ── 5. Hydrate MASTER_DATA from IndexedDB ───────────────────
function hydrateMasterData(db) {
    return new Promise(function(resolve, reject) {
        var tx  = db.transaction(STORE_UNIFIED, 'readonly');
        var req = tx.objectStore(STORE_UNIFIED).getAll();
        req.onsuccess = function(e) {
            MASTER_DATA = e.target.result || [];
            resolve(MASTER_DATA);
        };
        req.onerror = function(e) { reject(e.target.error); };
    });
}

// ── 6. Main Sync Orchestrator ────────────────────────────────
function runEngineSync() {
    var db;

    return initEngineDB()
        .then(function(openedDB) {
            db = openedDB;
            if (typeof showToast === 'function') showToast('Engine syncing...');
            console.log('[Engine] Fetching source files...');
            return fetchSourceFiles();
        })
        .then(function(results) {
            var symbols = results[0];
            var fData   = results[1];
            var pData   = results[2];

            // unified-symbols.json must be an array
            if (!Array.isArray(symbols)) {
                throw new Error('unified-symbols.json must be a JSON array');
            }

            console.log('[Engine] Building unified records for', symbols.length, 'symbols...');
            var records = buildUnifiedRecords(symbols, fData, pData);
            return writeToIndexedDB(db, records);
        })
        .then(function() {
            console.log('[Engine] IndexedDB written. Hydrating MASTER_DATA...');
            return hydrateMasterData(db);
        })
        .then(function(data) {
            console.log('[Engine] Sync complete —', data.length, 'stocks in memory.');
            if (typeof showToast === 'function') showToast('Engine synced ✓');

            // Notify UI
            if (typeof render === 'function') {
                render();
            } else {
                window.dispatchEvent(new CustomEvent('engine-updated'));
            }
        })
        .catch(function(err) {
            console.error('[Engine] Sync failed:', err.message);
            if (typeof showToast === 'function') showToast('Sync failed: ' + err.message);
        });
}

// ── 7. Read MASTER_DATA from IndexedDB (no re-fetch) ────────
// Call this after a local DB update without needing to re-fetch files
function rehydrateFromDB() {
    return initEngineDB()
        .then(function(db) {
            return hydrateMasterData(db);
        })
        .then(function(data) {
            MASTER_DATA = data;
            if (typeof render === 'function') render();
            return data;
        });
}

// ── 8. Filter helpers for UI ────────────────────────────────
function getPortfolioStocks() {
    return MASTER_DATA.filter(function(s) { return s.category === 'portfolio'; });
}

function getWatchlistStocks() {
    return MASTER_DATA.filter(function(s) { return s.category === 'watchlist'; });
}
