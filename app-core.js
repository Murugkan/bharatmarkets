/** ONYX v10.0 CORE - Simple Pass Version */
window.S = JSON.parse(localStorage.getItem('bm_settings')) || { settings: { ghToken: '', ghRepo: '' } };
window.SYMBOLS = JSON.parse(localStorage.getItem('bm_symbols')) || [];

const ghHeaders = () => ({ 
    'Authorization': `token ${S.settings.ghToken}`, 
    'Accept': 'application/vnd.github.v3+json', 
    'Cache-Control': 'no-cache' 
});

function normalizeName(n) { 
    return n.toUpperCase().replace(/LTD|LIMITED|CORP|INC|PLC/g, '').replace(/[^\w\s]/gi, '').trim(); 
}

function checkDuplicate(name) { 
    const norm = normalizeName(name); 
    return window.SYMBOLS.find(s => normalizeName(s.name) === norm); 
}

async function parseFile(file) {
    return new Promise((resolve) => {
        const reader = new FileReader();
        const ext = file.name.split('.').pop().toLowerCase();
        reader.onload = (e) => {
            let data = [];
            if (ext === 'xlsx' || ext === 'xls') {
                const workbook = XLSX.read(e.target.result, { type: 'binary' });
                const firstSheet = workbook.Sheets[workbook.SheetNames[0]];
                data = XLSX.utils.sheet_to_json(firstSheet);
            } else {
                const rows = e.target.result.split('\n').filter(r => r.trim().length > 5);
                const headers = rows[0].toLowerCase().split(',');
                const nIdx = headers.indexOf('company name'), qIdx = headers.indexOf('qty'), aIdx = headers.indexOf('avg price');
                data = rows.slice(1).map(r => {
                    const p = r.split(',');
                    return { "Company Name": p[nIdx], "Qty": p[qIdx], "Avg Price": p[aIdx] };
                });
            }
            resolve(data.map(d => ({ name: d["Company Name"] || '', qty: d["Qty"] || 0, avg: d["Avg Price"] || 0 })));
        };
        if (ext === 'xlsx' || ext === 'xls') reader.readAsBinaryString(file);
        else reader.readAsText(file);
    });
}

function calculateSimilarity(str1, str2) {
    const s1 = normalizeName(str1), s2 = normalizeName(str2);
    const w1 = new Set(s1.split(/\s+/)), w2 = new Set(s2.split(/\s+/));
    const intersection = new Set([...w1].filter(x => w2.has(x)));
    const overlap = (intersection.size * 2) / (w1.size + w2.size);
    const lenRatio = Math.min(s1.length, s2.length) / Math.max(s1.length, s2.length);
    return (overlap * 0.7 + lenRatio * 0.3) * 100;
}

async function searchYahoo(query) {
    try {
        const url = `https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(query)}&region=IN&lang=en-IN`;
        const res = await fetch(url);
        if (!res.ok) return null;
        const data = await res.json();
        const nsResults = (data.quotes || []).filter(q => q.symbol && q.symbol.endsWith('.NS'));
        if (!nsResults.length) return null;
        let best = { score: 0, quote: null };
        nsResults.forEach(q => {
            const score = calculateSimilarity(query, q.shortname || q.longname || '');
            if (score > best.score) best = { score, quote: q };
        });
        return best;
    } catch (e) { return null; }
}

async function ghPut(path, content, message) {
    const url = `https://api.github.com/repos/${S.settings.ghRepo}/contents/${path}`;
    const getRes = await fetch(url, { headers: ghHeaders() });
    let sha = null;
    if (getRes.ok) { const d = await getRes.json(); sha = d.sha; }
    const body = { message: message, content: btoa(unescape(encodeURIComponent(content))), sha: sha };
    return fetch(url, { method: 'PUT', headers: ghHeaders(), body: JSON.stringify(body) });
}

function saveSettings() { 
    localStorage.setItem('bm_settings', JSON.stringify(S)); 
}

function loadState() {
    const syms = localStorage.getItem('bm_symbols');
    if (syms) window.SYMBOLS = JSON.parse(syms);
}
loadState();
