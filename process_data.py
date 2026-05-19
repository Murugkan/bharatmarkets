#!/usr/bin/env python3
"""
CANONICAL JSON GENERATOR (GitHub Workflow Compatible)
Root-relative paths for GitHub Actions execution

Paths are relative to repository root:
  - Input:  data/raw_market_data.json
  - Output: data/complete_ticker_profiles.json
  - Logs:   data/logs/complete_processing.log
"""

import json
import sys
import logging
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

# ============================================================================
# SECTOR PROFILES (Sector-Aware)
# ============================================================================

SECTOR_PROFILES = {
    'Financials': {
        'name': 'Banking & Financials',
        'weights': {'fundamental': 50, 'technical': 20, 'valuation': 20, 'sentiment': 10},
        'prof_thresholds': {'excellent': 0.18, 'good': 0.15, 'fair': 0.12},
        'solv_thresholds': {'de_limit': 12, 'npa_limit': 0.02, 'car_min': 0.12},
    },
    'Information Technology': {
        'name': 'IT & Software',
        'weights': {'fundamental': 35, 'technical': 35, 'valuation': 20, 'sentiment': 10},
        'prof_thresholds': {'excellent': 0.30, 'good': 0.25, 'fair': 0.20},
        'solv_thresholds': {'de_limit': 0.5, 'ic_min': 50},
    },
    'Industrials': {
        'name': 'Industrials & Engineering',
        'weights': {'fundamental': 45, 'technical': 25, 'valuation': 20, 'sentiment': 10},
        'prof_thresholds': {'excellent': 0.20, 'good': 0.15, 'fair': 0.10},
        'solv_thresholds': {'de_limit': 1.5, 'ic_min': 3},
    },
    'Consumer Staples': {
        'name': 'FMCG & Staples',
        'weights': {'fundamental': 50, 'technical': 15, 'valuation': 25, 'sentiment': 10},
        'prof_thresholds': {'excellent': 0.25, 'good': 0.20, 'fair': 0.15},
        'solv_thresholds': {'de_limit': 1.0, 'ic_min': 5},
    },
    'Consumer Discretionary': {
        'name': 'Consumer Discretionary',
        'weights': {'fundamental': 35, 'technical': 40, 'valuation': 15, 'sentiment': 10},
        'prof_thresholds': {'excellent': 0.15, 'good': 0.12, 'fair': 0.08},
        'solv_thresholds': {'de_limit': 1.5, 'ic_min': 3},
    },
    'Healthcare': {
        'name': 'Healthcare & Pharma',
        'weights': {'fundamental': 40, 'technical': 20, 'valuation': 30, 'sentiment': 10},
        'prof_thresholds': {'excellent': 0.25, 'good': 0.20, 'fair': 0.15},
        'solv_thresholds': {'de_limit': 1.0, 'ic_min': 4},
    },
    'Materials': {
        'name': 'Metals & Mining',
        'weights': {'fundamental': 30, 'technical': 45, 'valuation': 15, 'sentiment': 10},
        'prof_thresholds': {'excellent': 0.20, 'good': 0.15, 'fair': 0.10},
        'solv_thresholds': {'de_limit': 2.0, 'ic_min': 2},
    },
    'Energy': {
        'name': 'Oil, Gas & Power',
        'weights': {'fundamental': 35, 'technical': 40, 'valuation': 15, 'sentiment': 10},
        'prof_thresholds': {'excellent': 0.18, 'good': 0.12, 'fair': 0.08},
        'solv_thresholds': {'de_limit': 2.0, 'ic_min': 2.5},
    },
    'Telecom': {
        'name': 'Telecom & Broadcasting',
        'weights': {'fundamental': 40, 'technical': 25, 'valuation': 25, 'sentiment': 10},
        'prof_thresholds': {'excellent': 0.20, 'good': 0.15, 'fair': 0.10},
        'solv_thresholds': {'de_limit': 2.0, 'ic_min': 2},
    },
    'Real Estate': {
        'name': 'Real Estate & Construction',
        'weights': {'fundamental': 35, 'technical': 30, 'valuation': 25, 'sentiment': 10},
        'prof_thresholds': {'excellent': 0.25, 'good': 0.20, 'fair': 0.15},
        'solv_thresholds': {'de_limit': 2.0, 'ic_min': 2},
    },
    'Utilities': {
        'name': 'Utilities & Infrastructure',
        'weights': {'fundamental': 60, 'technical': 10, 'valuation': 20, 'sentiment': 10},
        'prof_thresholds': {'excellent': 0.18, 'good': 0.15, 'fair': 0.12},
        'solv_thresholds': {'de_limit': 2.5, 'ic_min': 2},
    },
    'Unknown': {
        'name': 'Unknown Sector',
        'weights': {'fundamental': 40, 'technical': 30, 'valuation': 20, 'sentiment': 10},
        'prof_thresholds': {'excellent': 0.20, 'good': 0.15, 'fair': 0.10},
        'solv_thresholds': {'de_limit': 1.5, 'ic_min': 3},
    }
}

