#!/usr/bin/env python3
"""
Complete market data processing with field-level mapping and rejection handling.
Implements the comprehensive field mapping specification.
"""

import json
import re
import sys
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict
from pathlib import Path
from enum import Enum


# ============================================================================
# SECTOR-AWARE SIGNAL ANALYZER MODULE (NEW)
# ============================================================================

class Signal(Enum):
    """Trading signals based on composite score"""
    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG SELL"


class SectorAwareSignalAnalyzer:
    """Generate sector-aware EOD signals for stocks."""
    
    def __init__(self):
        """Initialize with sector profiles."""
        self.sector_profiles = self._build_sector_profiles()
        self.sector_mapping = self._build_sector_mapping()
    
    def _build_sector_mapping(self) -> Dict[str, str]:
        """Map data sector/industry to sector profile."""
        return {
            'Financial Services': 'Banking',
            'Financial Conglomerates': 'Banking',
            'Banks': 'Banking',
            'Technology': 'Information Technology',
            'Software': 'Information Technology',
            'Industrials': 'Industrials',
            'Machinery': 'Industrials',
            'Consumer Defensive': 'Consumer Staples',
            'Food & Beverage': 'Consumer Staples',
            'Consumer Discretionary': 'Consumer Discretionary',
            'Retail': 'Consumer Discretionary',
            'Healthcare': 'Healthcare',
            'Pharmaceuticals': 'Healthcare',
            'Basic Materials': 'Materials',
            'Metals & Mining': 'Materials',
            'Energy': 'Energy',
            'Oil & Gas E&P': 'Energy',
            'Utilities': 'Utilities',
            'Electric Utilities': 'Utilities',
            'Communication Services': 'Telecom',
            'Telecom': 'Telecom',
            'Real Estate': 'Real Estate',
        }
    
    def _build_sector_profiles(self) -> Dict[str, Dict]:
        """Build sector profiles with thresholds."""
        return {
            'Banking': {
                'name': 'Banking',
                'weights': {'fundamental': 0.50, 'technical': 0.20, 'valuation': 0.20, 'sentiment': 0.10},
                'de_limit': 12.0,
                'roe_excellent': 0.18,
            },
            'Information Technology': {
                'name': 'Technology',
                'weights': {'fundamental': 0.35, 'technical': 0.35, 'valuation': 0.20, 'sentiment': 0.10},
                'de_limit': 0.5,
                'roe_excellent': 0.30,
            },
            'Industrials': {
                'name': 'Industrials',
                'weights': {'fundamental': 0.45, 'technical': 0.25, 'valuation': 0.20, 'sentiment': 0.10},
                'de_limit': 1.5,
                'roe_excellent': 0.20,
            },
            'Consumer Staples': {
                'name': 'Consumer Staples',
                'weights': {'fundamental': 0.50, 'technical': 0.15, 'valuation': 0.25, 'sentiment': 0.10},
                'de_limit': 1.0,
                'roe_excellent': 0.25,
            },
            'Consumer Discretionary': {
                'name': 'Consumer Discretionary',
                'weights': {'fundamental': 0.35, 'technical': 0.40, 'valuation': 0.15, 'sentiment': 0.10},
                'de_limit': 1.5,
                'roe_excellent': 0.18,
            },
            'Healthcare': {
                'name': 'Healthcare',
                'weights': {'fundamental': 0.40, 'technical': 0.20, 'valuation': 0.30, 'sentiment': 0.10},
                'de_limit': 1.0,
                'roe_excellent': 0.25,
            },
            'Materials': {
                'name': 'Materials',
                'weights': {'fundamental': 0.30, 'technical': 0.45, 'valuation': 0.15, 'sentiment': 0.10},
                'de_limit': 2.0,
                'roe_excellent': 0.20,
            },
            'Energy': {
                'name': 'Energy',
                'weights': {'fundamental': 0.35, 'technical': 0.40, 'valuation': 0.15, 'sentiment': 0.10},
                'de_limit': 2.0,
                'roe_excellent': 0.18,
            },
            'Telecom': {
                'name': 'Telecom',
                'weights': {'fundamental': 0.40, 'technical': 0.25, 'valuation': 0.25, 'sentiment': 0.10},
                'de_limit': 2.0,
                'roe_excellent': 0.20,
            },
            'Real Estate': {
                'name': 'Real Estate',
                'weights': {'fundamental': 0.35, 'technical': 0.30, 'valuation': 0.25, 'sentiment': 0.10},
                'de_limit': 2.0,
                'roe_excellent': 0.25,
            },
            'Utilities': {
                'name': 'Utilities',
                'weights': {'fundamental': 0.60, 'technical': 0.10, 'valuation': 0.20, 'sentiment': 0.10},
                'de_limit': 2.5,
                'roe_excellent': 0.18,
            },
        }
    
    def generate_signal(self, stock: Dict) -> Dict:
        """Generate sector-aware signal for a stock."""
        try:
            ticker = stock.get('ticker', 'UNKNOWN')
            sector = self._detect_sector(stock.get('sector', ''), stock.get('industry', ''))
            profile = self.sector_profiles.get(sector, self.sector_profiles['Industrials'])
            
            # Calculate scores
            val_score = self._score_valuation(stock)
            health_score = self._score_health(stock, profile)
            growth_score = self._score_growth(stock)
            tech_score = self._score_technical(stock)
            
            # Composite using sector weights
            weights = profile['weights']
            composite = (
                val_score * weights['valuation'] +
                health_score * weights['fundamental'] +
                growth_score * weights['technical'] +
                tech_score * weights['sentiment']
            )
            
            signal = self._get_signal(composite)
            
            return {
                'signal': signal.value,
                'composite_score': round(composite, 2),
                'component_scores': {
                    'valuation': round(val_score, 2),
                    'health': round(health_score, 2),
                    'growth': round(growth_score, 2),
                    'technical': round(tech_score, 2),
                },
                'sector': sector,
                'sector_weights': weights,
                'confidence': self._assess_confidence(stock),
            }
        except Exception as e:
            return {
                'signal': Signal.HOLD.value,
                'composite_score': 50.0,
                'error': str(e),
            }
    
    def _detect_sector(self, sector: str, industry: str) -> str:
        """Detect sector from sector/industry fields."""
        for key, value in self.sector_mapping.items():
            if key.lower() in (sector or '').lower() or key.lower() in (industry or '').lower():
                return value
        return 'Industrials'
    
    def _score_valuation(self, stock: Dict) -> float:
        """Score valuation (0-100)."""
        scores = []
        
        pe = stock.get('trailing_pe')
        if pe and pe > 0:
            scores.append(70 if pe < 25 else (50 if pe < 35 else 30))
        
        pb = stock.get('price_to_book')
        if pb and pb > 0:
            scores.append(75 if pb < 2 else (50 if pb < 3 else 30))
        
        return sum(scores) / len(scores) if scores else 50
    
    def _score_health(self, stock: Dict, profile: Dict) -> float:
        """Score financial health using sector thresholds."""
        scores = []
        
        roe = stock.get('return_on_equity', 0)
        if roe:
            if roe >= profile['roe_excellent']:
                scores.append(95)
            elif roe >= profile['roe_excellent'] * 0.75:
                scores.append(85)
            else:
                scores.append(60)
        
        de = stock.get('debt_to_equity', 0)
        if de >= 0:
            if de <= profile['de_limit'] * 0.5:
                scores.append(95)
            elif de <= profile['de_limit']:
                scores.append(85)
            else:
                scores.append(50)
        
        cr = stock.get('current_ratio')
        if cr and cr > 0:
            scores.append(90 if cr >= 2 else (75 if cr >= 1.5 else 50))
        
        margin = stock.get('profit_margins', 0)
        if margin > 0:
            scores.append(90 if margin >= 0.20 else (75 if margin >= 0.15 else 50))
        
        return sum(scores) / len(scores) if scores else 50
    
    def _score_growth(self, stock: Dict) -> float:
        """Score growth metrics."""
        scores = []
        
        rev_g = stock.get('revenue_growth', 0)
        if rev_g is not None:
            scores.append(90 if rev_g >= 0.15 else (70 if rev_g >= 0.10 else 50))
        
        earn_g = stock.get('earnings_growth', 0)
        if earn_g is not None:
            scores.append(90 if earn_g >= 0.20 else (70 if earn_g >= 0.10 else 50))
        
        return sum(scores) / len(scores) if scores else 50
    
    def _score_technical(self, stock: Dict) -> float:
        """Score technical indicators."""
        scores = []
        
        beta = stock.get('beta')
        if beta and beta > 0:
            scores.append(75 if beta < 1.2 else 50)
        
        momentum = stock.get('week_52_change', 0)
        if momentum is not None:
            scores.append(80 if momentum >= 0.20 else (60 if momentum >= 0 else 40))
        
        return sum(scores) / len(scores) if scores else 50
    
    def _get_signal(self, score: float) -> Signal:
        """Convert score to signal."""
        if score >= 80:
            return Signal.STRONG_BUY
        elif score >= 65:
            return Signal.BUY
        elif score >= 50:
            return Signal.HOLD
        elif score >= 35:
            return Signal.SELL
        else:
            return Signal.STRONG_SELL
    
    def _assess_confidence(self, stock: Dict) -> str:
        """Assess confidence level."""
        data_points = sum(1 for v in [
            stock.get('trailing_pe'),
            stock.get('return_on_equity'),
            stock.get('debt_to_equity'),
            stock.get('profit_margins'),
            stock.get('revenue_growth'),
            stock.get('earnings_growth'),
        ] if v is not None)
        
        if data_points >= 5:
            return 'HIGH'
        elif data_points >= 3:
            return 'MEDIUM'
        else:
            return 'LOW'


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def normalize_decimals(value: Any, decimals: int = 4) -> Any:
    """
    Normalize decimal places for numeric values recursively.
    
    Args:
        value: Input value (can be dict, list, or primitive)
        decimals: Number of decimal places to keep (default: 4)
    
    Returns:
        Value with normalized decimals
    """
    if isinstance(value, float):
        return round(value, decimals)
    elif isinstance(value, dict):
        return {k: normalize_decimals(v, decimals) for k, v in value.items()}
    elif isinstance(value, list):
        return [normalize_decimals(item, decimals) for item in value]
    else:
        return value


