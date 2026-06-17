#!/usr/bin/env python3
"""
Fetches Google News RSS for all tickers in unified-symbols.json
and writes a single data/news.json file.
Run by GitHub Actions every 6 hours.
"""
import json, os, re, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone
import re

# Noise headlines to skip — stock price pages, IPO listing articles
NOISE_RE = re.compile(
    r'share price today|live.*stock price|nse/bse|ipo listing|ipo date|ipo price|'
    r'ipo allotment|ipo gmp|stock.*chart|live price|price today|share price live',
    re.IGNORECASE
)

PORTFOLIO_FILE = 'data/unified-symbols.json'
OUTPUT_FILE    = 'data/news.json'
MAX_ITEMS      = 25
CUTOFF_DAYS    = 90

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
                items.append({
                    'title':   title,
                    'link':    gt('link'),
                    'pubDate': gt('pubDate'),
                    'source':  source,
                })
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
        GN + urllib.parse.quote(f'{co} NSE'),
        GN + urllib.parse.quote(f'{sym} NSE India'),
    ]
    cutoff_ts = datetime.now(timezone.utc).timestamp() - CUTOFF_DAYS * 86400
    seen, items = set(), []
    for q in queries:
        for it in parse_rss(fetch_rss(q)):
            key = it['link'] or it['title']
            if not key or key in seen: continue
            if NOISE_RE.search(it.get('title', '')): continue
            # Date filter
            try:
                from email.utils import parsedate_to_datetime
                pub_ts = parsedate_to_datetime(it['pubDate']).timestamp()
                if pub_ts < cutoff_ts: continue
            except Exception:
                pass  # keep if unparseable
            seen.add(key)
            items.append(it)
        if len(items) >= MAX_ITEMS:
            break
    return items[:MAX_ITEMS]

def main():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(PORTFOLIO_FILE, encoding='utf-8') as f:
        data = json.load(f)
    tickers = [(s['ticker'].strip(), s.get('name','').strip())
               for s in data.get('symbols', []) if s.get('ticker')]

    print(f'Fetching news for {len(tickers)} tickers...')

    result = {}
    for sym, name in tickers:
        print(f'  {sym}...', end=' ', flush=True)
        items = fetch_for_ticker(sym, name)
        result[sym] = items
        print(len(items))

    output = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'count':   len(result),
        'news':    result          # { "SBIN": [...], "GRAPHITE": [...], ... }
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, separators=(',', ':'))

    size_kb = os.path.getsize(OUTPUT_FILE) // 1024
    print(f'\nWritten {OUTPUT_FILE} ({size_kb} KB, {len(result)} tickers)')

if __name__ == '__main__':
    main()