# ============================================================================
# SETUP & UTILITIES (ROOT-RELATIVE PATHS)
# ============================================================================

def setup_logging():
    """Setup logging - root-relative paths"""
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "complete_processing.log"
    
    logger = logging.getLogger("CANONICAL-JSON")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    
    fh = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
    return logger, log_file


def load_json(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading {filepath}: {str(e)}")
        return None


def save_json(filepath, data):
    try:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error saving {filepath}: {str(e)}")
        return False


def normalize_ticker(ticker):
    return ticker.upper().strip() if isinstance(ticker, str) else ticker


def normalize_name(name):
    if isinstance(name, str):
        return ' '.join(word.capitalize() for word in name.split()).strip()
    return name


def normalize_sector(sector):
    if not isinstance(sector, str):
        return "Unknown"
    sector = sector.strip().lower()
    sector_map = {
        'financials': 'Financials', 'financial': 'Financials', 'banks': 'Financials',
        'information technology': 'Information Technology', 'it': 'Information Technology',
        'industrials': 'Industrials', 'industrial': 'Industrials',
        'consumer discretionary': 'Consumer Discretionary',
        'consumer staples': 'Consumer Staples', 'staples': 'Consumer Staples', 'fmcg': 'Consumer Staples',
        'healthcare': 'Healthcare', 'pharma': 'Healthcare',
        'materials': 'Materials', 'metals': 'Materials', 'mining': 'Materials',
        'utilities': 'Utilities', 'energy': 'Energy', 'power': 'Energy',
        'telecom': 'Telecom', 'defence': 'Defence', 'real estate': 'Real Estate',
    }
    return sector_map.get(sector, "Unknown")


def safe_divide(num, denom, decimals=4):
    if denom is None or denom == 0 or num is None:
        return None
    try:
        return round(num / denom, decimals)
    except:
        return None


# ============================================================================
# DATA EXTRACTION & PROCESSING
# ============================================================================

def extract_and_normalize_data(company):
    """Extract financial data from all sources"""
    data = {'bs': {}, 'is': {}}
    
    if 'yahoofin_raw' in company and isinstance(company['yahoofin_raw'], dict):
        raw = company['yahoofin_raw']
        data['bs'].update({k: raw.get(k) for k in ['total_assets', 'total_liabilities', 'equity', 'current_assets', 'current_liabilities', 'sector']})
    
    if 'yahoofin_financials' in company and isinstance(company['yahoofin_financials'], dict):
        fin = company['yahoofin_financials']
        for k in ['total_assets', 'total_liabilities', 'equity', 'current_assets', 'current_liabilities']:
            if k not in data['bs'] or data['bs'][k] is None:
                data['bs'][k] = fin.get(k)
        data['bs'].update({k: fin.get(k) for k in ['inventory', 'cash', 'total_debt']})
        data['is'].update({k: fin.get(k) for k in ['revenue', 'net_profit', 'ebit', 'interest_expense', 'tax_expense']})
    
    if 'screener_financials' in company and isinstance(company['screener_financials'], dict):
        scr = company['screener_financials']
        if 'tables' in scr:
            tables = scr['tables']
            if 'profit_loss' in tables and isinstance(tables['profit_loss'], dict):
                pl = tables['profit_loss']
                for k in ['revenue', 'ebit', 'interest_expense', 'net_profit']:
                    if k not in data['is'] or data['is'][k] is None:
                        data['is'][k] = pl.get(k)
                data['is'].update({k: pl.get(k) for k in ['cogs', 'gross_profit']})
            
            if 'balance_sheet' in tables and isinstance(tables['balance_sheet'], dict):
                bs = tables['balance_sheet']
                for k in ['total_assets', 'current_assets', 'total_liabilities', 'current_liabilities', 'equity']:
                    if k not in data['bs'] or data['bs'][k] is None:
                        data['bs'][k] = bs.get(k)
    
    return data


def calculate_ratios(bs, is_stmt):
    """Calculate financial ratios"""
    ratios = {}
    
    if is_stmt.get('revenue') and is_stmt['revenue'] > 0:
        rev = is_stmt['revenue']
        if is_stmt.get('cogs'):
            ratios['gm'] = safe_divide(rev - is_stmt['cogs'], rev)
        if is_stmt.get('ebit'):
            ratios['om'] = safe_divide(is_stmt['ebit'], rev)
        if is_stmt.get('net_profit'):
            ratios['nm'] = safe_divide(is_stmt['net_profit'], rev)
    
    if bs.get('equity') and bs['equity'] > 0 and is_stmt.get('net_profit'):
        ratios['roe'] = safe_divide(is_stmt['net_profit'], bs['equity'])
    
    if bs.get('total_assets') and bs['total_assets'] > 0 and is_stmt.get('net_profit'):
        ratios['roa'] = safe_divide(is_stmt['net_profit'], bs['total_assets'])
    
    if bs.get('equity') and bs['equity'] > 0 and bs.get('total_debt'):
        ratios['de'] = safe_divide(bs['total_debt'], bs['equity'])
    
    if is_stmt.get('interest_expense') and is_stmt['interest_expense'] > 0 and is_stmt.get('ebit'):
        ratios['ic'] = safe_divide(is_stmt['ebit'], is_stmt['interest_expense'])
    
    if bs.get('current_liabilities') and bs['current_liabilities'] > 0:
        if bs.get('current_assets'):
            ratios['cr'] = safe_divide(bs['current_assets'], bs['current_liabilities'])
        if bs.get('current_assets') and bs.get('inventory'):
            quick = bs['current_assets'] - bs['inventory']
            ratios['qr'] = safe_divide(quick, bs['current_liabilities'])
    
    return ratios


def calculate_health_score(ratios, sector_profile):
    """Calculate health score with sector-specific thresholds"""
    score = 0
    prof_thresholds = sector_profile['prof_thresholds']
    
    roe = ratios.get('roe')
    if roe:
        if roe >= prof_thresholds['excellent']:
            score += 25
        elif roe >= prof_thresholds['good']:
            score += 15
        elif roe >= prof_thresholds['fair']:
            score += 10
        else:
            score += 5
    
    de = ratios.get('de')
    de_limit = sector_profile['solv_thresholds'].get('de_limit', 1.5)
    if de is not None:
        if de <= de_limit * 0.33:
            score += 25
        elif de <= de_limit * 0.67:
            score += 15
        elif de <= de_limit:
            score += 10
        else:
            score += 5
    
    cr = ratios.get('cr')
    if cr:
        if cr >= 2.0:
            score += 25
        elif cr >= 1.5:
            score += 15
        elif cr >= 1.0:
            score += 10
        else:
            score += 5
    
    return score


def validate_accounting(bs, is_stmt, sector_profile):
    """Validate accounting with sector-specific thresholds"""
    violations = []
    warnings = []
    acc_score = 0
    
    if bs.get('equity') and bs['equity'] <= 0:
        violations.append("Negative equity")
    elif bs.get('equity'):
        acc_score += 15
    
    if bs.get('equity') and bs['equity'] > 0 and bs.get('total_debt'):
        de = bs['total_debt'] / bs['equity']
        de_limit = sector_profile['solv_thresholds'].get('de_limit', 1.5)
        if de > de_limit * 2:
            violations.append(f"D/E too high: {de:.2f}")
        elif de > de_limit:
            warnings.append(f"D/E elevated: {de:.2f}")
        else:
            acc_score += 15
    
    if bs.get('current_assets') and bs.get('current_liabilities') and bs['current_liabilities'] > 0:
        cr = bs['current_assets'] / bs['current_liabilities']
        if cr < 1.0:
            violations.append(f"Current ratio critical: {cr:.2f}")
        elif cr < 1.5:
            warnings.append(f"Current ratio low: {cr:.2f}")
        else:
            acc_score += 15
    
    if is_stmt.get('ebit') and is_stmt.get('interest_expense') and is_stmt['interest_expense'] > 0:
        ic = is_stmt['ebit'] / is_stmt['interest_expense']
        ic_min = sector_profile['solv_thresholds'].get('ic_min', 1.5)
        if ic < ic_min * 0.5:
            violations.append(f"Interest coverage critical: {ic:.2f}x")
        elif ic < ic_min:
            warnings.append(f"Interest coverage low: {ic:.2f}x")
        else:
            acc_score += 15
    
    if is_stmt.get('revenue') and is_stmt['revenue'] > 0 and is_stmt.get('net_profit'):
        margin = is_stmt['net_profit'] / is_stmt['revenue']
        if margin < -0.10:
            violations.append(f"Negative margin: {margin*100:.1f}%")
        elif margin > 0.40:
            warnings.append(f"Unusual margin: {margin*100:.1f}%")
        else:
            acc_score += 15
    
    return {
        'compliant': len(violations) == 0,
        'violations': violations,
        'warnings': warnings,
        'acc_score': min(acc_score, 100)
    }


def calculate_signal(health_score, ratios, validation, sector_profile):
    """Calculate signal with sector-specific weightages"""
    weights = sector_profile['weights']
    
    fund = min(int((health_score / 100) * weights['fundamental']), weights['fundamental'])
    tech = 15
    val = 10
    sent = 6 if validation['compliant'] else 3
    
    total = fund + tech + val + sent
    
    if total >= 80:
        signal_type, confidence = 0, 'H'
    elif total >= 60:
        signal_type, confidence = 1, 'M'
    elif total >= 40:
        signal_type, confidence = 2, 'L'
    elif total >= 20:
        signal_type, confidence = 3, 'M'
    else:
        signal_type, confidence = 4, 'H'
    
    return {
        'type': signal_type,
        'score': min(total, 100),
        'confidence': confidence,
        'weights': weights,
        'components': [fund, tech, val, sent]
    }


def compress_company(idx, ticker, company, profile, ratios, health_score, validation, signal):
    """Build compressed company record"""
    bs = profile['bs']
    is_stmt = profile['is']
    
    return {
        'id': idx,
        't': normalize_ticker(ticker),
        'n': normalize_name(company.get('name', 'Unknown')),
        'i': company.get('isin', 'Unknown'),
        's': normalize_sector(bs.get('sector', 'Unknown')),
        'f': {
            'bs': {
                'ta': int(bs.get('total_assets', 0)),
                'tl': int(bs.get('total_liabilities', 0)),
                'eq': int(bs.get('equity', 0)),
                'ca': int(bs.get('current_assets', 0)),
                'cl': int(bs.get('current_liabilities', 0)),
                'td': int(bs.get('total_debt', 0)),
            },
            'is': {
                'rev': int(is_stmt.get('revenue', 0)),
                'np': int(is_stmt.get('net_profit', 0)),
                'ebit': int(is_stmt.get('ebit', 0)),
                'ie': int(is_stmt.get('interest_expense', 0)),
            }
        },
        'r': {k: round(v, 2) for k, v in ratios.items() if v is not None},
        'h': health_score,
        'a': validation['acc_score'],
        'sg': {
            's': signal['type'],
            'sc': signal['score'],
            'cf': signal['confidence'],
            'f': signal['components']
        },
        'v': {
            'c': validation['compliant'],
            'vl': validation['violations'],
            'wn': validation['warnings']
        },
        'src': [
            'yahoofin_raw' in company,
            'screener_raw' in company,
            'screener_financials' in company,
            'yahoofin_financials' in company
        ]
    }


def compute_analytics(companies):
    """Compute pre-aggregated analytics"""
    
    by_sector = defaultdict(lambda: {
        'count': 0,
        'compliant': 0,
        'health_scores': [],
        'signal_scores': [],
        'signals': defaultdict(int)
    })
    
    by_signal = defaultdict(lambda: {
        'count': 0,
        'tickers': [],
        'sectors': defaultdict(int)
    })
    
    all_health = []
    all_signals = []
    
    for company in companies:
        sector = company['s']
        signal_type = company['sg']['s']
        ticker = company['t']
        health = company['h']
        signal_score = company['sg']['sc']
        
        by_sector[sector]['count'] += 1
        by_sector[sector]['health_scores'].append(health)
        by_sector[sector]['signal_scores'].append(signal_score)
        by_sector[sector]['signals'][signal_type] += 1
        if company['v']['c']:
            by_sector[sector]['compliant'] += 1
        
        by_signal[signal_type]['count'] += 1
        by_signal[signal_type]['tickers'].append(ticker)
        by_signal[signal_type]['sectors'][sector] += 1
        
        all_health.append(health)
        all_signals.append(signal_score)
    
    analytics = {
        'by_sector': {},
        'by_signal': {},
        'overall': {}
    }
    
    for sector, stats in by_sector.items():
        analytics['by_sector'][sector] = {
            'count': stats['count'],
            'compliant': stats['compliant'],
            'avg_health': round(sum(stats['health_scores']) / len(stats['health_scores']), 1) if stats['health_scores'] else 0,
            'avg_signal': round(sum(stats['signal_scores']) / len(stats['signal_scores']), 1) if stats['signal_scores'] else 0,
            'signals': dict(stats['signals'])
        }
    
    for signal_type, stats in by_signal.items():
        analytics['by_signal'][signal_type] = {
            'count': stats['count'],
            'tickers': stats['tickers'],
            'sectors': dict(stats['sectors'])
        }
    
    analytics['overall'] = {
        'total': len(companies),
        'compliant': sum(1 for c in companies if c['v']['c']),
        'avg_health': round(sum(all_health) / len(all_health), 1) if all_health else 0,
        'avg_signal': round(sum(all_signals) / len(all_signals), 1) if all_signals else 0,
        'signals': [
            sum(1 for c in companies if c['sg']['s'] == i) for i in range(5)
        ]
    }
    
    return analytics


# ============================================================================
# MAIN EXECUTION (ROOT-RELATIVE PATHS)
# ============================================================================

def main():
    """Main execution - build canonical JSON"""
    
    logger, log_file = setup_logging()
    
    logger.info("=" * 120)
    logger.info("CANONICAL JSON GENERATION (GitHub Workflow)")
    logger.info("Sector-aware processing with optimized output structure")
    logger.info("=" * 120)
    
    print(f"\n📊 CANONICAL JSON GENERATION")
    print(f"{'='*100}")
    
    # Load input (root-relative path)
    print(f"\n📥 Loading raw market data...")
    input_file = Path("data/raw_market_data.json")
    
    if not input_file.exists():
        print(f"❌ Input file not found: {input_file}")
        logger.error(f"Input file not found: {input_file}")
        return False
    
    raw_data = load_json(str(input_file))
    
    # Debug output
    if not raw_data:
        print(f"❌ Failed to load JSON - file is empty or invalid")
        logger.error("Failed to load JSON - file is empty or invalid")
        return False
    
    print(f"✓ JSON loaded successfully")
    print(f"  Keys in file: {list(raw_data.keys())}")
    logger.info(f"File keys: {list(raw_data.keys())}")
    
    # Try different possible structures
    if 'data' in raw_data:
        companies_raw = raw_data['data']
    elif 'companies' in raw_data:
        companies_raw = raw_data['companies']
    elif isinstance(raw_data, dict) and len(raw_data) > 0:
        # Try first key
        first_key = list(raw_data.keys())[0]
        if isinstance(raw_data[first_key], dict):
            companies_raw = {first_key: raw_data[first_key]}
        else:
            companies_raw = raw_data
    else:
        print(f"❌ Cannot find companies data in file")
        print(f"❌ File structure: {type(raw_data)}")
        if isinstance(raw_data, dict):
            print(f"❌ Keys: {list(raw_data.keys())}")
        logger.error(f"Cannot find companies data - structure unknown")
        return False
    
    if not isinstance(companies_raw, dict) or len(companies_raw) == 0:
        print(f"❌ No companies found in data")
        print(f"❌ Type: {type(companies_raw)}, Length: {len(companies_raw) if hasattr(companies_raw, '__len__') else 'unknown'}")
        logger.error("No companies found in data")
        return False
    
    print(f"✓ Loaded {len(companies_raw)} companies")
    logger.info(f"Loaded {len(companies_raw)} companies")
    
    # Process companies
    print(f"\n🔄 Processing (sector-aware: validate + normalize + signal)...")
    logger.info("Processing all companies...")
    
    companies = []
    indexes = {
        'ticker': {},
        'sector': defaultdict(list),
        'signal': defaultdict(list)
    }
    
    for idx, (ticker, company) in enumerate(companies_raw.items()):
        try:
            profile = extract_and_normalize_data(company)
            bs = profile['bs']
            is_stmt = profile['is']
            
            sector = normalize_sector(bs.get('sector', 'Unknown'))
            sector_profile = SECTOR_PROFILES.get(sector, SECTOR_PROFILES['Unknown'])
            
            ratios = calculate_ratios(bs, is_stmt)
            health_score = calculate_health_score(ratios, sector_profile)
            validation = validate_accounting(bs, is_stmt, sector_profile)
            signal = calculate_signal(health_score, ratios, validation, sector_profile)
            
            company_rec = compress_company(idx, ticker, company, profile, ratios, health_score, validation, signal)
            companies.append(company_rec)
            
            indexes['ticker'][ticker] = idx
            indexes['sector'][sector].append(idx)
            indexes['signal'][signal['type']].append(idx)
            
            if (idx + 1) % 20 == 0:
                print(f"  Progress: {idx + 1}/{len(companies_raw)}")
        
        except Exception as e:
            logger.warning(f"Error processing {ticker}: {str(e)}")
    
    print(f"✓ Processed {len(companies)} companies")
    logger.info(f"Processed {len(companies)} companies")
    
    # Safety check
    if len(companies) == 0:
        print(f"❌ No companies processed!")
        print(f"❌ Check that data/raw_market_data.json exists and has 'data' key")
        logger.error("No companies processed - raw_market_data.json may be invalid")
        return False
    
    # Compute analytics
    print(f"\n📊 Computing analytics...")
    analytics = compute_analytics(companies)
    
    # Build canonical JSON
    print(f"\n💾 Building canonical JSON...")
    
    canonical = {
        '_meta': {
            'version': '1.0',
            'canonical': True,
            'generated': datetime.now(timezone.utc).isoformat(),
            'processing_method': 'SECTOR-AWARE',
            'records': len(companies),
            'compliant': analytics['overall']['compliant'],
            'format_notes': 'Optimized for analysis & sector queries'
        },
        '_index': {
            'ticker': indexes['ticker'],
            'sector': dict(indexes['sector']),
            'signal': dict(indexes['signal'])
        },
        'companies': companies,
        '_analytics': analytics
    }
    
    # Save canonical JSON (root-relative path)
    output_file = Path("data/market_data.json")
    if not save_json(str(output_file), canonical):
        logger.error("Failed to save canonical JSON")
        return False
    
    print(f"✓ Canonical JSON: {output_file}")
    logger.info(f"Canonical JSON saved: {output_file}")
    
    # Summary
    print(f"\n{'='*100}")
    print("CANONICAL JSON GENERATION COMPLETE")
    print(f"{'='*100}")
    
    print(f"\n📊 COVERAGE:")
    total = analytics['overall']['total']
    if total > 0:
        compliant = analytics['overall']['compliant']
        print(f"  Total: {total}")
        print(f"  Compliant: {compliant} ({compliant/total*100:.1f}%)")
        print(f"  Avg Health: {analytics['overall']['avg_health']:.1f}/100")
        print(f"  Avg Signal: {analytics['overall']['avg_signal']:.1f}/100")
    else:
        print(f"  ❌ No data to process")
    
    print(f"\n🔔 SIGNAL DISTRIBUTION:")
    signal_names = ['STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL']
    if total > 0:
        for i, count in enumerate(analytics['overall']['signals']):
            pct = count / total * 100
            print(f"  {signal_names[i]:12s}: {count:3d} ({pct:5.1f}%)")
    else:
        print(f"  ❌ No signals to display")
    
    print(f"\n✅ CANONICAL JSON READY!")
    
    logger.info(f"Total: {len(companies)}, Compliant: {analytics['overall']['compliant']}")
    logger.info(f"Signals: {analytics['overall']['signals']}")
    logger.info("Status: SUCCESS ✓")
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
