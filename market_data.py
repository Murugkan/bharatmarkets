"""
bucket_market_data.py
─────────────────────
Reads  market_data_raw.json
Writes market_data_bucketed.json + derived_metrics

GitHub Repo Structure:
  PROJECT_ROOT/
    data/
      market_data_raw.json (INPUT)
      market_data_complete.json (OUTPUT: buckets + derived_metrics)
      logs/
        market_data.log

Design principles
─────────────────
1. MAP-DRIVEN  — FIELD_MAP declares every explicit mapping.
                 To handle a new source field, add one entry here.
2. ZERO LOSS   — anything not in FIELD_MAP lands in `_unmapped`
                 so no input data is ever silently dropped.
3. FUTURE-SAFE — new source sections / metrics on 90+ other symbols
                 are automatically captured in `_unmapped`.

Buckets (8 consolidated)
────────────────────────
 1. company_details           (company info + exchange + portfolio context + shareholding_pattern)
 2. financials                (income_statement_quarterly_consolidated/standalone + 
                               income_statement_annual + income_statement_half_yearly_standalone +
                               balance_sheet_annual + cash_flow_annual)
 3. ratios                    (efficiency_ratios + profitability_growth)
 4. valuation                 (valuations + eps metrics + dividend metrics)
 5. price                     (price_trading: live quote + OHLCV history)
 6. websignals                (risk_and_governance + analyst_consensus + management_guidance)
 7. kpis                      (operational_kpis: company-specific metrics from screener_raw:Insights)
 8. derived_metrics           (investment signals, scores, risk flags)
 +. _unmapped                 (catch-all for unmapped fields)
"""

import json
import sys
import logging
from pathlib import Path
from copy import deepcopy
from datetime import datetime

# GitHub repo paths
PROJECT_ROOT = Path(__file__).parent.parent if Path(__file__).parent.name == 'src' else Path(__file__).parent
DATA_DIR = PROJECT_ROOT / 'data'
LOGS_DIR = DATA_DIR / 'logs'

LOGS_DIR.mkdir(parents=True, exist_ok=True)

INPUT_FILE = DATA_DIR / "market_data_raw.json"
OUTPUT_FILE = DATA_DIR / "market_data.json"
LOG_FILE = LOGS_DIR / "market_data.log"

# Purge old log file
LOG_FILE.write_text("")

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# STANDARDIZATION FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def standardize_metric(value):
    """
    Convert metric values to float where appropriate.
    Handles: strings with %, commas, None, already-numeric.
    
    Examples:
        "45.32"       → 45.32
        "45.32%"      → 45.32
        "1,234,567"   → 1234567.0
        "N/A" or ""   → None
        45.32         → 45.32
        None          → None
    """
    if value is None:
        return None
    
    # Already numeric
    if isinstance(value, (int, float)):
        return float(value)
    
    # String conversion
    if isinstance(value, str):
        value = value.strip()
        if not value or value.upper() in ['N/A', 'NA', 'N.A', 'NAN', 'NONE']:
            return None
        
        # Remove percentage sign and convert
        if '%' in value:
            try:
                return float(value.replace('%', '').strip())
            except (ValueError, AttributeError):
                return None
        
        # Remove commas and convert
        if ',' in value:
            try:
                return float(value.replace(',', '').strip())
            except (ValueError, AttributeError):
                return None
        
        # Try direct conversion
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    return None


def apply_standardization_to_dict(obj, depth=0, max_depth=5):
    """
    Recursively standardize numeric values in a dict/list structure.
    Converts text metrics to float where applicable.
    Avoids standardizing identifiers, keys, dates, and strings needed as-is.
    """
    if depth > max_depth:
        return obj
    
    # Skip certain key patterns that should NOT be standardized
    skip_keys = {
        'ticker', 'name', 'symbol', 'isin', 'sector', 'industry', 'type',
        'address', 'city', 'country', 'phone', 'email', 'website',
        'currency', 'exchange', 'date', 'time', 'metric', 'period',
        'consolidation', 'granule', '_source', '_periods', '_granule', '_consolidation'
    }
    
    if isinstance(obj, dict):
        result = {}
        for key, val in obj.items():
            # Check if this key should skip standardization
            key_lower = key.lower()
            should_skip = any(skip in key_lower for skip in skip_keys)
            
            if should_skip or key.startswith('_'):
                result[key] = val
            elif isinstance(val, (dict, list)):
                result[key] = apply_standardization_to_dict(val, depth + 1, max_depth)
            elif isinstance(val, (int, float)):
                result[key] = val
            else:
                # Try to standardize
                std_val = standardize_metric(val)
                result[key] = std_val if std_val is not None else val
        return result
    
    elif isinstance(obj, list):
        return [apply_standardization_to_dict(item, depth + 1, max_depth) if isinstance(item, (dict, list)) else item for item in obj]
    
    return obj





# ══════════════════════════════════════════════════════════════════════════════
# FIELD MAP
# ══════════════════════════════════════════════════════════════════════════════
# Structure:
#   FIELD_MAP[source_section][source_field] = ("target_bucket", "target_key")
#
# source_section  — top-level key in raw data["symbol"]["data"]
# source_field    — for list sections: metric name
#                   for dict sections: dict key
#
# Special target_key values:
#   "__skip__"    — intentionally excluded (e.g. empty Raw PDF fields)
#   "__ts__"      — time-series; value is the full periods dict
#   "__history__" — OHLCV history; value is the full values list
#   "__ltp__"     — Last Traded Price scalar
#   "__all_ts__"  — map every metric in the section as a time-series
#                   (used for operational_kpis whose metrics vary per symbol)
# ══════════════════════════════════════════════════════════════════════════════

