#!/usr/bin/env python3
"""
Fetches Google News RSS for all tickers in data/unified-symbols.json.
Generates a pre-market brief from actual fetched headlines.
Writes data/news.json.
Run by GitHub Actions every 6 hours.
"""
import json, os, re, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

PORTFOLIO_FILE = 'data/unified-symbols.json'
OUTPUT_FILE    = 'data/news.json'
MAX_ITEMS      = 25
CUTOFF_DAYS    = 30   # 1 month

NOISE_RE = re.compile(
    r'share price today|live.*stock price|nse/bse|ipo listing|ipo date|ipo price|'
    r'ipo allotment|ipo gmp|stock.*chart|live price|price today|share price live|'
    r'most active equities|stocks to watch|stocks in news|top stocks|stocks that|'
    r'multibagger|penny stock|trading activity today|daily brief india|week ahead|'
    r'trade spotlight|market wrap|opening bell|closing bell',
    re.IGNORECASE
)

# ─────────────────────────────────────────────────────────────
# Fetch & parse RSS
# ─────────────────────────────────────────────────────────────

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
    return ' '.join(w for w in words if w and w.upper() not in STOP)[:40]

def fetch_for_ticker(sym, name):
    GN = 'https://news.google.com/rss/search?hl=en-IN&gl=IN&ceid=IN:en&q='
    co = clean_name(name, sym)

    GENERIC = {'india','limited','energy','power','capital','finance','tech',
               'technologies','services','solutions','group','holdings','corp',
               'quality','national','general','global','enterprise','ventures'}
    COMMON_TICKERS = {
        'quality','power','oil','coal','gold','steel','glass','solar','wind',
        'rail','road','port','ship','air','fire','water','gas','salt','sugar',
        'milk','rice','paper','wood','iron','zinc','lead','silver','copper',
        'diamond','pearl','star','sun','moon','dawn','prime','first','ace',
        'pioneer','champion','alpha','omega','titan','atlas','arrow','shield',
        'crown','capital','fortune','liberty','unity','focus','vision','action'
    }
    name_words = [w.lower() for w in re.sub(r'[^a-zA-Z0-9 ]', ' ', name).split()
                  if len(w) > 3 and w.lower() not in GENERIC]
    sym_lower = sym.lower()
    # Fewer specific words → lower threshold
    hit_threshold = 1 if len(name_words) <= 2 else 2

    def is_relevant(title):
        tl = title.lower()
        if f'nse:{sym_lower}' in tl: return True
        if sym_lower not in COMMON_TICKERS:
            if re.search(r'\b' + re.escape(sym_lower) + r'\b', tl): return True
        hits = sum(1 for w in name_words if w in tl)
        if hits >= hit_threshold: return True
        # First 2 specific name words as phrase
        sp = [w for w in re.sub(r'[^a-zA-Z0-9 ]', ' ', name).split()
              if w.lower() not in GENERIC and len(w) > 3]
        if len(sp) >= 2 and (sp[0] + ' ' + sp[1]).lower() in tl: return True
        return False

    # Plain queries only — quoted phrases kill results for small-caps
    queries = [
        GN + urllib.parse.quote(f'{co} NSE'),
        GN + urllib.parse.quote(f'{sym} NSE India'),
        GN + urllib.parse.quote(f'{co} share'),
    ]
    cutoff_ts = datetime.now(timezone.utc).timestamp() - CUTOFF_DAYS * 86400
    seen, items = set(), []

    for q in queries:
        for it in parse_rss(fetch_rss(q)):
            key = it['link'] or it['title']
            if not key or key in seen: continue
            if NOISE_RE.search(it['title']): continue
            if not is_relevant(it['title']): continue
            try:
                if parsedate_to_datetime(it['pubDate']).timestamp() < cutoff_ts: continue
            except Exception:
                pass
            seen.add(key)
            items.append(it)

    # Fallback: if still nothing, accept anything from first query (no relevance filter)
    if not items:
        for it in parse_rss(fetch_rss(queries[0])):
            key = it['link'] or it['title']
            if not key or key in seen: continue
            if NOISE_RE.search(it['title']): continue
            try:
                if parsedate_to_datetime(it['pubDate']).timestamp() < cutoff_ts: continue
            except Exception:
                pass
            seen.add(key)
            items.append(it)

    return items[:MAX_ITEMS]


def clean_title(t):
    """Strip trailing ' - Source Name' suffix."""
    return re.sub(r'\s*[-–|]\s*.{2,28}$', '', t or '').strip()

