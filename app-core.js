/**
 * ONYX SYSTEM v8 - PRODUCTION CORE ENGINE
 * Logic: Data Management, GitHub Sync, & Stock Resolution
 */

// 1. GLOBAL STATE & CONFIG
window.S = JSON.parse(localStorage.getItem('bm_settings')) || {
    settings: { ghToken: '', ghRepo: '', aiKey: '', _ghStatus: 'dim' }
};

window.DB = {
    symbols: [],      // symbols.json
    fundamentals: {}, // fundamentals.json
    prices: {},       // prices.json
    guidance: {}      // guidance.json
};

// 2. INITIALIZATION & SCHEMA MIGRATION
const Core = {
    async init() {
        this.log("Initializing Onyx Core v8...");
        await this.loadLocal();
        this.migrateSchema();
        this.updateStatusDots();
    },

    loadLocal() {
        const cachedSymbols = localStorage.getItem('bm_symbols');
        if (cachedSymbols) DB.symbols = JSON.parse(cachedSymbols);
        // Load other modules if available in localStorage
    },

    migrateSchema() {
        let changed = false;
        DB.symbols = DB.symbols.map(s => {
            if (s.source && Array.isArray(s.source)) {
                s.category = s.source[0] || 'portfolio';
                delete s.source;
                changed = true;
            }
            if (s.resolved === undefined) { s.resolved = true; changed = true; }
            return s;
        });
        if (changed) {
            this.log("Schema migration complete: source[] -> category");
            this.savePF();
        }
    },

    savePF() {
        localStorage.setItem('bm_symbols', JSON.stringify(DB.symbols));
    },

    saveSettings() {
        localStorage.setItem('bm_settings', JSON.stringify(S));
    },

    // 3. GITHUB API OPERATIONS (Production Pattern)
    async ghPut(path, content, message) {
        const { ghToken, ghRepo } = S.settings;
        if (!ghToken || !ghRepo) return this.log("❌ Error: Missing PAT/Repo", "red");

        const url = `https://api.github.com/repos/${ghRepo}/contents/${path}`;
        const headers = {
            'Authorization': `token ${ghToken}`,
            'Accept': 'application/vnd.github.v3+json'
        };

        try {
            let sha = null;
            const res = await fetch(url, { headers });
            if (res.ok) {
                const data = await res.json();
                sha = data.sha;
            }

            const body = {
                message: message || `Update ${path}`,
                content: btoa(unescape(encodeURIComponent(content))),
                sha: sha
            };

            const putRes = await fetch(url, {
                method: 'PUT',
                headers,
                body: JSON.stringify(body)
            });

            if (putRes.ok) {
                this.log(`✅ GitHub Sync: ${path} updated`, "green");
                return true;
            }
        } catch (e) {
            this.log(`❌ GitHub Error: ${e.message}`, "red");
        }
        return false;
    },

    async ghFetchRaw(path) {
        const { ghToken, ghRepo } = S.settings;
        const url = `https://raw.githubusercontent.com/${ghRepo}/main/${path}?t=${Date.now()}`;
        const res = await fetch(url, {
            headers: { 'Authorization': `token ${ghToken}` },
            cache: 'no-store'
        });
        return res.ok ? await res.json() : null;
    },

    // 4. RESOLUTION PIPELINE (Yahoo + NSE)
    async resolveStock(name) {
        this.log(`⏳ Resolving: ${name}...`);
        
        // Step 1: Yahoo Finance Search
        try {
            const yUrl = `https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(name)}&region=IN`;
            const yRes = await fetch(yUrl);
            const yData = await yRes.json();
            
            const match = yData.quotes?.find(q => q.symbol.endsWith('.NS'));
            if (match) {
                this.log(`✅ Found Yahoo: ${match.symbol}`, "green");
                return { sym: match.symbol.replace('.NS', ''), source: 'yahoo' };
            }
        } catch (e) { console.error("Yahoo failed", e); }

        // Step 2: NSE Fallback
        try {
            const nUrl = `https://www.nseindia.com/api/suggest?q=${encodeURIComponent(name)}`;
            const nRes = await fetch(nUrl);
            const nData = await nRes.json();
            if (nData && nData.length > 0) {
                this.log(`✅ Found NSE: ${nData[0].symbol}`, "green");
                return { sym: nData[0].symbol, source: 'nse' };
            }
        } catch (e) { console.error("NSE failed", e); }

        this.log(`❌ Unresolved: ${name}`, "red");
        return null;
    },

    // 5. UTILS & UI BRIDGES
    updateStatusDots() {
        const setDot = (id, val) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.className = 'dot ' + (val ? 'dot-ok' : 'dot-off');
        };
        setDot('dot-token', S.settings.ghToken);
        setDot('dot-repo', S.settings.ghRepo);
        setDot('dot-ai', S.settings.aiKey);
    },

    log(msg, colorClass = "") {
        const term = document.getElementById('log-terminal');
        if (!term) return;
        const time = new Date().toLocaleTimeString([], { hour12: false });
        const entry = document.createElement('div');
        entry.style.marginBottom = "4px";
        if (colorClass === "green") entry.style.color = "var(--gr)";
        if (colorClass === "red") entry.style.color = "var(--rd)";
        entry.innerHTML = `[${time}] ${msg}`;
        term.appendChild(entry);
        term.scrollTop = term.scrollHeight;
    },

    toast(msg) {
        alert(msg); // Replace with UI toast if available
    }
};

// Initialize on Load
window.onload = () => Core.init();