FIELD_MAP = {

    # ── unified_symbols:metadata ──────────────────────────────────────────────
    "unified_symbols:metadata": {
        "ticker":   ("company_details",  "ticker"),
        "name":     ("company_details",  "name"),
        "qty":      ("company_details",  "qty"),
        "avg":      ("company_details",  "avg_cost"),
        "isin":     ("company_details",   "isin"),
        "sector":   ("company_details",   "sector"),
        "industry": ("company_details",   "industry"),
        "type":     ("company_details",   "type"),
        "source":   ("company_details",   "data_source"),
    },

    # ── yahoofin_raw:info ─────────────────────────────────────────────────────
    "yahoofin_raw:info": {
        # identity
        "shortName":             ("company_details", "short_name"),
        "longName":              ("company_details", "long_name"),
        "symbol":                ("company_details", "symbol_yahoo"),
        "address1":              ("company_details", "address1"),
        "address2":              ("company_details", "address2"),
        "city":                  ("company_details", "city"),
        "zip":                   ("company_details", "zip"),
        "country":               ("company_details", "country"),
        "phone":                 ("company_details", "phone"),
        "fax":                   ("company_details", "fax"),
        "website":               ("company_details", "website"),
        "irWebsite":             ("company_details", "ir_website"),
        "industry":              ("company_details", "industry_yahoo"),
        "industryDisp":          ("company_details", "industry_disp"),
        "sector":                ("company_details", "sector_yahoo"),
        "sectorDisp":            ("company_details", "sector_disp"),
        "longBusinessSummary":   ("company_details", "long_business_summary"),
        "fullTimeEmployees":     ("company_details", "full_time_employees"),
        "companyOfficers":       ("company_details", "company_officers"),
        "currency":              ("company_details", "currency"),
        "financialCurrency":     ("company_details", "financial_currency"),
        "quoteType":             ("company_details", "quote_type"),
        "typeDisp":              ("company_details", "type_disp"),
        "language":              ("company_details", "language"),
        "region":                ("company_details", "region"),
        "exchange":              ("company_details", "exchange"),
        "fullExchangeName":      ("company_details", "full_exchange_name"),
        "esgPopulated":          ("company_details", "esg_populated"),
        "nameChangeDate":        ("company_details", "name_change_date"),
        "prevName":              ("company_details", "prev_name"),
        # valuation
        "marketCap":                   ("valuation", "market_cap"),
        "nonDilutedMarketCap":         ("valuation", "non_diluted_market_cap"),
        "enterpriseValue":             ("valuation", "enterprise_value"),
        "trailingPE":                  ("valuation", "trailing_pe"),
        "forwardPE":                   ("valuation", "forward_pe"),
        "pegRatio":                    ("valuation", "peg_ratio"),
        "priceToBook":                 ("valuation", "price_to_book"),
        "priceToSalesTrailing12Months":("valuation", "price_to_sales_ttm"),
        "enterpriseToRevenue":         ("valuation", "ev_to_revenue"),
        "enterpriseToEbitda":          ("valuation", "ev_to_ebitda"),
        "ebitda":                      ("valuation", "ebitda"),
        "totalDebt":                   ("valuation", "total_debt"),
        "bookValue":                   ("valuation", "book_value"),
        "trailingEps":                 ("valuation", "trailing_eps"),
        "forwardEps":                  ("valuation", "forward_eps"),
        "epsTrailingTwelveMonths":     ("valuation", "eps_ttm"),
        "epsForward":                  ("valuation", "eps_forward"),
        "epsCurrentYear":              ("valuation", "eps_current_year"),
        "priceEpsCurrentYear":         ("valuation", "price_eps_current_year"),
        "trailingPegRatio":            ("valuation", "trailing_peg_ratio"),
        # price & trading
        "currentPrice":                  ("price", "current_price"),
        "previousClose":                 ("price", "previous_close"),
        "regularMarketPreviousClose":    ("price", "regular_market_previous_close"),
        "open":                          ("price", "open"),
        "regularMarketOpen":             ("price", "regular_market_open"),
        "dayLow":                        ("price", "day_low"),
        "dayHigh":                       ("price", "day_high"),
        "regularMarketDayLow":           ("price", "regular_market_day_low"),
        "regularMarketDayHigh":          ("price", "regular_market_day_high"),
        "regularMarketDayRange":         ("price", "regular_market_day_range"),
        "regularMarketPrice":            ("price", "regular_market_price"),
        "regularMarketChange":           ("price", "regular_market_change"),
        "regularMarketChangePercent":    ("price", "regular_market_change_pct"),
        "volume":                        ("price", "volume"),
        "regularMarketVolume":           ("price", "regular_market_volume"),
        "averageVolume":                 ("price", "average_volume"),
        "averageVolume10days":           ("price", "average_volume_10d"),
        "averageDailyVolume10Day":       ("price", "average_daily_volume_10d"),
        "averageDailyVolume3Month":      ("price", "average_daily_volume_3mo"),
        "bid":                           ("price", "bid"),
        "bidSize":                       ("price", "bid_size"),
        "ask":                           ("price", "ask"),
        "askSize":                       ("price", "ask_size"),
        "fiftyDayAverage":               ("price", "fifty_day_avg"),
        "fiftyDayAverageChange":         ("price", "fifty_day_avg_change"),
        "fiftyDayAverageChangePercent":  ("price", "fifty_day_avg_change_pct"),
        "twoHundredDayAverage":          ("price", "two_hundred_day_avg"),
        "twoHundredDayAverageChange":    ("price", "two_hundred_day_avg_change"),
        "twoHundredDayAverageChangePercent": ("price", "two_hundred_day_avg_change_pct"),
        "fiftyTwoWeekLow":               ("price", "fifty_two_week_low"),
        "fiftyTwoWeekHigh":              ("price", "fifty_two_week_high"),
        "fiftyTwoWeekLowChange":         ("price", "fifty_two_week_low_change"),
        "fiftyTwoWeekHighChange":        ("price", "fifty_two_week_high_change"),
        "fiftyTwoWeekLowChangePercent":  ("price", "fifty_two_week_low_change_pct"),
        "fiftyTwoWeekHighChangePercent": ("price", "fifty_two_week_high_change_pct"),
        "fiftyTwoWeekRange":             ("price", "fifty_two_week_range"),
        "fiftyTwoWeekChangePercent":     ("price", "fifty_two_week_change_pct"),
        "52WeekChange":                  ("price", "fifty_two_week_change"),
        "allTimeHigh":                   ("price", "all_time_high"),
        "allTimeLow":                    ("price", "all_time_low"),
        "beta":                          ("price", "beta"),
        # dividends & splits → company_details
        "dividendRate":                  ("company_details", "dividend_rate"),
        "dividendYield":                 ("company_details", "dividend_yield"),
        "exDividendDate":                ("company_details", "ex_dividend_date"),
        "payoutRatio":                   ("company_details", "payout_ratio"),
        "trailingAnnualDividendRate":    ("company_details", "trailing_annual_dividend_rate"),
        "trailingAnnualDividendYield":   ("company_details", "trailing_annual_dividend_yield"),
        "lastDividendValue":             ("company_details", "last_dividend_value"),
        "lastDividendDate":              ("company_details", "last_dividend_date"),
        "fiveYearAvgDividendYield":      ("company_details", "five_year_avg_dividend_yield"),
        "lastSplitDate":                 ("company_details", "last_split_date"),
        "lastSplitFactor":               ("company_details", "last_split_factor"),
        "heldPercentInsiders":           ("company_details", "held_pct_insiders"),
        "heldPercentInstitutions":       ("company_details", "held_pct_institutions"),
        "floatShares":                   ("company_details", "float_shares"),
        "sharesOutstanding":             ("company_details", "shares_outstanding"),
        "impliedSharesOutstanding":      ("company_details", "implied_shares_outstanding"),
        # profitability & growth
        "profitMargins":             ("ratios", "profit_margins"),
        "grossMargins":              ("ratios", "gross_margins"),
        "ebitdaMargins":             ("ratios", "ebitda_margins"),
        "operatingMargins":          ("ratios", "operating_margins"),
        "earningsGrowth":            ("ratios", "earnings_growth"),
        "revenueGrowth":             ("ratios", "revenue_growth"),
        "earningsQuarterlyGrowth":   ("ratios", "earnings_quarterly_growth"),
        "revenuePerShare":           ("ratios", "revenue_per_share"),
        "totalCash":                 ("ratios", "total_cash"),
        "totalCashPerShare":         ("ratios", "total_cash_per_share"),
        "debtToEquity":              ("ratios", "debt_to_equity"),
        "currentRatio":              ("ratios", "current_ratio"),
        "quickRatio":                ("ratios", "quick_ratio"),
        "netIncomeToCommon":         ("ratios", "net_income_to_common"),
        "grossProfits":              ("ratios", "gross_profits"),
        "totalRevenue":              ("ratios", "total_revenue"),
        "returnOnAssets":            ("ratios", "return_on_assets"),
        "returnOnEquity":            ("ratios", "return_on_equity"),
        "freeCashflow":              ("ratios", "free_cashflow"),
        "operatingCashflow":         ("ratios", "operating_cashflow"),
        # risk & governance
        "auditRisk":             ("websignals", "audit_risk"),
        "boardRisk":             ("websignals", "board_risk"),
        "compensationRisk":      ("websignals", "compensation_risk"),
        "shareHolderRightsRisk": ("websignals", "shareholder_rights_risk"),
        "overallRisk":           ("websignals", "overall_risk"),
        "governanceEpochDate":   ("websignals", "governance_epoch_date"),
        # analyst consensus
        "targetHighPrice":           ("websignals", "target_high_price"),
        "targetLowPrice":            ("websignals", "target_low_price"),
        "targetMeanPrice":           ("websignals", "target_mean_price"),
        "targetMedianPrice":         ("websignals", "target_median_price"),
        "recommendationMean":        ("websignals", "recommendation_mean"),
        "recommendationKey":         ("websignals", "recommendation_key"),
        "numberOfAnalystOpinions":   ("websignals", "number_of_analyst_opinions"),
        "averageAnalystRating":      ("websignals", "average_analyst_rating"),
        "SandP52WeekChange":         ("websignals", "sandp_52_week_change"),
        # earnings calendar
        "earningsTimestamp":          ("websignals", "earnings_timestamp"),
        "earningsTimestampStart":     ("websignals", "earnings_timestamp_start"),
        "earningsTimestampEnd":       ("websignals", "earnings_timestamp_end"),
        "earningsCallTimestampStart": ("websignals", "earnings_call_ts_start"),
        "earningsCallTimestampEnd":   ("websignals", "earnings_call_ts_end"),
        "isEarningsDateEstimate":     ("websignals", "is_earnings_date_estimate"),
        # exchange metadata
        "exchange":                       ("company_details", "exchange"),
        "exchangeTimezoneName":           ("company_details", "exchange_timezone_name"),
        "exchangeTimezoneShortName":      ("company_details", "exchange_timezone_short"),
        "gmtOffSetMilliseconds":          ("company_details", "gmt_offset_ms"),
        "market":                         ("company_details", "market"),
        "quoteSourceName":                ("company_details", "quote_source_name"),
        "marketState":                    ("company_details", "market_state"),
        "sourceInterval":                 ("company_details", "source_interval"),
        "exchangeDataDelayedBy":          ("company_details", "exchange_data_delay"),
        "firstTradeDateMilliseconds":     ("company_details", "first_trade_date_ms"),
        "regularMarketTime":              ("company_details", "regular_market_time"),
        "lastFiscalYearEnd":              ("company_details", "last_fiscal_year_end"),
        "nextFiscalYearEnd":              ("company_details", "next_fiscal_year_end"),
        "mostRecentQuarter":              ("company_details", "most_recent_quarter"),
        "priceHint":                      ("company_details", "price_hint"),
        "tradeable":                      ("company_details", "tradeable"),
        "triggerable":                    ("company_details", "triggerable"),
        "customPriceAlertConfidence":     ("company_details", "custom_price_alert_confidence"),
        "hasPrePostMarketData":           ("company_details", "has_pre_post_market_data"),
        "corporateActions":               ("company_details", "corporate_actions"),
        "messageBoardId":                 ("company_details", "message_board_id"),
        "cryptoTradeable":                ("company_details", "crypto_tradeable"),
        "compensationAsOfEpochDate":      ("company_details", "compensation_as_of_epoch"),
    },

    # ── yahoofin_fin:latest ───────────────────────────────────────────────────
    "yahoofin_fin:latest": {
        # income statement
        "revenue":            ("financials",  "revenue"),
        "ebitda":             ("financials",  "ebitda"),
        "ebit":               ("financials",  "ebit"),
        "gross_profit":       ("financials",  "gross_profit"),
        "operating_income":   ("financials",  "operating_income"),
        "net_profit":         ("financials",  "net_profit"),
        "normalized_income":  ("financials",  "normalized_income"),
        "unusual_items":      ("financials",  "unusual_items"),
        "tax_rate":           ("financials",  "tax_rate"),
        "cost_of_revenue":    ("financials",  "cost_of_revenue"),
        "operating_expenses": ("financials",  "operating_expenses"),
        "rd_expense":         ("financials",  "rd_expense"),
        "interest_income":    ("financials",  "interest_income"),
        # balance sheet
        "total_liabilities":         ("financials", "total_liabilities"),
        "total_debt":                ("financials", "total_debt"),
        "short_term_debt":           ("financials", "short_term_debt"),
        "long_term_debt":            ("financials", "long_term_debt"),
        "net_debt":                  ("financials", "net_debt"),
        "capital_lease_obligations": ("financials", "capital_lease_obligations"),
        "net_tangible_assets":       ("financials", "net_tangible_assets"),
        "tangible_book_value":       ("financials", "tangible_book_value"),
        "total_assets":              ("financials", "total_assets"),
        "total_equity":              ("financials", "total_equity"),
        "retained_earnings":         ("financials", "retained_earnings"),
        "invested_capital":          ("financials", "invested_capital"),
        "working_capital":           ("financials", "working_capital"),
        "accounts_receivable":       ("financials", "accounts_receivable"),
        "cash_and_equivalents":      ("financials", "cash_and_equivalents"),
        "deposits":                  ("financials", "deposits"),
        "advances":                  ("financials", "advances"),
        "npa":                       ("financials", "npa"),
        "minority_interest":         ("financials", "minority_interest"),
        "total_capitalization":      ("financials", "total_capitalization"),
        "fixed_assets":              ("financials", "fixed_assets"),
        # cash flow
        "operating_cash_flow": ("financials", "operating_cash_flow"),
        "free_cash_flow":      ("financials", "free_cash_flow"),
        "capex":               ("financials", "capex"),
        "depreciation":        ("financials", "depreciation"),
        "interest_expense":    ("financials", "interest_expense"),
        # valuation
        "diluted_eps":      ("valuation", "diluted_eps"),
        "basic_eps":        ("valuation", "basic_eps"),
        "diluted_shares":   ("valuation", "diluted_shares"),
        "basic_shares":     ("valuation", "basic_shares"),
        "shares_outstanding":("valuation","shares_outstanding_yf"),
    },

    # ── screener_fin:profit_loss  (quarterly consolidated) ───────────────────
    "screener_fin:profit_loss": {
        "Revenue +":         ("financials", "Sales"),
        "Revenue +":        ("financials", "Sales"),  # Non-breaking space variant
        "Sales +":           ("financials", "Sales"),
        "Sales\xa0+":          ("financials", "Sales"),  # Non-breaking space variant
        "Expenses +":        ("financials", "Expenses"),
        "Expenses\xa0+":       ("financials", "Expenses"),  # Non-breaking space variant
        "Operating Profit":  ("financials", "Operating_Profit"),
        "OPM %":             ("financials", "OPM_pct"),
        "Other Income +":    ("financials", "Other_Income"),
        "Other Income\xa0+":   ("financials", "Other_Income"),  # Non-breaking space variant
        "Interest":          ("financials", "Interest"),
        "Depreciation":      ("financials", "Depreciation"),
        "Profit before tax": ("financials", "Profit_before_tax"),
        "Tax %":             ("financials", "Tax_pct"),
        "Net Profit +":      ("financials", "Net_Profit"),
        "Net Profit\xa0+":     ("financials", "Net_Profit"),  # Non-breaking space variant
        "EPS in Rs":         ("financials", "EPS_Rs"),
        "Financing Profit":  ("financials", "Financing_Profit"),
        "Financing Margin %":("financials", "Financing_Margin_pct"),
        "Gross NPA %":       ("financials", "Gross_NPA_pct"),
        "Net NPA %":         ("financials", "Net_NPA_pct"),
        "Raw PDF":           ("websignals", "raw_pdf_profit_loss"),
    },

    # ── screener_fin:balance_sheet  (annual consolidated P&L, 7yr) ───────────
    "screener_fin:balance_sheet": {
        "Revenue +":          ("financials", "Sales"),
        "Revenue +":         ("financials", "Sales"),  # Non-breaking space variant
        "Sales +":            ("financials", "Sales"),
        "Sales\xa0+":           ("financials", "Sales"),  # Non-breaking space variant
        "Expenses +":         ("financials", "Expenses"),
        "Expenses\xa0+":        ("financials", "Expenses"),  # Non-breaking space variant
        "Operating Profit":   ("financials", "Operating_Profit"),
        "OPM %":              ("financials", "OPM_pct"),
        "Other Income +":     ("financials", "Other_Income"),
        "Other Income\xa0+":    ("financials", "Other_Income"),  # Non-breaking space variant
        "Interest":           ("financials", "Interest"),
        "Depreciation":       ("financials", "Depreciation"),
        "Profit before tax":  ("financials", "Profit_before_tax"),
        "Tax %":              ("financials", "Tax_pct"),
        "Net Profit +":       ("financials", "Net_Profit"),
        "Net Profit\xa0+":      ("financials", "Net_Profit"),  # Non-breaking space variant
        "EPS in Rs":          ("financials", "EPS_Rs"),
        "Dividend Payout %":  ("financials", "Dividend_Payout_pct"),
        "Financing Profit":   ("financials", "Financing_Profit"),
        "Financing Margin %": ("financials", "Financing_Margin_pct"),
    },

    # ── screener_fin:cash_flow  (annual consolidated balance sheet, 7yr) ─────
    "screener_fin:cash_flow": {
        "Equity Capital":     ("financials", "Equity_Capital"),
        "Reserves":           ("financials", "Reserves"),
        "Borrowing":          ("financials", "Borrowing"),
        "Borrowings +":       ("financials", "Borrowings"),
        "Borrowings\xa0+":      ("financials", "Borrowings"),  # Non-breaking space variant
        "Other Liabilities +":("financials", "Other_Liabilities"),
        "Other Liabilities\xa0+":("financials", "Other_Liabilities"),  # Non-breaking space variant
        "Total Liabilities":  ("financials", "Total_Liabilities"),
        "Fixed Assets +":     ("financials", "Fixed_Assets"),
        "Fixed Assets\xa0+":    ("financials", "Fixed_Assets"),  # Non-breaking space variant
        "CWIP":               ("financials", "CWIP"),
        "Investments":        ("financials", "Investments"),
        "Other Assets +":     ("financials", "Other_Assets"),
        "Other Assets\xa0+":    ("financials", "Other_Assets"),  # Non-breaking space variant
        "Total Assets":       ("financials", "Total_Assets"),
        "Deposits":           ("financials", "Deposits"),  # Bank-specific field
    },

    # ── screener_fin:ratios  (annual consolidated cash flow, 7yr) ────────────
    "screener_fin:ratios": {
        "Cash from Operating Activity +": ("financials", "CFO"),
        "Cash from Operating Activity\xa0+": ("financials", "CFO"),  # Non-breaking space variant
        "Cash from Investing Activity +": ("financials", "CFI"),
        "Cash from Investing Activity\xa0+": ("financials", "CFI"),  # Non-breaking space variant
        "Cash from Financing Activity +": ("financials", "CFF"),
        "Cash from Financing Activity\xa0+": ("financials", "CFF"),  # Non-breaking space variant
        "Net Cash Flow":                  ("financials", "Net_Cash_Flow"),
        "Free Cash Flow":                 ("financials", "Free_Cash_Flow"),
        "CFO/OP":                         ("financials", "CFO_over_OP"),
    },

    # ── screener_raw:Quarterly Results  (quarterly standalone) ───────────────
    "screener_raw:Quarterly Results": {
        "Sales +":           ("financials", "Sales"),
        "Revenue +":         ("financials", "Sales"),
        "Revenue +":        ("financials", "Sales"),  # Non-breaking space variant
        "Expenses +":        ("financials", "Expenses"),
        "Operating Profit":  ("financials", "Operating_Profit"),
        "OPM %":             ("financials", "OPM_pct"),
        "Other Income +":    ("financials", "Other_Income"),
        "Interest":          ("financials", "Interest"),
        "Depreciation":      ("financials", "Depreciation"),
        "Profit before tax": ("financials", "Profit_before_tax"),
        "Tax %":             ("financials", "Tax_pct"),
        "Net Profit +":      ("financials", "Net_Profit"),
        "EPS in Rs":         ("financials", "EPS_Rs"),
        "Financing Profit":  ("financials", "Financing_Profit"),
        "Financing Margin %":("financials", "Financing_Margin_pct"),
        "Gross NPA %":       ("financials", "Gross_NPA_pct"),
        "Net NPA %":         ("financials", "Net_NPA_pct"),
        "Raw PDF":           ("__skip__", "__skip__"),
    },

    # ── screener_raw:Profit & Loss  (annual standalone P&L, 12yr) ────────────
    "screener_raw:Profit & Loss": {
        "Sales +":           ("financials", "Sales"),
        "Revenue +":         ("financials", "Sales"),
        "Revenue +":        ("financials", "Sales"),  # Non-breaking space variant
        "Expenses +":        ("financials", "Expenses"),
        "Operating Profit":  ("financials", "Operating_Profit"),
        "OPM %":             ("financials", "OPM_pct"),
        "Other Income +":    ("financials", "Other_Income"),
        "Interest":          ("financials", "Interest"),
        "Depreciation":      ("financials", "Depreciation"),
        "Profit before tax": ("financials", "Profit_before_tax"),
        "Tax %":             ("financials", "Tax_pct"),
        "Net Profit +":      ("financials", "Net_Profit"),
        "EPS in Rs":         ("financials", "EPS_Rs"),
        "Dividend Payout %": ("financials", "Dividend_Payout_pct"),
        "Financing Profit":  ("financials", "Financing_Profit"),
        "Financing Margin %":("financials", "Financing_Margin_pct"),
    },

    # ── screener_raw:Balance Sheet  (annual standalone, 12yr) ────────────────
    "screener_raw:Balance Sheet": {
        "Equity Capital":      ("financials", "Equity_Capital"),
        "Reserves":            ("financials", "Reserves"),
        "Borrowing":           ("financials", "Borrowing"),
        "Borrowings +":        ("financials", "Borrowings"),
        "Deposits":            ("financials", "Deposits"),
        "Other Liabilities +": ("financials", "Other_Liabilities"),
        "Total Liabilities":   ("financials", "Total_Liabilities"),
        "Fixed Assets +":      ("financials", "Fixed_Assets"),
        "CWIP":                ("financials", "CWIP"),
        "Investments":         ("financials", "Investments"),
        "Other Assets +":      ("financials", "Other_Assets"),
        "Total Assets":        ("financials", "Total_Assets"),
    },

    # ── screener_raw:Cash Flows  (annual standalone, 12yr) ───────────────────
    "screener_raw:Cash Flows": {
        "Cash from Operating Activity +": ("financials", "CFO"),
        "Cash from Investing Activity +": ("financials", "CFI"),
        "Cash from Financing Activity +": ("financials", "CFF"),
        "Net Cash Flow":                  ("financials", "Net_Cash_Flow"),
        "Free Cash Flow":                 ("financials", "Free_Cash_Flow"),
        "CFO/OP":                         ("financials", "CFO_over_OP"),
    },

    # ── screener_raw:Ratios  (annual efficiency ratios) ───────────────────────
    "screener_raw:Ratios": {
        "Debtor Days":           ("ratios", "Debtor_Days"),
        "Inventory Days":        ("ratios", "Inventory_Days"),
        "Days Payable":          ("ratios", "Days_Payable"),
        "Cash Conversion Cycle": ("ratios", "Cash_Conversion_Cycle"),
        "Working Capital Days":  ("ratios", "Working_Capital_Days"),
        "ROCE %":                ("ratios", "ROCE_pct"),
        "ROE %":                 ("ratios", "ROE_pct"),
    },

    # ── screener_raw:Shareholding Pattern ────────────────────────────────────
    "screener_raw:Shareholding Pattern": {
        "Promoters +":        ("company_details", "promoters"),
        "FIIs +":             ("company_details", "fiis"),
        "DIIs +":             ("company_details", "diis"),
        "Public +":           ("company_details", "public"),
        "Government +":       ("company_details", "government"),
        "Others +":           ("company_details", "others"),
        "No. of Shareholders":("company_details", "no_of_shareholders"),
    },

    # ── screener_raw:Insights  (all metrics → operational_kpis, varies per symbol)
    # handled via __all_ts__ sentinel — no need to enumerate every KPI
    "screener_raw:Insights": "__all_ts__",

    # ── screener_raw:Half Yearly Results  (half-yearly standalone) ────────────
    "screener_raw:Half Yearly Results": {
        "Sales +":           ("financials", "Sales"),
        "Revenue +":         ("financials", "Sales"),
        "Revenue +":        ("financials", "Sales"),  # Non-breaking space variant
        "Expenses +":        ("financials", "Expenses"),
        "Operating Profit":  ("financials", "Operating_Profit"),
        "OPM %":             ("financials", "OPM_pct"),
        "Other Income +":    ("financials", "Other_Income"),
        "Interest":          ("financials", "Interest"),
        "Depreciation":      ("financials", "Depreciation"),
        "Profit before tax": ("financials", "Profit_before_tax"),
        "Tax %":             ("financials", "Tax_pct"),
        "Net Profit +":      ("financials", "Net_Profit"),
        "EPS in Rs":         ("financials", "EPS_Rs"),
        "Raw PDF":           ("__skip__", "__skip__"),
    },

    # ── guidance:* ──────────────────────────────────────────────────────────────
    # NOTE: guidance.json is loaded separately in main() and added directly to
    # derived_metrics.ai_insights_guidance. Do NOT map guidance fields through FIELD_MAP.
    # Keeping entries commented for reference only:
    # "guidance:guidance": { ... guidance fields ... },
    # "guidance:insights": { ... insight fields ... },

    # ── yahoofin_raw:history_*  (OHLCV) ──────────────────────────────────────
    # handled separately via __history__ logic below
    "yahoofin_raw:history_6mo_1d": "__history__",
    "yahoofin_raw:history_5y_1wk": "__history__",
    "yahoofin_raw:history_5y_1mo": "__history__",
}


