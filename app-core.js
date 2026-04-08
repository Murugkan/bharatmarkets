/** ONYX v12.0 CORE - Professional Resolution Engine */
window.S = JSON.parse(localStorage.getItem('bm_settings')) || { settings: { ghToken: '', ghRepo: '' } };
window.SYMBOLS = JSON.parse(localStorage.getItem('bm_symbols')) || [];
// Persistent map for manual overrides (User Learning)
window.ALIAS_MAP = JSON.parse(localStorage.getItem('bm_aliases')) || {};

const ghHeaders = () => ({ 
    'Authorization': `token ${S.settings.ghToken}`, 
    'Accept': 'application/vnd.github.v3+json' 
});

async function testConnection(token, repo) {
    const headers = { 'Authorization': `token ${token}`, 'Accept': 'application/vnd.github.v3+json' };
    try {
        const rRes = await fetch(`https://api.github.com/repos/${repo}`, { headers });
        if (!rRes.ok) return { repo: false, status: 'fail' };
        const wRes = await fetch(`https://api.github.com/repos/${repo}/contents/.github/workflows/fetch-prices.yml`, { headers });
        return { repo: true, workflow: wRes.ok, status: 'ok' };
    } catch (e) {
        return { repo: false, status: 'network_block' };
    }
}

// Professional Name Sanitizer (No hard-coding)
function normalizeName(n) {
    if (!n) return '';
    return n.toUpperCase()
        .replace(/\b(LTD|LIMITED|CORP|INC|PLC|EQUITY|EQ|IND|INDUSTRIES|SERVICES|GROUP|HOLDINGS)\b/g, '')
        .replace(/[^\w\s]/gi, '')
        .replace(/\s+/g, ' ')
        .trim();
}

// Tiered Resolution: Alias -> Normalization -> Fuzzy Search
async function resolveSymbol(rawName) {
    const clean = normalizeName(rawName);
    
    // 1. Check User Alias Map (Memory)
    if (window.ALIAS_MAP[clean]) return { symbol: window.ALIAS_MAP[clean], method: 'alias' };

    // 2. Dynamic Search with fallback
    try {
        const url = `https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(clean)}&region=IN`;
        const res = await fetch(url);
        const data = await res.json();
        const quotes = (data.quotes || []).filter(q => q.symbol && (q.symbol.endsWith('.NS') || q.symbol.endsWith('.BO')));
        
        if (!quotes.length) return null;

        // Scoring based on token overlap
        let best = { score: 0, quote: null };
        const cleanTokens = clean.split(' ');
        
        quotes.forEach(q => {
            const qName = normalizeName(q.shortname || q.longname || '');
            const qTokens = qName.split(' ');
            const matchCount = cleanTokens.filter(t => qTokens.includes(t)).length;
            const score = (matchCount / Math.max(cleanTokens.length, qTokens.length)) * 100;
            
            if (score > best.score) best = { score, quote: q };
        });

        return best.score > 60 ? { symbol: best.quote.symbol, method: 'fuzzy' } : null;
    } catch (e) { return null; }
}

function saveAlias(rawName, symbol) {
    const clean = normalizeName(rawName);
    window.ALIAS_MAP[clean] = symbol.toUpperCase();
    localStorage.setItem('bm_aliases', JSON.stringify(window.ALIAS_MAP));
}

async function parseFile(file) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const workbook = XLSX.read(e.target.result, { type: 'binary' });
            const sheet = workbook.Sheets[workbook.SheetNames[0]];
            const json = XLSX.utils.sheet_to_json(sheet);
            resolve(json.map(d => ({ 
                name: d["Company Name"] || d["Security Name"] || d["Entity"] || '', 
                qty: d["Qty"] || d["Quantity"] || 0, 
                avg: d["Avg Price"] || d["Price"] || 0 
            })));
        };
        reader.readAsBinaryString(file);
    });
}

function saveSettings() { localStorage.setItem('bm_settings', JSON.stringify(S)); }
