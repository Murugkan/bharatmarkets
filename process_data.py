#!/usr/bin/env python3
"""
Complete market data processing with field-level mapping and rejection handling.
Implements the comprehensive field mapping specification.
"""

import json
import re
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from pathlib import Path


# ============================================================================
# REJECTION TRACKING
# ============================================================================

class RejectionTracker:
    """Track all field-level rejections with retry capability."""
    
    CRITICAL = "CRITICAL"
    SECTION = "SECTION"
    FIELD = "FIELD"
    WARNING = "WARNING"
    
    def __init__(self):
        self.rejections = []
        self.resolved = []
        
    def reject(self, ticker: str, section: str, field: str, 
               source_value: Any, reason: str, severity: str):
        """Record a rejection."""
        self.rejections.append({
            "ticker": ticker,
            "section": section,
            "field": field,
            "source_value": str(source_value)[:100],
            "reason": reason,
            "severity": severity,
            "retry_count": 0,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def mark_resolved(self, rejection: Dict):
        """Mark a rejection as resolved after retry."""
        self.resolved.append(rejection)
        self.rejections.remove(rejection)
    
    def get_summary(self) -> Dict:
        """Get rejection summary."""
        return {
            "total_rejections": len(self.rejections) + len(self.resolved),
            "unresolved": len(self.rejections),
            "resolved_after_retry": len(self.resolved),
            "by_severity": self._count_by_severity(),
            "rejections": self.rejections,
            "resolved": self.resolved
        }
    
    def _count_by_severity(self) -> Dict:
        counts = defaultdict(int)
        for r in self.rejections:
            counts[r["severity"]] += 1
        return dict(counts)


# ============================================================================
# ADVANCED PARSING WITH RETRY LOGIC
# ============================================================================

class AdvancedParser:
    """Advanced parsing with multiple fallback strategies."""
    
    def __init__(self, rejection_tracker: RejectionTracker):
        self.tracker = rejection_tracker
        self.stats = defaultdict(int)
    
    def parse_numeric(self, value: Any, ticker: str, section: str, 
                     field: str, severity: str = RejectionTracker.FIELD) -> Optional[float]:
        """Parse numeric with advanced fallbacks."""
        if value is None or value == "":
            return None
        
        # Already numeric
        if isinstance(value, (int, float)):
            self.stats[f"{section}.direct_numeric"] += 1
            return float(value)
        
        if not isinstance(value, str):
            self.tracker.reject(ticker, section, field, value, 
                              "not_string_or_numeric", severity)
            return None
        
        # Try standard parsing
        try:
            cleaned = value.replace(',', '').replace(' ', '').replace('%', '').strip()
            if cleaned in ('', '-', 'N/A', 'NA', 'n/a'):
                return None
            result = float(cleaned)
            self.stats[f"{section}.parsed_numeric"] += 1
            return result
        except ValueError:
            pass
        
        # Advanced fallbacks
        # Try removing currency symbols
        cleaned = re.sub(r'[₹$€£¥]', '', value).strip()
        try:
            result = float(cleaned.replace(',', ''))
            self.stats[f"{section}.currency_removed"] += 1
            return result
        except ValueError:
            pass
        
        # Try scientific notation
        try:
            result = float(value)
            self.stats[f"{section}.scientific_notation"] += 1
            return result
        except ValueError:
            pass
        
        # Final rejection
        self.tracker.reject(ticker, section, field, value, 
                          "numeric_parse_failed", severity)
        return None
    
    def parse_date(self, date_str: str, ticker: str, section: str, 
                   field: str) -> str:
        """Parse date with multiple format support."""
        if not date_str or date_str == "":
            return ""
        
        # Strategy 1: "Mar 2023" format
        match = re.match(r'^([A-Za-z]{3})\s+(\d{4})$', date_str.strip())
        if match:
            try:
                dt = datetime.strptime(date_str.strip(), '%b %Y')
                # Last day of month
                if dt.month == 12:
                    next_month = dt.replace(year=dt.year + 1, month=1, day=1)
                else:
                    next_month = dt.replace(month=dt.month + 1, day=1)
                last_day = next_month - timedelta(days=1)
                self.stats[f"{section}.date_month_year"] += 1
                return last_day.strftime('%Y-%m-%d')
            except:
                pass
        
        # Strategy 2: ISO format "2026-03-31" or with time
        match = re.match(r'^(\d{4}-\d{2}-\d{2})', date_str)
        if match:
            self.stats[f"{section}.date_iso"] += 1
            return match.group(1)
        
        # Strategy 3: Try various formats
        formats = ['%Y/%m/%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                self.stats[f"{section}.date_alternate"] += 1
                return dt.strftime('%Y-%m-%d')
            except:
                continue
        
        # Rejection
        self.tracker.reject(ticker, section, field, date_str, 
                          "date_parse_failed", RejectionTracker.FIELD)
        return date_str
    
    def period_to_quarter(self, date_str: str) -> str:
        """Convert date to quarter label."""
        try:
            dt = datetime.fromisoformat(date_str.split()[0])
            quarter = (dt.month - 1) // 3 + 1
            return f"{dt.year}-Q{quarter}"
        except:
            return date_str


# ============================================================================
# FIELD MAPPERS
# ============================================================================

class YahooInfoMapper:
    """Map Yahoo Finance info fields to target schema."""
    
    # Field mapping: source -> (target, action)
    FIELD_MAP = {
        # Skip metadata
        'maxAge': (None, 'SKIP'),
        'priceHint': (None, 'SKIP'),
        'sourceInterval': (None, 'SKIP'),
        'quoteSourceName': (None, 'SKIP'),
        'symbol': (None, 'SKIP'),  # Duplicate of ticker
        
        # Direct mappings
        '52WeekChange': ('week_52_change', 'numeric'),
        'SandP52WeekChange': ('sandp_52_week_change', 'numeric'),
        'address1': ('address_line_1', 'string'),
        'address2': ('address_line_2', 'string'),
        'allTimeHigh': ('all_time_high', 'numeric'),
        'allTimeLow': ('all_time_low', 'numeric'),
        'ask': ('ask_price', 'numeric'),
        'askSize': ('ask_size', 'numeric'),
        'averageAnalystRating': ('average_analyst_rating', 'string'),
        'averageDailyVolume10Day': ('avg_daily_volume_10d', 'numeric'),
        'averageDailyVolume3Month': ('avg_daily_volume_3m', 'numeric'),
        'averageVolume': ('average_volume', 'numeric'),
        'averageVolume10days': ('average_volume_10d', 'numeric'),
        'beta': ('beta', 'numeric'),
        'bid': ('bid_price', 'numeric'),
        'bidSize': ('bid_size', 'numeric'),
        'bookValue': ('book_value', 'numeric'),
        'city': ('city', 'string'),
        'companyOfficers': ('executives', 'preserve'),
        'compensationAsOfEpochDate': ('compensation_date', 'numeric'),
        'corporateActions': ('corporate_actions', 'preserve'),
        'country': ('country', 'string'),
        'cryptoTradeable': ('crypto_tradeable', 'preserve'),
        'currency': ('currency', 'string'),
        'currentPrice': ('price', 'numeric_critical'),
        'currentRatio': ('current_ratio', 'numeric'),
        'customPriceAlertConfidence': ('price_alert_confidence', 'string'),
        'dayHigh': ('day_high', 'numeric'),
        'dayLow': ('day_low', 'numeric'),
        'debtToEquity': ('debt_to_equity', 'numeric'),
        'earningsCallTimestampEnd': ('earnings_call_end', 'numeric'),
        'earningsCallTimestampStart': ('earnings_call_start', 'numeric'),
        'earningsGrowth': ('earnings_growth', 'numeric'),
        'earningsQuarterlyGrowth': ('earnings_quarterly_growth', 'numeric'),
        'earningsTimestamp': ('earnings_timestamp', 'numeric'),
        'earningsTimestampEnd': ('earnings_timestamp_end', 'numeric'),
        'earningsTimestampStart': ('earnings_timestamp_start', 'numeric'),
        'ebitdaMargins': ('ebitda_margins', 'numeric'),
        'enterpriseToRevenue': ('enterprise_to_revenue', 'numeric'),
        'enterpriseValue': ('enterprise_value', 'numeric'),
        'epsCurrentYear': ('eps_current_year', 'numeric'),
        'epsForward': ('eps_forward', 'numeric'),
        'epsTrailingTwelveMonths': ('eps_ttm', 'numeric'),
        'esgPopulated': ('esg_populated', 'preserve'),
        'exchange': ('exchange', 'string'),
        'exchangeDataDelayedBy': ('exchange_delay_minutes', 'numeric'),
        'exchangeTimezoneName': ('exchange_timezone', 'string'),
        'exchangeTimezoneShortName': ('exchange_timezone_short', 'string'),
        'executiveTeam': ('executive_team', 'preserve'),
        'fiftyDayAverage': ('day_50_average', 'numeric'),
        'fiftyDayAverageChange': ('day_50_avg_change', 'numeric'),
        'fiftyDayAverageChangePercent': ('day_50_avg_change_pct', 'numeric'),
        'fiftyTwoWeekChangePercent': ('week_52_change_pct', 'numeric'),
        'fiftyTwoWeekHigh': ('week_52_high', 'numeric'),
        'fiftyTwoWeekHighChange': ('week_52_high_change', 'numeric'),
        'fiftyTwoWeekHighChangePercent': ('week_52_high_change_pct', 'numeric'),
        'fiftyTwoWeekLow': ('week_52_low', 'numeric'),
        'fiftyTwoWeekLowChange': ('week_52_low_change', 'numeric'),
        'fiftyTwoWeekLowChangePercent': ('week_52_low_change_pct', 'numeric'),
        'fiftyTwoWeekRange': ('week_52_range', 'string'),
        'financialCurrency': ('financial_currency', 'string'),
        'firstTradeDateMilliseconds': ('first_trade_date_ms', 'numeric'),
        'floatShares': ('float_shares', 'numeric'),
        'forwardEps': ('forward_eps', 'numeric'),
        'forwardPE': ('forward_pe', 'numeric'),
        'fullExchangeName': ('exchange_name_full', 'string'),
        'fullTimeEmployees': ('employees', 'numeric'),
        'gmtOffSetMilliseconds': ('gmt_offset_ms', 'numeric'),
        'grossMargins': ('gross_margins', 'numeric'),
        'grossProfits': ('gross_profits', 'numeric'),
        'hasPrePostMarketData': ('has_pre_post_market', 'preserve'),
        'heldPercentInsiders': ('held_pct_insiders', 'numeric'),
        'heldPercentInstitutions': ('held_pct_institutions', 'numeric'),
        'impliedSharesOutstanding': ('implied_shares_outstanding', 'numeric'),
        'industry': ('industry', 'string'),
        'industryDisp': ('industry_display', 'string'),
        'industryKey': ('industry_key', 'string'),
        'isEarningsDateEstimate': ('is_earnings_date_estimate', 'preserve'),
        'language': ('language', 'string'),
        'lastFiscalYearEnd': ('last_fiscal_year_end', 'numeric'),
        'longBusinessSummary': ('business_summary', 'string'),
        'longName': ('name_long', 'string'),
        'market': ('market', 'string'),
        'marketCap': ('market_cap', 'numeric_critical'),
        'marketState': ('market_state', 'string'),
        'messageBoardId': ('message_board_id', 'string'),
        'mostRecentQuarter': ('most_recent_quarter', 'numeric'),
        'netIncomeToCommon': ('net_income_to_common', 'numeric'),
        'nextFiscalYearEnd': ('next_fiscal_year_end', 'numeric'),
        'nonDilutedMarketCap': ('market_cap_non_diluted', 'numeric'),
        'numberOfAnalystOpinions': ('analyst_opinion_count', 'numeric'),
        'open': ('open', 'numeric'),
        'operatingCashflow': ('operating_cashflow', 'numeric'),
        'operatingMargins': ('operating_margins', 'numeric'),
        'payoutRatio': ('payout_ratio', 'numeric'),
        'phone': ('phone', 'string'),
        'previousClose': ('previous_close', 'numeric'),
        'priceEpsCurrentYear': ('price_eps_current_year', 'numeric'),
        'priceToBook': ('price_to_book', 'numeric'),
        'priceToSalesTrailing12Months': ('price_to_sales_ttm', 'numeric'),
        'profitMargins': ('profit_margins', 'numeric'),
        'quickRatio': ('quick_ratio', 'numeric'),
        'quoteType': ('quote_type', 'string'),
        'recommendationKey': ('recommendation_key', 'string'),
        'recommendationMean': ('recommendation_mean', 'numeric'),
        'region': ('region', 'string'),
        'regularMarketChange': ('market_change', 'numeric'),
        'regularMarketChangePercent': ('market_change_pct', 'numeric'),
        'regularMarketDayHigh': ('market_day_high', 'numeric'),
        'regularMarketDayLow': ('market_day_low', 'numeric'),
        'regularMarketDayRange': ('market_day_range', 'string'),
        'regularMarketOpen': ('market_open', 'numeric'),
        'regularMarketPreviousClose': ('market_previous_close', 'numeric'),
        'regularMarketPrice': ('market_price', 'numeric'),
        'regularMarketTime': ('market_time', 'numeric'),
        'regularMarketVolume': ('market_volume', 'numeric'),
        'returnOnAssets': ('return_on_assets', 'numeric'),
        'returnOnEquity': ('return_on_equity', 'numeric'),
        'revenueGrowth': ('revenue_growth', 'numeric'),
        'revenuePerShare': ('revenue_per_share', 'numeric'),
        'sector': ('sector', 'string'),
        'sectorDisp': ('sector_display', 'string'),
        'sectorKey': ('sector_key', 'string'),
        'sharesOutstanding': ('shares_outstanding', 'numeric'),
        'shortName': ('name_short', 'string'),
        'targetHighPrice': ('target_price_high', 'numeric'),
        'targetLowPrice': ('target_price_low', 'numeric'),
        'targetMeanPrice': ('target_price_mean', 'numeric'),
        'targetMedianPrice': ('target_price_median', 'numeric'),
        'totalCash': ('total_cash', 'numeric'),
        'totalCashPerShare': ('total_cash_per_share', 'numeric'),
        'totalDebt': ('total_debt', 'numeric'),
        'totalRevenue': ('total_revenue', 'numeric'),
        'tradeable': ('tradeable', 'preserve'),
        'trailingAnnualDividendRate': ('trailing_annual_dividend_rate', 'numeric'),
        'trailingAnnualDividendYield': ('trailing_annual_dividend_yield', 'numeric'),
        'trailingEps': ('trailing_eps', 'numeric'),
        'trailingPE': ('trailing_pe', 'numeric'),
        'trailingPegRatio': ('trailing_peg_ratio', 'numeric'),
        'triggerable': ('triggerable', 'preserve'),
        'twoHundredDayAverage': ('day_200_average', 'numeric'),
        'twoHundredDayAverageChange': ('day_200_avg_change', 'numeric'),
        'twoHundredDayAverageChangePercent': ('day_200_avg_change_pct', 'numeric'),
        'typeDisp': ('type_display', 'string'),
        'volume': ('volume', 'numeric'),
        'website': ('website', 'string'),
        'zip': ('zip_code', 'string'),
    }
    
    def __init__(self, parser: AdvancedParser):
        self.parser = parser
    
    def map(self, info_dict: Dict, ticker: str) -> Dict:
        """Map Yahoo info fields to target schema."""
        result = {}
        
        for source_field, value in info_dict.items():
            if source_field not in self.FIELD_MAP:
                # Unmapped field - preserve with original name
                result[source_field] = value
                continue
            
            target_field, action = self.FIELD_MAP[source_field]
            
            if action == 'SKIP':
                continue
            
            if action == 'string':
                result[target_field] = value
            
            elif action == 'preserve':
                result[target_field] = value
            
            elif action == 'numeric':
                parsed = self.parser.parse_numeric(
                    value, ticker, 'yahoo_info', source_field,
                    RejectionTracker.FIELD
                )
                if parsed is not None:
                    result[target_field] = parsed
            
            elif action == 'numeric_critical':
                parsed = self.parser.parse_numeric(
                    value, ticker, 'yahoo_info', source_field,
                    RejectionTracker.CRITICAL
                )
                if parsed is not None:
                    result[target_field] = parsed
                else:
                    raise ValueError(f"Critical field {source_field} failed to parse")
        
        return result


# ============================================================================
# MAIN PROCESSOR
# ============================================================================

class DataProcessor:
    """Main data processing orchestrator."""
    
    def __init__(self):
        self.rejection_tracker = RejectionTracker()
        self.parser = AdvancedParser(self.rejection_tracker)
        self.yahoo_mapper = YahooInfoMapper(self.parser)
        self.stats = {
            'stocks_processed': 0,
            'stocks_failed': 0,
            'fields_mapped': 0,
            'data_points_processed': 0
        }
    
    def process_yahoo_info(self, stock_data: Dict, ticker: str) -> Dict:
        """Process Yahoo Finance info section."""
        try:
            if 'yahoofin_raw' not in stock_data:
                return {}
            
            yahoo_raw = stock_data['yahoofin_raw']
            
            if 'observations' not in yahoo_raw or not yahoo_raw['observations']:
                return {}
            
            obs = yahoo_raw['observations'][0]
            
            if 'raw' not in obs or 'info' not in obs['raw']:
                return {}
            
            info = obs['raw']['info']
            
            # Map all fields
            result = self.yahoo_mapper.map(info, ticker)
            
            self.stats['fields_mapped'] += len(result)
            self.stats['data_points_processed'] += len(result)
            
            return result
            
        except Exception as e:
            self.rejection_tracker.reject(
                ticker, 'yahoo_info', 'processing', 
                str(e), f"Fatal error: {str(e)}", 
                RejectionTracker.SECTION
            )
            return {}
    
    def process_price_history(self, stock_data: Dict, ticker: str) -> Dict:
        """Process price history arrays."""
        result = {}
        
        try:
            if 'yahoofin_raw' not in stock_data:
                return result
            
            yahoo_raw = stock_data['yahoofin_raw']
            
            if 'observations' not in yahoo_raw or not yahoo_raw['observations']:
                return result
            
            obs = yahoo_raw['observations'][0]
            
            if 'raw' not in obs:
                return result
            
            raw = obs['raw']
            
            # Map each history type
            history_map = {
                'history_6mo_1d': 'daily',
                'history_5y_1wk': 'weekly',
                'history_5y_1mo': 'monthly'
            }
            
            for source_key, target_key in history_map.items():
                if source_key not in raw:
                    continue
                
                history_data = raw[source_key]
                
                if not isinstance(history_data, list):
                    continue
                
                processed_records = []
                
                for record in history_data:
                    if not isinstance(record, dict):
                        continue
                    
                    proc_record = {}
                    
                    # Date
                    if 'Date' in record:
                        proc_record['date'] = self.parser.parse_date(
                            record['Date'], ticker, 'price_history', 'Date'
                        )
                    
                    # OHLCV
                    for field in ['Open', 'High', 'Low', 'Close', 'Volume']:
                        if field in record:
                            parsed = self.parser.parse_numeric(
                                record[field], ticker, 'price_history', field,
                                RejectionTracker.FIELD
                            )
                            if parsed is not None:
                                proc_record[field.lower()] = parsed
                    
                    # Dividends, Splits
                    for field in ['Dividends', 'Stock Splits']:
                        if field in record:
                            key = field.lower().replace(' ', '_')
                            parsed = self.parser.parse_numeric(
                                record[field], ticker, 'price_history', field,
                                RejectionTracker.FIELD
                            )
                            if parsed is not None:
                                proc_record[key] = parsed
                    
                    if 'date' in proc_record and 'close' in proc_record:
                        processed_records.append(proc_record)
                        self.stats['data_points_processed'] += len(proc_record)
                
                if processed_records:
                    result[target_key] = processed_records
            
        except Exception as e:
            self.rejection_tracker.reject(
                ticker, 'price_history', 'processing',
                str(e), f"Fatal error: {str(e)}",
                RejectionTracker.SECTION
            )
        
        return result
    
    def process_screener_raw(self, stock_data: Dict, ticker: str) -> Dict:
        """Process screener raw data - preserve structure."""
        try:
            if 'screener_raw' not in stock_data:
                return {}
            
            screener = stock_data['screener_raw']
            
            if 'observations' not in screener or not screener['observations']:
                return {}
            
            obs = screener['observations'][0]
            
            if 'raw' not in obs:
                return {}
            
            raw_data = obs['raw']
            
            # Check for error
            if 'error' in raw_data:
                self.rejection_tracker.reject(
                    ticker, 'screener_raw', 'scrape',
                    raw_data['error'], raw_data['error'],
                    RejectionTracker.SECTION
                )
                return {}
            
            # Preserve url and tables
            result = {}
            if 'url' in raw_data:
                result['url'] = raw_data['url']
            if 'tables' in raw_data:
                result['tables'] = raw_data['tables']
                self.stats['data_points_processed'] += len(raw_data['tables'])
            
            return result
            
        except Exception as e:
            self.rejection_tracker.reject(
                ticker, 'screener_raw', 'processing',
                str(e), f"Fatal error: {str(e)}",
                RejectionTracker.SECTION
            )
            return {}
    
    def process_screener_financials(self, stock_data: Dict, ticker: str) -> Dict:
        """Process screener financials - convert to row format."""
        result = {}
        
        try:
            if 'screener_financials' not in stock_data:
                return result
            
            sf = stock_data['screener_financials']
            
            if 'tables' not in sf or not isinstance(sf['tables'], dict):
                return result
            
            # Process each table
            for table_name, table_data in sf['tables'].items():
                if not isinstance(table_data, dict) or 'data' not in table_data:
                    continue
                
                data = table_data['data']
                
                if not isinstance(data, dict):
                    continue
                
                # Get periods
                periods = []
                if data:
                    first_metric = next(iter(data.values()))
                    if isinstance(first_metric, dict):
                        periods = list(first_metric.keys())
                
                if not periods:
                    continue
                
                # Convert to rows
                rows = []
                for period in periods:
                    row = {
                        'period': self.parser.period_to_quarter(
                            self.parser.parse_date(period, ticker, table_name, 'period')
                        ),
                        'date': self.parser.parse_date(period, ticker, table_name, 'date')
                    }
                    
                    # Process each metric
                    for metric_name, metric_values in data.items():
                        if not isinstance(metric_values, dict):
                            continue
                        
                        if period not in metric_values:
                            continue
                        
                        value = metric_values[period]
                        
                        # Parse numeric (multiply by 10M for Crores)
                        parsed = self.parser.parse_numeric(
                            value, ticker, table_name, metric_name,
                            RejectionTracker.FIELD
                        )
                        
                        # Convert snake_case field name
                        field_name = re.sub(r'[^\w\s]', '', metric_name)
                        field_name = field_name.strip().lower().replace(' ', '_')
                        
                        if parsed is not None:
                            # Multiply by 10M if looks like financial amount
                            if field_name not in ['eps', 'margin', 'pct', 'ratio'] and not field_name.endswith('_pct'):
                                row[field_name] = parsed * 10000000
                            else:
                                row[field_name] = parsed
                        
                        self.stats['data_points_processed'] += 1
                    
                    rows.append(row)
                
                if rows:
                    result[table_name] = rows
            
        except Exception as e:
            self.rejection_tracker.reject(
                ticker, 'screener_financials', 'processing',
                str(e), f"Fatal error: {str(e)}",
                RejectionTracker.SECTION
            )
        
        return result
    
    def process_yahoo_financials(self, stock_data: Dict, ticker: str) -> Dict:
        """Process Yahoo financials."""
        result = {}
        
        try:
            if 'yahoofin_financials' not in stock_data:
                return result
            
            yf = stock_data['yahoofin_financials']
            
            if 'observations' not in yf or not yf['observations']:
                return result
            
            obs = yf['observations'][0]
            
            if 'raw' not in obs:
                return result
            
            raw_data = obs['raw']
            
            # Process historical periods
            if 'historical_periods' in raw_data and isinstance(raw_data['historical_periods'], list):
                periods = []
                
                for period in raw_data['historical_periods']:
                    if not isinstance(period, dict):
                        continue
                    
                    proc_period = {}
                    
                    for key, value in period.items():
                        if key == 'period':
                            date_val = self.parser.parse_date(value, ticker, 'yahoo_financials', key)
                            proc_period['period'] = self.parser.period_to_quarter(date_val)
                            proc_period['date'] = date_val
                        else:
                            parsed = self.parser.parse_numeric(
                                value, ticker, 'yahoo_financials', key,
                                RejectionTracker.FIELD
                            )
                            if parsed is not None:
                                proc_period[key] = parsed
                        
                        self.stats['data_points_processed'] += 1
                    
                    periods.append(proc_period)
                
                if periods:
                    result['statements'] = periods
            
        except Exception as e:
            self.rejection_tracker.reject(
                ticker, 'yahoo_financials', 'processing',
                str(e), f"Fatal error: {str(e)}",
                RejectionTracker.SECTION
            )
        
        return result
    
    def process_stock(self, ticker: str, stock_data: Dict) -> Optional[Dict]:
        """Process a complete stock."""
        try:
            # Basic validation
            if not ticker or not stock_data.get('name'):
                self.rejection_tracker.reject(
                    ticker, 'root', 'validation',
                    'missing ticker or name', 'Missing required fields',
                    RejectionTracker.CRITICAL
                )
                self.stats['stocks_failed'] += 1
                return None
            
            result = {
                'ticker': ticker,
                'name': stock_data.get('name'),
                'isin': stock_data.get('isin')
            }
            
            # Process each section
            yahoo_info = self.process_yahoo_info(stock_data, ticker)
            if yahoo_info:
                result.update(yahoo_info)
            
            price_history = self.process_price_history(stock_data, ticker)
            if price_history:
                result['price_history'] = price_history
            
            scraped = self.process_screener_raw(stock_data, ticker)
            if scraped:
                result['scraped_data'] = scraped
            
            financials = self.process_screener_financials(stock_data, ticker)
            if financials:
                # Split quarterly vs annual
                if 'profit_loss' in financials:
                    if 'financials' not in result:
                        result['financials'] = {}
                    result['financials']['quarterly'] = financials['profit_loss']
                
                annual_tables = {}
                for table in ['balance_sheet', 'cash_flow', 'ratios']:
                    if table in financials:
                        annual_tables[table] = financials[table]
                
                if annual_tables:
                    if 'financials' not in result:
                        result['financials'] = {}
                    # Merge annual data
                    result['financials']['annual'] = self._merge_annual_data(annual_tables)
            
            yahoo_fin = self.process_yahoo_financials(stock_data, ticker)
            if yahoo_fin and 'statements' in yahoo_fin:
                if 'financials' not in result:
                    result['financials'] = {}
                result['financials']['statements'] = yahoo_fin['statements']
            
            self.stats['stocks_processed'] += 1
            
            return result
            
        except Exception as e:
            self.rejection_tracker.reject(
                ticker, 'stock', 'processing',
                str(e), f"Fatal stock processing error: {str(e)}",
                RejectionTracker.CRITICAL
            )
            self.stats['stocks_failed'] += 1
            return None
    
    def _merge_annual_data(self, tables: Dict) -> List[Dict]:
        """Merge annual data from multiple tables by period."""
        # Collect all periods
        all_periods = set()
        for table_data in tables.values():
            for row in table_data:
                if 'period' in row:
                    all_periods.add(row['period'])
        
        # Merge by period
        merged = []
        for period in sorted(all_periods):
            merged_row = {'period': period}
            
            # Find row from each table for this period
            for table_name, table_data in tables.items():
                for row in table_data:
                    if row.get('period') == period:
                        # Add all fields except period/date
                        for key, value in row.items():
                            if key not in ['period', 'date']:
                                merged_row[key] = value
                        if 'date' in row:
                            merged_row['date'] = row['date']
                        break
            
            merged.append(merged_row)
        
        return merged


# ============================================================================
# FILE I/O
# ============================================================================

def load_raw_data(filepath: str) -> Tuple[Optional[Dict], Optional[str]]:
    """Load and validate raw data."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, dict):
            return None, "Root is not a dictionary"
        
        if 'data' not in data:
            return None, "Missing 'data' key"
        
        if not isinstance(data['data'], dict):
            return None, "'data' is not a dictionary"
        
        return data, None
        
    except FileNotFoundError:
        return None, f"File not found: {filepath}"
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON: {str(e)}"
    except Exception as e:
        return None, f"Error: {str(e)}"


def save_json(data: Dict, filepath: str) -> Tuple[bool, Optional[str]]:
    """Save JSON file."""
    try:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        return True, None
    except Exception as e:
        return False, f"Error: {str(e)}"


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("="*80)
    print("MARKET DATA PROCESSING - COMPLETE FIELD MAPPING")
    print("="*80)
    print()
    
    # Load
    print("Loading raw data...")
    raw_data, error = load_raw_data('data/raw_market_data.json')
    
    if error:
        print(f"✗ FATAL: {error}")
        sys.exit(1)
    
    total_stocks = len(raw_data['data'])
    print(f"✓ Loaded {total_stocks} stocks")
    print()
    
    # Process
    print("Processing...")
    processor = DataProcessor()
    
    processed_stocks = {}
    
    for idx, (ticker, stock_data) in enumerate(raw_data['data'].items(), 1):
        if idx % 10 == 0:
            print(f"  {idx}/{total_stocks} stocks...")
        
        result = processor.process_stock(ticker, stock_data)
        if result:
            processed_stocks[ticker] = result
    
    print(f"✓ Processed {processor.stats['stocks_processed']} stocks")
    print(f"  Failed: {processor.stats['stocks_failed']}")
    print(f"  Fields mapped: {processor.stats['fields_mapped']:,}")
    print(f"  Data points: {processor.stats['data_points_processed']:,}")
    print()
    
    # Save
    print("Saving outputs...")
    
    # Main output
    output = {
        'stocks': processed_stocks
    }
    
    success, error = save_json(output, 'data/market_data.json')
    if success:
        print("✓ data/market_data.json")
    else:
        print(f"✗ {error}")
    
    # Rejections
    rejection_summary = processor.rejection_tracker.get_summary()
    success, error = save_json(rejection_summary, 'data/rejections.json')
    if success:
        print(f"✓ data/rejections.json")
        print(f"  Total rejections: {rejection_summary['total_rejections']}")
        print(f"  Resolved: {rejection_summary['resolved_after_retry']}")
        print(f"  Unresolved: {rejection_summary['unresolved']}")
    else:
        print(f"✗ {error}")
    
    # Parser stats
    success, error = save_json(dict(processor.parser.stats), 'data/parser_stats.json')
    if success:
        print(f"✓ data/parser_stats.json")
    
    print()
    print("="*80)
    print("COMPLETE")
    print("="*80)


if __name__ == '__main__':
    main()
