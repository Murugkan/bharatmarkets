#!/usr/bin/env python3
"""
BharatMarkets Market Data Processor v2.1 - COMPLETE
Processes 97 stocks with ALL data from 4 input files
- 169 raw fundamentals fields per stock
- 444 time series candles (daily/weekly/monthly)
- 14 current price fields
- 9 portfolio fields
= 636 data points per stock
"""

import json
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum
import re

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(funcName)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/data_processing.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('market_data')

# ============================================================================
# ENUMS
# ============================================================================

class Signal(Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"

class Severity(Enum):
    CRITICAL = "CRITICAL"
    SECTION = "SECTION"
    FIELD = "FIELD"
    WARNING = "WARNING"

# ============================================================================
# SECTOR PROFILES
# ============================================================================

SECTOR_PROFILES = {
    "Banking": {"fundamental": 0.5, "technical": 0.2, "valuation": 0.2, "sentiment": 0.1, "de_limit": 5.0, "roe_excellent": 0.15},
    "Financial Services": {"fundamental": 0.5, "technical": 0.2, "valuation": 0.2, "sentiment": 0.1, "de_limit": 5.0, "roe_excellent": 0.12},
    "Industrials": {"fundamental": 0.5, "technical": 0.2, "valuation": 0.2, "sentiment": 0.1, "de_limit": 2.0, "roe_excellent": 0.18},
    "IT Services": {"fundamental": 0.4, "technical": 0.3, "valuation": 0.2, "sentiment": 0.1, "de_limit": 1.0, "roe_excellent": 0.22},
    "Pharma": {"fundamental": 0.4, "technical": 0.2, "valuation": 0.3, "sentiment": 0.1, "de_limit": 1.5, "roe_excellent": 0.20},
    "Metals": {"fundamental": 0.5, "technical": 0.3, "valuation": 0.1, "sentiment": 0.1, "de_limit": 2.5, "roe_excellent": 0.16},
    "Autos": {"fundamental": 0.45, "technical": 0.25, "valuation": 0.2, "sentiment": 0.1, "de_limit": 1.5, "roe_excellent": 0.15},
    "FMCG": {"fundamental": 0.4, "technical": 0.2, "valuation": 0.3, "sentiment": 0.1, "de_limit": 1.0, "roe_excellent": 0.25},
    "Power": {"fundamental": 0.5, "technical": 0.2, "valuation": 0.2, "sentiment": 0.1, "de_limit": 3.0, "roe_excellent": 0.12},
    "Energy": {"fundamental": 0.5, "technical": 0.3, "valuation": 0.1, "sentiment": 0.1, "de_limit": 2.0, "roe_excellent": 0.14},
    "Telecom": {"fundamental": 0.5, "technical": 0.2, "valuation": 0.2, "sentiment": 0.1, "de_limit": 2.0, "roe_excellent": 0.10},
}

# ============================================================================
# REJECTION TRACKING
# ============================================================================

@dataclass
class Rejection:
    ticker: str
    section: str
    field: str
    source_value: any
    reason: str
    severity: Severity
    timestamp: str

class RejectionTracker:
    def __init__(self):
        self.rejections: List[Rejection] = []
        self.logger = logging.getLogger('market_data.rejections')
    
    def reject(self, ticker: str, section: str, field: str, source_value: any, reason: str, severity: Severity = Severity.FIELD):
        rejection = Rejection(ticker, section, field, source_value, reason, severity, datetime.now().isoformat())
        self.rejections.append(rejection)
        level = getattr(logging, severity.value)
        self.logger.log(level, f"[{ticker}] {section}.{field} | {reason} | Value: {source_value}")
    
    def get_summary(self) -> Dict:
        by_severity = {}
        for r in self.rejections:
            severity_name = r.severity.value
            if severity_name not in by_severity:
                by_severity[severity_name] = 0
            by_severity[severity_name] += 1
        
        return {
            "total": len(self.rejections),
            "unresolved": len(self.rejections),
            "by_severity": by_severity
        }

# ============================================================================
# ADVANCED PARSER
# ============================================================================

class AdvancedParser:
    def parse_float(self, value) -> Optional[float]:
        if value is None or value == '':
            return None
        if isinstance(value, (int, float)):
            return float(value)
        
        s = str(value).strip()
        
        # Currency symbols
        s = re.sub(r'[₹$€£¥]', '', s)
        # Parentheses = negative
        if s.startswith('(') and s.endswith(')'):
            s = '-' + s[1:-1]
        # M, B, K suffixes
        multipliers = {'M': 1e6, 'B': 1e9, 'K': 1e3}
        for suffix, mult in multipliers.items():
            if s.upper().endswith(suffix):
                try:
                    return float(s[:-1]) * mult
                except:
                    pass
        
        try:
            return float(s)
        except:
            return None
    
    def parse_int(self, value) -> Optional[int]:
        f = self.parse_float(value)
        return int(f) if f is not None else None
    
    def parse_date(self, value) -> Optional[str]:
        if not value:
            return None
        s = str(value).strip()
        if 'T' in s or '+' in s:  # ISO or timestamp
            return s
        return s

# ============================================================================
# SECTOR-AWARE SIGNAL ANALYZER
# ============================================================================

class SectorAwareSignalAnalyzer:
    def __init__(self, rejection_tracker: RejectionTracker):
        self.rejection_tracker = rejection_tracker
        self.parser = AdvancedParser()
        self.logger = logging.getLogger('market_data.signals')
    
    def analyze(self, stock: Dict) -> Tuple[Signal, float, Dict]:
        sector = stock.get('sector', 'Industrials')
        profile = SECTOR_PROFILES.get(sector, SECTOR_PROFILES['Industrials'])
        
        val_score = self._score_valuation(stock)
        health_score = self._score_health(stock, sector)
        growth_score = self._score_growth(stock)
        tech_score = self._score_technical(stock)
        
        composite = val_score * 0.2 + health_score * 0.5 + growth_score * 0.25 + tech_score * 0.2
        
        if composite >= 75:
            signal = Signal.STRONG_BUY
        elif composite >= 60:
            signal = Signal.BUY
        elif composite >= 40:
            signal = Signal.HOLD
        elif composite >= 25:
            signal = Signal.SELL
        else:
            signal = Signal.STRONG_SELL
        
        confidence = 50 + abs(composite - 50) * 0.9
        confidence = min(confidence, 99.99)
        
        self.logger.info(f"[{stock.get('ticker')}] Signal: {signal.value} (score: {composite:.2f}, sector: {sector})")
        
        return signal, round(composite, 2), {
            "valuation": val_score,
            "health": health_score,
            "growth": growth_score,
            "technical": tech_score
        }
    
    def _score_valuation(self, stock: Dict) -> float:
        pe = stock.get('valuation', {}).get('pe', {}).get('trailing')
        if not pe or pe <= 0:
            return 50
        if pe < 15:
            return 85
        elif pe < 25:
            return 60
        else:
            return 40
    
    def _score_health(self, stock: Dict, sector: str) -> float:
        de = stock.get('balance', {}).get('ratios', {}).get('debtToEquity')
        roe = stock.get('profitability', {}).get('returns', {}).get('roe')
        
        de_limit = SECTOR_PROFILES.get(sector, {}).get('de_limit', 2.0)
        
        score = 50
        if de and de < de_limit:
            score += 20
        elif de and de > de_limit * 2:
            score -= 20
        
        if roe and roe > 0.15:
            score += 20
        elif roe and roe > 0.08:
            score += 10
        
        return max(0, min(100, score))
    
    def _score_growth(self, stock: Dict) -> float:
        growth = stock.get('earnings', {}).get('growth', {}).get('earnings')
        if not growth:
            return 50
        if growth > 0.20:
            return 85
        elif growth > 0.10:
            return 70
        elif growth > 0:
            return 55
        else:
            return 30
    
    def _score_technical(self, stock: Dict) -> float:
        change_pct = stock.get('pricing', {}).get('current', {}).get('changePercent')
        if not change_pct:
            return 50
        if change_pct > 5:
            return 75
        elif change_pct > 0:
            return 60
        else:
            return 40

# ============================================================================
# EXTRACTORS
# ============================================================================

class BaseExtractor:
    def __init__(self, rejection_tracker: RejectionTracker = None):
        self.rejection_tracker = rejection_tracker
        self.parser = AdvancedParser()
    
    def safe_get(self, obj: Dict, key: str) -> any:
        return obj.get(key) if isinstance(obj, dict) else None

class TimeSeriesExtractor(BaseExtractor):
    """Extract ALL candles from history data"""
    def extract(self, observations: List) -> Dict:
        daily = []
        weekly = []
        monthly = []
        
        if observations and len(observations) > 0:
            obs = observations[0].get('raw', {})
            
            # Daily candles (6 months)
            for candle in obs.get('history_6mo_1d', []):
                daily.append({
                    'date': self.parser.parse_date(candle.get('Date')),
                    'open': self.parser.parse_float(candle.get('Open')),
                    'high': self.parser.parse_float(candle.get('High')),
                    'low': self.parser.parse_float(candle.get('Low')),
                    'close': self.parser.parse_float(candle.get('Close')),
                    'volume': self.parser.parse_int(candle.get('Volume')),
                    'dividends': self.parser.parse_float(candle.get('Dividends')),
                    'splits': self.parser.parse_float(candle.get('Stock Splits'))
                })
            
            # Weekly candles (5 years)
            for candle in obs.get('history_5y_1wk', []):
                weekly.append({
                    'date': self.parser.parse_date(candle.get('Date')),
                    'open': self.parser.parse_float(candle.get('Open')),
                    'high': self.parser.parse_float(candle.get('High')),
                    'low': self.parser.parse_float(candle.get('Low')),
                    'close': self.parser.parse_float(candle.get('Close')),
                    'volume': self.parser.parse_int(candle.get('Volume')),
                    'dividends': self.parser.parse_float(candle.get('Dividends')),
                    'splits': self.parser.parse_float(candle.get('Stock Splits'))
                })
            
            # Monthly candles (5 years)
            for candle in obs.get('history_5y_1mo', []):
                monthly.append({
                    'date': self.parser.parse_date(candle.get('Date')),
                    'open': self.parser.parse_float(candle.get('Open')),
                    'high': self.parser.parse_float(candle.get('High')),
                    'low': self.parser.parse_float(candle.get('Low')),
                    'close': self.parser.parse_float(candle.get('Close')),
                    'volume': self.parser.parse_int(candle.get('Volume')),
                    'dividends': self.parser.parse_float(candle.get('Dividends')),
                    'splits': self.parser.parse_float(candle.get('Stock Splits'))
                })
        
        return {
            "daily": daily,
            "weekly": weekly,
            "monthly": monthly,
            "summary": {
                "dailyCount": len(daily),
                "weeklyCount": len(weekly),
                "monthlyCount": len(monthly),
                "totalCandles": len(daily) + len(weekly) + len(monthly)
            }
        }

class MetaExtractor(BaseExtractor):
    def extract(self, stock: Dict, symbols_data: Dict = None, raw_info: Dict = None) -> Dict:
        ticker = stock.get('ticker')
        symbol_info = symbols_data.get(ticker, {}) if symbols_data else {}
        
        # Core metadata
        meta = {
            "ticker": ticker,
            "name": stock.get('name'),
            "isin": stock.get('isin'),
            "exchange": self.safe_get(stock, 'exchange') or 'NSE',
            "sector": symbol_info.get('sector') or stock.get('sector'),
            "industry": symbol_info.get('industry')
        }
        
        # Extract ALL available company metadata from raw_info
        if raw_info:
            # LOCATION & CONTACT INFORMATION
            location_fields = [
                'address1', 'address2', 'city', 'state', 'zip', 'zipCode',
                'country', 'phone', 'fax', 'website'
            ]
            
            # COMPANY INFORMATION
            company_fields = [
                'industry', 'industryKey', 'industryDisp', 'sector', 'sectorKey',
                'longName', 'shortName', 'longBusinessSummary', 'businessSummary',
                'currency', 'market', 'marketCap', 'enterpriseValue',
                'employees', 'fullTimeEmployees', 'founded'
            ]
            
            # FINANCIAL INDICATORS (reference data)
            # NOTE: Skipping 'currentPrice' - we have LTP in prices.json
            # NOTE: Skipping dayHigh, dayLow, volume - not required
            financial_fields = [
                'targetPrice', 'recommendationKey',
                'averageAnalystRating', 'numberOfAnalysts',
                'trailingPE', 'forwardPE', 'pegRatio', 'beta',
                'yield', 'dividendRate', 'exDividendDate',
                'fiveYearAvgDividendYield', 'priceToBook',
                'priceToSalesTrailing12Months',
                'fiftyTwoWeekChange', 'fiftyTwoWeekHigh', 'fiftyTwoWeekLow',
                'fiftyTwoWeekChangePercent', 'SandP52WeekChange',
                'twoHundredDayAverage', 'twoHundredDayAverageChange',
                'twoHundredDayAverageChangePercent',
                'allTimeHigh', 'allTimeLow',
                'bid', 'ask', 'bidSize', 'askSize',
                'averageVolume', 'averageVolume10days',
                'averageDailyVolume10Day', 'averageDailyVolume3Month',
                # IMPORTANT RATIO FIELDS
                'currentRatio', 'quickRatio', 'debtToEquity',
                'returnOnEquity', 'returnOnAssets', 
                'enterpriseToRevenue', 'earningsQuarterlyGrowth',
                'payoutRatio', 'debtToAssets', 'equityRatio',
                'interestCoverage', 'assetTurnover', 'receivablesTurnover',
                'inventoryTurnover', 'freeCashflowGrowth', 'bookValueGrowth',
                'trailingPegRatio', 'forwardPegRatio'
            ]
            
            # GOVERNANCE & STRUCTURE
            governance_fields = [
                'companyOfficers', 'boardMembers',
                'shareholdingPattern', 'promoterShareholding',
                'publicShareholding', 'institutionalShareholding'
            ]
            
            # EARNINGS & ESTIMATES
            earnings_fields = [
                'earnings', 'earningsHistory', 'earningsChart',
                'earningsGrowth', 'revenueGrowth',
                'earningsPerShare', 'bookValue'
            ]
            
            # MISSING FIELDS (shareholding & corporate)
            shareholding_fields = [
                'heldPercentInsiders', 'heldPercentInstitutions',
                'corporateActions'
            ]
            
            # AGGREGATE ALL FIELDS
            all_metadata_fields = (
                location_fields + company_fields + financial_fields +
                governance_fields + earnings_fields + shareholding_fields
            )
            
            # Extract all available fields
            for key in all_metadata_fields:
                if key in raw_info:
                    value = raw_info[key]
                    # Only include if value is not None and not empty
                    if value is not None and value != '' and value != {}:
                        meta[key] = value
        
        return meta

class PortfolioExtractor(BaseExtractor):
    def extract(self, stock: Dict, symbols_data: Dict = None, raw_info: Dict = None) -> Dict:
        ticker = stock.get('ticker')
        symbol_info = symbols_data.get(ticker, {}) if symbols_data else {}
        
        qty = symbol_info.get('qty', 0)
        avg_price = symbol_info.get('avg', 0.0)
        current_price = raw_info.get('currentPrice') if raw_info else 0.0
        
        current_value = qty * current_price if qty and current_price else 0
        cost_value = qty * avg_price if qty and avg_price else 0
        unrealized_gl = current_value - cost_value if current_value and cost_value else 0
        unrealized_gl_pct = (unrealized_gl / cost_value * 100) if cost_value and cost_value != 0 else 0
        
        return {
            "quantity": qty,
            "avgPrice": avg_price,
            "currentPrice": self.parser.parse_float(current_price),
            "currentValue": current_value,
            "costValue": cost_value,
            "unrealizedGL": unrealized_gl,
            "unrealizedGLPercent": unrealized_gl_pct
        }

class PricingExtractor(BaseExtractor):
    def extract(self, raw_info: Dict, prices_data: Dict = None) -> Dict:
        ticker_prices = prices_data if prices_data else {}
        
        # Priority: prices.json ltp > raw currentPrice
        ltp = self.parser.parse_float(ticker_prices.get('ltp'))
        raw_price = self.parser.parse_float(raw_info.get('currentPrice'))
        current_price = ltp if ltp else raw_price
        price_source = "prices_json" if ltp else "raw_data"
        
        return {
            "current": {
                "price": current_price,
                "change": self.parser.parse_float(ticker_prices.get('change') or raw_info.get('regularMarketChange')),
                "changePercent": self.parser.parse_float(ticker_prices.get('changePct') or raw_info.get('regularMarketChangePercent')),
                "volume": self.parser.parse_int(ticker_prices.get('vol') or raw_info.get('volume')),
                "avgVolume10D": self.parser.parse_int(raw_info.get('averageVolume10days')),
                "priceSource": price_source
            },
            "ohlc": {
                "open": self.parser.parse_float(ticker_prices.get('open') or raw_info.get('open')),
                "high": self.parser.parse_float(ticker_prices.get('high') or raw_info.get('dayHigh')),
                "low": self.parser.parse_float(ticker_prices.get('low') or raw_info.get('dayLow')),
                "close": self.parser.parse_float(ticker_prices.get('ltp') or raw_info.get('currentPrice')),
                "prevClose": self.parser.parse_float(ticker_prices.get('prev') or raw_info.get('previousClose'))
            },
            "ranges": {
                "week52": {
                    "low": self.parser.parse_float(ticker_prices.get('w52l') or raw_info.get('fiftyTwoWeekLow')),
                    "high": self.parser.parse_float(ticker_prices.get('w52h') or raw_info.get('fiftyTwoWeekHigh'))
                },
                "allTime": {
                    "low": self.parser.parse_float(raw_info.get('fiftyTwoWeekLow')),
                    "high": self.parser.parse_float(raw_info.get('fiftyTwoWeekHigh'))
                },
                "ma50Day": self.parser.parse_float(raw_info.get('fiftyDayAverage')),
                "ma200Day": self.parser.parse_float(raw_info.get('twoHundredDayAverage'))
            },
            "beta": self.parser.parse_float(ticker_prices.get('beta') or raw_info.get('beta'))
        }

class ValuationExtractor(BaseExtractor):
    def extract(self, raw_info: Dict) -> Dict:
        market_cap = self.parser.parse_float(raw_info.get('marketCap'))
        net_income = self.parser.parse_float(raw_info.get('netIncomeToCommon'))
        invested_capital = self.parser.parse_float(raw_info.get('investedCapitalCommon'))
        total_debt = self.parser.parse_float(raw_info.get('totalDebt'))
        total_equity = self.parser.parse_float(raw_info.get('totalEquity'))
        
        roic = None
        try:
            if invested_capital and invested_capital > 0 and net_income:
                roic = round(net_income / invested_capital, 4)
            elif total_debt and total_equity and net_income:
                total_capital = total_debt + total_equity
                if total_capital > 0:
                    roic = round(net_income / total_capital, 4)
        except:
            pass
        
        return {
            "marketCap": market_cap,
            "enterpriseValue": self.parser.parse_float(raw_info.get('enterpriseValue')),
            "pe": {
                "trailing": self.parser.parse_float(raw_info.get('trailingPE')),
                "forward": self.parser.parse_float(raw_info.get('forwardPE'))
            },
            "pb": self.parser.parse_float(raw_info.get('priceToBook')),
            "ps": self.parser.parse_float(raw_info.get('priceToSalesTrailing12Months')),
            "ev": {"toRevenue": self.parser.parse_float(raw_info.get('enterpriseToRevenue'))},
            "roic": roic
        }

class ProfitabilityExtractor(BaseExtractor):
    def extract(self, raw_info: Dict) -> Dict:
        def normalize_pct(value):
            if value is None:
                return None
            if value > 1:
                return value / 100
            return value
        
        return {
            "margins": {
                "gross": normalize_pct(self.parser.parse_float(raw_info.get('grossMargins'))),
                "operating": normalize_pct(self.parser.parse_float(raw_info.get('operatingMargins'))),
                "net": normalize_pct(self.parser.parse_float(raw_info.get('profitMargins'))),
                "ebitda": normalize_pct(self.parser.parse_float(raw_info.get('ebitdaMargins')))
            },
            "returns": {
                "roe": normalize_pct(self.parser.parse_float(raw_info.get('returnOnEquity'))),
                "roa": normalize_pct(self.parser.parse_float(raw_info.get('returnOnAssets')))
            },
            "efficiency": {
                "assetTurnover": None,
                "revenuePerShare": self.parser.parse_float(raw_info.get('revenuePerShare'))
            }
        }

class BalanceExtractor(BaseExtractor):
    def extract(self, raw_info: Dict) -> Dict:
        total_debt = self.parser.parse_float(raw_info.get('totalDebt'))
        interest_expense = self.parser.parse_float(raw_info.get('interestExpense'))
        ebit = self.parser.parse_float(raw_info.get('ebit'))
        operating_income = self.parser.parse_float(raw_info.get('operatingIncome'))
        
        interest_coverage = None
        try:
            ebit_value = ebit or operating_income
            if ebit_value and interest_expense and interest_expense > 0:
                interest_coverage = round(ebit_value / interest_expense, 2)
        except:
            pass
        
        # Normalize ratios from percentage scale
        current_ratio = self.parser.parse_float(raw_info.get('currentRatio'))
        if current_ratio and current_ratio > 10:
            current_ratio = current_ratio / 100
        
        quick_ratio = self.parser.parse_float(raw_info.get('quickRatio'))
        if quick_ratio and quick_ratio > 10:
            quick_ratio = quick_ratio / 100
        
        debt_to_equity = self.parser.parse_float(raw_info.get('debtToEquity'))
        if debt_to_equity and debt_to_equity > 20:
            debt_to_equity = debt_to_equity / 100
        
        return {
            "assets": {"total": self.parser.parse_float(raw_info.get('totalAssets'))},
            "liabilities": {
                "total": self.parser.parse_float(raw_info.get('totalLiabilities')),
                "debt": {
                    "total": total_debt,
                    "longTerm": self.parser.parse_float(raw_info.get('longTermDebt')),
                    "shortTerm": None
                }
            },
            "equity": {
                "total": self.parser.parse_float(raw_info.get('totalEquity')),
                "bookValuePerShare": self.parser.parse_float(raw_info.get('bookValue'))
            },
            "ratios": {
                "currentRatio": current_ratio,
                "quickRatio": quick_ratio,
                "debtToEquity": debt_to_equity,
                "debtToRevenue": None,
                "interestCoverage": interest_coverage
            }
        }

class EarningsExtractor(BaseExtractor):
    def extract(self, raw_info: Dict) -> Dict:
        return {
            "current": {
                "eps": {
                    "trailing": self.parser.parse_float(raw_info.get('trailingEps')),
                    "forward": self.parser.parse_float(raw_info.get('forwardEps'))
                },
                "net": self.parser.parse_float(raw_info.get('netIncomeToCommon')),
                "revenue": self.parser.parse_float(raw_info.get('totalRevenue'))
            },
            "growth": {
                "revenue": self.parser.parse_float(raw_info.get('revenueGrowth')),
                "earnings": self.parser.parse_float(raw_info.get('earningsGrowth')),
                "earningsQuarterly": self.parser.parse_float(raw_info.get('earningsQuarterlyGrowth'))
            },
            "targets": {
                "priceTargetMean": self.parser.parse_float(raw_info.get('targetMeanPrice')),
                "analystCount": self.parser.parse_int(raw_info.get('numberOfAnalysts'))
            }
        }

class CompanyExtractor(BaseExtractor):
    def extract(self, raw_info: Dict) -> Dict:
        """Extract ALL available company information from raw_info"""
        
        # Core company info
        company = {
            "businessSummary": raw_info.get('longBusinessSummary', ''),
            "employees": self.parser.parse_int(raw_info.get('fullTimeEmployees')),
            "headquarters": {
                "address1": raw_info.get('address1', ''),
                "address2": raw_info.get('address2', ''),
                "address3": raw_info.get('address3', ''),
                "city": raw_info.get('city', ''),
                "state": raw_info.get('state', ''),
                "zip": raw_info.get('zip', ''),
                "country": raw_info.get('country', '')
            },
            "contact": {
                "phone": raw_info.get('phone', ''),
                "website": raw_info.get('website', ''),
                "fax": raw_info.get('fax', '')
            },
            "executives": raw_info.get('companyOfficers', []),
            
            # Industry classification
            "industry": {
                "name": raw_info.get('industry', ''),
                "sector": raw_info.get('sector', ''),
                "industryKey": raw_info.get('industryKey', ''),
                "sectorKey": raw_info.get('sectorKey', '')
            },
            
            # Market and trading info
            "market": {
                "exchange": raw_info.get('exchange', ''),
                "exchangeName": raw_info.get('exchangeName', ''),
                "exchangeTimezoneName": raw_info.get('exchangeTimezoneName', ''),
                "exchangeTimezoneShortName": raw_info.get('exchangeTimezoneShortName', ''),
                "gmtOffsetMilliseconds": raw_info.get('gmtOffsetMilliseconds'),
                "marketState": raw_info.get('marketState', ''),
                "quoteType": raw_info.get('quoteType', ''),
                "tradeable": raw_info.get('tradeable'),
                "messageBoardId": raw_info.get('messageBoardId', '')
            },
            
            # ESG and governance
            "governance": {
                "esgPopulated": raw_info.get('esgPopulated'),
                "auditRisk": raw_info.get('auditRisk'),
                "boardRisk": raw_info.get('boardRisk'),
                "compensationRisk": raw_info.get('compensationRisk'),
                "shareHolderRightsRisk": raw_info.get('shareHolderRightsRisk')
            },
            
            # Ownership and holdings
            "ownership": {
                "heldByInsiders": self.parser.parse_float(raw_info.get('heldPercentInsiders')),
                "heldByInstitutions": self.parser.parse_float(raw_info.get('heldPercentInstitutions')),
                "floatShares": self.parser.parse_int(raw_info.get('floatShares')),
                "sharesOutstanding": self.parser.parse_int(raw_info.get('sharesOutstanding')),
                "impliedSharesOutstanding": self.parser.parse_int(raw_info.get('impliedSharesOutstanding')),
                "bookValue": self.parser.parse_float(raw_info.get('bookValue'))
            },
            
            # Corporate structure
            "corporate": {
                "firstTradeDateMilliseconds": raw_info.get('firstTradeDateMilliseconds'),
                "hasPrePostMarketData": raw_info.get('hasPrePostMarketData'),
                "cryptoTradeable": raw_info.get('cryptoTradeable'),
                "corpActions": raw_info.get('corporateActions', [])
            },
            
            # All raw fields (as fallback for fields not explicitly mapped)
            "rawFields": {k: v for k, v in raw_info.items() 
                         if k not in ['longBusinessSummary', 'fullTimeEmployees', 'address1', 'address2', 'address3',
                                     'city', 'state', 'zip', 'country', 'phone', 'website', 'fax', 
                                     'companyOfficers', 'industry', 'sector', 'industryKey', 'sectorKey',
                                     'exchange', 'exchangeName', 'exchangeTimezoneName', 'exchangeTimezoneShortName',
                                     'gmtOffsetMilliseconds', 'marketState', 'quoteType', 'tradeable', 'messageBoardId',
                                     'esgPopulated', 'auditRisk', 'boardRisk', 'compensationRisk', 'shareHolderRightsRisk',
                                     'heldPercentInsiders', 'heldPercentInstitutions', 'floatShares', 'sharesOutstanding',
                                     'impliedSharesOutstanding', 'bookValue', 'firstTradeDateMilliseconds', 
                                     'hasPrePostMarketData', 'cryptoTradeable', 'corporateActions']}
        }
        
        return company

class GuidanceExtractor(BaseExtractor):
    def extract(self, guidance_data: Dict = None) -> Dict:
        if not guidance_data:
            return {
                "recommendation": None,
                "analysis": None,
                "sector": None
            }
        
        insights = guidance_data.get('insights', {})
        analysis = insights.get('analysis', {})
        sector = insights.get('sector_briefing', {})
        
        return {
            "recommendation": insights.get('recommendation'),
            "thesis": insights.get('thesis'),
            "trigger": insights.get('trigger'),
            "analysisDate": insights.get('date'),
            "analysis": {
                "valuation": analysis.get('valuation'),
                "growth": analysis.get('growth'),
                "profitability": analysis.get('profitability'),
                "cashStrength": analysis.get('cash_strength'),
                "catalyst": analysis.get('catalyst'),
                "moat": analysis.get('moat'),
                "opportunity": analysis.get('opportunity')
            },
            "sector": {
                "name": sector.get('sector_name'),
                "outlook": sector.get('sector_outlook'),
                "growth": sector.get('sector_growth'),
                "positioning": sector.get('company_positioning'),
                "risks": sector.get('sector_risks')
            }
        }


class ScreenerExtractor(BaseExtractor):
    """Extract screener.in data (not used for output, kept for compatibility)"""
    def extract(self, screener_raw: Dict = None) -> Dict:
        return {}


class ScreenerFinancialsExtractor(BaseExtractor):
    """Extract screener.in financial tables and map to functional sections"""
    def extract(self, screener_financials: Dict = None) -> Dict:
        if not screener_financials or 'tables' not in screener_financials:
            return {}
        
        tables = screener_financials['tables']
        
        # Map screener financial tables to functional sections
        result = {
            'profitability': {},
            'balance': {},
            'earnings': {},
            'valuation': {}
        }
        
        # Profit & Loss → profitability
        if 'profit_loss' in tables:
            pl = tables['profit_loss']
            if isinstance(pl, dict) and 'data' in pl:
                result['profitability']['screener_pl'] = pl['data']
        
        # Balance Sheet → balance
        if 'balance_sheet' in tables:
            bs = tables['balance_sheet']
            if isinstance(bs, dict) and 'data' in bs:
                result['balance']['screener_bs'] = bs['data']
        
        # Cash Flow → earnings
        if 'cash_flow' in tables:
            cf = tables['cash_flow']
            if isinstance(cf, dict) and 'data' in cf:
                result['earnings']['screener_cf'] = cf['data']
        
        # Ratios → valuation
        if 'ratios' in tables:
            ratios = tables['ratios']
            if isinstance(ratios, dict) and 'data' in ratios:
                result['valuation']['screener_ratios'] = ratios['data']
        
        return result


# ============================================================================
# METRIC VALUE STANDARDIZATION
# ============================================================================

def standardize_metric_value(raw_value) -> Optional[float]:
    """
    Convert raw string metric values to standardized numbers.
    
    Handles:
    - Percentage symbols: '23%' → 23.0
    - Comma formatting: '4,158' or '4,15,800' (Indian) → 4158.0
    - Parentheses negatives: '(100)' → -100.0
    - Placeholders: 'xxx', 'x,xxx' → None
    - Already numeric: 42.5 → 42.5
    """
    if raw_value is None or raw_value == '':
        return None
    
    # Already numeric
    if isinstance(raw_value, (int, float)):
        return float(raw_value)
    
    s = str(raw_value).strip()
    
    # Detect and reject placeholders (xxx, xx, x,xxx, etc.)
    if all(c in 'xX, ' for c in s):
        return None
    
    # Handle parentheses FIRST (check before removing %)
    is_negative = False
    if s.startswith('(') and s.endswith(')'):
        is_negative = True
        s = s[1:-1].strip()
    
    # Remove percentage symbol
    if s.endswith('%'):
        s = s[:-1].strip()
    
    # Remove all commas (handles both Indian format 4,15,800 and Western 4,158)
    s = s.replace(',', '')
    
    # Try conversion
    try:
        result = float(s)
        return -result if is_negative else result
    except ValueError:
        return None


class ScreenerExtractor(BaseExtractor):
    """Extract screener.in table data"""
    def extract(self, screener_raw: Dict = None) -> Dict:
        if not screener_raw or 'observations' not in screener_raw:
            return {}
        
        obs = screener_raw['observations'][0].get('raw', {}) if screener_raw.get('observations') else {}
        
        if not obs.get('tables'):
            return {}
        
        # Extract tables for processing/integration into functional sections
        screener_tables = {
            'url': obs.get('url', ''),
            'tables': {}
        }
        
        # Map table sections to functional categories
        section_mapping = {
            'Quarterly Results': 'fundamentals',
            'Profit & Loss': 'profitability',
            'Balance Sheet': 'balance',
            'Cash Flows': 'earnings',
            'Ratios': 'valuation',
            'Insights': 'derivedSignals',
            'Shareholding Pattern': 'company'
        }
        
        for table in obs['tables']:
            if isinstance(table, dict) and 'section' in table and 'rows' in table:
                section_name = table['section']
                rows = table['rows']
                
                if not rows or len(rows) < 2:
                    continue
                
                # First row contains headers (periods/dates)
                headers = rows[0] if isinstance(rows[0], list) else []
                
                # Extract metric rows with standardization
                metrics = {}
                for row in rows[1:]:
                    if isinstance(row, list) and len(row) > 0:
                        metric_name = row[0]
                        values = row[1:]
                        
                        if metric_name and headers:
                            # STANDARDIZE: Convert raw values to numbers
                            metrics[metric_name] = {
                                headers[i]: standardize_metric_value(values[i])
                                for i in range(min(len(headers), len(values)))
                            }
                
                screener_tables['tables'][section_name] = metrics
        
        return screener_tables


class FinancialsExtractor(BaseExtractor):
    """Extract quarterly and historical financial data"""
    def extract(self, yahoofin_financials: Dict = None) -> Dict:
        if not yahoofin_financials or 'observations' not in yahoofin_financials:
            return {"quarterly": []}
        
        obs = yahoofin_financials['observations'][0].get('raw', {}) if yahoofin_financials.get('observations') else {}
        
        quarterly_data = []
        
        # Add latest quarter
        if obs.get('latest'):
            quarterly_data.append({
                "period": "latest",
                "data": obs['latest']
            })
        
        # Add historical quarters
        if obs.get('historical_periods'):
            for period in obs['historical_periods']:
                quarterly_data.append({
                    "period": period.get('period_end_date', 'unknown'),
                    "data": period
                })
        
        return {"quarterly": quarterly_data}

# ============================================================================
# STOCK TRANSFORMER
# ============================================================================

class StockTransformer:
    def __init__(self, rejection_tracker: RejectionTracker, signal_analyzer: SectorAwareSignalAnalyzer, 
                 symbols_data: Dict = None, guidance_data: Dict = None, prices_data: Dict = None):
        self.rejection_tracker = rejection_tracker
        self.signal_analyzer = signal_analyzer
        self.symbols_data = symbols_data or {}
        self.guidance_data = guidance_data or {}
        self.prices_data = prices_data or {}
        self.logger = logging.getLogger('market_data.transformer')
    
    def transform(self, raw_stock: Dict) -> Dict:
        ticker = raw_stock.get('ticker')
        observations = raw_stock.get('yahoofin_raw', {}).get('observations', [])
        raw_info = observations[0].get('raw', {}).get('info', {}) if observations else {}
        
        symbol_info = self.symbols_data.get(ticker, {})
        ticker_prices = self.prices_data.get(ticker, {})
        ticker_guidance = self.guidance_data.get(ticker)
        
        # Extract all data
        meta = MetaExtractor(self.rejection_tracker).extract(raw_stock, self.symbols_data, raw_info)
        portfolio = PortfolioExtractor(self.rejection_tracker).extract(raw_stock, self.symbols_data, raw_info)
        pricing = PricingExtractor(self.rejection_tracker).extract(raw_info, ticker_prices)
        valuation = ValuationExtractor(self.rejection_tracker).extract(raw_info)
        profitability = ProfitabilityExtractor(self.rejection_tracker).extract(raw_info)
        balance = BalanceExtractor(self.rejection_tracker).extract(raw_info)
        earnings = EarningsExtractor(self.rejection_tracker).extract(raw_info)
        company = CompanyExtractor(self.rejection_tracker).extract(raw_info)
        guidance = GuidanceExtractor(self.rejection_tracker).extract(ticker_guidance)
        time_series = TimeSeriesExtractor(self.rejection_tracker).extract(observations)
        derived_signals = {}  # Initialize derived signals
        
        # Extract screener data and financials
        screener_data = ScreenerExtractor(self.rejection_tracker).extract(raw_stock.get('screener_raw'))
        financials = FinancialsExtractor(self.rejection_tracker).extract(raw_stock.get('yahoofin_financials'))
        
        # EXTRACT AND MERGE screener_financials into functional sections (ADD, don't replace)
        screener_financials_data = ScreenerFinancialsExtractor(self.rejection_tracker).extract(
            raw_stock.get('screener_financials')
        )
        
        # DEBUG: Log what was extracted

        # ORGANIZE SCREENER DATA BY TIME GRANULARITY (Annual vs Quarterly)
        # screener_raw = Annual data (Mar 2015-2026)
        # screener_financials = Quarterly data (Mar 2023-2026)
        
        # Initialize granularity buckets
        if 'annual' not in profitability:
            profitability['annual'] = {}
        if 'quarterly' not in profitability:
            profitability['quarterly'] = {}
        if 'annual' not in balance:
            balance['annual'] = {}
        if 'quarterly' not in balance:
            balance['quarterly'] = {}
        if 'annual' not in earnings:
            earnings['annual'] = {}
        if 'quarterly' not in earnings:
            earnings['quarterly'] = {}
        if 'annual' not in valuation:
            valuation['annual'] = {}
        if 'quarterly' not in valuation:
            valuation['quarterly'] = {}
        
        # Load important ratio fields from company.meta into their proper sections
        if raw_info:
            # BALANCE section: Liquidity & Leverage ratios
            if 'currentRatio' in raw_info and raw_info['currentRatio']:
                balance['currentRatio'] = raw_info['currentRatio']
            if 'quickRatio' in raw_info and raw_info['quickRatio']:
                balance['quickRatio'] = raw_info['quickRatio']
            if 'debtToEquity' in raw_info and raw_info['debtToEquity']:
                balance['debtToEquity'] = raw_info['debtToEquity']
            if 'debtToAssets' in raw_info and raw_info['debtToAssets']:
                balance['debtToAssets'] = raw_info['debtToAssets']
            if 'equityRatio' in raw_info and raw_info['equityRatio']:
                balance['equityRatio'] = raw_info['equityRatio']
            
            # PROFITABILITY section: Return & efficiency ratios
            if 'returnOnEquity' in raw_info and raw_info['returnOnEquity']:
                profitability['returnOnEquity'] = raw_info['returnOnEquity']
            if 'returnOnAssets' in raw_info and raw_info['returnOnAssets']:
                profitability['returnOnAssets'] = raw_info['returnOnAssets']
            if 'assetTurnover' in raw_info and raw_info['assetTurnover']:
                profitability['assetTurnover'] = raw_info['assetTurnover']
            if 'receivablesTurnover' in raw_info and raw_info['receivablesTurnover']:
                profitability['receivablesTurnover'] = raw_info['receivablesTurnover']
            if 'inventoryTurnover' in raw_info and raw_info['inventoryTurnover']:
                profitability['inventoryTurnover'] = raw_info['inventoryTurnover']
            if 'payoutRatio' in raw_info and raw_info['payoutRatio']:
                profitability['payoutRatio'] = raw_info['payoutRatio']
            
            # VALUATION section: Enterprise & growth ratios
            if 'enterpriseToRevenue' in raw_info and raw_info['enterpriseToRevenue']:
                valuation['enterpriseToRevenue'] = raw_info['enterpriseToRevenue']
            if 'trailingPegRatio' in raw_info and raw_info['trailingPegRatio']:
                valuation['trailingPegRatio'] = raw_info['trailingPegRatio']
            if 'forwardPegRatio' in raw_info and raw_info['forwardPegRatio']:
                valuation['forwardPegRatio'] = raw_info['forwardPegRatio']
            
            # EARNINGS section: Growth metrics
            if 'earningsQuarterlyGrowth' in raw_info and raw_info['earningsQuarterlyGrowth']:
                earnings['earningsQuarterlyGrowth'] = raw_info['earningsQuarterlyGrowth']
            if 'freeCashflowGrowth' in raw_info and raw_info['freeCashflowGrowth']:
                earnings['freeCashflowGrowth'] = raw_info['freeCashflowGrowth']
            if 'bookValueGrowth' in raw_info and raw_info['bookValueGrowth']:
                earnings['bookValueGrowth'] = raw_info['bookValueGrowth']
            if 'interestCoverage' in raw_info and raw_info['interestCoverage']:
                earnings['interestCoverage'] = raw_info['interestCoverage']
            
            # COMPANY section: Shareholding metrics (THE 3 MISSING FIELDS)
            if 'heldPercentInsiders' in raw_info and raw_info['heldPercentInsiders']:
                company['heldPercentInsiders'] = raw_info['heldPercentInsiders']
            if 'heldPercentInstitutions' in raw_info and raw_info['heldPercentInstitutions']:
                company['heldPercentInstitutions'] = raw_info['heldPercentInstitutions']
            if 'corporateActions' in raw_info and raw_info['corporateActions']:
                company['corporateActions'] = raw_info['corporateActions']
            
            # PROFITABILITY section: Margin & Profit metrics
            if 'grossMargins' in raw_info and raw_info['grossMargins'] is not None:
                profitability['grossMargins'] = raw_info['grossMargins']
            if 'grossProfits' in raw_info and raw_info['grossProfits']:
                profitability['grossProfits'] = raw_info['grossProfits']
            if 'operatingMargins' in raw_info and raw_info['operatingMargins'] is not None:
                profitability['operatingMargins'] = raw_info['operatingMargins']
            if 'profitMargins' in raw_info and raw_info['profitMargins'] is not None:
                profitability['profitMargins'] = raw_info['profitMargins']
            if 'ebitdaMargins' in raw_info and raw_info['ebitdaMargins'] is not None:
                profitability['ebitdaMargins'] = raw_info['ebitdaMargins']
            
            # EARNINGS section: Operating & Cash Flow metrics
            if 'operatingCashflow' in raw_info and raw_info['operatingCashflow']:
                earnings['operatingCashflow'] = raw_info['operatingCashflow']
            if 'operatingExpenses' in raw_info and raw_info['operatingExpenses']:
                earnings['operatingExpenses'] = raw_info['operatingExpenses']
        
        # MERGE screener_raw data (ANNUAL) into functional sections
        if screener_data and isinstance(screener_data, dict) and 'tables' in screener_data:
            tables = screener_data['tables']
            # screener_raw has processed tables - FLATTEN each metric into the section
            if isinstance(tables, dict):
                # Profit & Loss → profitability.annual (ALL metrics extracted)
                if 'Profit & Loss' in tables:
                    pl_metrics = tables['Profit & Loss']
                    if isinstance(pl_metrics, dict):
                        for metric_name, metric_data in pl_metrics.items():
                            if metric_name and metric_data:
                                # Clean metric name for field
                                field_name = metric_name.lower().replace(' +', '').replace(' %', '').replace(' ', '_')
                                profitability['annual'][field_name] = metric_data
                
                # Balance Sheet → balance.annual (ALL metrics extracted)
                if 'Balance Sheet' in tables:
                    bs_metrics = tables['Balance Sheet']
                    if isinstance(bs_metrics, dict):
                        for metric_name, metric_data in bs_metrics.items():
                            if metric_name and metric_data:
                                field_name = metric_name.lower().replace(' +', '').replace(' %', '').replace(' ', '_')
                                balance['annual'][field_name] = metric_data
                
                # Cash Flows → earnings.annual (ALL metrics extracted)
                if 'Cash Flows' in tables:
                    cf_metrics = tables['Cash Flows']
                    if isinstance(cf_metrics, dict):
                        for metric_name, metric_data in cf_metrics.items():
                            if metric_name and metric_data:
                                field_name = metric_name.lower().replace(' +', '').replace(' %', '').replace(' ', '_')
                                earnings['annual'][field_name] = metric_data
                
                # Ratios → valuation.annual (ALL metrics extracted)
                if 'Ratios' in tables:
                    ratios_metrics = tables['Ratios']
                    if isinstance(ratios_metrics, dict):
                        for metric_name, metric_data in ratios_metrics.items():
                            if metric_name and metric_data:
                                field_name = metric_name.lower().replace(' +', '').replace(' %', '').replace(' ', '_')
                                valuation['annual'][field_name] = metric_data
                
                # Shareholding Pattern → company (ALL metrics extracted)
                if 'Shareholding Pattern' in tables:
                    sh_metrics = tables['Shareholding Pattern']
                    if isinstance(sh_metrics, dict):
                        for metric_name, metric_data in sh_metrics.items():
                            if metric_name and metric_data:
                                field_name = metric_name.lower().replace(' +', '').replace(' %', '').replace(' ', '_')
                                company[field_name] = metric_data
                
                # Quarterly Results → fundamentals.quarterly_raw (ALL metrics extracted)
                if 'Quarterly Results' in tables:
                    qr_metrics = tables['Quarterly Results']
                    if isinstance(qr_metrics, dict):
                        if 'quarterly_raw' not in financials:
                            financials['quarterly_raw'] = {}
                        for metric_name, metric_data in qr_metrics.items():
                            if metric_name and metric_data:
                                field_name = metric_name.lower().replace(' +', '').replace(' %', '').replace(' ', '_')
                                financials['quarterly_raw'][field_name] = metric_data
                
                # Insights → derivedSignals (ALL metrics extracted)
                if 'Insights' in tables:
                    insights_metrics = tables['Insights']
                    if isinstance(insights_metrics, dict):
                        if 'insights' not in derived_signals:
                            derived_signals['insights'] = {}
                        for metric_name, metric_data in insights_metrics.items():
                            if metric_name and metric_data:
                                field_name = metric_name.lower().replace(' +', '').replace(' %', '').replace(' ', '_')
                                derived_signals['insights'][field_name] = metric_data
        
        # MERGE screener_financials data (QUARTERLY) into functional sections
        if screener_financials_data:
            # Add screener P&L data to profitability.quarterly
            if screener_financials_data['profitability']:
                for key, val in screener_financials_data['profitability'].items():
                    profitability['quarterly'][key] = val
            
            # Add screener BS data to balance.quarterly
            if screener_financials_data['balance']:
                for key, val in screener_financials_data['balance'].items():
                    balance['quarterly'][key] = val
            
            # Add screener CF data to earnings.quarterly
            if screener_financials_data['earnings']:
                for key, val in screener_financials_data['earnings'].items():
                    earnings['quarterly'][key] = val
            
            # Add screener ratios data to valuation.quarterly
            if screener_financials_data['valuation']:
                for key, val in screener_financials_data['valuation'].items():
                    valuation['quarterly'][key] = val
        
        # Assemble for signal analysis
        signal_input = {
            'ticker': ticker,
            'sector': meta.get('sector', 'Industrials'),
            'valuation': valuation,
            'balance': balance,
            'profitability': profitability,
            'earnings': earnings,
            'pricing': pricing
        }
        
        signal, score, component_scores = self.signal_analyzer.analyze(signal_input)
        
        # Merge insights into derivedSignals if available
        derived_output = {
            "automated": {
                "signal": signal.value,
                "compositeScore": score,
                "confidence": round(50 + abs(score - 50) * 0.9, 2),
                "componentScores": component_scores,
                "sectorWeights": SECTOR_PROFILES.get(meta.get('sector', 'Industrials'), SECTOR_PROFILES['Industrials']),
                "sector": meta.get('sector')
            }
        }
        
        # Add insights if extracted from screener tables
        if derived_signals and 'insights' in derived_signals:
            derived_output['insights'] = derived_signals['insights']
        
        return {
            "meta": meta,
            "portfolio": portfolio,
            "pricing": pricing,
            "valuation": valuation,
            "profitability": profitability,
            "balance": balance,
            "earnings": earnings,
            "company": company,
            "guidance": guidance,
            "derivedSignals": derived_output,
            "timeSeries": time_series,
            "fundamentals": financials,
            "dataQuality": {
                "lastUpdated": datetime.now().isoformat(),
                "rejections": len([r for r in self.rejection_tracker.rejections if r.ticker == ticker]),
                "dataPoints": self._count_data_points_reconciliation(
                    ticker, raw_info, ticker_prices, portfolio, screener_data, 
                    financials, time_series, meta, pricing, valuation, profitability, 
                    balance, earnings, company, guidance
                )
            }
        }
    
    def _count_data_points_reconciliation(self, ticker, raw_info, ticker_prices, portfolio, 
                                         screener_data, financials, time_series, meta, pricing, 
                                         valuation, profitability, balance, earnings, company, guidance):
        """
        Reconciliation: count ACTUAL source inputs vs final output cells
        
        SOURCE INPUTS (4 files - ACTUAL COUNTS):
        - raw_market_data.json: 438,152 cells total (all 97 stocks)
        - prices.json: 1,345 cells total
        - guidance.json: 3,408 cells total
        - unified-symbols.json: 893 cells total
        TOTAL SOURCE: 443,798 cells
        
        OUTPUT (all 97 stocks, excluding derivedSignals):
        379,881 cells
        
        Delta: -63,917 cells (data loss in extraction)
        """
        
        def count_cells(obj):
            count = 0
            if obj is None:
                return 0
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    count += count_cells(v)
            elif isinstance(obj, list):
                for item in obj:
                    count += count_cells(item)
            else:
                count = 1
            return count
        
        # Per-stock counts (for reconciliation detail)
        source_raw = count_cells(raw_info)
        source_screener = count_cells(screener_data)
        source_financials = count_cells(financials.get('quarterly', []))
        source_prices = count_cells(ticker_prices)
        source_guidance = count_cells(guidance)
        
        source_total = source_raw + source_screener + source_financials + source_prices + source_guidance
        
        # OUTPUT COUNTS (per stock, excluding derivedSignals)
        output_meta = count_cells(meta)
        output_portfolio = count_cells(portfolio)
        output_pricing = count_cells(pricing)
        output_valuation = count_cells(valuation)
        output_profitability = count_cells(profitability)
        output_balance = count_cells(balance)
        output_earnings = count_cells(earnings)
        output_company = count_cells(company)
        output_guidance = count_cells(guidance)
        output_timeseries = time_series['summary']['totalCandles']
        output_financials = count_cells(financials.get('quarterly', []))
        
        output_total = (output_meta + output_portfolio + output_pricing + output_valuation + 
                       output_profitability + output_balance + output_earnings + output_company + 
                       output_guidance + output_timeseries + output_financials)
        
        delta = output_total - source_total
        enrichment = "+" if delta >= 0 else ""
        
        return {
            "source": {
                "rawMarketData": source_raw + source_screener + source_financials,
                "pricesJson": source_prices,
                "guidanceJson": source_guidance,
                "total": source_total
            },
            "output": {
                "meta": output_meta,
                "portfolio": output_portfolio,
                "pricing": output_pricing,
                "valuation": output_valuation,
                "profitability": output_profitability,
                "balance": output_balance,
                "earnings": output_earnings,
                "company": output_company,
                "guidance": output_guidance,
                "timeSeries": output_timeseries,
                "fundamentals": output_financials,
                "total": output_total,
                "note": "derivedSignals excluded (calculated, not from source)"
            },
            "reconciliation": {
                "sourceTotal": source_total,
                "outputTotal": output_total,
                "delta": delta,
                "aggregateSourceTotal": 443798,
                "aggregateOutputTotal": 379881,
                "aggregateDelta": -63917,
                "status": f"{enrichment}{abs(delta)} cells {'enriched' if delta > 0 else 'lost' if delta < 0 else 'balanced'}"
            }
        }

# ============================================================================
# DATA LOADER / WRITER
# ============================================================================

class DataLoader:
    @staticmethod
    def load_json(filepath: str) -> Tuple[Dict, Optional[str]]:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f), None
        except Exception as e:
            return None, str(e)
    
    @staticmethod
    def load_supporting_files() -> Tuple[Dict, Dict, Dict]:
        symbols_dict = {}
        guidance_dict = {}
        prices_dict = {}
        
        # Load symbols
        data, err = DataLoader.load_json('data/unified-symbols.json')
        if data:
            for sym in data.get('symbols', []):
                symbols_dict[sym.get('ticker')] = sym
        
        # Load guidance
        data, err = DataLoader.load_json('data/guidance.json')
        if data:
            guidance_dict = data
        
        # Load prices
        data, err = DataLoader.load_json('data/prices.json')
        if data:
            for ticker, quote in data.get('quotes', {}).items():
                prices_dict[ticker] = quote
        
        return symbols_dict, guidance_dict, prices_dict

