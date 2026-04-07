/**
 * ONYX CORE ENGINE v8
 * Standardization: Modular Logic & GitHub Bridge
 * Purpose: Handle Data Ingestion, DQA, and Cloud Sync for iPhone Deployment
 */

// 1. GLOBAL STATE & CONFIG
window.S = {
    portfolio: JSON.parse(localStorage.getItem('portfolio') || '[]'),
    config: {
        token: localStorage.getItem('gh_token'),
        owner: localStorage.getItem('gh_owner') || "YOUR_GITHUB_USERNAME",
        repo: localStorage.getItem('gh_repo') || "YOUR_REPO_NAME",
        path: "symbols.json"
    }
};

const Core = {
    init() {
        this.updateStatusDots();
        console.log("Core Engine Initialized");
    },

    // 2. AUTHENTICATION CHECKS
    updateStatusDots() {
        const dotToken = document.getElementById('dot-token');
        const dotRepo = document.getElementById('dot-repo');
        
        if (dotToken) dotToken.className = S.config.token ? 'dot dot-on' : 'dot dot-off';
        if (dotRepo) dotRepo.className = S.config.repo ? 'dot dot-on' : 'dot dot-off';
    },

    // 3. THE "SMART-SPLIT" PARSER (Fixes "Resolution Failed")
    parseInput(text) {
        const lines = text.trim().split('\n');
        let newStocks = [];

        lines.forEach(line => {
            // Standardized Regex: Split by one or more spaces, tabs, or commas
            const parts = line.split(/[\s,]+/).filter(p => p.trim().length > 0);
            
            if (parts.length >= 3) {
                const name = parts[0].toUpperCase();
                const qty = parseFloat(parts[1]);
                const avg = parseFloat(parts[2]);

                if (!isNaN(qty) && !isNaN(avg)) {
                    newStocks.push({ symbol: name, qty: qty, avg: avg });
                }
            }
        });
        return newStocks;
    },

    // 4. FILE INGESTION (Fixes "Reading..." Hang)
    processFile(input) {
        const file = input.files[0];
        if (!file) return;

        UI.log(`Accessing ${file.name}...`);
        const reader = new FileReader();
        
        reader.onload = (e) => {
            try {
                const data = new Uint8Array(e.target.result);
                const wb = XLSX.read(data, { type: 'array' });
                const rows = XLSX.utils.sheet_to_json(wb.Sheets[wb.SheetNames[0]], { header: 1 });

                let count = 0;
                rows.forEach(r => {
                    // Logic: Extract Col 0 (Name), Col 1 (Qty), Col 2 (Avg)
                    if (r.length >= 3 && typeof r[1] === 'number') {
                        S.portfolio.push({ symbol: r[0], qty: r[1], avg: r[2] });
                        count++;
                    }
                });
                this.commit(count);
            } catch (err) {
                UI.log("READ ERROR: Check file format.");
            }
        };
        reader.readAsArrayBuffer(file);
    },

    // 5. THE NEXUS BRIDGE (GitHub Cloud Sync)
    async syncToCloud() {
        if (!S.config.token) { UI.log("ERR: Missing Token"); return; }
        UI.log("Pushing update to GitHub...");

        try {
            const url = `https://api.github.com/repos/${S.config.owner}/${S.config.repo}/contents/${S.config.path}`;
            const ref = await fetch(url, { headers: { 'Authorization': `token ${S.config.token}` } });
            const fileData = await ref.json();

            // Logic: Migrate current local state to symbols.json
            const content = btoa(unescape(encodeURIComponent(JSON.stringify(S.portfolio))));
            
            const push = await fetch(url, {
                method: 'PUT',
                headers: { 'Authorization': `token ${S.config.token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: "Nexus Update via iPhone",
                    content: content,
                    sha: fileData.sha
                })
            });

            if (push.ok) UI.log("CLOUD SYNC COMPLETE ✅");
            else UI.log("SYNC FAILED ❌");
        } catch (e) {
            UI.log("SYNC ERROR: Network or Config issue.");
        }
    },

    commit(count) {
        localStorage.setItem('portfolio', JSON.stringify(S.portfolio));
        UI.refreshCache();
        UI.log(`SUCCESS: ${count} stocks committed.`);
        this.syncToCloud();
    },

    wipeDB() {
        if (confirm("Permanently wipe local portfolio?")) {
            localStorage.removeItem('portfolio');
            S.portfolio = [];
            UI.refreshCache();
            UI.log("DATABASE WIPED");
        }
    }
};

// 6. UI COMPONENT CONTROLLER
const UI = {
    refreshCache() {
        const el = document.getElementById('cache-count');
        if (el) el.textContent = S.portfolio.length + " STOCKS";
    },

    log(msg) {
        const el = document.getElementById('status-line');
        if (el) el.innerHTML = `<div>> ${msg}</div>` + el.innerHTML;
    },

    triggerFile() {
        // Prevents execution if XLSX library isn't loaded yet
        if (typeof XLSX === 'undefined') {
            alert("Waiting for XLSX engine...");
            return;
        }
        document.getElementById('f-input').click();
    },

    openManual() {
        const val = prompt("Enter Stocks (NAME QTY AVG):");
        if (val) {
            const result = Core.parseInput(val);
            if (result.length > 0) {
                S.portfolio = S.portfolio.concat(result);
                Core.commit(result.length);
            } else {
                alert("Resolution failed. Verify format: SYMBOL QTY PRICE");
            }
        }
    }
};
