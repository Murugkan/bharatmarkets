#!/usr/bin/env python3
"""
Fetches Google News RSS for all tickers in data/unified-symbols.json
and writes a single data/news.json file with news items + text summary per ticker.
Run by GitHub Actions every 6 hours.
"""
import json, os, re, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

PORTFOLIO_FILE = 'data/unified-symbols.json'
OUTPUT_FILE    = 'data/news.json'
MAX_ITEMS      = 25
CUTOFF_DAYS    = 90

NOISE_RE = re.compile(
    r'share price today|live.*stock price|nse/bse|ipo listing|ipo date|ipo price|'
    r'ipo allotment|ipo gmp|stock.*chart|live price|price today|share price live',
    re.IGNORECASE
)

# ── Fetch ────────────────────────────────────────────────────────────────────

def fetch_rss(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1)',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*'
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f'    fetch error: {e}')
        return ''

def parse_rss(xml_text):
    items = []
    try:
        root = ET.fromstring(xml_text)
        for item in root.findall('.//item'):
            def gt(tag):
                el = item.find(tag)
                return (el.text or '').strip()
            source_el = item.find('source')
            source = (source_el.text or '').strip() if source_el is not None else ''
            title = gt('title')
            if title:
                items.append({'title': title, 'link': gt('link'),
                              'pubDate': gt('pubDate'), 'source': source})
    except Exception as e:
        print(f'    parse error: {e}')
    return items

def clean_name(name, sym):
    STOP = {'LTD','LIMITED','PVT','PRIVATE','INC','CORP','LLP','MOB'}
    words = re.sub(r'[^a-zA-Z0-9 ]', ' ', name or sym).split()
    clean = [w for w in words if w and w.upper() not in STOP]
    return ' '.join(clean[:3])

def fetch_for_ticker(sym, name):
    GN = 'https://news.google.com/rss/search?hl=en-IN&gl=IN&ceid=IN:en&q='
    co = clean_name(name, sym)
    queries = [
        GN + urllib.parse.quote(f'{sym} NSE'),
        GN + urllib.parse.quote(f'{sym} India stock'),
        GN + urllib.parse.quote(f'{co} NSE India'),
    ]
    cutoff_ts = datetime.now(timezone.utc).timestamp() - CUTOFF_DAYS * 86400
    seen, items = set(), []
    for q in queries:
        for it in parse_rss(fetch_rss(q)):
            key = it['link'] or it['title']
            if not key or key in seen: continue
            if NOISE_RE.search(it.get('title', '')): continue
            try:
                if parsedate_to_datetime(it['pubDate']).timestamp() < cutoff_ts: continue
            except Exception:
                pass
            seen.add(key)
            items.append(it)
    return items[:MAX_ITEMS]

# ── Summary ───────────────────────────────────────────────────────────────────

def generate_summary(items):
    """2-3 sentence factual summary from last 7 days of headlines. No API needed."""
    cutoff_7d = datetime.now(timezone.utc).timestamp() - 7 * 86400
    recent = []
    for it in items:
        try:
            if parsedate_to_datetime(it['pubDate']).timestamp() >= cutoff_7d:
                recent.append(it['title'])
        except Exception:
            recent.append(it['title'])  # include if date unparseable

    if not recent:
        return ''

    def clean(t):
        return re.sub(r'\s*[-–|]\s*.{2,25}$', '', t).strip()

    cleaned = [clean(t) for t in recent[:10]]

    results, corp, analyst, other = [], [], [], []
    for t in cleaned:
        tl = t.lower()
        if any(w in tl for w in ['result','profit','loss','revenue','ebitda','earning','q1','q2','q3','q4']):
            results.append(t)
        elif any(w in tl for w in ['dividend','buyback','split','agm','merger','acqui','order','contract','sebi','penalty','fraud','notice','fine']):
            corp.append(t)
        elif any(w in tl for w in ['upgrade','downgrade','target','analyst','outperform','overweight','underweight']):
            analyst.append(t)
        else:
            other.append(t)

    parts = []
    for bucket in [results, corp, analyst, other]:
        if bucket and len(parts) < 3:
            t = bucket[0]
            parts.append(t if t.endswith('.') else t + '.')

    return ' '.join(parts[:3])

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(PORTFOLIO_FILE, encoding='utf-8') as f:
        data = json.load(f)
    tickers = [(s['ticker'].strip(), s.get('name', '').strip())
               for s in data.get('symbols', []) if s.get('ticker')]

    print(f'Fetching news for {len(tickers)} tickers...')

    result = {}
    for sym, name in tickers:
        print(f'  {sym}...', end=' ', flush=True)
        items   = fetch_for_ticker(sym, name)
        summary = generate_summary(items)
        result[sym] = {'items': items, 'summary': summary}
        print(f'{len(items)} items' + (' + summary' if summary else ''))

    output = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'count':   len(result),
        'news':    result
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, separators=(',', ':'))

    size_kb = os.path.getsize(OUTPUT_FILE) // 1024
    print(f'\nWritten {OUTPUT_FILE} ({size_kb} KB, {len(result)} tickers)')

if __name__ == '__main__':
    main()