def parse_number(value: str) -> float:
    """
    Parse number from string, handling Indian number format with commas.
    Examples: "1,672" -> 1672.0, "12.5" -> 12.5
    """
    if not value or not isinstance(value, str):
        return 0.0
    try:
        # Remove commas and whitespace
        cleaned = value.replace(',', '').strip()
        return float(cleaned)
    except:
        return 0.0


def parse_quarter_date(quarter_str: str) -> datetime:
    """
    Parse quarter string to datetime for sorting.
    Examples: "Mar 2023" -> datetime(2023, 3, 1), "Dec 2024" -> datetime(2024, 12, 1)
    """
    try:
        return datetime.strptime(quarter_str, "%b %Y")
    except:
        return datetime(2000, 1, 1)  # Default for unparseable dates


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
# ACCOUNTING PRINCIPLES & DERIVED METRICS MODULE
# ============================================================================

class AccountingPrinciplesEngine:
    """
    Calculate derived financial metrics based on accounting principles.
    Adds calculated fields for financial analysis.
    """
    
    def __init__(self):
        self.logger = logging.getLogger('AccountingEngine')
        self.calculations_performed = 0
        self.calculation_errors = 0
    
    def calculate_all_metrics(self, stock_data: Dict, ticker: str) -> Dict:
        """Calculate all derived metrics for a stock."""
        
        self.logger.info(f"Calculating accounting metrics for {ticker}")
        
        metrics = {}
        
        try:
            # Valuation Metrics
            valuation = self._calculate_valuation_metrics(stock_data, ticker)
            if valuation:
                metrics['valuation_metrics'] = valuation
            
            # Profitability Metrics
            profitability = self._calculate_profitability_metrics(stock_data, ticker)
            if profitability:
                metrics['profitability_metrics'] = profitability
            
            # Liquidity Metrics
            liquidity = self._calculate_liquidity_metrics(stock_data, ticker)
            if liquidity:
                metrics['liquidity_metrics'] = liquidity
            
            # Leverage Metrics
            leverage = self._calculate_leverage_metrics(stock_data, ticker)
            if leverage:
                metrics['leverage_metrics'] = leverage
            
            # Efficiency Metrics
            efficiency = self._calculate_efficiency_metrics(stock_data, ticker)
            if efficiency:
                metrics['efficiency_metrics'] = efficiency
            
            # Growth Metrics
            growth = self._calculate_growth_metrics(stock_data, ticker)
            if growth:
                metrics['growth_metrics'] = growth
            
            # Cash Flow Metrics
            cashflow = self._calculate_cashflow_metrics(stock_data, ticker)
            if cashflow:
                metrics['cashflow_metrics'] = cashflow
            
            # Per Share Metrics
            per_share = self._calculate_per_share_metrics(stock_data, ticker)
            if per_share:
                metrics['per_share_metrics'] = per_share
            
            self.logger.info(f"Calculated {len(metrics)} metric categories for {ticker}")
            
        except Exception as e:
            self.calculation_errors += 1
            self.logger.error(f"Error calculating metrics for {ticker}: {str(e)}")
        
        return metrics
    
    def _safe_divide(self, numerator: float, denominator: float) -> Optional[float]:
        """Safely divide two numbers, return None if division by zero."""
        try:
            if denominator == 0 or denominator is None:
                return None
            return numerator / denominator
        except:
            return None
    
    def _calculate_valuation_metrics(self, stock_data: Dict, ticker: str) -> Dict:
        """Calculate valuation metrics."""
        metrics = {}
        
        try:
            price = stock_data.get('price')
            market_cap = stock_data.get('market_cap')
            trailing_pe = stock_data.get('trailing_pe')
            forward_pe = stock_data.get('forward_pe')
            price_to_book = stock_data.get('price_to_book')
            enterprise_value = stock_data.get('enterprise_value')
            total_revenue = stock_data.get('total_revenue')
            
            # EV/Sales
            if enterprise_value and total_revenue:
                metrics['ev_to_sales'] = self._safe_divide(enterprise_value, total_revenue)
            
            # P/E Relative (Forward PE / Trailing PE)
            if forward_pe and trailing_pe:
                metrics['pe_relative'] = self._safe_divide(forward_pe, trailing_pe)
            
            # Market Cap to Sales
            if market_cap and total_revenue:
                metrics['market_cap_to_sales'] = self._safe_divide(market_cap, total_revenue)
            
            # PEG Ratio (PE / Earnings Growth Rate)
            earnings_growth = stock_data.get('earnings_growth')
            if trailing_pe and earnings_growth:
                metrics['peg_ratio'] = self._safe_divide(trailing_pe, earnings_growth * 100)
            
            self.calculations_performed += len(metrics)
            
        except Exception as e:
            self.logger.debug(f"Error in valuation metrics for {ticker}: {str(e)}")
        
        return metrics
    
    def _calculate_profitability_metrics(self, stock_data: Dict, ticker: str) -> Dict:
        """Calculate profitability metrics."""
        metrics = {}
        
        try:
            # ROE (Return on Equity)
            roe = stock_data.get('return_on_equity')
            if roe:
                metrics['roe'] = roe
            
            # ROA (Return on Assets)
            roa = stock_data.get('return_on_assets')
            if roa:
                metrics['roa'] = roa
            
            # Profit Margins
            profit_margins = stock_data.get('profit_margins')
            if profit_margins:
                metrics['net_profit_margin'] = profit_margins
            
            operating_margins = stock_data.get('operating_margins')
            if operating_margins:
                metrics['operating_margin'] = operating_margins
            
            gross_margins = stock_data.get('gross_margins')
            if gross_margins:
                metrics['gross_margin'] = gross_margins
            
            # DuPont Analysis Components
            # ROE = Net Profit Margin × Asset Turnover × Equity Multiplier
            if profit_margins and roa and roe:
                # Asset Turnover = ROA / Net Profit Margin
                asset_turnover = self._safe_divide(roa, profit_margins)
                if asset_turnover:
                    metrics['asset_turnover_ratio'] = asset_turnover
                
                # Equity Multiplier = ROE / ROA
                equity_multiplier = self._safe_divide(roe, roa)
                if equity_multiplier:
                    metrics['equity_multiplier'] = equity_multiplier
            
            self.calculations_performed += len(metrics)
            
        except Exception as e:
            self.logger.debug(f"Error in profitability metrics for {ticker}: {str(e)}")
        
        return metrics
    
    def _calculate_liquidity_metrics(self, stock_data: Dict, ticker: str) -> Dict:
        """Calculate liquidity metrics."""
        metrics = {}
        
        try:
            current_ratio = stock_data.get('current_ratio')
            if current_ratio:
                metrics['current_ratio'] = current_ratio
            
            quick_ratio = stock_data.get('quick_ratio')
            if quick_ratio:
                metrics['quick_ratio'] = quick_ratio
            
            # Working Capital Ratio
            total_cash = stock_data.get('total_cash')
            total_debt = stock_data.get('total_debt')
            
            if total_cash and total_debt:
                # Cash to Debt Ratio
                metrics['cash_to_debt_ratio'] = self._safe_divide(total_cash, total_debt)
            
            # Operating Cash Flow Ratio
            operating_cashflow = stock_data.get('operating_cashflow')
            if operating_cashflow and total_debt:
                metrics['ocf_to_debt_ratio'] = self._safe_divide(operating_cashflow, total_debt)
            
            self.calculations_performed += len(metrics)
            
        except Exception as e:
            self.logger.debug(f"Error in liquidity metrics for {ticker}: {str(e)}")
        
        return metrics
    
    def _calculate_leverage_metrics(self, stock_data: Dict, ticker: str) -> Dict:
        """Calculate leverage/solvency metrics."""
        metrics = {}
        
        try:
            debt_to_equity = stock_data.get('debt_to_equity')
            if debt_to_equity:
                metrics['debt_to_equity'] = debt_to_equity
            
            total_debt = stock_data.get('total_debt')
            market_cap = stock_data.get('market_cap')
            total_revenue = stock_data.get('total_revenue')
            
            # Debt to Market Cap
            if total_debt and market_cap:
                metrics['debt_to_market_cap'] = self._safe_divide(total_debt, market_cap)
            
            # Debt to Revenue
            if total_debt and total_revenue:
                metrics['debt_to_revenue'] = self._safe_divide(total_debt, total_revenue)
            
            # Interest Coverage Ratio (from financials if available)
            if 'financials' in stock_data and 'quarterly' in stock_data['financials']:
                latest = stock_data['financials']['quarterly'][0] if stock_data['financials']['quarterly'] else {}
                
                # EBIT / Interest Expense
                ebit = latest.get('profit_before_tax')
                interest = latest.get('interest_income')  # Note: might need interest_expense
                
                if ebit and interest and interest != 0:
                    metrics['interest_coverage_ratio'] = self._safe_divide(ebit, interest)
            
            self.calculations_performed += len(metrics)
            
        except Exception as e:
            self.logger.debug(f"Error in leverage metrics for {ticker}: {str(e)}")
        
        return metrics
    
    def _calculate_efficiency_metrics(self, stock_data: Dict, ticker: str) -> Dict:
        """Calculate efficiency/activity metrics."""
        metrics = {}
        
        try:
            # Asset Turnover
            total_revenue = stock_data.get('total_revenue')
            
            # From financials
            if 'financials' in stock_data and 'statements' in stock_data['financials']:
                statements = stock_data['financials']['statements']
                if statements:
                    latest = statements[0]
                    total_assets = latest.get('total_assets')
                    
                    if total_revenue and total_assets:
                        metrics['asset_turnover'] = self._safe_divide(total_revenue, total_assets)
            
            # Revenue per Share
            revenue_per_share = stock_data.get('revenue_per_share')
            if revenue_per_share:
                metrics['revenue_per_share'] = revenue_per_share
            
            self.calculations_performed += len(metrics)
            
        except Exception as e:
            self.logger.debug(f"Error in efficiency metrics for {ticker}: {str(e)}")
        
        return metrics
    
    def _calculate_growth_metrics(self, stock_data: Dict, ticker: str) -> Dict:
        """Calculate growth metrics."""
        metrics = {}
        
        try:
            # From existing fields
            revenue_growth = stock_data.get('revenue_growth')
            if revenue_growth:
                metrics['revenue_growth_rate'] = revenue_growth
            
            earnings_growth = stock_data.get('earnings_growth')
            if earnings_growth:
                metrics['earnings_growth_rate'] = earnings_growth
            
            earnings_quarterly_growth = stock_data.get('earnings_quarterly_growth')
            if earnings_quarterly_growth:
                metrics['earnings_quarterly_growth_rate'] = earnings_quarterly_growth
            
            # Calculate YoY growth from financials if available
            if 'financials' in stock_data and 'quarterly' in stock_data['financials']:
                quarters = stock_data['financials']['quarterly']
                
                if len(quarters) >= 5:  # Need at least 5 quarters for YoY
                    # Current quarter vs same quarter last year (4 quarters ago)
                    current_revenue = quarters[0].get('revenue')
                    yoy_revenue = quarters[4].get('revenue')
                    
                    if current_revenue and yoy_revenue and yoy_revenue != 0:
                        yoy_growth = ((current_revenue - yoy_revenue) / yoy_revenue)
                        metrics['revenue_yoy_growth'] = yoy_growth
                    
                    # Same for profit
                    current_profit = quarters[0].get('net_profit')
                    yoy_profit = quarters[4].get('net_profit')
                    
                    if current_profit and yoy_profit and yoy_profit != 0:
                        yoy_profit_growth = ((current_profit - yoy_profit) / yoy_profit)
                        metrics['profit_yoy_growth'] = yoy_profit_growth
            
            self.calculations_performed += len(metrics)
            
        except Exception as e:
            self.logger.debug(f"Error in growth metrics for {ticker}: {str(e)}")
        
        return metrics
    
    def _calculate_cashflow_metrics(self, stock_data: Dict, ticker: str) -> Dict:
        """Calculate cash flow metrics."""
        metrics = {}
        
        try:
            operating_cashflow = stock_data.get('operating_cashflow')
            market_cap = stock_data.get('market_cap')
            total_revenue = stock_data.get('total_revenue')
            
            # Operating Cash Flow to Market Cap
            if operating_cashflow and market_cap:
                metrics['ocf_to_market_cap'] = self._safe_divide(operating_cashflow, market_cap)
            
            # Operating Cash Flow to Revenue
            if operating_cashflow and total_revenue:
                metrics['ocf_to_revenue'] = self._safe_divide(operating_cashflow, total_revenue)
            
            # Free Cash Flow Yield
            # FCF Yield = Free Cash Flow / Market Cap
            if 'financials' in stock_data and 'statements' in stock_data['financials']:
                statements = stock_data['financials']['statements']
                if statements:
                    latest = statements[0]
                    free_cash_flow = latest.get('free_cash_flow')
                    
                    if free_cash_flow and market_cap:
                        metrics['free_cashflow_yield'] = self._safe_divide(free_cash_flow, market_cap)
            
            self.calculations_performed += len(metrics)
            
        except Exception as e:
            self.logger.debug(f"Error in cashflow metrics for {ticker}: {str(e)}")
        
        return metrics
    
    def _calculate_per_share_metrics(self, stock_data: Dict, ticker: str) -> Dict:
        """Calculate per-share metrics."""
        metrics = {}
        
        try:
            shares_outstanding = stock_data.get('shares_outstanding')
            
            if not shares_outstanding or shares_outstanding == 0:
                return metrics
            
            # Book Value per Share
            book_value = stock_data.get('book_value')
            if book_value:
                metrics['book_value_per_share'] = book_value
            
            # Cash per Share
            total_cash_per_share = stock_data.get('total_cash_per_share')
            if total_cash_per_share:
                metrics['cash_per_share'] = total_cash_per_share
            
            # EPS metrics
            trailing_eps = stock_data.get('trailing_eps')
            if trailing_eps:
                metrics['eps_trailing'] = trailing_eps
            
            forward_eps = stock_data.get('forward_eps')
            if forward_eps:
                metrics['eps_forward'] = forward_eps
            
            # Revenue per Share
            revenue_per_share = stock_data.get('revenue_per_share')
            if revenue_per_share:
                metrics['revenue_per_share'] = revenue_per_share
            
            # Operating Cash Flow per Share
            operating_cashflow = stock_data.get('operating_cashflow')
            if operating_cashflow:
                metrics['operating_cashflow_per_share'] = self._safe_divide(
                    operating_cashflow, shares_outstanding
                )
            
            self.calculations_performed += len(metrics)
            
        except Exception as e:
            self.logger.debug(f"Error in per-share metrics for {ticker}: {str(e)}")
        
        return metrics
    
    def get_summary(self) -> Dict:
        """Get calculation summary statistics."""
        summary = {
            'total_calculations_performed': self.calculations_performed,
            'calculation_errors': self.calculation_errors,
            'success_rate': self._safe_divide(
                self.calculations_performed - self.calculation_errors,
                self.calculations_performed
            ) if self.calculations_performed > 0 else 0
        }
        
        self.logger.info("="*80)
        self.logger.info("ACCOUNTING METRICS SUMMARY")
        self.logger.info("="*80)
        self.logger.info(f"Calculations Performed: {summary['total_calculations_performed']}")
        self.logger.info(f"Calculation Errors: {summary['calculation_errors']}")
        self.logger.info(f"Success Rate: {summary['success_rate']*100:.2f}%")
        
        return summary