# ══════════════════════════════════════════════════════════════════════════════
# BUCKETING ENGINE
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# BUCKETING ENGINE
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# SECTOR PROFILES — FROZEN
# ══════════════════════════════════════════════════════════════════════════════
# Sector-specific thresholds, weights, and benchmarks for derived metrics.
# Do not modify without version bump.
# ══════════════════════════════════════════════════════════════════════════════

SECTOR_PROFILES = {
    "Banking": {
        "fundamental": 0.5, "technical": 0.2, "valuation": 0.2, "sentiment": 0.1,
        "de_limit": 5.0, "roe_excellent": 0.15
    },
    "Financial Services": {
        "fundamental": 0.5, "technical": 0.2, "valuation": 0.2, "sentiment": 0.1,
        "de_limit": 5.0, "roe_excellent": 0.12
    },
    "IT Services": {
        "fundamental": 0.4, "technical": 0.3, "valuation": 0.2, "sentiment": 0.1,
        "de_limit": 1.0, "roe_excellent": 0.22
    },
    "Industrials": {
        "fundamental": 0.5, "technical": 0.2, "valuation": 0.2, "sentiment": 0.1,
        "de_limit": 2.0, "roe_excellent": 0.18
    },
    "Pharma": {
        "fundamental": 0.4, "technical": 0.2, "valuation": 0.3, "sentiment": 0.1,
        "de_limit": 1.5, "roe_excellent": 0.20
    },
    "Metals": {
        "fundamental": 0.5, "technical": 0.3, "valuation": 0.1, "sentiment": 0.1,
        "de_limit": 2.5, "roe_excellent": 0.16
    },
    "Autos": {
        "fundamental": 0.45, "technical": 0.25, "valuation": 0.2, "sentiment": 0.1,
        "de_limit": 1.5, "roe_excellent": 0.15
    },
    "FMCG": {
        "fundamental": 0.4, "technical": 0.2, "valuation": 0.3, "sentiment": 0.1,
        "de_limit": 1.0, "roe_excellent": 0.25
    },
    "Power": {
        "fundamental": 0.5, "technical": 0.2, "valuation": 0.2, "sentiment": 0.1,
        "de_limit": 3.0, "roe_excellent": 0.12
    },
    "Energy": {
        "fundamental": 0.5, "technical": 0.3, "valuation": 0.1, "sentiment": 0.1,
        "de_limit": 2.0, "roe_excellent": 0.14
    },
    "Telecom": {
        "fundamental": 0.5, "technical": 0.2, "valuation": 0.2, "sentiment": 0.1,
        "de_limit": 2.0, "roe_excellent": 0.10
    },
}

