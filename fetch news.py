#!/usr/bin/env python3
"""
Fetches Google News RSS for each ticker in the portfolio JSON
and writes data/news/{TICKER}.json files.
Run by GitHub Actions every 6 hours.
"""
import json, os, re, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone

PORTFOLIO_FILE = 'unified-symbols.json'
OUTPUT_DIR = 'data/news'
MAX_ITEMS = 20

def fetch_rss(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1)',
        'Accept': 'application/rss+xml, application/xml, text/xml, */*'
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f'  fetch error: {e}')
        return ''

def parse_rss(xml_text):
    items = []
    try:
        root = ET.fromstring(xml_text)
        ns = {'media': 'http://search.yahoo.com/mrss/'}
        for item in root.findall('.//item'):
            def gt(tag):
                el = item.find(tag)
                return el.text.strip() if el is not None and el.text else ''
            source_el = item.find('source')
            source = source_el.text.strip() if source_el is not None and source_el.text else ''
            items.append({
                'title':   gt('title'),
                'link':    gt('link'),
                'pubDate': gt('pubDate'),
                'source':  source,
            })
    except Exception as e:
        print(f'  parse error: {e}')
    return items

def get_tickers():
    """Read tickers from unified-symbols.json -> symbols[].ticker
       Also grab name for better news queries."""
    with open(PORTFOLIO_FILE, encoding='utf-8') as f:
        data = json.load(f)
    symbols = data.get('symbols', [])
    result = []
    for s in symbols:
        t = str(s.get('ticker', '')).strip()
        n = str(s.get('name', '')).strip()
        if t:
            result.append((t, n))
    print(f'Loaded {len(result)} tickers from {PORTFOLIO_FILE}')
    return result

def clean_name_for_query(name, sym):
    STOP = {'LTD','LIMITED','PVT','PRIVATE','INC','CORP','LLP','MOB','AND'}
    words = re.sub(r'[^a-zA-Z0-9 ]', ' ', name or sym).split()
    clean = [w for w in words if w and w.upper() not in STOP]
    return ' '.join(clean[:3])

def fetch_news_for_ticker(sym, name=''):
    GN = 'https://news.google.com/rss/search?hl=en-IN&gl=IN&ceid=IN:en&q='
    co = clean_name_for_query(name, sym)
    
    queries = [
        GN + urllib.parse.quote(f'{co} NSE'),
        GN + urllib.parse.quote(f'{sym} NSE India'),
    ]
    
    seen, items = set(), []
    for q in queries:
        xml = fetch_rss(q)
        if not xml: continue
        for it in parse_rss(xml):
            key = it['link'] or it['title']
            if key and key not in seen:
                seen.add(key)
                items.append(it)
        if len(items) >= MAX_ITEMS: break
    
    return items[:MAX_ITEMS]

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    tickers = get_tickers()
    
    if not tickers:
        print('No tickers found. Add at least one ticker to portfolio JSON.')
        return
    
    print(f'Fetching news for {len(tickers)} tickers: {", ".join(t for t,n in tickers[:10])}{"..." if len(tickers)>10 else ""}')
    
    updated = []
    for sym, name in tickers:
        print(f'  {sym}...', end=' ', flush=True)
        items = fetch_news_for_ticker(sym, name)
        out = {
            'ticker': sym,
            'updated': datetime.now(timezone.utc).isoformat(),
            'items': items
        }
        path = os.path.join(OUTPUT_DIR, f'{sym}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False)
        print(f'{len(items)} items')
        updated.append({'ticker': sym, 'count': len(items), 'updated': out['updated']})
    
    # Write index
    with open(os.path.join(OUTPUT_DIR, 'index.json'), 'w') as f:
        json.dump({'updated': datetime.now(timezone.utc).isoformat(), 'tickers': updated}, f)
    
    print(f'\nDone. {len(updated)} files written to {OUTPUT_DIR}/')

if __name__ == '__main__':
    main()