# ============================================================================
# MAIN PROCESSOR
# ============================================================================

class DataProcessor:
    """Main data processing orchestrator."""
    
    def __init__(self):
        self.rejection_tracker = RejectionTracker()
        self.parser = AdvancedParser(self.rejection_tracker)
        self.yahoo_mapper = YahooInfoMapper(self.parser)
        self.accounting_engine = AccountingPrinciplesEngine()
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
            
            # Calculate derived accounting metrics
            accounting_metrics = self.accounting_engine.calculate_all_metrics(result, ticker)
            if accounting_metrics:
                result['derived_metrics'] = accounting_metrics
            
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
    """Save JSON file with NaN handling."""
    try:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        # Convert NaN/Infinity to None (null in JSON)
        import math
        
        def clean_value(obj):
            """Recursively clean NaN and Infinity values."""
            if isinstance(obj, float):
                if math.isnan(obj) or math.isinf(obj):
                    return None
                return obj
            elif isinstance(obj, dict):
                return {k: clean_value(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_value(item) for item in obj]
            else:
                return obj
        
        cleaned_data = clean_value(data)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(cleaned_data, f, indent=2, allow_nan=False)
        
        return True, None
    except Exception as e:
        return False, f"Error: {str(e)}"


# ============================================================================
# MAIN
# ============================================================================

def generate_signals_for_stocks(stocks_array: List[Dict]) -> None:
    """Generate and add signals to all stocks."""
    analyzer = SectorAwareSignalAnalyzer()
    
    print()
    print("="*80)
    print("GENERATING SECTOR-AWARE SIGNALS FOR ALL STOCKS")
    print("="*80)
    print()
    
    signal_distribution = defaultdict(int)
    
    for i, stock in enumerate(stocks_array):
        signal_data = analyzer.generate_signal(stock)
        stock['signal'] = signal_data
        signal_distribution[signal_data['signal']] += 1
        
        if (i + 1) % 20 == 0:
            print(f"  ✓ Processed {i + 1}/{len(stocks_array)} stocks")
    
    print()
    print("Signal Distribution:")
    for sig in ['STRONG BUY', 'BUY', 'HOLD', 'SELL', 'STRONG SELL']:
        count = signal_distribution[sig]
        pct = (count / len(stocks_array) * 100) if stocks_array else 0
        print(f"  {sig:.<20} {count:>3} ({pct:>5.1f}%)")
    print()


def main():
    print("="*80)
    print("MARKET DATA PROCESSING - COMPLETE FIELD MAPPING")
    print("="*80)
    print()
    
    # Get logger
    logger = logging.getLogger('Main')
    
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
    
    # Get accounting metrics summary
    accounting_summary = processor.accounting_engine.get_summary()
    print()
    
    # Save - SINGLE CONSOLIDATED OUTPUT
    print("Saving output...")
    
    rejection_summary = processor.rejection_tracker.get_summary()
    
    # Build rejection map by ticker for easy lookup
    rejections_by_ticker = rejection_summary.get('by_ticker', {})
    
    # NOTE: Rejections integrated PER STOCK (not scattered in metadata)
    
    # Normalize all decimal places in stock data
    # BUT FIRST: Copy financials from raw data for quarterly transformation
    for ticker, processed_stock in processed_stocks.items():
        if ticker in raw_data['data']:
            raw_stock = raw_data['data'][ticker]
            if 'screener_financials' in raw_stock:
                processed_stock['screener_financials'] = raw_stock['screener_financials']
            if 'yahoofin_financials' in raw_stock:
                processed_stock['yahoofin_financials'] = raw_stock['yahoofin_financials']
    
    normalized_stocks = normalize_decimals(processed_stocks, decimals=4)
    
    # Convert stocks dictionary to array for JavaScript compatibility
    stocks_array = list(normalized_stocks.values())
    
    # ========================================================================
    # GENERATE SECTOR-AWARE SIGNALS (NEW)
    # ========================================================================
    
    generate_signals_for_stocks(stocks_array)
    
    # ========================================================================
    # ADD REJECTIONS PER STOCK (NEW)
    # ========================================================================
    
    for stock in stocks_array:
        ticker = stock.get('ticker', '')
        if ticker in rejections_by_ticker:
            stock['rejections'] = rejections_by_ticker[ticker]
    
    # Single comprehensive output file (WITH rejections integrated per stock)
    output = {
        'metadata': {
            'version': '1.0.0',
            'processed_at': datetime.now().isoformat(),
            'total_stocks': len(normalized_stocks),
            'processing_stats': {
                'stocks_processed': processor.stats['stocks_processed'],
                'stocks_failed': processor.stats['stocks_failed'],
                'fields_mapped': processor.stats['fields_mapped'],
                'data_points_processed': processor.stats['data_points_processed']
            },
            'rejection_stats': {
                'total_rejections': rejection_summary['total_rejections'],
                'resolved': rejection_summary['resolved_after_retry'],
                'unresolved': rejection_summary['unresolved'],
                'by_severity': rejection_summary['by_severity'],
                'note': 'Detailed rejections per stock are included in each stock object'
            },
            'accounting_stats': accounting_summary,
            'decimal_precision': 4
        },
        'stocks': stocks_array  # Array, not dictionary
    }
    
    # ========================================================================
    # PORTFOLIO MERGE (from unified-symbols.json)
    # ========================================================================
    
    portfolio_path = 'unified-symbols.json'
    if Path(portfolio_path).exists():
        print()
        print("="*80)
        print("MERGING PORTFOLIO DATA (unified-symbols.json)")
        print("="*80)
        print()
        
        try:
            with open(portfolio_path, 'r') as f:
                portfolio = json.load(f)
            
            portfolio_stocks = portfolio.get('symbols', [])
            print(f"Portfolio stocks: {len(portfolio_stocks)}")
            print(f"Portfolio updated: {portfolio.get('updated', 'N/A')}")
            print()
            
            # Create lookup
            portfolio_lookup = {}
            for stock in portfolio_stocks:
                ticker = stock.get('ticker', '').upper()
                if ticker:
                    portfolio_lookup[ticker] = stock
            
            # Merge
            merged_count = 0
            watchlist_count = 0
            
            for stock in stocks_array:
                ticker = stock.get('ticker', '').upper()
                
                if ticker in portfolio_lookup:
                    portfolio_stock = portfolio_lookup[ticker]
                    stock['qty'] = portfolio_stock.get('qty', 0)
                    stock['avg'] = portfolio_stock.get('avg', 0)
                    stock['type'] = portfolio_stock.get('type', 'portfolio')
                    stock['source'] = portfolio_stock.get('source', 'import')
                    merged_count += 1
                    print(f"  ✓ {ticker:12} qty={stock['qty']:>6}  avg={stock['avg']:>8.2f}")
                else:
                    # Watchlist
                    if 'qty' not in stock:
                        stock['qty'] = 0
                    if 'avg' not in stock:
                        stock['avg'] = 0
                    if 'type' not in stock:
                        stock['type'] = 'watchlist'
                    watchlist_count += 1
            
            # Check for missing stocks
            market_tickers = {s.get('ticker', '').upper() for s in stocks_array}
            missing = [t for t in portfolio_lookup.keys() if t not in market_tickers]
            
            print()
            print(f"Portfolio stocks merged: {merged_count}")
            print(f"Watchlist only: {watchlist_count}")
            
            if missing:
                print(f"⚠️  In portfolio but NOT in market data: {len(missing)}")
                for ticker in missing[:5]:
                    print(f"     - {ticker}")
                if len(missing) > 5:
                    print(f"     ... and {len(missing) - 5} more")
            
            # Update metadata
            output['metadata']['portfolio_merged'] = True
            output['metadata']['portfolio_updated'] = portfolio.get('updated')
            output['metadata']['portfolio_count'] = merged_count
            
            print()
            
        except Exception as e:
            print(f"⚠️  Portfolio merge failed: {str(e)}")
            print("   Continuing without portfolio data...")
            print()
    else:
        print()
        print(f"⚠️  No portfolio file found at: {portfolio_path}")
        print("   All stocks will be marked as 'watchlist'")
        print()
        
        # Set defaults
        for stock in stocks_array:
            if 'qty' not in stock:
                stock['qty'] = 0
            if 'avg' not in stock:
                stock['avg'] = 0
            if 'type' not in stock:
                stock['type'] = 'watchlist'
    
    # ========================================================================
    # GUIDANCE MERGE (from guidance.json)
    # ========================================================================
    
    guidance_path = 'guidance.json'
    if Path(guidance_path).exists():
        print("="*80)
        print("MERGING GUIDANCE DATA (guidance.json)")
        print("="*80)
        print()
        
        try:
            with open(guidance_path, 'r') as f:
                guidance_data = json.load(f)
            
            # Remove metadata if present
            if '_metadata' in guidance_data:
                del guidance_data['_metadata']
            
            print(f"Guidance entries: {len(guidance_data)}")
            print()
            
            # Merge guidance into stocks
            guidance_merged = 0
            
            for stock in stocks_array:
                ticker = stock.get('ticker', '').upper()
                
                if ticker in guidance_data:
                    # Add guidance data
                    stock['guidance'] = guidance_data[ticker].get('guidance', {})
                    stock['insights'] = guidance_data[ticker].get('insights', {})
                    guidance_merged += 1
                    print(f"  ✓ {ticker:12} guidance added")
            
            print()
            print(f"Stocks with guidance: {guidance_merged}")
            print(f"Stocks without guidance: {len(stocks_array) - guidance_merged}")
            
            # Update metadata
            output['metadata']['guidance_merged'] = True
            output['metadata']['guidance_count'] = guidance_merged
            
            print()
            
        except Exception as e:
            print(f"⚠️  Guidance merge failed: {str(e)}")
            print("   Continuing without guidance data...")
            print()
    else:
        print(f"⚠️  No guidance file found at: {guidance_path}")
        print()
    
    # ========================================================================
    # TRANSFORM QUARTERLY FINANCIALS
    # ========================================================================
    
    print("="*80)
    print("TRANSFORMING QUARTERLY & HISTORICAL FINANCIALS")
    print("="*80)
    print()
    
    quarterly_count = 0
    for stock in stocks_array:
        ticker = stock.get('ticker', '').upper()
        
        # Get data from both Screener and Yahoo Finance
        has_screener = 'screener_financials' in stock
        has_yahoo = 'yahoofin_financials' in stock
        
        if not has_screener and not has_yahoo:
            continue
        
        # === EXTRACT FROM SCREENER FINANCIALS (Quarterly) ===
        quarterly_by_period = {}
        
        if has_screener:
            sf = stock.get('screener_financials', {})
            if isinstance(sf, dict) and 'tables' in sf:
                tables = sf['tables']
                if isinstance(tables, dict):
                    pl_data = tables.get('profit_loss', {}).get('data', {})
                    bs_data = tables.get('balance_sheet', {}).get('data', {})
                    cf_data = tables.get('cash_flow', {}).get('data', {})
                    ratios_data = tables.get('ratios', {}).get('data', {})
                    
                    # Get all unique quarters
                    all_quarters = set()
                    for table_data in [pl_data, bs_data, cf_data, ratios_data]:
                        if isinstance(table_data, dict):
                            for metric_data in table_data.values():
                                if isinstance(metric_data, dict):
                                    all_quarters.update(metric_data.keys())
                    
                    # Extract metrics for each quarter
                    for quarter_str in all_quarters:
                        q = {'quarter': quarter_str, 'd': quarter_str, 'source': 'screener'}
                        
                        # P&L metrics
                        if isinstance(pl_data, dict):
                            sales = pl_data.get('Sales +', {}).get(quarter_str) or pl_data.get('Sales\xa0+', {}).get(quarter_str)
                            if sales: q['rev'] = parse_number(sales)
                            
                            expenses = pl_data.get('Expenses +', {}).get(quarter_str) or pl_data.get('Expenses\xa0+', {}).get(quarter_str)
                            if expenses: q['expenses'] = parse_number(expenses)
                            
                            op = pl_data.get('Operating Profit', {}).get(quarter_str)
                            if op: q['operating_profit'] = parse_number(op)
                            
                            opm_pct = pl_data.get('OPM %', {}).get(quarter_str)
                            if opm_pct: q['opm'] = parse_number(opm_pct)
                            if 'opm' not in q and 'rev' in q and 'operating_profit' in q and q['rev'] > 0:
                                q['opm'] = (q['operating_profit'] / q['rev']) * 100
                            
                            other_income = pl_data.get('Other Income +', {}).get(quarter_str) or pl_data.get('Other Income\xa0+', {}).get(quarter_str)
                            if other_income: q['other_income'] = parse_number(other_income)
                            
                            interest = pl_data.get('Interest', {}).get(quarter_str)
                            if interest: q['interest'] = parse_number(interest)
                            
                            depreciation = pl_data.get('Depreciation', {}).get(quarter_str)
                            if depreciation: q['depreciation'] = parse_number(depreciation)
                            
                            if 'operating_profit' in q and 'depreciation' in q:
                                q['ebitda'] = q['operating_profit'] + q['depreciation']
                            
                            pbt = pl_data.get('Profit before tax', {}).get(quarter_str)
                            if pbt: q['pbt'] = parse_number(pbt)
                            
                            tax_pct = pl_data.get('Tax %', {}).get(quarter_str)
                            if tax_pct: q['tax_pct'] = parse_number(tax_pct)
                            
                            net = pl_data.get('Net Profit +', {}).get(quarter_str) or pl_data.get('Net Profit\xa0+', {}).get(quarter_str)
                            if net: q['net'] = parse_number(net)
                            
                            eps = pl_data.get('EPS in Rs', {}).get(quarter_str)
                            if eps: q['eps'] = parse_number(eps)
                        
                        # Balance sheet metrics
                        if isinstance(cf_data, dict):
                            equity = cf_data.get('Equity Capital', {}).get(quarter_str)
                            if equity: q['equity_capital'] = parse_number(equity)
                            
                            reserves = cf_data.get('Reserves', {}).get(quarter_str)
                            if reserves: q['reserves'] = parse_number(reserves)
                            
                            borrowings = cf_data.get('Borrowings +', {}).get(quarter_str) or cf_data.get('Borrowings\xa0+', {}).get(quarter_str)
                            if borrowings: q['debt'] = parse_number(borrowings)
                            
                            other_liab = cf_data.get('Other Liabilities +', {}).get(quarter_str) or cf_data.get('Other Liabilities\xa0+', {}).get(quarter_str)
                            if other_liab: q['other_liabilities'] = parse_number(other_liab)
                            
                            total_liab = cf_data.get('Total Liabilities', {}).get(quarter_str)
                            if total_liab: q['total_liabilities'] = parse_number(total_liab)
                            
                            fixed_assets = cf_data.get('Fixed Assets +', {}).get(quarter_str) or cf_data.get('Fixed Assets\xa0+', {}).get(quarter_str)
                            if fixed_assets: q['fixed_assets'] = parse_number(fixed_assets)
                            
                            cwip = cf_data.get('CWIP', {}).get(quarter_str)
                            if cwip: q['cwip'] = parse_number(cwip)
                            
                            investments = cf_data.get('Investments', {}).get(quarter_str)
                            if investments: q['investments'] = parse_number(investments)
                            
                            other_assets = cf_data.get('Other Assets +', {}).get(quarter_str) or cf_data.get('Other Assets\xa0+', {}).get(quarter_str)
                            if other_assets: q['other_assets'] = parse_number(other_assets)
                            
                            total_assets = cf_data.get('Total Assets', {}).get(quarter_str)
                            if total_assets: q['total_assets'] = parse_number(total_assets)
                        
                        # Cash flow metrics (annual)
                        if isinstance(ratios_data, dict):
                            cfo = ratios_data.get('Cash from Operating Activity +', {}).get(quarter_str) or ratios_data.get('Cash from Operating Activity\xa0+', {}).get(quarter_str)
                            if cfo: q['cfo'] = parse_number(cfo)
                            
                            cfi = ratios_data.get('Cash from Investing Activity +', {}).get(quarter_str) or ratios_data.get('Cash from Investing Activity\xa0+', {}).get(quarter_str)
                            if cfi: q['cfi'] = parse_number(cfi)
                            
                            cff = ratios_data.get('Cash from Financing Activity +', {}).get(quarter_str) or ratios_data.get('Cash from Financing Activity\xa0+', {}).get(quarter_str)
                            if cff: q['cff'] = parse_number(cff)
                            
                            net_cf = ratios_data.get('Net Cash Flow', {}).get(quarter_str)
                            if net_cf: q['net_cash_flow'] = parse_number(net_cf)
                            
                            fcf = ratios_data.get('Free Cash Flow', {}).get(quarter_str)
                            if fcf: q['fcf'] = parse_number(fcf)
                            
                            cfo_op = ratios_data.get('CFO/OP', {}).get(quarter_str)
                            if cfo_op: q['cfo_op_ratio'] = parse_number(cfo_op)
                        
                        quarterly_by_period[quarter_str] = q
        
        # === EXTRACT FROM YAHOO FINANCE (Annual) ===
        if has_yahoo:
            yf = stock.get('yahoofin_financials', {})
            if isinstance(yf, dict) and 'observations' in yf and yf['observations']:
                raw = yf['observations'][0].get('raw', {})
                historical = raw.get('historical_periods', [])
                
                for period_data in historical:
                    period_str = period_data.get('period', '')
                    if not period_str:
                        continue
                    
                    # Use existing quarter or create new entry
                    q = quarterly_by_period.get(period_str, {
                        'quarter': period_str,
                        'd': period_str,
                        'source': 'yahoo'
                    })
                    
                    # Revenue (prefer Screener if exists, otherwise Yahoo)
                    if 'rev' not in q and period_data.get('revenue'):
                        q['rev'] = period_data['revenue'] / 10000000  # Convert to Crores
                    
                    # Cost of Revenue
                    if period_data.get('cost_of_revenue'):
                        q['cost_of_revenue'] = period_data['cost_of_revenue'] / 10000000
                    
                    # Gross Profit
                    if period_data.get('gross_profit'):
                        q['gross_profit'] = period_data['gross_profit'] / 10000000
                    
                    # EBITDA (prefer Screener calc, otherwise Yahoo)
                    if 'ebitda' not in q and period_data.get('ebitda'):
                        q['ebitda'] = period_data['ebitda'] / 10000000
                    
                    # EBIT
                    if period_data.get('ebit'):
                        q['ebit'] = period_data['ebit'] / 10000000
                    
                    # Net Profit (prefer Screener)
                    if 'net' not in q and period_data.get('net_profit'):
                        q['net'] = period_data['net_profit'] / 10000000
                    
                    # EPS (prefer Screener)
                    if 'eps' not in q:
                        if period_data.get('diluted_eps'):
                            q['eps'] = period_data['diluted_eps']
                        elif period_data.get('basic_eps'):
                            q['eps'] = period_data['basic_eps']
                    
                    # Depreciation (prefer Screener)
                    if 'depreciation' not in q and period_data.get('depreciation'):
                        q['depreciation'] = period_data['depreciation'] / 10000000
                    
                    # Interest Expense (prefer Screener)
                    if 'interest' not in q and period_data.get('interest_expense'):
                        q['interest'] = period_data['interest_expense'] / 10000000
                    
                    # Debt metrics
                    if period_data.get('total_debt'):
                        q['total_debt'] = period_data['total_debt'] / 10000000
                    if period_data.get('long_term_debt'):
                        q['long_term_debt'] = period_data['long_term_debt'] / 10000000
                    if period_data.get('short_term_debt') and period_data['short_term_debt']:
                        q['short_term_debt'] = period_data['short_term_debt'] / 10000000
                    if period_data.get('net_debt'):
                        q['net_debt'] = period_data['net_debt'] / 10000000
                    
                    # Working Capital
                    if period_data.get('working_capital'):
                        q['working_capital'] = period_data['working_capital'] / 10000000
                    
                    # Cash & Equivalents
                    if period_data.get('cash_and_equivalents'):
                        q['cash'] = period_data['cash_and_equivalents'] / 10000000
                    
                    # Accounts Receivable
                    if period_data.get('accounts_receivable'):
                        q['accounts_receivable'] = period_data['accounts_receivable'] / 10000000
                    
                    # Shares Outstanding
                    if period_data.get('shares_outstanding'):
                        q['shares_outstanding'] = period_data['shares_outstanding']
                    if period_data.get('diluted_shares'):
                        q['diluted_shares'] = period_data['diluted_shares']
                    
                    # Capital
                    if period_data.get('invested_capital'):
                        q['invested_capital'] = period_data['invested_capital'] / 10000000
                    if period_data.get('total_capitalization'):
                        q['total_capitalization'] = period_data['total_capitalization'] / 10000000
                    
                    # Tax Rate
                    if period_data.get('tax_rate'):
                        q['tax_rate'] = period_data['tax_rate'] * 100  # Convert to percentage
                    
                    quarterly_by_period[period_str] = q
        
        # Convert to sorted array
        if quarterly_by_period:
            quarterly = sorted(quarterly_by_period.values(), key=lambda x: parse_quarter_date(x['quarter']))
            stock['quarterly'] = quarterly
            quarterly_count += 1
            metrics_count = len(quarterly[0].keys()) - 3 if quarterly else 0  # Exclude quarter, d, source
            print(f"  ✓ {ticker:12} {len(quarterly)} periods, {metrics_count} metrics/period")
    
    print()
    print(f"Stocks with quarterly/historical data: {quarterly_count}/{len(stocks_array)}")
    print()
    
    # ========================================================================
    # SAVE FINAL OUTPUT
    # ========================================================================
    
    rejections_log_path = 'data/process.json'
    
    success, error = save_json(output, 'data/market_data.json')
    if success:
        print("="*80)
        print("SAVED: data/market_data.json")
        print("="*80)
        print(f"  Stocks: {len(stocks_array)}")
        if output['metadata'].get('portfolio_merged'):
            print(f"  Portfolio: {output['metadata'].get('portfolio_count')} stocks")
        if output['metadata'].get('guidance_merged'):
            print(f"  Guidance: {output['metadata'].get('guidance_count')} stocks")
        print(f"  Decimal precision: 4 places")
        print(f"  Rejections logged to: {rejections_log_path}")
    else:
        print(f"✗ {error}")
    
    print()
    print("="*80)
    print("✅ COMPLETE - READY FOR INDEXDB")
    print("="*80)
    print()
    print("Next steps:")
    print("  1. Open data.html in browser")
    print("  2. Click 🚀 LOAD JSON button")
    print("  3. Open index.html to see your portfolio")
    print()


if __name__ == '__main__':
    main()