ALL_BUCKETS = [
    "company_details",
    "financials",
    "ratios",
    "valuation",
    "price",
    "websignals",
    "kpis",
    "derived_metrics",
    "_unmapped",
]


def bucket_symbol(symbol: str, sections: dict) -> dict:
    B = {b: {} for b in ALL_BUCKETS}

    for sec_key, records in sections.items():
        # ── SKIP guidance sections (loaded separately from guidance.json) ──────
        if sec_key in ("guidance:guidance", "guidance:insights"):
            continue
        
        sec_map = FIELD_MAP.get(sec_key)

        # ── section not in FIELD_MAP at all → entire section goes to _unmapped
        if sec_map is None:
            B["_unmapped"][sec_key] = deepcopy(records)
            continue

        # ── OHLCV history sections ─────────────────────────────────────────
        if sec_map == "__history__":
            hist_key = sec_key.split(":")[-1]   # e.g. history_6mo_1d
            for r in (records if isinstance(records, list) else []):
                if not isinstance(r, dict):
                    continue
                if r.get("metric") == "LTP":
                    B["price"]["ltp"] = r.get("data")
                elif r.get("values"):
                    # Remove Dividends and Stock Splits columns from history
                    # (these are already in company_details.shareholding.dividends)
                    cleaned_values = []
                    for record in r["values"]:
                        if isinstance(record, dict):
                            # Make a copy and remove redundant columns
                            clean_record = {k: v for k, v in record.items() 
                                          if k not in ['Dividends', 'Stock Splits']}
                            cleaned_values.append(clean_record)
                        else:
                            cleaned_values.append(record)
                    
                    B["price"][hist_key] = cleaned_values
            continue

        # ── operational_kpis: all metrics as-is ───────────────────────────
        if sec_map == "__all_ts__":
            # Handle both old flat list structure and new consolidation > granularity structure
            if isinstance(records, list):
                # Old format: flat list
                for r in records:
                    if isinstance(r, dict):
                        m = r.get("metric", "")
                        if m:
                            B["kpis"][m] = r.get("periods", {})
            elif isinstance(records, dict):
                # New format: consolidation > granularity > [metrics]
                for consol, consol_dict in records.items():
                    if isinstance(consol_dict, dict):
                        for granule, metrics_list in consol_dict.items():
                            if isinstance(metrics_list, list):
                                for r in metrics_list:
                                    if isinstance(r, dict):
                                        m = r.get("metric", "")
                                        if m:
                                            # Store with consolidation/granularity context
                                            key = f"{m}"
                                            if key not in B["kpis"]:
                                                B["kpis"][key] = r.get("periods", {})
            continue

        # ── screener_raw & screener_fin sections with consolidation > granularity hierarchy ──
        if (sec_key.startswith("screener_raw:") or sec_key.startswith("screener_fin:")) and isinstance(records, dict):
            # New structure: section > consolidation > granularity > [metrics]
            for consol, granule_dict in records.items():
                if isinstance(granule_dict, dict):
                    for granule, metrics_list in granule_dict.items():
                        if isinstance(metrics_list, list):
                            for r in metrics_list:
                                if not isinstance(r, dict):
                                    continue
                                metric = r.get("metric", "")
                                mapping = sec_map.get(metric)

                                if mapping is None:
                                    unmapped_key = f"{sec_key}::{metric}"
                                    B["_unmapped"][unmapped_key] = r.get("periods", deepcopy(r))
                                elif mapping == ("__skip__", "__skip__"):
                                    pass
                                else:
                                    target_bucket, target_key = mapping
                                    # Wrap with metadata - use consolidation from metric object if available
                                    metric_consol = r.get("consolidation") or consol
                                    periods_data = {
                                        "_periods": r.get("periods", {}),
                                        "_source": sec_key,
                                        "_granule": r.get("granule") or granule,
                                        "_consolidation": metric_consol
                                    }
                                    
                                    # Check if metric exists
                                    if target_key in B[target_bucket]:
                                        existing = B[target_bucket][target_key]
                                        # If already a list, append
                                        if isinstance(existing, list):
                                            existing.append(periods_data)
                                        # If dict with source, convert to list then append
                                        elif isinstance(existing, dict) and "_source" in existing:
                                            B[target_bucket][target_key] = [existing, periods_data]
                                        # Otherwise overwrite
                                        else:
                                            B[target_bucket][target_key] = periods_data
                                    else:
                                        B[target_bucket][target_key] = periods_data
            continue

        # ── list-based sections (time-series metrics) ──────────────────────
        if isinstance(records, list):
            for r in records:
                if not isinstance(r, dict):
                    continue
                metric = r.get("metric", "")
                mapping = sec_map.get(metric)

                if mapping is None:
                    unmapped_key = f"{sec_key}::{metric}"
                    B["_unmapped"][unmapped_key] = r.get("periods", deepcopy(r))
                elif mapping == ("__skip__", "__skip__"):
                    pass
                else:
                    target_bucket, target_key = mapping
                    # Wrap periods with source info
                    periods_data = {
                        "_periods": r.get("periods", {}),
                        "_source": sec_key
                    }
                    
                    # Check if metric exists
                    if target_key in B[target_bucket]:
                        existing = B[target_bucket][target_key]
                        # If already a list, append
                        if isinstance(existing, list):
                            existing.append(periods_data)
                        # If dict with source, convert to list then append
                        elif isinstance(existing, dict) and "_source" in existing:
                            B[target_bucket][target_key] = [existing, periods_data]
                        # Otherwise overwrite
                        else:
                            B[target_bucket][target_key] = periods_data
                    else:
                        B[target_bucket][target_key] = periods_data

        # ── dict-based sections ────────────────────────────────────────────
        elif isinstance(records, dict):
            for field_key, field_val in records.items():
                mapping = sec_map.get(field_key)

                if mapping is None:
                    unmapped_key = f"{sec_key}::{field_key}"
                    B["_unmapped"][unmapped_key] = deepcopy(field_val)
                elif mapping == ("__skip__", "__skip__"):
                    pass
                else:
                    target_bucket, target_key = mapping
                    # Apply standardization to the field value
                    standardized_val = apply_standardization_to_dict(field_val)
                    B[target_bucket][target_key] = standardized_val

    return B


