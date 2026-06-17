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
    # Ticker first (most precise), then company name variants
    # Don't run co-only query if co is too generic (>3 common words)
    queries = [
        GN + urllib.parse.quote(f'{sym} NSE'),           # CDSL NSE
        GN + urllib.parse.quote(f'{sym} India stock'),   # CDSL India stock
        GN + urllib.parse.quote(f'{co} NSE India'),      # Central Depository Services NSE India
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
    return items[:MAX_ITEMS]

def generate_summary(sym, name, items):
    """Build a factual 2-3 sentence news summary from recent headlines. No API needed."""
    from email.utils import parsedate_to_datetime
    cutoff_7d = datetime.now(timezone.utc).timestamp() - 7 * 86400

    recent = []
    for it in items:
        try:
            if parsedate_to_datetime(it['pubDate']).timestamp() >= cutoff_7d:
                recent.append(it['title'])
        except Exception:
            pass

    if not recent:
        return ''

    # Clean titles: strip trailing " - Source Name"
    import re as _re
    def clean(t):
        return _re.sub(r'\s*[-–|]\s*.{2,25}$', '', t).strip()

    cleaned = [clean(t) for t in recent[:8]]

    # Group by rough category
    results, corp, regulatory, other = [], [], [], []
    for t in cleaned:
        tl = t.lower()
        if any(w in tl for w in ['result','profit','loss','revenue','ebitda','earning','q1','q2','q3','q4']):
            results.append(t)
        elif any(w in tl for w in ['dividend','buyback','split','agm','merger','acqui','order','contract','sebi','penalty','fraud']):
            corp.append(t)
        elif any(w in tl for w in ['upgrade','downgrade','target','analyst','outperform','buy','sell']):
            regulatory.append(t)
        else:
            other.append(t)

    parts = []
    if results:
        parts.append(results[0] + ('.' if not results[0].endswith('.') else ''))
    if corp:
        parts.append(corp[0] + ('.' if not corp[0].endswith('.') else ''))
    if regulatory:
        parts.append(regulatory[0] + ('.' if not regulatory[0].endswith('.') else ''))
    # Fill up to 3 sentences from other if needed
    for t in other:
        if len(parts) >= 3:
            break
        parts.append(t + ('.' if not t.endswith('.') else ''))

    return ' '.join(parts[:3])

if __name__ == '__main__':
    main()