def build_brief(items):
    """
    Generates a structured pre-market brief from real fetched headlines.
    Returns a dict with: sentiment, catalyst, risk, street_view, summary
    """
    if not items:
        return {}

    # Use last 7 days for brief; fall back to all items if none in 7d
    now_ts = datetime.now(timezone.utc).timestamp()
    week   = [it for it in items
              if _parse_ts(it['pubDate']) >= now_ts - 7*86400]
    pool   = week if week else items[:10]

    titles = [clean_title(it['title']) for it in pool]

    # Bucket by category
    results, corp, analyst, regulatory, other = [], [], [], [], []
    for t in titles:
        tl = t.lower()
        if any(w in tl for w in ['result','profit','loss','revenue','ebitda','earning','q1','q2','q3','q4','quarterly']):
            results.append(t)
        elif any(w in tl for w in ['dividend','buyback','split','agm','merger','acqui','qip','order','contract','raise','fund']):
            corp.append(t)
        elif any(w in tl for w in ['upgrade','downgrade','target','analyst','outperform','overweight','underweight','buy','sell','hold']):
            analyst.append(t)
        elif any(w in tl for w in ['sebi','nclt','penalty','fine','notice','fraud','scam','fir','raid','ban','regulatory']):
            regulatory.append(t)
        else:
            other.append(t)

    # Sentiment: count positive vs negative signals
    pos_words = ['rise','rally','surge','jump','gain','high','record','beat','strong','upgrade','buy','outperform','positive','profit','growth']
    neg_words = ['fall','drop','decline','tank','loss','weak','miss','cut','downgrade','sell','underperform','negative','concern','penalty','fraud']
    pos = sum(1 for t in titles for w in pos_words if w in t.lower())
    neg = sum(1 for t in titles for w in neg_words if w in t.lower())

    if pos > neg + 1:
        sentiment = 'Bullish'
    elif neg > pos + 1:
        sentiment = 'Bearish'
    elif pos == 0 and neg == 0:
        sentiment = 'Neutral'
    else:
        sentiment = 'Mixed'

    # Catalyst: most important single headline (priority: results > regulatory > corp > analyst > other)
    # Prefer stock-specific headlines (no comma-separated list of multiple stocks)
    def is_specific(t):
        # Roundup articles list 3+ stocks separated by commas
        parts = t.split(',')
        return len(parts) < 3

    catalyst = ''
    for bucket in [results, regulatory, corp, analyst, other]:
        specific = [t for t in bucket if is_specific(t)]
        if specific:
            catalyst = specific[0]
            break
        elif bucket and not catalyst:
            catalyst = bucket[0]  # fallback to roundup if nothing else

    # Risk: look for negative signals in all buckets
    risk = ''
    risk_words = ['fall','drop','decline','tank','loss','weak','miss','concern','penalty','fraud','notice','fine','ban','scam','raid']
    for t in titles:
        if any(w in t.lower() for w in risk_words):
            risk = t
            break
    if not risk and neg > 0:
        risk = 'Watch for selling pressure based on recent news flow'

    # Street view: analyst headlines
    street_view = analyst[0] if analyst else (other[0] if other else '')

    # Summary: 2-3 sentences from top buckets
    parts = []
    for bucket in [results, corp, regulatory, analyst, other]:
        if bucket and len(parts) < 3:
            t = bucket[0]
            parts.append(t if t.endswith('.') else t + '.')
    summary = ' '.join(parts[:3])

    return {
        'sentiment':   sentiment,
        'catalyst':    catalyst,
        'risk':        risk or 'No specific risk signals in recent news.',
        'street_view': street_view,
        'summary':     summary,
        'as_of':       datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC'),
    }

def _parse_ts(pub_date):
    try:
        return parsedate_to_datetime(pub_date).timestamp()
    except Exception:
        return 0

# ─────────────────────────────────────────────────────────────
# Git commit/push with rebase-retry
# ─────────────────────────────────────────────────────────────

def _run(cmd, check=True):
    print(f'  $ {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip():
        print(f'    {result.stdout.strip()}')
    if result.stderr.strip():
        print(f'    {result.stderr.strip()}')
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, result.stdout, result.stderr)
    return result

def commit_and_push(paths, message, max_retries=5):
    """
    Stages the given paths, commits if there's a diff, then pushes with
    a fetch+rebase retry loop to survive races with other workflows
    pushing to the same branch.
    """
    _run(['git', 'config', 'user.name',  'github-actions[bot]'])
    _run(['git', 'config', 'user.email', 'github-actions[bot]@users.noreply.github.com'])

    _run(['git', 'add'] + paths)

    diff = subprocess.run(['git', 'diff', '--staged', '--quiet'])
    if diff.returncode == 0:
        print('  No changes to commit.')
        return

    _run(['git', 'commit', '-m', message])

    for attempt in range(1, max_retries + 1):
        push = subprocess.run(['git', 'push'], capture_output=True, text=True)
        if push.returncode == 0:
            print('  Pushed successfully.')
            return
        print(f'  Push rejected (attempt {attempt}/{max_retries}): {push.stderr.strip()}')

        _run(['git', 'fetch', 'origin', 'main'])
        rebase = subprocess.run(['git', 'rebase', 'origin/main'], capture_output=True, text=True)
        if rebase.returncode != 0:
            print(f'    rebase failed: {rebase.stderr.strip()}')
            _run(['git', 'rebase', '--abort'], check=False)
            raise RuntimeError('Rebase failed while retrying push; manual intervention needed.')

        time.sleep(random.uniform(1, 5))

    raise RuntimeError(f'Push failed after {max_retries} retries.')

# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────

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
        items = fetch_for_ticker(sym, name)
        brief = build_brief(items)
        result[sym] = {'items': items, 'brief': brief}
        has_brief = '+ brief' if brief.get('catalyst') else ''
        print(f'{len(items)} items {has_brief}')

    output = {
        'updated': datetime.now(timezone.utc).isoformat(),
        'count':   len(result),
        'news':    result
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, separators=(',', ':'))

    size_kb = os.path.getsize(OUTPUT_FILE) // 1024
    print(f'\nWritten {OUTPUT_FILE} ({size_kb} KB)')

    print('\nCommitting and pushing...')
    commit_and_push([OUTPUT_FILE], 'chore: update news.json [skip ci]')

if __name__ == '__main__':
    main()