def normalize_metric_history(periods_dict):
    """
    Reorganize time-series metric by granularity (daily, monthly, quarterly, half_yearly, annual).
    Skip empty granularities. Return in reverse chronological order.
    """
    if not isinstance(periods_dict, dict) or not periods_dict:
        return {}
    
    from datetime import datetime
    
    # Categorize each date by granularity
    granularities = {
        'daily': {},
        'monthly': {},
        'quarterly': {},
        'half_yearly': {},
        'annual': {}
    }
    
    for date_key, value in periods_dict.items():
        if value == "" or value is None:
            continue
        
        date_str = str(date_key).lower()
        
        # Detect granularity
        granule = None
        
        # Annual: FY####, standalone_####_*, or just 4-digit year, or specific date patterns
        if (date_str.startswith('fy') or 'standalone' in date_str or 
            (date_str.isdigit() and len(date_str) == 4)):
            granule = 'annual'
        # Half-yearly: H1/H2
        elif 'h1' in date_str or 'h2' in date_str:
            granule = 'half_yearly'
        # Quarterly: Q1-Q4
        elif any(f'q{i}' in date_str for i in range(1, 5)):
            granule = 'quarterly'
        # Date-based (ISO format YYYY-MM-DD)
        elif '-' in date_str:
            try:
                dt = datetime.fromisoformat(date_str.split('T')[0])
                month = dt.month
                day = dt.day
                
                # Determine granularity by month patterns
                # Half-yearly: months 3 & 9 (H1 & H2 ends)
                # Annual: month 3 but need to distinguish from H1
                # Check if it's half-yearly by looking at frequency
                if month in [3, 9]:
                    # Could be annual (March FY end) or half-yearly (March H1, Sept H2)
                    # If we see both 03 and 09 in same metric → half-yearly
                    # For now, treat 09 as half-yearly, 03 needs context
                    if month == 9:
                        granule = 'half_yearly'
                    elif month == 3:
                        # Default to half-yearly if day is 01 (not typical FY-end reporting)
                        granule = 'half_yearly' if day == 1 else 'annual'
                elif month == 12:
                    # December could be annual or half-yearly
                    granule = 'annual' if day >= 28 else 'half_yearly'
                elif month == 6:
                    granule = 'half_yearly'
                elif day > 1 and day < 28:
                    granule = 'daily'
                else:
                    granule = 'monthly'
            except:
                granule = 'monthly'  # Default
        
        if granule:
            granularities[granule][date_key] = value
    
    # Build result with non-empty granularities (reverse chronologically sorted)
    result = {}
    
    # Add non-empty granularities (reverse chronological order)
    for granule in ['daily', 'monthly', 'quarterly', 'half_yearly', 'annual']:
        if granularities[granule]:
            # Sort by date key reverse chronologically
            sorted_dates = sorted(granularities[granule].keys(), reverse=True)
            result[granule] = {k: granularities[granule][k] for k in sorted_dates}
    
    return result


def detect_granularity_from_dates(periods_dict):
    """
    Detect granularity by analyzing actual date patterns.
    - Annual: only month 3 (March), 12+ months apart
    - Quarterly: months 3,6,9,12 present
    - Half-yearly: only months 3,9 present
    - Monthly: various months
    - Daily: day > 1
    """
    if not periods_dict:
        return None
    
    from datetime import datetime
    
    # Extract months from dates
    months_seen = set()
    days_seen = set()
    dates_list = []
    
    for date_key in periods_dict.keys():
        try:
            date_str = str(date_key).lower()
            
            # Skip non-date formats
            if '-' not in date_str:
                continue
            
            dt = datetime.fromisoformat(date_str.split('T')[0])
            months_seen.add(dt.month)
            days_seen.add(dt.day)
            dates_list.append(dt)
        except:
            continue
    
    if not months_seen:
        return None
    
    # Determine granularity by month pattern
    months_sorted = sorted(months_seen)
    
    # Annual: only month 3 (March FY-end)
    if months_seen == {3}:
        return 'annual'
    
    # Half-yearly: only months 3 and 9
    if months_seen == {3, 9}:
        return 'half_yearly'
    
    # Quarterly: months 3,6,9,12 (or subset with quarter pattern)
    if months_seen <= {3, 6, 9, 12} and len(months_seen) >= 2:
        return 'quarterly'
    
    # Monthly: various months
    if len(months_seen) > 1:
        return 'monthly'
    
    # Daily: day varies
    if 1 in days_seen and len(days_seen) > 1:
        return 'daily'
    
    return 'monthly'  # Default


def clean_websignals(bucketed: dict) -> dict:
    """
    Clean websignals:
    - Remove empty/null values
    - Remove dicts with all empty values
    """
    if "websignals" not in bucketed:
        return bucketed
    
    ws = bucketed["websignals"]
    cleaned = {}
    
    for key, val in ws.items():
        # Skip None/null
        if val is None:
            continue
        
        # Skip empty strings
        if isinstance(val, str) and val.strip() == "":
            continue
        
        # Skip dicts with only empty values
        if isinstance(val, dict):
            # Remove empty values from dict
            cleaned_dict = {k: v for k, v in val.items() if v != "" and v is not None}
            if cleaned_dict:  # Only keep dict if it has non-empty values
                cleaned[key] = cleaned_dict
        else:
            cleaned[key] = val
    
    bucketed["websignals"] = cleaned
    return bucketed


def clean_metadata_wrapper(bucketed: dict) -> dict:
    """
    Remove _periods, _source, _granule, _consolidation metadata from all buckets.
    Unwrap the actual data.
    """
    for bucket_name, bucket_data in bucketed.items():
        if not isinstance(bucket_data, dict):
            continue
        
        cleaned = {}
        for key, value in bucket_data.items():
            # Remove metadata wrapping
            if isinstance(value, dict):
                # If has _periods, unwrap it (this is the actual time-series data)
                if "_periods" in value:
                    cleaned[key] = value["_periods"]
                # Skip metadata-only values (_granule, _consolidation, etc)
                elif any(k.startswith("_") for k in value.keys()):
                    # Has metadata but no periods - skip these
                    continue
                else:
                    # Regular dict, keep as-is
                    cleaned[key] = value
            elif isinstance(value, list):
                # Handle lists (multiple sources for same metric)
                cleaned_list = []
                for item in value:
                    if isinstance(item, dict) and "_periods" in item:
                        # Convert to consolidated/standalone structure if it has consolidation info
                        consol = item.get("_consolidation")
                        if consol:
                            # Keep the structure for consolidation grouping
                            cleaned_list.append({
                                "_periods": item["_periods"],
                                "_consolidation": consol,
                                "_granule": item.get("_granule")
                            })
                        else:
                            cleaned_list.append(item["_periods"])
                    else:
                        cleaned_list.append(item)
                if cleaned_list:
                    cleaned[key] = cleaned_list
            else:
                # Scalar values, keep as-is
                cleaned[key] = value
        
        bucketed[bucket_name] = cleaned
    
    return bucketed


def reorganize_by_period(bucketed: dict) -> dict:
    """
    Normalize each metric in financials: separate by consolidation > granularity.
    Uses metadata from input: _granule and _consolidation
    Structure: metric > consolidation > granularity > dates
    """
    if "financials" not in bucketed:
        return bucketed
    
    financials = bucketed["financials"]
    
    # First pass: extract all metrics with source info
    metrics_by_name = {}
    for metric_key, metric_value in financials.items():
        # Handle list of sources (same metric from different sources)
        if isinstance(metric_value, list):
            if metric_key not in metrics_by_name:
                metrics_by_name[metric_key] = {}
            
            for item in metric_value:
                if isinstance(item, dict) and "_periods" in item:
                    periods_dict = item["_periods"]
                    
                    # Get metadata from input
                    granule = item.get("_granule")
                    consol = item.get("_consolidation")
                    
                    # Use granule from metadata if available
                    if not granule:
                        # Fallback to detect from dates
                        granule = detect_granularity_from_dates(periods_dict)
                    
                    if granule and isinstance(periods_dict, dict) and periods_dict:
                        sorted_dates = sorted(periods_dict.keys(), reverse=True)
                        date_dict = {k: periods_dict[k] for k in sorted_dates}
                        
                        # Structure: consolidation > granule > dates
                        if consol:
                            if consol not in metrics_by_name[metric_key]:
                                metrics_by_name[metric_key][consol] = {}
                            metrics_by_name[metric_key][consol][granule] = date_dict
                        else:
                            # No consolidation info, put at granule level
                            if granule not in metrics_by_name[metric_key]:
                                metrics_by_name[metric_key][granule] = {}
                            metrics_by_name[metric_key][granule]["_data"] = date_dict
        
        # Handle single source
        elif isinstance(metric_value, dict) and "_periods" in metric_value:
            periods_dict = metric_value["_periods"]
            
            if isinstance(periods_dict, dict) and periods_dict:
                # Get metadata from input
                granule = metric_value.get("_granule")
                consol = metric_value.get("_consolidation")
                
                # Use granule from metadata if available
                if not granule:
                    # Fallback to detect from dates
                    granule = detect_granularity_from_dates(periods_dict)
                
                if granule:
                    if metric_key not in metrics_by_name:
                        metrics_by_name[metric_key] = {}
                    
                    sorted_dates = sorted(periods_dict.keys(), reverse=True)
                    date_dict = {k: periods_dict[k] for k in sorted_dates}
                    
                    # Structure: consolidation > granule > dates
                    if consol:
                        if consol not in metrics_by_name[metric_key]:
                            metrics_by_name[metric_key][consol] = {}
                        metrics_by_name[metric_key][consol][granule] = date_dict
                    else:
                        # No consolidation info, put at granule level
                        if granule not in metrics_by_name[metric_key]:
                            metrics_by_name[metric_key][granule] = {}
                        metrics_by_name[metric_key][granule]["_data"] = date_dict
        
        # Scalar values
        elif metric_value and not isinstance(metric_value, dict):
            metrics_by_name[metric_key] = metric_value
        elif isinstance(metric_value, dict) and metric_value and "_periods" not in metric_value:
            metrics_by_name[metric_key] = metric_value
    
    bucketed["financials"] = metrics_by_name
    return bucketed


def reorganize_ratios_revenue(bucketed: dict) -> dict:
    """
    Group revenue-related metrics under 'revenue' sub-object in ratios.
    Remove originals to avoid scattering.
    """
    if "ratios" not in bucketed:
        return bucketed
    
    ratios = bucketed["ratios"]
    
    revenue_keys = {
        'total_revenue', 'revenue_per_share', 'revenue_growth'
    }
    
    # Extract revenue metrics (using pop to remove originals)
    revenue_obj = {}
    for key in revenue_keys:
        if key in ratios:
            revenue_obj[key] = ratios.pop(key)
    
    # Add revenue object back if it has data
    if revenue_obj:
        ratios['revenue'] = revenue_obj
    
    bucketed["ratios"] = ratios
    return bucketed