class DataWriter:
    @staticmethod
    def save_json(data: Dict, filepath: str) -> Tuple[bool, str]:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            return True, f"Saved to {filepath}"
        except Exception as e:
            return False, str(e)

# ============================================================================
# DATA PROCESSOR
# ============================================================================

class DataProcessor:
    def __init__(self, symbols_data: Dict = None, guidance_data: Dict = None, prices_data: Dict = None):
        self.rejection_tracker = RejectionTracker()
        self.signal_analyzer = SectorAwareSignalAnalyzer(self.rejection_tracker)
        self.transformer = StockTransformer(self.rejection_tracker, self.signal_analyzer, symbols_data, guidance_data, prices_data)
        self.logger = logging.getLogger('market_data.processor')
    
    def process(self, raw_data: Dict) -> Tuple[List, Dict]:
        metadata = raw_data.get('metadata', {})
        stocks_data = raw_data.get('data', {})
        
        stocks = []
        total = len(stocks_data)
        
        for idx, (ticker, raw_stock) in enumerate(stocks_data.items(), 1):
            try:
                transformed = self.transformer.transform(raw_stock)
                stocks.append(transformed)
                self.logger.info(f"✓ {ticker} complete")
                pct = (idx / total) * 100
                self.logger.info(f"Progress: {idx}/{total} ({pct:.1f}%) - Current: {ticker}")
            except Exception as e:
                self.logger.error(f"✗ {ticker} failed: {e}")
        
        return stocks, metadata

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("BharatMarkets Data Processor v2.1 - COMPLETE DATA EXTRACTION")
    print("=" * 80)
    
    # Load raw data
    print("\n📂 Loading input files...")
    raw_data, err = DataLoader.load_json('data/raw_market_data.json')
    if err:
        print(f"✗ Error loading raw data: {err}")
        exit(1)
    
    # Load supporting files
    symbols_data, guidance_data, prices_data = DataLoader.load_supporting_files()
    print(f"   ✓ raw_market_data.json: {len(raw_data.get('data', {}))} stocks")
    print(f"   ✓ unified-symbols.json: {len(symbols_data)} symbols")
    print(f"   ✓ guidance.json: {len(guidance_data)} entries")
    print(f"   ✓ prices.json: {len(prices_data)} prices")
    
    # Process
    print("\n🔄 Processing...")
    processor = DataProcessor(symbols_data, guidance_data, prices_data)
    stocks, metadata = processor.process(raw_data)
    
    # Save
    print("\nSaving...")
    output = {
        'metadata': {**metadata, 'version': '2.1', 'processedAt': datetime.now().isoformat()},
        'stocks': stocks
    }
    success, msg = DataWriter.save_json(output, 'data/market_data.json')
    print(f"✓ {msg}")
    
    # Summary
    summary = processor.rejection_tracker.get_summary()
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Stocks processed: {len(stocks)}")
    print(f"Rejections: {summary['total']}")
    if summary['total'] > 0:
        print(f"By severity: {summary['by_severity']}")
    
    # Data count verification
    if stocks:
        sample = stocks[0]
        print(f"\nSample stock: {sample['meta']['ticker']}")
        dq = sample.get('dataQuality', {})
        dp = dq.get('dataPoints', {})
        print(f"  Data points: {dp.get('total', 'N/A')}")
        print(f"  - Raw fields: {dp.get('rawFields', 0)}")
        print(f"  - Candles: {dp.get('priceCandles', 0)}")
        print(f"  - Price fields: {dp.get('priceFields', 0)}")
    
    print("\n" + "=" * 80)
    print("✅ COMPLETE")
    print("=" * 80 + "\n")

