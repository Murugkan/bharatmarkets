/**
 * ONYX SYSTEM v9.5 - MASTER CORE
 * Requirements: Automated Resolution, Similarity Scoring, Header Gatekeeper, PAT Auth
 */
window.S = JSON.parse(localStorage.getItem('bm_settings')) || {
    settings: { ghToken: '', ghRepo: '', _ghStatus: 'dim' }
};
window.SYMBOLS = JSON.parse(localStorage.getItem('bm_symbols')) || [];

const ghHeaders = () => ({
    'Authorization': `token ${S.settings.ghToken}`,
    'Accept': 'application/vnd.github.v3+json',
    'Cache-Control': 'no-cache'
});

async function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = (e) => reject(e);
        reader.readAsText(file);
    });
}

function isCrap(text) {
    const hasBinary = /[\x00-\x08\x0E-\x1F\x7F]/.test(text.slice(0, 500));
    const lower = text.toLowerCase();
    const hasHeaders = lower.includes('name') && (lower.includes('qty') || lower.includes('avg'));
    return hasBinary || !hasHeaders;
}

function calculateSimilarity(str1, str2) {
    const s1 = str1.toUpperCase().replace(/LTD|LIMITED|CORP|INC/g, '').trim();
    const s2 = str2.toUpperCase().replace(/LTD|LIMITED|CORP|INC/g, '').trim();
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

async function searchNSE(query) {
    try {
        const url = `https://www.nseindia.com/api/suggest?q=${encodeURIComponent(query)}`;
        const res = await fetch(url);
        if (!res.ok) return null;
        const data = await res.json();
        const firstEquity = (data.keywords || []).find(k => k.type === 'Equity');
        return firstEquity ? firstEquity.symbol : null;
    } catch (e) { return null; }
}

async function ghPut(path, content, message) {
    const url = `https://api.github.com/repos/${S.settings.ghRepo}/contents/${path}`;
    const getRes = await fetch(url, { headers: ghHeaders() });
    let sha = null;
    if (getRes.ok) { const d = await getRes.json(); sha = d.sha; }
    const body = {
        message: message,
        content: btoa(unescape(encodeURIComponent(content))),
        sha: sha
    };
    return fetch(url, { method: 'PUT', headers: ghHeaders(), body: JSON.stringify(body) });
}

async function validatePAT() {
    const res = await fetch(`https://api.github.com/repos/${S.settings.ghRepo}`, { headers: ghHeaders() });
    return res.ok;
}

function saveSettings() { localStorage.setItem('bm_settings', JSON.stringify(S)); }
function loadState() {
    const syms = localStorage.getItem('bm_symbols');
    if (syms) window.SYMBOLS = JSON.parse(syms);
}
loadState();