def reorganize_valuation_eps_pe(bucketed: dict) -> dict:
    """
    Group EPS and P/E metrics under separate sub-objects in valuation.
    Remove original keys to avoid duplicates.
    """
    if "valuation" not in bucketed:
        return bucketed
    
    valuation = bucketed["valuation"]
    
    eps_keys = {
        'eps_ttm', 'eps_forward', 'eps_current_year', 'diluted_eps', 'basic_eps',
        'trailing_eps', 'forward_eps', 'price_eps_current_year'
    }
    
    pe_keys = {
        'trailing_pe', 'forward_pe', 'peg_ratio', 'trailing_peg_ratio', 'price_to_book',
        'price_to_sales_ttm', 'forward_peg_ratio'
    }
    
    # Extract EPS metrics (and remove from top level)
    eps_obj = {}
    for key in eps_keys:
        if key in valuation:
            eps_obj[key] = valuation.pop(key)
    
    # Extract P/E metrics (and remove from top level)
    pe_obj = {}
    for key in pe_keys:
        if key in valuation:
            pe_obj[key] = valuation.pop(key)
    
    # Add sub-objects back
    if eps_obj:
        valuation['eps'] = eps_obj
    if pe_obj:
        valuation['pe'] = pe_obj
    
    bucketed["valuation"] = valuation
    return bucketed


def compute_derived_metrics(bucketed: dict, sector: str = None) -> dict:
    """
    Compute derived metrics from bucketed data with sector-aware weightage.
    Handles nested financial structure: metric > consolidation > granularity > dates > values
    """
    derived = bucketed.copy()
    sector = sector or derived.get("company_details", {}).get("sector", "Industrials")
    sector_profile = SECTOR_PROFILES.get(sector, SECTOR_PROFILES["Industrials"])
    
    metrics = {}
    
    # Helper to extract latest scalar value from nested structure
    def get_latest_value(metric_dict):
        if not isinstance(metric_dict, dict):
            return None
        for consol_key in ['consolidated', 'standalone']:
            if consol_key in metric_dict:
                consol_data = metric_dict[consol_key]
                if isinstance(consol_data, dict):
                    for granule_key in ['annual', 'quarterly']:
                        if granule_key in consol_data:
                            granule_data = consol_data[granule_key]
                            if isinstance(granule_data, dict):
                                dates = sorted(granule_data.keys(), reverse=True)
                                if dates:
                                    val = granule_data[dates[0]]
                                    if isinstance(val, (int, float)) and val is not None:
                                        return val
        return None
    
    def get_flat_value(obj, key):
        if isinstance(obj, dict):
            val = obj.get(key)
            if isinstance(val, (int, float)) and val is not None:
                return val
        return None
    
    fin = bucketed.get("financials", {})
    val = bucketed.get("valuation", {})
    price = bucketed.get("price", {})
    websignals = bucketed.get("websignals", {})
    
    # FUNDAMENTAL METRICS
    roe_pct = get_latest_value(fin.get("Return_on_Equity_pct", {}))
    if roe_pct is not None:
        metrics["roe_pct"] = round(roe_pct, 2)
        roe_excellent = sector_profile.get("roe_excellent", 0.15)
        if roe_pct >= roe_excellent * 100:
            metrics["roe_score"] = 100
        elif roe_pct >= roe_excellent * 100 * 0.75:
            metrics["roe_score"] = 75
        elif roe_pct >= roe_excellent * 100 * 0.5:
            metrics["roe_score"] = 50
        else:
            metrics["roe_score"] = 25
    
    total_debt = get_latest_value(fin.get("Total_Debt", {}))
    equity = get_latest_value(fin.get("Equity_Capital", {}))
    if total_debt is not None and equity and equity > 0:
        de_ratio = total_debt / equity
        metrics["debt_to_equity"] = round(de_ratio, 2)
        de_limit = sector_profile.get("de_limit", 2.0)
        if de_ratio <= de_limit * 0.5:
            metrics["de_score"] = 100
        elif de_ratio <= de_limit:
            metrics["de_score"] = 75
        elif de_ratio <= de_limit * 1.5:
            metrics["de_score"] = 50
        else:
            metrics["de_score"] = 25
    
    net_margin = get_latest_value(fin.get("Net_Margin_pct", {}))
    if net_margin is not None:
        metrics["net_margin_pct"] = round(net_margin, 2)
        if net_margin >= 15:
            metrics["margin_score"] = 100
        elif net_margin >= 10:
            metrics["margin_score"] = 75
        elif net_margin >= 5:
            metrics["margin_score"] = 50
        else:
            metrics["margin_score"] = 25
    
    # VALUATION METRICS
    pe_data = val.get("pe", {})
    trailing_pe = get_flat_value(pe_data, "trailing_pe")
    if trailing_pe and trailing_pe > 0:
        metrics["pe_ratio"] = round(trailing_pe, 2)
        if trailing_pe < 10:
            metrics["pe_score"] = 100
        elif trailing_pe < 15:
            metrics["pe_score"] = 80
        elif trailing_pe < 20:
            metrics["pe_score"] = 60
        elif trailing_pe < 30:
            metrics["pe_score"] = 40
        else:
            metrics["pe_score"] = 20
    
    pb = get_flat_value(pe_data, "price_to_book")
    if pb and pb > 0:
        metrics["price_to_book"] = round(pb, 2)
        if pb < 1:
            metrics["pb_score"] = 100
        elif pb < 1.5:
            metrics["pb_score"] = 80
        elif pb < 3:
            metrics["pb_score"] = 60
        else:
            metrics["pb_score"] = 40
    
    # TECHNICAL METRICS
    price_change = get_flat_value(price, "regular_market_change_pct")
    if price_change is not None:
        metrics["price_momentum_pct"] = round(price_change, 2)
        if price_change > 10:
            metrics["momentum_score"] = 100
        elif price_change > 5:
            metrics["momentum_score"] = 75
        elif price_change > 0:
            metrics["momentum_score"] = 60
        elif price_change > -5:
            metrics["momentum_score"] = 40
        else:
            metrics["momentum_score"] = 20
    
    avg_vol = get_flat_value(price, "average_volume")
    avg_vol_3m = get_flat_value(price, "average_volume_3mo")
    if avg_vol and avg_vol_3m and avg_vol_3m > 0:
        vol_ratio = avg_vol / avg_vol_3m
        metrics["volume_ratio"] = round(vol_ratio, 2)
        if vol_ratio > 1.2:
            metrics["volume_score"] = 100
        elif vol_ratio > 1.0:
            metrics["volume_score"] = 75
        elif vol_ratio > 0.8:
            metrics["volume_score"] = 50
        else:
            metrics["volume_score"] = 25
    
    # SENTIMENT METRICS
    sentiment = websignals.get("ai_insights_date")
    if sentiment:
        metrics["sentiment_score"] = 60
    
    # COMPOSITE SCORE WITH SECTOR WEIGHTAGE
    fundamental_score = 50
    technical_score = 50
    valuation_score = 50
    sentiment_score = 50
    
    fundamental_components = []
    if "roe_score" in metrics:
        fundamental_components.append(metrics["roe_score"])
    if "de_score" in metrics:
        fundamental_components.append(metrics["de_score"])
    if "margin_score" in metrics:
        fundamental_components.append(metrics["margin_score"])
    
    if fundamental_components:
        fundamental_score = round(sum(fundamental_components) / len(fundamental_components), 1)
    metrics["fundamental_score"] = fundamental_score
    
    technical_components = []
    if "momentum_score" in metrics:
        technical_components.append(metrics["momentum_score"])
    if "volume_score" in metrics:
        technical_components.append(metrics["volume_score"])
    
    if technical_components:
        technical_score = round(sum(technical_components) / len(technical_components), 1)
    metrics["technical_score"] = technical_score
    
    valuation_components = []
    if "pe_score" in metrics:
        valuation_components.append(metrics["pe_score"])
    if "pb_score" in metrics:
        valuation_components.append(metrics["pb_score"])
    
    if valuation_components:
        valuation_score = round(sum(valuation_components) / len(valuation_components), 1)
    metrics["valuation_score"] = valuation_score
    
    if sentiment:
        sentiment_score = 70
    metrics["sentiment_score"] = sentiment_score
    
    weights = sector_profile
    composite = (
        fundamental_score * weights.get("fundamental", 0.5) +
        technical_score * weights.get("technical", 0.2) +
        valuation_score * weights.get("valuation", 0.2) +
        sentiment_score * weights.get("sentiment", 0.1)
    )
    metrics["composite_score"] = round(composite, 1)
    
    score = metrics["composite_score"]
    if score >= 75:
        metrics["rating"] = "STRONG BUY"
    elif score >= 60:
        metrics["rating"] = "BUY"
    elif score >= 50:
        metrics["rating"] = "HOLD"
    elif score >= 35:
        metrics["rating"] = "SELL"
    else:
        metrics["rating"] = "STRONG SELL"
    
    metrics["sector"] = sector
    metrics["sector_weights"] = {
        "fundamental": weights.get("fundamental", 0.5),
        "technical": weights.get("technical", 0.2),
        "valuation": weights.get("valuation", 0.2),
        "sentiment": weights.get("sentiment", 0.1)
    }
    
    derived["derived_metrics"]["calculated_metrics"] = metrics
    return derived


def reorganize_derived_metrics_guidance(bucketed: dict) -> dict:
    """
    Remove guidance fields from websignals (they're duplicated in ai_insights_guidance).
    Keep only ai_insights_guidance which comes from guidance.json.
    """
    if "websignals" not in bucketed or "derived_metrics" not in bucketed:
        return bucketed
    
    websignals = bucketed["websignals"]
    
    # Guidance-related keys to REMOVE (they're duplicated in ai_insights_guidance)
    guidance_keys = {
        'quarter', 'financial', 'business', 'management', 'summary', 'deals_and_pipeline',
        'customers', 'segments', 'geography', 'operations', 'capital_allocation',
        'competitive_position', 'investor_verdict', 'analyst_dimensions', 'date'
    }
    
    # Remove guidance keys from websignals (using pop)
    for key in guidance_keys:
        websignals.pop(key, None)
    
    bucketed["websignals"] = websignals
    return bucketed


