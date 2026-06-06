#!/usr/bin/env python3
"""
BharatMarkets Onyx Pro Terminal - Multi-Ticker Data Pipeline
Dynamically processes all tickers from prices.json without hardcoding
All logs written to file for GitHub workflow
Headers preserve exact source names (no underscore stripping)
"""

import json
import re
import os
import sys
from datetime import datetime
from collections import OrderedDict
from pathlib import Path

# ===== CONFIGURATION =====
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / 'data'
LOGS_DIR = DATA_DIR / 'logs'

LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ===== LOGGING SETUP =====
LOG_FILE = LOGS_DIR / 'market_data_flatten.log'

class Logger:
    """Write all logs to file (for GitHub workflow)"""
    def __init__(self, log_path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        # Initialize log file
        with open(self.log_path, 'w') as f:
            f.write(f"{'='*120}\n")
            f.write(f"BharatMarkets Onyx Pro Terminal - Pipeline Execution Log\n")
            f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"{'='*120}\n\n")
    
    def write(self, message, category='INFO'):
        """Write message to log file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.log_path, 'a') as f:
            f.write(f"[{timestamp}] [{category:10}] {message}\n")
    
    def write_section(self, title):
        """Write section header"""
        with open(self.log_path, 'a') as f:
            f.write(f"\n{'='*120}\n{title}\n{'='*120}\n")
    
    def write_rejection(self, ticker, source, metric, reason, details=''):
        """Log rejected metric"""
        msg = f"{ticker:15} | {source:15} | {metric:40} | {reason}"
        if details:
            msg += f" | {details}"
        self.write(msg, 'REJECTION')
    
    def write_error(self, ticker, source, metric, error_msg):
        """Log error"""
        msg = f"{ticker:15} | {source:15} | {metric:40} | {error_msg}"
        self.write(msg, 'ERROR')
    
    def write_ticker_start(self, ticker):
        """Log start of ticker processing"""
        self.write(f"\n>>> Processing {ticker}", 'TICKER')
    
    def write_ticker_summary(self, ticker, sections_count, metrics_loaded, rejections_list, errors_list):
        """Write ticker processing summary"""
        self.write(f"\n✓ {ticker} - Loaded {metrics_loaded} metrics across {sections_count} sections", 'SUCCESS')
        
        if rejections_list:
            self.write(f"  Rejections: {len(rejections_list)}", 'SUMMARY')
            for r in rejections_list[:10]:
                self.write(f"    - {r}", 'DETAIL')
            if len(rejections_list) > 10:
                self.write(f"    ... and {len(rejections_list)-10} more", 'DETAIL')
        
        if errors_list:
            self.write(f"  Errors: {len(errors_list)}", 'SUMMARY')
            for e in errors_list[:10]:
                self.write(f"    - {e}", 'DETAIL')
            if len(errors_list) > 10:
                self.write(f"    ... and {len(errors_list)-10} more", 'DETAIL')
    
    def write_final_summary(self, total_tickers, output_file_size):
        """Write final execution summary"""
        self.write_section("FINAL SUMMARY")
        self.write(f"Processed {total_tickers} tickers successfully", 'COMPLETE')
        self.write(f"Output file size: {output_file_size} bytes", 'COMPLETE')
        self.write(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 'COMPLETE')

logger = Logger(LOG_FILE)

# Read tickers from prices.json dynamically
logger.write_section("INITIALIZATION")
logger.write("Reading tickers from screener_raw_data.json", 'INIT')

# Try to get tickers from screener_raw first, then prices as fallback
try:
    with open(DATA_DIR / 'screener_raw_data.json') as f:
        screener_raw_file = json.load(f)
    TICKERS_TO_PROCESS = list(screener_raw_file.keys())
    if TICKERS_TO_PROCESS:
        logger.write(f"Found {len(TICKERS_TO_PROCESS)} tickers from screener_raw", 'INIT')
    else:
        raise ValueError("screener_raw is empty")
except:
    with open(DATA_DIR / 'prices.json') as f:
        prices_file = json.load(f)
    prices_data = prices_file.get("quotes", {})
    TICKERS_TO_PROCESS = list(prices_data.keys())
    logger.write(f"Found {len(TICKERS_TO_PROCESS)} tickers from prices.json", 'INIT')

logger.write(f"Processing tickers: {', '.join(TICKERS_TO_PROCESS)}", 'INIT')
logger.write(f"Input directory: {DATA_DIR}", 'INIT')
logger.write(f"Output: {DATA_DIR / 'market_data_raw.json'}", 'INIT')

# Console output (minimal)
print(f"Pipeline running... Check {LOG_FILE} for detailed logs")
print(f"Processing {len(TICKERS_TO_PROCESS)} tickers: {', '.join(TICKERS_TO_PROCESS)}")

TODAY = datetime.now().strftime('%Y-%m-%d')

# ===== UTILITY FUNCTIONS =====
def parse_period_to_iso(period_str):
    """Convert period strings (Jun 2023, Mar 2026) to ISO 8601 (2023-06-01).
    Strips whitespace/newlines from Screener labels like 'Mar 2016\\n  9m'."""
    try:
        # Collapse all whitespace — handles multiline Screener labels like 'Mar 2016\n  9m'
        clean = ' '.join(str(period_str).split())
        # Only accept clean 2-word patterns (Mon YYYY); reject labels with extra tokens
        parts = clean.split()
        if len(parts) == 2:
            months = {'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
                     'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'}
            if parts[0] in months and parts[1].isdigit() and len(parts[1]) == 4:
                return f"{parts[1]}-{months[parts[0]]}-01"
            elif parts[1] in months and parts[0].isdigit() and len(parts[0]) == 4:
                return f"{parts[0]}-{months[parts[1]]}-01"
        # More than 2 tokens (e.g. 'Mar 2016 9m') → reject as malformed
    except Exception as e:
        logger.write_error('UTIL', 'parse_period', period_str, f"Parse error: {str(e)}")
    return None

def parse_datetime_to_iso(date_str):
    """Convert datetime to ISO 8601 date"""
    try:
        if isinstance(date_str, str):
            if ' ' in date_str:
                dt = datetime.strptime(date_str.split('+')[0].strip(), '%Y-%m-%d %H:%M:%S')
                return dt.strftime('%Y-%m-%d')
            else:
                return date_str[:10]
    except Exception as e:
        logger.write_error('UTIL', 'parse_datetime', date_str, str(e))
    return date_str

def standardize_value(value):
    """Convert numeric strings to float. Strips commas and % signs. Empty strings → None."""
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        cleaned = value.replace(',', '').strip()
        if cleaned == '':
            return None
        # Strip trailing % — store as float (e.g. '68.51%' → 68.51, '20%' → 20.0)
        if cleaned.endswith('%'):
            cleaned = cleaned[:-1]
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            pass
    return value

def sort_array_by_date(values_array):
    """Sort OHLCV array by Date descending (latest first)"""
    if not isinstance(values_array, list):
        return values_array
    try:
        return sorted(values_array, key=lambda x: x.get('Date', ''), reverse=True)
    except Exception as e:
        logger.write_error('UTIL', 'sort_array_by_date', 'array', str(e))
        return values_array

def standardize_array_dates(values_array):
    """Standardize dates in array records"""
    if not isinstance(values_array, list):
        return values_array
    for record in values_array:
        if isinstance(record, dict) and 'Date' in record:
            record['Date'] = parse_datetime_to_iso(record['Date'])
    return values_array

# No categorization - load raw data only from source

def clean_metric_names(obj):
    """Clean metric names - remove non-breaking spaces only"""
    if isinstance(obj, dict):
        cleaned_dict = {}
        for k, v in obj.items():
            # Preserve exact keys as they appear in input - NO normalization
            cleaned_key = k
            
            cleaned_value = clean_metric_names(v)
            
            if isinstance(cleaned_value, dict) and 'metric' in cleaned_value:
                # Preserve exact metric names from input - NO normalization
                cleaned_value['metric'] = cleaned_value['metric']
            
            cleaned_dict[cleaned_key] = cleaned_value
        return cleaned_dict
    
    elif isinstance(obj, list):
        cleaned_list = []
        for item in obj:
            cleaned_item = clean_metric_names(item)
            if isinstance(cleaned_item, dict) and 'metric' in cleaned_item:
                # Preserve exact metric names from input - NO normalization
                cleaned_item['metric'] = cleaned_item['metric']
            cleaned_list.append(cleaned_item)
        return cleaned_list
    
    else:
        return obj

# ===== LOAD DATA FOR ALL TICKERS =====
def load_all_data():
    """Load all source files - these are ticker-independent"""
    logger.write_section("LOADING SOURCE FILES")
    
    data = {}
    files = {
        'screener_fin': DATA_DIR / 'screener_financials.json',
        'screener_raw': DATA_DIR / 'screener_raw_data.json',
        'yahoofin_fin': DATA_DIR / 'yahoofin_financials.json',
        'yahoofin_raw': DATA_DIR / 'yahoofin_raw_data.json',
        'guidance': DATA_DIR / 'guidance.json',
        'prices': DATA_DIR / 'prices.json',
        'unified_symbols': DATA_DIR / 'unified-symbols.json',
    }
    
    for source, filepath in files.items():
        try:
            if filepath.exists():
                with open(filepath) as f:
                    data[source] = json.load(f)
                logger.write(f"✓ Loaded {source:20} ({len(data[source])} keys)", 'LOAD')
            else:
                data[source] = {}
                logger.write(f"⚠ Missing {source:20} (file not found)", 'WARN')
        except Exception as e:
            data[source] = {}
            logger.write_error('LOADER', source, filepath.name, f"Load failed: {str(e)}")
    
    return data

# ===== PROCESS ALL TICKERS =====
logger.write_section("DATA PROCESSING")
all_data = load_all_data()

# Extract quotes from prices (has metadata wrapper)
if "prices" in all_data:
    prices_file = all_data["prices"]
    all_data["prices"] = prices_file.get("quotes", {})

output_all = {}
total_rejections = 0
total_errors = 0

for TICKER in TICKERS_TO_PROCESS:
    logger.write_ticker_start(TICKER)
    
    output = {TICKER: {'data': {}}}
    metrics = {}
    ticker_rejections = []
    ticker_errors = []
    
    try:
        # === SCREENER FINANCIALS ===
        # Original structure: all_data['screener_fin']['data'][TICKER]['tables'][table_name]
        # Sample structure: all_data['screener_fin'][TICKER]['tables'][table_name]
        sf = all_data.get('screener_fin', {})
        
        # Handle both original and sample formats
        if 'data' in sf:
            # Original format
            sf = sf['data'].get(TICKER, {})
        else:
            # Sample format
            sf = sf.get(TICKER, {})
            
        tables = sf.get('tables', {})
        for table_name, table_data in tables.items():
            # Insights table is paywalled — all values are masked (xxx,xxx). Skip entirely.
            if table_name == 'insights':
                ticker_rejections.append(f"screener_fin | insights | Paywalled — excluded")
                continue
            table_dict = table_data.get('data', {}) if isinstance(table_data, dict) and 'data' in table_data else table_data
            for metric_name, period_data in table_dict.items():
                try:
                    if metric_name and metric_name.strip():
                        # Collect periods first
                        temp_periods = {}
                        for period, value in (period_data.items() if isinstance(period_data, dict) else []):
                            iso = parse_period_to_iso(period)
                            if iso:
                                temp_periods[iso] = standardize_value(value)
                            else:
                                temp_periods[str(period)] = standardize_value(value)
                        
                        # screener_fin granularity: quarterly_results is quarterly,
                        # all other sections (profit_loss, balance_sheet, cash_flow,
                        # ratios, shareholding_pattern) are annual consolidated.
                        if table_name == 'quarterly_results':
                            granule = 'quarterly'
                        else:
                            granule = 'annual'
                        
                        # screener_fin = consolidated
                        consol = 'consolidated'
                        
                        key = f"{metric_name}|{table_name}|{granule}|{consol}"
                        if key not in metrics:
                            metrics[key] = {'metric': metric_name, 'section': table_name, 'granule': granule, 'consolidation': consol, 'source': 'screener_fin', 'periods': temp_periods}
                        else:
                            metrics[key]['periods'].update(temp_periods)
                    else:
                        ticker_rejections.append(f"screener_fin | {table_name} | Empty metric name")
                except Exception as e:
                    ticker_errors.append(f"screener_fin | {table_name} | {metric_name} | {str(e)}")
                    logger.write_error(TICKER, 'screener_fin', metric_name, str(e))
        
        # === SCREENER RAW ===
        sr = all_data.get('screener_raw', {}).get(TICKER, {})
        sr_obs = sr.get('observations', [{}])[0].get('raw', {})
        for table in sr_obs.get('tables', []):
            section = table.get('section', '')
            
            # Insights is paywalled — values are masked xxx,xxx strings. Skip entirely.
            if section == 'Insights':
                ticker_rejections.append(f"screener_raw | Insights | Paywalled — excluded")
                continue
            
            rows = table.get('rows', [])
            for row in rows[1:]:
                try:
                    if row and row[0] and row[0].strip():
                        metric_name = row[0]
                        
                        # Raw PDF is always empty across all tickers — skip
                        if metric_name == 'Raw PDF':
                            ticker_rejections.append(f"screener_raw | {section} | Raw PDF — always empty, excluded")
                            continue
                        
                        # Collect periods first
                        temp_periods = {}
                        for col_idx in range(1, min(len(rows[0]), len(row))):
                            iso = parse_period_to_iso(rows[0][col_idx])
                            if iso:
                                temp_periods[iso] = standardize_value(row[col_idx])
                        
                        # Detect granularity from section name
                        if 'Quarterly' in section:
                            granule = 'quarterly'
                        elif 'Half Yearly' in section:
                            granule = 'half_yearly'
                        elif 'Shareholding' in section:
                            granule = 'quarterly'  # shareholding is reported quarterly
                        elif 'Profit' in section or 'Balance' in section or 'Cash' in section or 'Ratios' in section:
                            granule = 'annual'
                        else:
                            # Fallback: detect from dates
                            from datetime import datetime
                            months_seen = set()
                            for date_key in temp_periods.keys():
                                try:
                                    dt = datetime.fromisoformat(date_key[:10])
                                    months_seen.add(dt.month)
                                except:
                                    pass
                            
                            # A single month across all periods = annual data.
                            # Covers Mar (Indian FY), Dec (calendar FY), Sep, Jun year-ends.
                            if len(months_seen) == 1:
                                granule = 'annual'
                            elif {3, 6, 9, 12} <= months_seen:
                                granule = 'quarterly'
                            elif months_seen == {3, 9} or months_seen == {6, 12}:
                                granule = 'half_yearly'
                            else:
                                granule = 'other'
                        
                        # Determine consolidation type based on SOURCE
                        # screener_raw = standalone, screener_fin = consolidated
                        consol = 'standalone'  # screener_raw is always standalone
                        
                        # Create section key with granularity and consolidation
                        key = f"{metric_name}|{section}|{granule}|{consol}"
                        if key not in metrics:
                            metrics[key] = {'metric': metric_name, 'section': section, 'granule': granule, 'consolidation': consol, 'source': 'screener_raw', 'periods': temp_periods}
                        else:
                            metrics[key]['periods'].update(temp_periods)
                    else:
                        ticker_rejections.append(f"screener_raw | {section} | Empty metric")
                except Exception as e:
                    ticker_errors.append(f"screener_raw | {section} | {metric_name} | Error: {str(e)}")
                    logger.write_error(TICKER, 'screener_raw', section, str(e))
        
        # === YAHOOFIN FINANCIALS ===
        # Yahoo financial values are in absolute INR (e.g. 173900000000).
        # Screener values are in Crores (1 Crore = 1e7).
        # Convert Yahoo → Crores by dividing by 1e7 so units are uniform.
        # Yahoo financials = CONSOLIDATED view (matches screener_fin, not screener_raw).
        #
        # EXCEPTION: A few tickers (e.g. INFY) have Yahoo returning values in USD
        # despite financialCurrency sometimes showing as USD for others too.
        # Detect by ratio: if Yahoo revenue after /1e7 is >20x smaller than Screener Sales,
        # the values are in a different currency — skip Yahoo fin gap-fill for this ticker.
        def _get_screener_latest_sales():
            """Get latest Screener consolidated annual Sales for sanity check."""
            for key, m in metrics.items():
                if m.get('metric') in ('Sales\xa0+', 'Sales +', 'Revenue\xa0+', 'Revenue +') \
                        and m.get('consolidation') == 'consolidated' \
                        and m.get('granule') == 'annual':
                    periods = m.get('periods', {})
                    valid = {d: v for d, v in periods.items() if len(d) == 10 and isinstance(v, (int, float))}
                    if valid:
                        return sorted(valid.values(), reverse=True)[0]
            return None

        SKIP_YF_FIN = False
        yf = all_data.get('yahoofin_fin', {}).get(TICKER, {})
        raw = yf.get('observations', [{}])[0].get('raw', {}) if yf.get('observations') else {}
        yf_raw_revenue = None
        for hp in raw.get('historical_periods', [])[:1]:
            r = hp.get('revenue') or hp.get('net_profit')
            if r:
                try:
                    yf_raw_revenue = float(r) / 1e7
                except (TypeError, ValueError):
                    pass
        if yf_raw_revenue:
            sc_sales = _get_screener_latest_sales()
            if sc_sales and sc_sales > 0:
                ratio = sc_sales / yf_raw_revenue
                if ratio > 20:
                    SKIP_YF_FIN = True
                    logger.write(f"{TICKER} | Yahoo fin values appear to be in USD (ratio={ratio:.0f}x) — skipping gap-fill", 'WARN')
        YAHOO_FIN_RATIO_FIELDS = {
            'tax_rate', 'diluted_eps', 'basic_eps', 'diluted_shares', 'basic_shares',
            'shares_outstanding', 'total_capitalization'
        }
        # Fields that are per-share or counts — store as-is (no Crore conversion)
        YAHOO_FIN_PERUNIT_FIELDS = {
            'diluted_eps', 'basic_eps', 'diluted_shares', 'basic_shares',
            'shares_outstanding', 'tax_rate'
        }

        def yahoo_fin_value(k, v):
            """Convert Yahoo financial value to Crores where applicable"""
            if v is None or v == '':
                return v
            try:
                fv = float(v)
                if k in YAHOO_FIN_PERUNIT_FIELDS:
                    return fv  # ratios/per-share — no conversion
                return round(fv / 1e7, 2)  # absolute INR → Crores
            except (TypeError, ValueError):
                return v

        if not SKIP_YF_FIN:
            # --- latest snapshot ---
            for k, v in raw.get('latest', {}).items():
                try:
                    if k and k.strip() and k not in ['industryKey', 'industryDisp', 'sectorKey', 'sectorDisp', 'resolved_ticker', 'sector', 'status']:
                        metrics[f"{k}|latest"] = {
                            'metric': k,
                            'section': 'latest',
                            'source': 'yahoofin_fin',
                            'consolidation': 'consolidated',
                            'value': yahoo_fin_value(k, v)
                        }
                    elif k in ['industryKey', 'industryDisp', 'sectorKey', 'sectorDisp']:
                        ticker_rejections.append(f"yahoofin_fin | latest | Excluded metadata key: {k}")
                except Exception as e:
                    ticker_errors.append(f"yahoofin_fin | latest | {k} | {str(e)}")
                    logger.write_error(TICKER, 'yahoofin_fin', k, str(e))

            # --- historical_periods: build per-metric time-series (consolidated annual) ---
            for hp_item in raw.get('historical_periods', []):
                try:
                    period_date = hp_item.get('period')
                    if not period_date:
                        continue
                    iso_date = parse_datetime_to_iso(str(period_date))
                    for k, v in hp_item.items():
                        if k == 'period' or not k or not k.strip():
                            continue
                        metric_key = f"{k}|historical"
                        if metric_key not in metrics:
                            metrics[metric_key] = {
                                'metric': k,
                                'section': 'historical',
                                'source': 'yahoofin_fin',
                                'consolidation': 'consolidated',
                                'granule': 'annual',
                                'periods': {}
                            }
                        metrics[metric_key]['periods'][iso_date] = yahoo_fin_value(k, v)
                except Exception as e:
                    ticker_errors.append(f"yahoofin_fin | historical_periods | {str(e)}")
                    logger.write_error(TICKER, 'yahoofin_fin', 'historical_periods', str(e))
        
        # === YAHOOFIN RAW ===
        yr = all_data.get('yahoofin_raw', {}).get(TICKER, {})
        for k, v in yr.items():
            try:
                if k != 'observations' and k and k.strip():
                    metrics[f"{k}|metadata"] = {'metric': k, 'section': 'metadata', 'source': 'yahoofin_raw', 'value': standardize_value(v)}
            except Exception as e:
                ticker_errors.append(f"yahoofin_raw | metadata | {k} | {str(e)}")
                logger.write_error(TICKER, 'yahoofin_raw', k, str(e))
        
        obs = yr.get('observations', [])
        if obs:
            raw = obs[0].get('raw', {})
            
            # Yahoo info field sub-groups — tag each field with its category
            # so market_data.py can route them to the correct bucket.
            # Fields not in any group go to 'info' (catch-all).
            INFO_FIELD_GROUPS = {
                # valuation ratios
                'trailingPE': 'valuation', 'forwardPE': 'valuation',
                'priceToBook': 'valuation', 'enterpriseValue': 'valuation',
                'enterpriseToRevenue': 'valuation', 'enterpriseToEbitda': 'valuation',
                'pegRatio': 'valuation', 'priceToSalesTrailing12Months': 'valuation',
                # analyst targets
                'targetHighPrice': 'analyst', 'targetLowPrice': 'analyst',
                'targetMeanPrice': 'analyst', 'targetMedianPrice': 'analyst',
                'recommendationKey': 'analyst', 'numberOfAnalystOpinions': 'analyst',
                # margins
                'profitMargins': 'margins', 'grossMargins': 'margins',
                'ebitdaMargins': 'margins', 'operatingMargins': 'margins',
                # growth
                'earningsGrowth': 'growth', 'revenueGrowth': 'growth',
                'earningsQuarterlyGrowth': 'growth',
                # financial ratios
                'returnOnAssets': 'ratios', 'returnOnEquity': 'ratios',
                'debtToEquity': 'ratios', 'quickRatio': 'ratios',
                'currentRatio': 'ratios', 'revenuePerShare': 'ratios',
                'totalCashPerShare': 'ratios',
                # share data
                'floatShares': 'share_data', 'sharesOutstanding': 'share_data',
                'heldPercentInsiders': 'share_data', 'heldPercentInstitutions': 'share_data',
                'impliedSharesOutstanding': 'share_data', 'bookValue': 'share_data',
                # dividends
                'dividendRate': 'dividends', 'dividendYield': 'dividends',
                'exDividendDate': 'dividends', 'payoutRatio': 'dividends',
                'fiveYearAvgDividendYield': 'dividends',
                'trailingAnnualDividendRate': 'dividends',
                'trailingAnnualDividendYield': 'dividends',
                # earnings dates
                'earningsTimestamp': 'earnings_dates',
                'earningsTimestampStart': 'earnings_dates',
                'earningsTimestampEnd': 'earnings_dates',
                'earningsCallTimestampStart': 'earnings_dates',
                'earningsCallTimestampEnd': 'earnings_dates',
                # governance risk scores
                'auditRisk': 'risk_scores', 'boardRisk': 'risk_scores',
                'compensationRisk': 'risk_scores',
                'shareHolderRightsRisk': 'risk_scores', 'overallRisk': 'risk_scores',
            }
            # Fields to skip entirely from info
            INFO_SKIP_FIELDS = {
                'industryKey', 'sectorKey', 'maxAge', 'executiveTeam',
                'language', 'region', 'quoteSourceName', 'messageBoardId',
                'esgPopulated', 'triggerable', 'customPriceAlertConfidence',
                'cryptoTradeable', 'tradeable', 'sourceInterval',
                'exchangeDataDelayedBy', 'gmtOffSetMilliseconds',
                'hasPrePostMarketData', 'priceHint',
            }

            for k, v in raw.get('info', {}).items():
                try:
                    if not k or not k.strip() or k in INFO_SKIP_FIELDS:
                        if k not in INFO_SKIP_FIELDS:
                            ticker_rejections.append(f"yahoofin_raw | info | Empty field name")
                        continue

                    sub_section = INFO_FIELD_GROUPS.get(k, 'info')
                    metric_key = f"{k}|{sub_section}"

                    if isinstance(v, (list, dict)):
                        metrics[metric_key] = {'metric': k, 'section': sub_section,
                                               'source': 'yahoofin_raw', 'value': v}
                    else:
                        metrics[metric_key] = {'metric': k, 'section': sub_section,
                                               'source': 'yahoofin_raw',
                                               'value': standardize_value(v)}
                except Exception as e:
                    ticker_errors.append(f"yahoofin_raw | info | {k} | {str(e)}")
                    logger.write_error(TICKER, 'yahoofin_raw', k, str(e))
            
            # Canonical output keys — structure never changes regardless of 5yr/10yr input.
            # history_6mo_1d → history_6mo_1d  (daily, always present)
            # history_5y_1wk / history_10y_1wk → history_1wk  (weekly, whichever is present)
            # history_5y_1mo / history_10y_1mo → history_1mo  (monthly, whichever is present)
            HISTORY_CANONICAL = {
                'history_6mo_1d':  'history_6mo_1d',
                'history_5y_1wk':  'history_1wk',
                'history_10y_1wk': 'history_1wk',
                'history_5y_1mo':  'history_1mo',
                'history_10y_1mo': 'history_1mo',
            }
            OHLCV_COLS = {
                'Open':   'open',
                'High':   'high',
                'Low':    'low',
                'Close':  'close',
                'Volume': 'volume',
            }
            for section_key, canonical_key in HISTORY_CANONICAL.items():
                try:
                    history = raw.get(section_key, [])
                    if not history:
                        continue
                    standardized = standardize_array_dates(history)
                    sorted_hist  = sort_array_by_date(standardized)

                    # One metric row per OHLCV column — {date: value} periods dict
                    for col, col_key in OHLCV_COLS.items():
                        periods = {}
                        for bar in sorted_hist:
                            date = bar.get('Date', '')
                            if not date or len(date) != 10:
                                continue
                            raw_val = bar.get(col)
                            if raw_val is None:
                                continue
                            try:
                                v = int(float(raw_val)) if col == 'Volume' else round(float(raw_val), 2)
                            except (ValueError, TypeError):
                                continue
                            periods[date] = v
                        if periods:
                            mk = f"{canonical_key}|{col_key}"
                            metrics[mk] = {
                                'metric':        col_key,
                                'section':       canonical_key,
                                'source':        'yahoofin_raw',
                                'granule':       'daily' if '1d' in canonical_key else 'weekly' if '1wk' in canonical_key else 'monthly',
                                'consolidation': 'consolidated',
                                'periods':       periods,
                            }
                except Exception as e:
                    ticker_errors.append(f"yahoofin_raw | {section_key} | {str(e)}")
                    logger.write_error(TICKER, 'yahoofin_raw', section_key, str(e))
        
        # === GUIDANCE ===
        guidance = all_data.get('guidance', {}).get(TICKER, {})
        for category in ['guidance', 'insights']:
            try:
                cat_data = guidance.get(category, {})
                if isinstance(cat_data, dict):
                    for k, v in cat_data.items():
                        if k and k.strip():
                            metrics[f"{k}|{category}"] = {'metric': k, 'section': category, 'source': 'guidance', 'value': v}
                elif isinstance(cat_data, list):
                    # List format: store each item indexed by position
                    for i, item in enumerate(cat_data):
                        k = f"{category}_{i}"
                        metrics[f"{k}|{category}"] = {'metric': k, 'section': category, 'source': 'guidance', 'value': item}
            except Exception as e:
                ticker_errors.append(f"guidance | {category} | {str(e)}")
                logger.write_error(TICKER, 'guidance', category, str(e))
        
        # === UNIFIED SYMBOLS ===
        try:
            us = all_data.get('unified_symbols', {})
            us_ticker = next((s for s in us.get('symbols', []) if s.get('ticker') == TICKER), {})
            for k, v in us_ticker.items():
                metrics[f"{k}|metadata"] = {'metric': k, 'section': 'metadata', 'source': 'unified_symbols', 'value': standardize_value(v)}
        except Exception as e:
            ticker_errors.append(f"unified_symbols | {str(e)}")
            logger.write_error(TICKER, 'unified_symbols', 'symbols', str(e))
        
        # === TRANSFORM TO OUTPUT ===
        # One row per logical metric name. All flavours (consolidation, granularity,
        # source) are merged into a single row:
        #   {
        #     "metric": "eps",
        #     "periods": {
        #       "consolidated": {"annual": {date:val}, "quarterly": {date:val}},
        #       "standalone":   {"annual": {date:val}, "quarterly": {date:val}}
        #     }
        #   }
        # Scalar fields (value only, no periods) stored as {metric: value} flat dict.
        # History (OHLCV) stored as list of {metric, periods} rows per column.

        # Group metrics by their canonical name (strip section/source prefix)
        merged = {}   # canonical_name → merged row
        scalars = {}  # section_key → {field: value}  (info, metadata, etc.)

        for key, obj in metrics.items():
            source      = obj.get('source', 'unknown')
            section_name = obj['section']
            granule     = obj.get('granule', '')
            consol      = obj.get('consolidation', '')
            metric_name = obj['metric']

            # ── Scalar (single value, no periods) ────────────────────────────
            if 'value' in obj and 'periods' not in obj:
                sec_key = f"{source}:{section_name}"
                if sec_key not in scalars:
                    scalars[sec_key] = {}
                scalars[sec_key][metric_name] = obj['value']
                continue

            # ── Time-series (has periods) ─────────────────────────────────────
            if not obj.get('periods'):
                continue

            periods_data = OrderedDict(sorted(obj['periods'].items(), reverse=True))

            # Canonical key: normalise metric name — strip \xa0 (non-breaking space),
            # trailing + decorators, and whitespace so all flavours merge into one row
            canon = metric_name.replace('\xa0+','').replace('\xa0','').replace('+','').strip()

            if canon not in merged:
                merged[canon] = {
                    'metric':  canon,
                    'periods': {},
                    'sources': set(),
                }

            row = merged[canon]
            row['sources'].add(source)

            if consol and granule:
                # Nested: periods[consolidation][granularity] = {date: val}
                if consol not in row['periods']:
                    row['periods'][consol] = {}
                existing = row['periods'][consol].get(granule, {})
                # Merge — Screener (month-start dates) wins over Yahoo period-end
                from_ym = {d[:7] for d in existing}
                for d, v in periods_data.items():
                    if d[:7] not in from_ym:
                        existing[d] = v
                        from_ym.add(d[:7])
                row['periods'][consol][granule] = dict(
                    sorted(existing.items(), reverse=True)
                )
            else:
                # No consolidation — flat {date: val} (history OHLCV columns)
                row['periods'].update(periods_data)

        # Write merged rows to output — one list per logical section group
        # Group by primary source for the section key
        SECTION_MAP = {
            # Screener financial sections → one section key
            'Profit & Loss':         'financials',
            'Balance Sheet':         'financials',
            'Cash Flows':            'financials',
            'Quarterly Results':     'financials',
            'profit_loss':           'financials',
            'balance_sheet':         'financials',
            'cash_flow':             'financials',
            'quarterly_results':     'financials',
            'Ratios':                'ratios',
            'ratios':                'ratios',
            'Shareholding Pattern':  'shareholding',
            'shareholding_pattern':  'shareholding',
        }

        # Build section_key → [rows] from merged
        section_rows = {}
        for canon, row in merged.items():
            # Find original section name — search with normalised metric name
            def _norm(s):
                return s.replace('\xa0+','').replace('\xa0','').replace('+','').strip()
            orig_obj = next(
                (obj for k, obj in metrics.items() if _norm(obj.get('metric','')) == canon),
                {}
            )
            orig_section = orig_obj.get('section', '')

            # Determine output section bucket
            if orig_section in SECTION_MAP:
                sec_key = SECTION_MAP[orig_section]
            elif 'history' in orig_section:
                sec_key = f"yahoofin_raw:{orig_section}"
            elif orig_section:
                # Any other known source:section — but Screener financial sections
                # should always be in SECTION_MAP. If not, route to financials as fallback.
                first_source = next(iter(row['sources']), 'unknown')
                if first_source in ('screener_fin', 'screener_raw'):
                    sec_key = 'financials'
                else:
                    sec_key = f"{first_source}:{orig_section}"
            else:
                sec_key = 'financials'  # fallback

            if sec_key not in section_rows:
                section_rows[sec_key] = []

            out_row = {
                'metric':  row['metric'],
                'periods': row['periods'],
                'sources': sorted(row['sources']),
            }
            section_rows[sec_key].append(out_row)

        # Write scalars
        for sec_key, fields in scalars.items():
            output[TICKER]['data'][sec_key] = fields

        # Write time-series rows
        for sec_key, rows in section_rows.items():
            output[TICKER]['data'][sec_key] = rows
        
        # === ADD LTP FROM PRICES ===
        prices_dict = all_data.get('prices', {})
        ticker_prices = prices_dict.get('quotes', {}).get(TICKER, {}) if prices_dict else {}
        daily_section = "yahoofin_raw:history_6mo_1d"
        daily_data = output[TICKER]['data'].get(daily_section, [])
        
        if daily_data and len(daily_data) > 0:
            ltp_obj = {
                'metric': 'LTP',
                'source': 'prices',
                'section': 'latest_price',
                'data': {
                    'ltp': ticker_prices.get('ltp'),
                    'change': ticker_prices.get('change'),
                    'changePct': ticker_prices.get('changePct'),
                    'open': ticker_prices.get('open'),
                    'high': ticker_prices.get('high'),
                    'low': ticker_prices.get('low'),
                    'prev': ticker_prices.get('prev'),
                    'vol': ticker_prices.get('vol'),
                    'w52h': ticker_prices.get('w52h'),
                    'w52l': ticker_prices.get('w52l'),
                    'beta': ticker_prices.get('beta'),
                }
            }
            daily_data.insert(0, ltp_obj)
        
        # === CLEAN AND FINALIZE ===
        output[TICKER]['data'] = clean_metric_names(output[TICKER]['data'])
        output_all[TICKER] = output[TICKER]
        
        logger.write_ticker_summary(TICKER, len(output[TICKER]['data']), len(metrics), ticker_rejections, ticker_errors)
        total_rejections += len(ticker_rejections)
        total_errors += len(ticker_errors)
    
    except Exception as e:
        logger.write_error(TICKER, 'TICKER_PROCESSING', 'OVERALL', f"Critical error: {str(e)}")
        total_errors += 1

# ===== SAVE OUTPUT =====
logger.write_section("SAVING OUTPUT")
output_file = DATA_DIR / 'market_data_raw.json'
try:
    # Add metadata
    output_with_metadata = {
        "_metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_tickers": len(output_all),
            "data_sources": [
                "screener_raw_data.json (97 tickers)",
                "screener_financials.json (97 tickers)",
                "yahoofin_raw_data.json (97 tickers)",
                "yahoofin_financials.json (97 tickers)",
                "guidance.json (29 tickers)",
                "prices.json (98 tickers)",
                "unified-symbols.json (97 tickers)"
            ],
            "structure": {
                "format": "section > consolidation > granularity > [metrics with periods]",
                "example_sections": [
                    "screener_raw:Profit & Loss",
                    "screener_raw:Balance Sheet",
                    "screener_raw:Quarterly Results",
                    "screener_fin:profit_loss",
                    "screener_fin:balance_sheet",
                    "yahoofin_raw:info",
                    "yahoofin_raw:history_6mo_1d",
                    "yahoofin_raw:history_1wk  (10yr weekly — canonical output key)",
                    "yahoofin_raw:history_1mo  (10yr monthly — canonical output key)",
                    "yahoofin_fin:latest",
                    "yahoofin_fin:historical  (consolidated annual, /1e7 → Crores, gap-fills screener_fin)",
                    "guidance:guidance",
                    "guidance:insights",
                    "unified_symbols:metadata"
                ],
                "consolidation_levels": ["consolidated", "standalone"],
                "granularity_levels": ["quarterly", "annual", "other"],
                "metric_structure": {
                    "metric": "Field name (exact from source)",
                    "source": "Data source file",
                    "section": "Section name",
                    "granule": "Quarterly/Annual/etc",
                    "consolidation": "Consolidated/Standalone",
                    "periods": {
                        "YYYY-MM-DD": "numeric_value"
                    }
                }
            },
            "field_preservation": "All field names preserved exactly as in source (including non-breaking spaces \\xa0)",
            "notes": "This is the normalized flattened structure. Use market_data.json for business-logic organized buckets.",
            "total_rejections": total_rejections,
            "total_errors": total_errors
        }
    }
    
    # Add all ticker data
    output_with_metadata.update(output_all)
    
    with open(output_file, 'w') as f:
        json.dump(output_with_metadata, f, indent=2, default=str)
    
    file_size = output_file.stat().st_size
    logger.write(f"Output saved: {output_file}", 'SAVE')
    logger.write(f"File size: {file_size} bytes ({file_size/1024:.2f} KB)", 'SAVE')
except Exception as e:
    logger.write_error('OUTPUT', 'save', output_file.name, f"Save failed: {str(e)}")

# ===== FINAL SUMMARY =====
logger.write_final_summary(len(output_all), output_file.stat().st_size if output_file.exists() else 0)

# Console feedback
print(f"\n✓ Processed {len(output_all)} tickers")
print(f"✓ Log file: {LOG_FILE}")

