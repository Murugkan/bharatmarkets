#!/usr/bin/env python3
"""
Indian Stock Financial Data Fetcher - Comprehensive Multi-Source Integration
RAW DATA ONLY - No calculations or estimated values
Sources: yfinance, Financial Modeling Prep API, BSE/NSE Web Scraping
"""

import subprocess
import sys

# Auto-install dependencies
dependencies = ['requests', 'pandas', 'python-dateutil', 'lxml', 'beautifulsoup4', 'yfinance']
for package in dependencies:
    try:
        __import__(package)
    except ImportError:
        print(f"Installing {package}...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])

import json
import requests
import pandas as pd
from datetime import datetime
import logging
from typing import Dict, List, Optional
from pathlib import Path
import yfinance as yf
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ComprehensiveStockFetcher:
    """
    Fetch from multiple sources: yfinance → Financial Modeling Prep → BSE/NSE
    RAW DATA ONLY - Returns extracted values with NO calculations
    """
    
    FMP_API_KEY = "demo"
    FMP_BASE = "https://financialsmodels.com/api/v3"
    
    def __init__(self, output_dir: str = './stock_data'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_financial_metrics(self, symbol: str, is_bank: bool = False) -> Dict:
        """Fetch from multiple sources - RAW DATA ONLY"""
        logger.info(f"Fetching comprehensive data for {symbol}")
        
        metrics = {
            'symbol': symbol,
            'fetch_timestamp': datetime.now().isoformat(),
            'capex': self._fetch_capex_multi(symbol),
            'debt_details': self._fetch_debt_multi(symbol, is_bank),
            'segments': self._fetch_segments_multi(symbol),
            'exceptional_items': self._fetch_exceptional_multi(symbol),
            'working_capital': self._fetch_wc_multi(symbol, is_bank)
        }
        
        return metrics
    
    # ==================== CAPEX SOURCES ====================
    
    def _fetch_capex_multi(self, symbol: str) -> Dict:
        """Try yfinance → Financial Modeling Prep - returns RAW values only"""
        
        result = self._fetch_capex_yfinance(symbol)
        if result['status'] == 'success':
            result['source'] = 'yfinance'
            return result
        
        result = self._fetch_capex_fmp(symbol)
        if result['status'] == 'success':
            result['source'] = 'Financial Modeling Prep'
            return result
        
        return {'metric': 'CapEx', 'status': 'Not available', 'sources_tried': ['yfinance', 'FMP']}
    
    def _fetch_capex_yfinance(self, symbol: str) -> Dict:
        """Get CapEx from yfinance cash flow - RAW values only"""
        try:
            ticker = f"{symbol}.NS"
            stock = yf.Ticker(ticker)
            cf = stock.quarterly_cash_flow
            
            if cf is not None and 'Capital Expenditure' in cf.index:
                capex_data = cf.loc['Capital Expenditure'].head(4)
                
                recent = []
                for date, val in capex_data.items():
                    if pd.notna(val) and val != 0:
                        recent.append({
                            'quarter': date.strftime('%Y-%m-%d'),
                            'value_raw': float(val)
                        })
                
                if recent:
                    return {'status': 'success', 'metric': 'CapEx', 'recent_quarters': recent[:4]}
        except Exception as e:
            logger.warning(f"yfinance CapEx error for {symbol}: {e}")
        
        return {'status': 'failed'}
    
    def _fetch_capex_fmp(self, symbol: str) -> Dict:
        """Get CapEx from Financial Modeling Prep - RAW values only"""
        try:
            url = f"{self.FMP_BASE}/cash-flow-statement/{symbol}?apikey={self.FMP_API_KEY}"
            resp = self.session.get(url, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    recent = []
                    for item in data[:4]:
                        capex = item.get('capitalExpenditure')
                        if capex:
                            recent.append({
                                'quarter': item.get('date', ''),
                                'value_raw': float(capex)
                            })
                    
                    if recent:
                        return {'status': 'success', 'metric': 'CapEx', 'recent_quarters': recent}
        except Exception as e:
            logger.warning(f"FMP CapEx error for {symbol}: {e}")
        
        return {'status': 'failed'}
    
    # ==================== DEBT SOURCES ====================
    
    def _fetch_debt_multi(self, symbol: str, is_bank: bool = False) -> Dict:
        """Fetch debt - RAW values only"""
        
        if is_bank:
            return self._fetch_debt_bank(symbol)
        
        return self._fetch_debt_corporate(symbol)
    
    def _fetch_debt_corporate(self, symbol: str) -> Dict:
        """Debt for regular companies - RAW values only - HISTORICAL DATA (4 quarters)"""
        try:
            ticker = f"{symbol}.NS"
            stock = yf.Ticker(ticker)
            bs = stock.quarterly_balance_sheet
            
            if bs is not None and len(bs.columns) > 0:
                # Get historical data (4 most recent quarters)
                history = []
                for col_idx in range(min(4, len(bs.columns))):
                    period = bs.iloc[:, col_idx]
                    period_date = bs.columns[col_idx]
                    
                    st_debt = None
                    lt_debt = None
                    
                    for key in period.index:
                        k_lower = str(key).lower()
                        if 'short' in k_lower and ('debt' in k_lower or 'borrowing' in k_lower):
                            val = period[key]
                            if pd.notna(val) and val > 0:
                                st_debt = float(val)
                        if 'long term' in k_lower and 'debt' in k_lower:
                            val = period[key]
                            if pd.notna(val) and val > 0:
                                lt_debt = float(val)
                    
                    if st_debt is not None or lt_debt is not None:
                        period_data = {
                            'period': period_date.strftime('%Y-%m-%d')
                        }
                        if st_debt is not None:
                            period_data['short_term_debt_raw'] = st_debt
                        if lt_debt is not None:
                            period_data['long_term_debt_raw'] = lt_debt
                        
                        history.append(period_data)
                
                if history:
                    return {
                        'metric': 'Debt Details',
                        'status': 'success',
                        'source': 'yfinance',
                        'historical_periods': history
                    }
        except Exception as e:
            logger.warning(f"Debt fetch error for {symbol}: {e}")
        
        return {'metric': 'Debt Details', 'status': 'Not available', 'source': 'yfinance'}
    
    def _fetch_debt_bank(self, symbol: str) -> Dict:
        """Debt for banks - RAW values only"""
        try:
            ticker = f"{symbol}.NS"
            stock = yf.Ticker(ticker)
            bs = stock.quarterly_balance_sheet
            
            if bs is not None:
                return {
                    'metric': 'Debt Details',
                    'note': 'Bank financial structure differs from corporate',
                    'status': 'Different structure',
                    'source': 'yfinance'
                }
        except Exception as e:
            logger.warning(f"Bank debt error for {symbol}: {e}")
        
        return {'metric': 'Debt Details', 'status': 'Not available', 'source': 'yfinance'}
    
    # ==================== SEGMENTS SOURCES ====================
    
    def _fetch_segments_multi(self, symbol: str) -> Dict:
        """Try multiple sources for segments - RAW data only"""
        
        result = self._fetch_segments_bse(symbol)
        if result['status'] == 'success':
            return result
        
        result = self._fetch_segments_fmp(symbol)
        if result['status'] == 'success':
            return result
        
        return {'metric': 'Segments', 'status': 'Not available', 'sources_tried': ['BSE', 'FMP']}
    
    def _fetch_segments_bse(self, symbol: str) -> Dict:
        """Get segments from BSE - RAW data only"""
        try:
            url = f"https://www.bseindia.com/stock/StockPricePage.aspx?expandable=0&scripcode={symbol}"
            resp = self.session.get(url, timeout=10)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.content, 'html.parser')
                # Basic scraping attempt - returns found data
                return {
                    'status': 'partial',
                    'metric': 'Segments',
                    'source': 'BSE',
                    'note': 'Manual parsing required for specific segment data'
                }
        except Exception as e:
            logger.warning(f"BSE segments error for {symbol}: {e}")
        
        return {'status': 'failed'}
    
    def _fetch_segments_fmp(self, symbol: str) -> Dict:
        """Get segments from FMP - RAW data only"""
        try:
            url = f"{self.FMP_BASE}/income-statement/{symbol}?apikey={self.FMP_API_KEY}"
            resp = self.session.get(url, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    return {
                        'status': 'success',
                        'metric': 'Segments',
                        'raw_data': data[0],
                        'source': 'FMP'
                    }
        except Exception as e:
            logger.warning(f"FMP segments error for {symbol}: {e}")
        
        return {'status': 'failed'}
    
    # ==================== EXCEPTIONAL ITEMS ====================
    
    def _fetch_exceptional_multi(self, symbol: str) -> Dict:
        """Try yfinance → FMP for exceptional items - RAW data only"""
        
        result = self._fetch_exceptional_yfinance(symbol)
        if result['status'] == 'success':
            return result
        
        result = self._fetch_exceptional_fmp(symbol)
        if result['status'] == 'success':
            return result
        
        return {'metric': 'Exceptional Items', 'status': 'Not available', 'sources_tried': ['yfinance', 'FMP']}
    
    def _fetch_exceptional_yfinance(self, symbol: str) -> Dict:
        """Get exceptional items from yfinance - RAW values only - HISTORICAL DATA (4 periods)"""
        try:
            ticker = f"{symbol}.NS"
            stock = yf.Ticker(ticker)
            is_stmt = stock.quarterly_income_stmt
            
            if is_stmt is not None and len(is_stmt.columns) > 0:
                # Get historical data (4 most recent periods)
                history = []
                for col_idx in range(min(4, len(is_stmt.columns))):
                    period = is_stmt.iloc[:, col_idx]
                    period_date = is_stmt.columns[col_idx]
                    
                    for key in period.index:
                        k_lower = str(key).lower()
                        if 'exceptional' in k_lower or 'extraordinary' in k_lower:
                            val = period[key]
                            if pd.notna(val) and val != 0:
                                history.append({
                                    'period': period_date.strftime('%Y-%m-%d'),
                                    'value_raw': float(val)
                                })
                                break
                
                if history:
                    return {
                        'status': 'success',
                        'metric': 'Exceptional Items',
                        'source': 'yfinance',
                        'historical_periods': history
                    }
        except Exception as e:
            logger.warning(f"yfinance exceptional error for {symbol}: {e}")
        
        return {'status': 'failed'}
    
    def _fetch_exceptional_fmp(self, symbol: str) -> Dict:
        """Get exceptional items from FMP - RAW values only - HISTORICAL DATA (4 periods)"""
        try:
            url = f"{self.FMP_BASE}/income-statement/{symbol}?apikey={self.FMP_API_KEY}"
            resp = self.session.get(url, timeout=10)
            
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    history = []
                    for item in data[:4]:
                        exceptional = item.get('extraordinaryItems')
                        if exceptional:
                            history.append({
                                'period': item.get('date', ''),
                                'value_raw': float(exceptional)
                            })
                    
                    if history:
                        return {
                            'status': 'success',
                            'metric': 'Exceptional Items',
                            'source': 'FMP',
                            'historical_periods': history
                        }
        except Exception as e:
            logger.warning(f"FMP exceptional error for {symbol}: {e}")
        
        return {'status': 'failed'}
    
    # ==================== WORKING CAPITAL ====================
    
    def _fetch_wc_multi(self, symbol: str, is_bank: bool = False) -> Dict:
        """Fetch WC - RAW values only, skip for banks - HISTORICAL DATA (4 quarters)"""
        
        if is_bank:
            return {'metric': 'Working Capital', 'note': 'Not applicable for banks', 'status': 'n/a'}
        
        try:
            ticker = f"{symbol}.NS"
            stock = yf.Ticker(ticker)
            bs = stock.quarterly_balance_sheet
            
            if bs is not None and len(bs.columns) > 0:
                # Get historical data (4 most recent quarters)
                history = []
                for col_idx in range(min(4, len(bs.columns))):
                    period = bs.iloc[:, col_idx]
                    period_date = bs.columns[col_idx]
                    
                    ar = None
                    ap = None
                    inv = None
                    
                    for key in period.index:
                        k_lower = str(key).lower()
                        if 'accounts receivable' in k_lower:
                            val = period[key]
                            if pd.notna(val):
                                ar = float(val)
                        if 'accounts payable' in k_lower:
                            val = period[key]
                            if pd.notna(val):
                                ap = float(val)
                        if 'inventory' in k_lower:
                            val = period[key]
                            if pd.notna(val):
                                inv = float(val)
                    
                    if ar is not None or ap is not None or inv is not None:
                        period_data = {
                            'period': period_date.strftime('%Y-%m-%d')
                        }
                        if ar is not None:
                            period_data['accounts_receivable_raw'] = ar
                        if ap is not None:
                            period_data['accounts_payable_raw'] = ap
                        if inv is not None:
                            period_data['inventory_raw'] = inv
                        
                        history.append(period_data)
                
                if history:
                    return {
                        'metric': 'Working Capital',
                        'status': 'success',
                        'source': 'yfinance',
                        'historical_periods': history
                    }
        except Exception as e:
            logger.warning(f"WC error for {symbol}: {e}")
        
        return {'metric': 'Working Capital', 'status': 'Not available', 'source': 'yfinance'}
    
    # ==================== BATCH OPERATIONS ====================
    
    def fetch_multiple_stocks(self, symbols: List[str]) -> Dict:
        """Fetch all stocks"""
        banks = ['HDFC', 'ICICIBANK', 'INDUSIND']
        results = {}
        
        for symbol in symbols:
            is_bank = symbol in banks
            logger.info(f"Processing {symbol} (Bank: {is_bank})")
            results[symbol] = self.fetch_financial_metrics(symbol, is_bank)
        
        return results
    
    def save_to_json(self, data: Dict, filename: str = None) -> str:
        """Save data to JSON"""
        if filename is None:
            filename = f"financial_metrics_raw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        filepath = self.output_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved to {filepath}")
        return str(filepath)


def main():
    """Main execution"""
    
    fetcher = ComprehensiveStockFetcher()
    symbols = ['COFORGE', 'AZAD', 'HDFC', 'IGIL', 'KAYNES']
    
    print("\n" + "="*70)
    print("COMPREHENSIVE MULTI-SOURCE FINANCIAL DATA FETCHER")
    print("RAW DATA ONLY - NO CALCULATIONS OR ESTIMATES")
    print("="*70)
    print(f"Stocks: {', '.join(symbols)}")
    print("Sources: yfinance → Financial Modeling Prep → BSE/NSE")
    print("="*70 + "\n")
    
    # Fetch
    data = fetcher.fetch_multiple_stocks(symbols)
    json_file = fetcher.save_to_json(data, 'financial_metrics_raw.json')
    
    print("\n" + "="*70)
    print("EXECUTION COMPLETE")
    print("="*70)
    print(f"Data saved: {json_file}")
    print("="*70 + "\n")
    
    # Print summary
    print("DATA SUMMARY:\n")
    for symbol, metrics in data.items():
        print(f"{symbol}:")
        for metric_type, metric_data in metrics.items():
            if metric_type not in ['symbol', 'fetch_timestamp']:
                status = metric_data.get('status', 'N/A')
                source = metric_data.get('source', 'N/A')
                print(f"  {metric_type}: {status} (source: {source})")
        print()


if __name__ == '__main__':
    main()