def reorganize_price_52w_volume(bucketed: dict) -> dict:
    """
    Group 52-week and volume metrics under separate sub-objects in price.
    Remove originals to avoid duplication.
    """
    if "price" not in bucketed:
        return bucketed
    
    price = bucketed["price"]
    
    week_52_keys = {
        'fifty_two_week_change', 'fifty_two_week_high', 'fifty_two_week_low',
        'fifty_two_week_change_pct'
    }
    
    volume_keys = {
        'volume', 'average_volume', 'average_volume_10d', 'average_daily_volume_10d',
        'average_daily_volume_3mo', 'regular_market_volume'
    }
    
    ltp_keys = {
        'open', 'beta', 'high', 'low', 'prev'
    }
    
    # Extract 52-week metrics (using pop to remove originals)
    week_52_obj = {}
    for key in week_52_keys:
        if key in price:
            week_52_obj[key] = price.pop(key)
    
    # Extract volume metrics (using pop to remove originals)
    volume_obj = {}
    for key in volume_keys:
        if key in price:
            volume_obj[key] = price.pop(key)
    
    # Extract ltp-related metrics (using pop to remove originals)
    ltp_obj = {}
    for key in ltp_keys:
        if key in price:
            ltp_obj[key] = price.pop(key)
    
    # If there's already an ltp dict, merge with it
    if 'ltp' in price and isinstance(price['ltp'], dict):
        ltp_obj.update(price.pop('ltp'))
    
    # Add sub-objects back
    if week_52_obj:
        price['52_week'] = week_52_obj
    if volume_obj:
        price['volume'] = volume_obj
    if ltp_obj:
        price['ltp'] = ltp_obj
    
    bucketed["price"] = price
    return bucketed


def reorganize_financials_debt(bucketed: dict) -> dict:
    """
    Group debt-related fields under 'debt' sub-object in financials.
    Remove originals to avoid duplication.
    """
    if "financials" not in bucketed:
        return bucketed
    
    financials = bucketed["financials"]
    
    debt_keys = {
        'total_debt', 'net_debt', 'short_term_debt', 'long_term_debt', 'capital_lease_obligations'
    }
    
    # Extract debt metrics (using pop to remove from financials)
    debt_obj = {}
    for key in debt_keys:
        if key in financials:
            debt_obj[key] = financials.pop(key)  # Remove original after copying
    
    # Add debt object back to financials if it has data
    if debt_obj:
        financials['debt'] = debt_obj
    
    bucketed["financials"] = financials
    return bucketed


def reorganize_identity_shareholding(bucketed: dict) -> dict:
    """
    Group shareholding-related fields under 'shareholding' sub-object in identity.
    Organizes into: shares, ownership, fiscal_dates, pattern, dividends.
    """
    if "company_details" not in bucketed:
        return bucketed
    
    identity = bucketed["company_details"]
    
    # Extract shareholding data
    shareholding_obj = {}
    
    # Shares sub-group
    shares_obj = {}
    for key in ['float_shares', 'shares_outstanding', 'implied_shares_outstanding']:
        if key in identity:
            shares_obj[key] = identity[key]
    if shares_obj:
        shareholding_obj['shares'] = shares_obj
    
    # Ownership sub-group
    ownership_obj = {}
    for key in ['held_pct_insiders', 'held_pct_institutions']:
        if key in identity:
            ownership_obj[key] = identity[key]
    if ownership_obj:
        shareholding_obj['ownership'] = ownership_obj
    
    # Fiscal dates sub-group
    fiscal_obj = {}
    for key in ['last_fiscal_year_end', 'next_fiscal_year_end', 'most_recent_quarter']:
        if key in identity:
            fiscal_obj[key] = identity[key]
    if fiscal_obj:
        shareholding_obj['fiscal_dates'] = fiscal_obj
    
    # Shareholding pattern sub-group
    pattern_obj = {}
    for key in ['promoters', 'fiis', 'diis', 'public', 'government', 'others', 'no_of_shareholders']:
        if key in identity:
            val = identity[key]
            # Simply extract _periods if available
            if isinstance(val, dict) and '_periods' in val:
                pattern_obj[key] = val.get('_periods', {})
            else:
                pattern_obj[key] = val
    if pattern_obj:
        shareholding_obj['pattern'] = pattern_obj
    
    # Dividends sub-group
    dividend_obj = {}
    dividend_keys = {
        'dividend_rate', 'dividend_yield', 'ex_dividend_date', 'payout_ratio',
        'trailing_annual_dividend_rate', 'trailing_annual_dividend_yield',
        'last_dividend_value', 'last_dividend_date', 'five_year_avg_dividend_yield'
    }
    for key in dividend_keys:
        if key in identity:
            dividend_obj[key] = identity.pop(key)  # Remove from identity
    if dividend_obj:
        shareholding_obj['dividends'] = dividend_obj
    
    # Stock Splits sub-group
    split_obj = {}
    split_keys = {'last_split_date', 'last_split_factor'}
    for key in split_keys:
        if key in identity:
            split_obj[key] = identity.pop(key)  # Remove from identity
    if split_obj:
        shareholding_obj['stock_splits'] = split_obj
    
    # Add shareholding object back to identity
    if shareholding_obj:
        identity['shareholding'] = shareholding_obj
    
    bucketed["company_details"] = identity
    return bucketed

# ══════════════════════════════════════════════════════════════════════════════
# BUCKETING MODULE — FROZEN
# ══════════════════════════════════════════════════════════════════════════════
# bucket_symbol() & FIELD_MAP are locked. Changes require version bump + changelog.
# Do not modify bucket_symbol() logic or FIELD_MAP structure after this point.
# ══════════════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════════════
# DERIVED METRICS MODULE
# ══════════════════════════════════════════════════════════════════════════════
# Computes secondary metrics from bucketed data.
# All derivations are deterministic & idempotent.
#
# Rules:
# 1. Source only from bucketed data buckets (never raw)
# 2. Handle nulls gracefully (return None, not crash)
# 3. Document source path for each metric
# 4. Add to DERIVED_METRICS_SPEC for registry
# ══════════════════════════════════════════════════════════════════════════════

DERIVED_METRICS_SPEC = {
    # ── VALUATION METRICS ──
    "valuation_score": {
        "bucket": "valuation",
        "sources": ["valuation.trailing_pe"],
        "description": "PE-based valuation score (0-100). <15=85, <25=60, >25=40, null=50"
    },
    
    # ── HEALTH & FINANCIAL STRENGTH ──
    "health_score": {
        "bucket": "websignals",
        "sources": ["balance_sheet_annual.de_ratio", "profitability_growth.roe"],
        "description": "Sector-aware health score: D/E vs sector limit + ROE strength"
    },
    "leverage_quality": {
        "bucket": "websignals",
        "sources": ["balance_sheet_annual.total_debt", "valuation.market_cap"],
        "description": "Debt-to-market-cap ratio; lower is stronger"
    },
    "interest_coverage": {
        "bucket": "websignals",
        "sources": ["income_statement_annual.ebit", "income_statement_annual.interest_expense"],
        "description": "EBIT / Interest Expense; >3 is healthy"
    },
    
    # ── GROWTH METRICS ──
    "growth_score": {
        "bucket": "ratios",
        "sources": ["profitability_growth.revenue_growth", "profitability_growth.earnings_growth"],
        "description": "Earnings growth scoring: >20%=85, >10%=70, >0%=55, ≤0%=30"
    },
    "revenue_growth_yoy": {
        "bucket": "ratios",
        "sources": ["income_statement_annual.revenue"],
        "description": "YoY revenue growth % (comparing latest 2 years)"
    },
    "earnings_growth_yoy": {
        "bucket": "ratios",
        "sources": ["income_statement_annual.net_profit"],
        "description": "YoY net profit growth %"
    },
    "fcf_growth": {
        "bucket": "ratios",
        "sources": ["cash_flow_annual.operating_cash_flow", "cash_flow_annual.capex"],
        "description": "Free Cash Flow growth YoY"
    },
    
    # ── TECHNICAL & MOMENTUM ──
    "technical_score": {
        "bucket": "price",
        "sources": ["price_trading.regular_market_change_pct"],
        "description": "Technical momentum score: >5%=75, >0%=60, ≤0%=40"
    },
    "price_momentum_short": {
        "bucket": "price",
        "sources": ["price_trading.regular_market_change_pct"],
        "description": "Recent price change % (last trading session)"
    },
    "volume_trend": {
        "bucket": "price",
        "sources": ["price_trading.regular_market_volume", "price_trading.average_daily_volume_3mo"],
        "description": "Current volume vs 3-month average; >1.2 = elevated"
    },
    "ma_50_position": {
        "bucket": "price",
        "sources": ["price_trading.current_price", "price_trading.fifty_day_avg"],
        "description": "Price position relative to 50-day MA; >1.0 = above MA (bullish)"
    },
    "ma_200_position": {
        "bucket": "price",
        "sources": ["price_trading.current_price", "price_trading.two_hundred_day_avg"],
        "description": "Price position relative to 200-day MA; >1.0 = above MA (bullish)"
    },
    
    # ── QUALITY & EFFICIENCY ──
    "quality_score": {
        "bucket": "ratios",
        "sources": ["profitability_growth.roe", "efficiency_ratios.asset_turnover", "profitability_growth.margin"],
        "description": "Composite quality: high ROE + asset efficiency + margins"
    },
    "profitability_ratio": {
        "bucket": "ratios",
        "sources": ["income_statement_annual.net_profit", "income_statement_annual.revenue"],
        "description": "Net profit margin %"
    },
    "operating_margin": {
        "bucket": "ratios",
        "sources": ["income_statement_annual.operating_profit", "income_statement_annual.revenue"],
        "description": "Operating profit margin %"
    },
    "fcf_yield": {
        "bucket": "valuation",
        "sources": ["cash_flow_annual.free_cash_flow", "valuation.market_cap"],
        "description": "Free Cash Flow / Market Cap; >5% is strong"
    },
    "roe": {
        "bucket": "ratios",
        "sources": ["income_statement_annual.net_profit", "balance_sheet_annual.equity"],
        "description": "Return on Equity; >15% is excellent"
    },
    "roa": {
        "bucket": "ratios",
        "sources": ["income_statement_annual.net_profit", "balance_sheet_annual.total_assets"],
        "description": "Return on Assets; >10% is strong"
    },
    "asset_turnover": {
        "bucket": "ratios",
        "sources": ["income_statement_annual.revenue", "balance_sheet_annual.total_assets"],
        "description": "Revenue / Total Assets; indicates capital efficiency"
    },
    
    # ── COMPOSITE SIGNALS ──
    "composite_score": {
        "bucket": "websignals",
        "sources": ["valuation_score", "health_score", "growth_score", "technical_score"],
        "description": "Weighted blend: 20% valuation + 50% health + 25% growth + 20% technical"
    },
    "investment_signal": {
        "bucket": "websignals",
        "sources": ["composite_score"],
        "description": "Signal classification: STRONG_BUY (≥75) | BUY (≥60) | HOLD (≥40) | SELL (≥25) | STRONG_SELL (<25)"
    },
    "signal_confidence": {
        "bucket": "websignals",
        "sources": ["composite_score"],
        "description": "Confidence % = min(99.99, 50 + |composite - 50| * 0.9)"
    },
    
    # ── VALUATION MULTIPLES (DERIVED) ──
    "ev_to_sales": {
        "bucket": "valuation",
        "sources": ["valuation.enterprise_value", "income_statement_annual.revenue"],
        "description": "Enterprise Value / Revenue; lower is cheaper"
    },
    "price_to_fcf": {
        "bucket": "valuation",
        "sources": ["valuation.market_cap", "cash_flow_annual.free_cash_flow"],
        "description": "Market Cap / FCF; valuation multiple"
    },
    "peg_ratio": {
        "bucket": "valuation",
        "sources": ["valuation.trailing_pe", "earnings_growth_yoy"],
        "description": "P/E / Growth rate; <1 suggests undervalued vs growth"
    },
    
    # ── RISK FLAGS ──
    "debt_risk_flag": {
        "bucket": "websignals",
        "sources": ["balance_sheet_annual.de_ratio", "balance_sheet_annual.total_debt"],
        "description": "High debt warning; flag if D/E > 2.5 or debt > 50% of assets"
    },
    "profitability_risk_flag": {
        "bucket": "websignals",
        "sources": ["profitability_growth.roe", "profitability_growth.margin"],
        "description": "Profitability concern; flag if ROE <8% or margin <5%"
    },
    "liquidity_risk_flag": {
        "bucket": "websignals",
        "sources": ["balance_sheet_annual.current_ratio", "balance_sheet_annual.quick_ratio"],
        "description": "Liquidity stress; flag if current ratio <1.2 or quick <0.8"
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# HELPER: Extract Scalar or Dict (FIX FOR TIME-SERIES ANOMALIES)
# ══════════════════════════════════════════════════════════════════════════════

def extract_scalar_or_dict(value):
    """
    Extract latest scalar value from time-series dict.
    Handles both old flat time-series and new granularity-nested structure.
    """
    if value is None or not isinstance(value, dict):
        return value
    if not value:
        return value
    
    keys = list(value.keys())
    first_key = str(keys[0]) if keys else ""
    
    # NEW: Check if it's granularity-nested (has keys like 'annual', 'quarterly', etc)
    granularity_keys = {'daily', 'monthly', 'quarterly', 'half_yearly', 'annual'}
    if set(keys).issubset(granularity_keys | {'_meta'}):
        # It's a granularity-nested structure, extract from first non-meta granularity
        for granule in ['annual', 'half_yearly', 'quarterly', 'monthly', 'daily']:
            if granule in value and value[granule]:
                # Get first (most recent) date's value from this granularity
                ts = value[granule]
                if isinstance(ts, dict) and ts:
                    sorted_keys = sorted(ts.keys(), reverse=True)
                    return ts[sorted_keys[0]]
        return None
    
    # OLD: Flat time-series
    is_timeseries = (
        ('-' in first_key and len(first_key) == 10) or  # YYYY-MM-DD
        ('FY' in first_key) or  # FY2026
        (first_key.isdigit() and len(first_key) == 4)    # 2026
    )
    
    if is_timeseries:
        sorted_keys = sorted(value.keys(), reverse=True)
        return value[sorted_keys[0]]
    
    return value


def generate_metadata_from_samples(output_data):
    """
    Generate real metadata structure from actual ticker data samples.
    Inspects all buckets across all tickers to build accurate field inventory.
    
    Returns:
        {
            "buckets": {
                "bucket_name": {
                    "fields": [...actual field names...],
                    "nested_structures": {
                        "sub_key": [...fields...]
                    },
                    "sample_values": {example of first few fields + types}
                }
            }
        }
    """
    buckets_inventory = {}
    
    ALL_BUCKETS = [
        "company_details", "financials", "ratios", "valuation", 
        "price", "websignals", "kpis", "derived_metrics", "_unmapped"
    ]
    
    for bucket in ALL_BUCKETS:
        buckets_inventory[bucket] = {
            "all_fields": set(),
            "nested_keys": {},  # For sub-dicts like {'pe': ['field1', 'field2']}
            "field_types": {}   # Track what type each field is
        }
    
    # Scan all tickers (excluding _metadata)
    for ticker, data in output_data.items():
        if ticker == '_metadata':
            continue
        
        for bucket in ALL_BUCKETS:
            if bucket not in data:
                continue
            
            bucket_data = data[bucket]
            if not isinstance(bucket_data, dict):
                continue
            
            # Iterate through all fields in this bucket
            for field_name, field_value in bucket_data.items():
                buckets_inventory[bucket]["all_fields"].add(field_name)
                
                # Track field type (for UI schema generation)
                if isinstance(field_value, dict):
                    field_type = "object"
                    # If it's a nested dict, track its sub-keys
                    if field_value and not field_value.get('_periods') and not field_value.get('_source'):
                        sub_keys = [k for k in field_value.keys() if not k.startswith('_')]
                        if sub_keys:
                            buckets_inventory[bucket]["nested_keys"][field_name] = sub_keys
                elif isinstance(field_value, list):
                    field_type = "array"
                elif isinstance(field_value, (int, float)):
                    field_type = "number"
                elif isinstance(field_value, bool):
                    field_type = "boolean"
                elif isinstance(field_value, str):
                    field_type = "string"
                else:
                    field_type = "unknown"
                
                if field_name not in buckets_inventory[bucket]["field_types"]:
                    buckets_inventory[bucket]["field_types"][field_name] = field_type
    
    # Format for output
    structure = {}
    for bucket in ALL_BUCKETS:
        inv = buckets_inventory[bucket]
        
        if not inv["all_fields"]:
            continue
        
        structure[bucket] = {
            "fields": sorted(list(inv["all_fields"])),
            "field_count": len(inv["all_fields"]),
            "field_types": inv["field_types"],
        }
        
        # Add nested structures if present
        if inv["nested_keys"]:
            structure[bucket]["nested_structures"] = {
                parent: sorted(children) 
                for parent, children in sorted(inv["nested_keys"].items())
            }
    
    return structure


def main():
    if not INPUT_FILE.exists():
        logger.error(f"INPUT FILE NOT FOUND: {INPUT_FILE}")
        sys.exit(1)

    logger.info(f"Reading {INPUT_FILE} …")
    with open(INPUT_FILE) as f:
        raw = json.load(f)
    
    # Load guidance data
    guidance_file = DATA_DIR / 'guidance.json'
    guidance_data = {}
    if guidance_file.exists():
        with open(guidance_file) as f:
            guidance_data = json.load(f)
        logger.info(f"  ✓ Loaded guidance.json ({len(guidance_data)} tickers)")

    output  = {}
    symbols = [k for k in raw.keys() if k != '_metadata']  # Skip _metadata
    total   = len(symbols)
    unmapped_summary = {}

    for i, symbol in enumerate(symbols, 1):
        sections = raw[symbol].get("data", {})
        bucketed = bucket_symbol(symbol, sections)
        bucketed = reorganize_by_period(bucketed)  # Separate by period type
        bucketed = clean_websignals(bucketed)  # Remove empty values from websignals
        bucketed = clean_metadata_wrapper(bucketed)  # Remove _periods and _source
        bucketed = reorganize_financials_debt(bucketed)  # Group debt metrics
        bucketed = reorganize_ratios_revenue(bucketed)  # Group revenue metrics in ratios
        bucketed = reorganize_valuation_eps_pe(bucketed)  # Group EPS & P/E in valuation
        bucketed = reorganize_price_52w_volume(bucketed)  # Group 52-week & volume in price
        bucketed = reorganize_identity_shareholding(bucketed)  # Group shareholding under company_details
        bucketed = compute_derived_metrics(bucketed)  # Compute derived financial metrics
        bucketed = reorganize_derived_metrics_guidance(bucketed)  # Move guidance to derived_metrics
        
        # Add guidance data from guidance.json
        if symbol in guidance_data:
            if 'derived_metrics' not in bucketed:
                bucketed['derived_metrics'] = {}
            bucketed['derived_metrics']['ai_insights_guidance'] = guidance_data[symbol]
        
        output[symbol] = bucketed

        # Report any unmapped fields for visibility
        u = bucketed.get("_unmapped", {})
        if u:
            unmapped_summary[symbol] = list(u.keys())

        status = f"  [{i:>3}/{total}] {symbol}"
        if u:
            status += f"  ⚠  {len(u)} unmapped field(s)"
        logger.info(status)

    logger.info(f"Writing {OUTPUT_FILE} …")
    
    # Generate real metadata from actual data structure
    real_structure = generate_metadata_from_samples(output)
    
    from datetime import datetime
    import time
    
    # Build metadata with real field inventory from actual data
    final_output = {
        "_metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_tickers": total,
            "tickers_with_guidance": len([s for s in symbols if s in guidance_data]),
            "data_sources": [
                "screener_raw_data.json",
                "screener_financials.json",
                "yahoofin_raw_data.json",
                "yahoofin_financials.json",
                "guidance.json",
                "prices.json",
                "unified-symbols.json"
            ],
            "schema": real_structure,
            "unmapped_count": sum(len(v) for v in unmapped_summary.values()),
            "unmapped_tickers": list(unmapped_summary.keys()),
            "notes": "Use 'schema' to map UI fields. Each bucket has 'fields' (all field names), 'field_count', 'field_types' (data types), and 'nested_structures' (for sub-objects)"
        }
    }
    
    # Add all ticker data
    final_output.update(output)
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(final_output, f, indent=2, default=str)

    size_kb = OUTPUT_FILE.stat().st_size / 1024
    logger.info(f"✓ DONE. {total} symbols → {OUTPUT_FILE} ({size_kb:.1f} KB)")
    logger.info(f"✓ Each symbol has 19 buckets (18 + derived_metrics)")

    if unmapped_summary:
        logger.warning("UNMAPPED FIELDS - add to FIELD_MAP:")
        for sym, fields in unmapped_summary.items():
            logger.warning(f"  {sym}: {fields}")
    else:
        logger.info("✓ All fields mapped — _unmapped is empty")


if __name__ == "__main__":
    main()
