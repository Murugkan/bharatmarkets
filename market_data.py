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
    # Contains only fields that stay in the catch-all 'info' sub-section.
    # Fields routed to sub-sections (valuation, analyst, margins, etc.) by
    # market_data_flatten.py are handled by dedicated FIELD_MAP entries below —
    # keeping them here would cause double-processing and bucket collisions.
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
        # valuation — point-in-time scalars that don't go to sub-sections
        "marketCap":               ("valuation", "market_cap"),
        "nonDilutedMarketCap":     ("valuation", "non_diluted_market_cap"),
        "ebitda":                  ("valuation", "ebitda"),
        "totalDebt":               ("valuation", "total_debt"),
        "trailingEps":             ("valuation", "trailing_eps"),
        "forwardEps":              ("valuation", "forward_eps"),
        "epsTrailingTwelveMonths": ("valuation", "eps_ttm"),
        "epsForward":              ("valuation", "eps_forward"),
        "epsCurrentYear":          ("valuation", "eps_current_year"),
        "priceEpsCurrentYear":     ("valuation", "price_eps_current_year"),
        "trailingPegRatio":        ("valuation", "trailing_peg_ratio"),
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
        # dividends scalar fields not in :dividends sub-section
        "lastDividendValue":   ("company_details", "last_dividend_value"),
        "lastDividendDate":    ("company_details", "last_dividend_date"),
        "lastSplitDate":       ("company_details", "last_split_date"),
        "lastSplitFactor":     ("company_details", "last_split_factor"),
        # other ratios not in sub-sections
        "totalCash":           ("ratios", "total_cash"),
        "netIncomeToCommon":   ("ratios", "net_income_to_common"),
        "grossProfits":        ("ratios", "gross_profits"),
        "totalRevenue":        ("ratios", "total_revenue"),
        "freeCashflow":        ("ratios", "free_cashflow"),
        "operatingCashflow":   ("ratios", "operating_cashflow"),
        # analyst extras not in :analyst sub-section
        "recommendationMean":  ("websignals", "recommendation_mean"),
        "averageAnalystRating":("websignals", "average_analyst_rating"),
        "SandP52WeekChange":   ("websignals", "sandp_52_week_change"),
        "isEarningsDateEstimate": ("websignals", "is_earnings_date_estimate"),
        # governance extra not in :risk_scores sub-section
        "governanceEpochDate": ("websignals", "governance_epoch_date"),
        # exchange metadata
        "exchangeTimezoneName":           ("company_details", "exchange_timezone_name"),
        "exchangeTimezoneShortName":      ("company_details", "exchange_timezone_short"),
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

    # ── yahoofin_raw sub-sections (split from info by market_data_flatten.py) ─
    # Each sub-section contains fields tagged by INFO_FIELD_GROUPS in flatten.
    # These must NOT overlap with yahoofin_raw:info above.

    "yahoofin_raw:valuation": {
        "trailingPE":                   ("valuation", "trailing_pe"),
        "forwardPE":                    ("valuation", "forward_pe"),
        "pegRatio":                     ("valuation", "peg_ratio"),
        "priceToBook":                  ("valuation", "price_to_book"),
        "priceToSalesTrailing12Months": ("valuation", "price_to_sales_ttm"),
        "enterpriseValue":              ("valuation", "enterprise_value"),
        "enterpriseToRevenue":          ("valuation", "ev_to_revenue"),
        "enterpriseToEbitda":           ("valuation", "ev_to_ebitda"),
    },

    "yahoofin_raw:analyst": {
        "targetHighPrice":         ("websignals", "target_high_price"),
        "targetLowPrice":          ("websignals", "target_low_price"),
        "targetMeanPrice":         ("websignals", "target_mean_price"),
        "targetMedianPrice":       ("websignals", "target_median_price"),
        "recommendationKey":       ("websignals", "recommendation_key"),
        "numberOfAnalystOpinions": ("websignals", "number_of_analyst_opinions"),
    },

    "yahoofin_raw:margins": {
        "profitMargins":    ("ratios", "profit_margins"),
        "grossMargins":     ("ratios", "gross_margins"),
        "ebitdaMargins":    ("ratios", "ebitda_margins"),
        "operatingMargins": ("ratios", "operating_margins"),
    },

    "yahoofin_raw:growth": {
        "earningsGrowth":          ("ratios", "earnings_growth"),
        "revenueGrowth":           ("ratios", "revenue_growth"),
        "earningsQuarterlyGrowth": ("ratios", "earnings_quarterly_growth"),
    },

    "yahoofin_raw:ratios": {
        "returnOnAssets":  ("ratios", "return_on_assets"),
        "returnOnEquity":  ("ratios", "return_on_equity"),
        "debtToEquity":    ("ratios", "debt_to_equity"),
        "quickRatio":      ("ratios", "quick_ratio"),
        "currentRatio":    ("ratios", "current_ratio"),
        "revenuePerShare": ("ratios", "revenue_per_share"),
        "totalCashPerShare":("ratios","total_cash_per_share"),
    },

    "yahoofin_raw:share_data": {
        "floatShares":              ("company_details", "float_shares"),
        "sharesOutstanding":        ("company_details", "shares_outstanding"),
        "heldPercentInsiders":      ("company_details", "held_pct_insiders"),
        "heldPercentInstitutions":  ("company_details", "held_pct_institutions"),
        "impliedSharesOutstanding": ("company_details", "implied_shares_outstanding"),
        "bookValue":                ("valuation", "book_value"),
    },

    "yahoofin_raw:dividends": {
        "dividendRate":              ("company_details", "dividend_rate"),
        "dividendYield":             ("company_details", "dividend_yield"),
        "exDividendDate":            ("company_details", "ex_dividend_date"),
        "payoutRatio":               ("company_details", "payout_ratio"),
        "fiveYearAvgDividendYield":  ("company_details", "five_year_avg_dividend_yield"),
        "trailingAnnualDividendRate":("company_details", "trailing_annual_dividend_rate"),
        "trailingAnnualDividendYield":("company_details","trailing_annual_dividend_yield"),
    },

    "yahoofin_raw:earnings_dates": {
        "earningsTimestamp":          ("websignals", "earnings_timestamp"),
        "earningsTimestampStart":     ("websignals", "earnings_timestamp_start"),
        "earningsTimestampEnd":       ("websignals", "earnings_timestamp_end"),
        "earningsCallTimestampStart": ("websignals", "earnings_call_ts_start"),
        "earningsCallTimestampEnd":   ("websignals", "earnings_call_ts_end"),
    },

    "yahoofin_raw:risk_scores": {
        "auditRisk":             ("websignals", "audit_risk"),
        "boardRisk":             ("websignals", "board_risk"),
        "compensationRisk":      ("websignals", "compensation_risk"),
        "shareHolderRightsRisk": ("websignals", "shareholder_rights_risk"),
        "overallRisk":           ("websignals", "overall_risk"),
    },

    # yahoofin_raw:metadata — top-level ticker/name/isin fields
    "yahoofin_raw:metadata": {
        "ticker": ("company_details", "ticker_yahoo"),
        "name":   ("company_details", "name_yahoo"),
        "isin":   ("company_details", "isin_yahoo"),
    },

    # ── yahoofin_fin:latest and yahoofin_fin:historical ──────────────────────
    # NOT processed via FIELD_MAP — handled exclusively by merge_yahoo_into_screener()
    # in main(). Marking as __skip__ prevents them falling into _unmapped.
    "yahoofin_fin:latest":           "__skip__",
    "yahoofin_fin:historical":       "__skip__",
    "yahoofin_fin:historical:annual":"__skip__",

    # ââ screener_fin:quarterly_results  (quarterly consolidated P&L) ââââââ
    "screener_fin:quarterly_results": {
        "Sales +":           ("financials", "Sales"),
        "Sales +":             ("financials", "Sales"),
        "Revenue +":         ("financials", "Sales"),
        "Revenue +":           ("financials", "Sales"),
        "Expenses +":        ("financials", "Expenses"),
        "Expenses +":          ("financials", "Expenses"),
        "Operating Profit":    ("financials", "Operating_Profit"),
        "OPM %":               ("financials", "OPM_pct"),
        "Other Income +":    ("financials", "Other_Income"),
        "Other Income +":      ("financials", "Other_Income"),
        "Interest":            ("financials", "Interest"),
        "Depreciation":        ("financials", "Depreciation"),
        "Profit before tax":   ("financials", "Profit_before_tax"),
        "Tax %":               ("financials", "Tax_pct"),
        "Net Profit +":      ("financials", "Net_Profit"),
        "Net Profit +":        ("financials", "Net_Profit"),
        "EPS in Rs":           ("financials", "EPS_Rs"),
        "Financing Profit":    ("financials", "Financing_Profit"),
        "Financing Margin %":  ("financials", "Financing_Margin_pct"),
        "Gross NPA %":         ("financials", "Gross_NPA_pct"),
        "Net NPA %":           ("financials", "Net_NPA_pct"),
    },

    # ââ screener_fin:profit_loss  (annual consolidated P&L, 12yr) ââââââââ
    "screener_fin:profit_loss": {
        "Revenue +":         ("financials", "Sales"),
        "Revenue +":           ("financials", "Sales"),
        "Sales +":           ("financials", "Sales"),
        "Sales +":             ("financials", "Sales"),
        "Expenses +":        ("financials", "Expenses"),
        "Expenses +":          ("financials", "Expenses"),
        "Operating Profit":    ("financials", "Operating_Profit"),
        "OPM %":               ("financials", "OPM_pct"),
        "Other Income +":    ("financials", "Other_Income"),
        "Other Income +":      ("financials", "Other_Income"),
        "Interest":            ("financials", "Interest"),
        "Depreciation":        ("financials", "Depreciation"),
        "Profit before tax":   ("financials", "Profit_before_tax"),
        "Tax %":               ("financials", "Tax_pct"),
        "Net Profit +":      ("financials", "Net_Profit"),
        "Net Profit +":        ("financials", "Net_Profit"),
        "EPS in Rs":           ("financials", "EPS_Rs"),
        "Dividend Payout %":   ("financials", "Dividend_Payout_pct"),
        "Financing Profit":    ("financials", "Financing_Profit"),
        "Financing Margin %":  ("financials", "Financing_Margin_pct"),
        "Gross NPA %":         ("financials", "Gross_NPA_pct"),
        "Net NPA %":           ("financials", "Net_NPA_pct"),
    },

    # ââ screener_fin:balance_sheet  (annual consolidated BS, 12yr) âââââââ
    "screener_fin:balance_sheet": {
        "Equity Capital":          ("financials", "Equity_Capital"),
        "Reserves":                ("financials", "Reserves"),
        "Borrowings +":        ("financials", "Borrowings"),
        "Borrowings +":            ("financials", "Borrowings"),
        "Borrowing":               ("financials", "Borrowing"),
        "Deposits":                ("financials", "Deposits"),
        "Other Liabilities +": ("financials", "Other_Liabilities"),
        "Other Liabilities +":     ("financials", "Other_Liabilities"),
        "Total Liabilities":       ("financials", "Total_Liabilities"),
        "Fixed Assets +":      ("financials", "Fixed_Assets"),
        "Fixed Assets +":          ("financials", "Fixed_Assets"),
        "CWIP":                    ("financials", "CWIP"),
        "Investments":             ("financials", "Investments"),
        "Other Assets +":      ("financials", "Other_Assets"),
        "Other Assets +":          ("financials", "Other_Assets"),
        "Total Assets":            ("financials", "Total_Assets"),
    },

    # ââ screener_fin:cash_flow  (annual consolidated CF, 12yr) ââââââââââ
    "screener_fin:cash_flow": {
        "Cash from Operating Activity +": ("financials", "CFO"),
        "Cash from Operating Activity +":   ("financials", "CFO"),
        "Cash from Investing Activity +": ("financials", "CFI"),
        "Cash from Investing Activity +":   ("financials", "CFI"),
        "Cash from Financing Activity +": ("financials", "CFF"),
        "Cash from Financing Activity +":   ("financials", "CFF"),
        "Net Cash Flow":                    ("financials", "Net_Cash_Flow"),
        "Free Cash Flow":                   ("financials", "Free_Cash_Flow"),
        "CFO/OP":                           ("financials", "CFO_over_OP"),
    },

    # ââ screener_fin:ratios  (annual consolidated ratios, 12yr) âââââââââ
    "screener_fin:ratios": {
        "Debtor Days":           ("ratios", "Debtor_Days"),
        "Inventory Days":        ("ratios", "Inventory_Days"),
        "Days Payable":          ("ratios", "Days_Payable"),
        "Cash Conversion Cycle": ("ratios", "Cash_Conversion_Cycle"),
        "Working Capital Days":  ("ratios", "Working_Capital_Days"),
        "ROCE %":                ("ratios", "ROCE_pct"),
        "ROE %":                 ("ratios", "ROE_pct"),
    },

    # ââ screener_fin:shareholding_pattern  (quarterly consolidated) ââââââ
    "screener_fin:shareholding_pattern": {
        "Promoters +":      ("company_details", "promoters"),
        "Promoters +":         ("company_details", "promoters"),
        "FIIs +":           ("company_details", "fiis"),
        "FIIs +":              ("company_details", "fiis"),
        "DIIs +":           ("company_details", "diis"),
        "DIIs +":              ("company_details", "diis"),
        "Government +":     ("company_details", "government"),
        "Government +":        ("company_details", "government"),
        "Public +":         ("company_details", "public"),
        "Public +":            ("company_details", "public"),
        "Others +":         ("company_details", "others"),
        "Others +":            ("company_details", "others"),
        "No. of Shareholders": ("company_details", "no_of_shareholders"),
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

    # ── screener_raw:Insights  (PAYWALLED — all values masked as xxx,xxx) ──────
    # Excluded from pipeline. Login required to see actual values on Screener.in.
    # "screener_raw:Insights": "__exclude__",  # kept for reference, skipped in flatten

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
    # Canonical keys — market_data_flatten.py normalises 5yr and 10yr source
    # variants to these same names, so output structure is always identical.
    # history_6mo_1d  — daily,   always present
    # history_1wk     — weekly,  from history_5y_1wk OR history_10y_1wk
    # history_1mo     — monthly, from history_5y_1mo OR history_10y_1mo
    "yahoofin_raw:history_6mo_1d": "__history__",
    "yahoofin_raw:history_1wk":    "__history__",
    "yahoofin_raw:history_1mo":    "__history__",
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

        # ── sections explicitly skipped (handled by merge layer or excluded) ──
        if sec_map == "__skip__":
            continue

        # ── OHLCV history sections ─────────────────────────────────────────
        if sec_map == "__history__":
            hist_key = sec_key.split(":")[-1]   # e.g. history_6mo_1d

            # New format: one metric per OHLCV column, each with periods={date: value}
            # Reconstruct the OHLCV bar list: [{Date, Open, High, Low, Close, Volume}]
            col_periods = {}  # col_name → {date: value}
            for r in (records if isinstance(records, list) else []):
                if not isinstance(r, dict):
                    continue
                metric = r.get("metric", "")
                if metric == "LTP":
                    B["price"]["ltp"] = r.get("data")
                elif metric in ("open", "high", "low", "close", "volume") and r.get("periods"):
                    col_periods[metric] = r["periods"]
                # Legacy format: single item with 'values' array
                elif r.get("values"):
                    cleaned_values = []
                    for record in r["values"]:
                        if isinstance(record, dict):
                            clean_record = {}
                            for k, v in record.items():
                                if k in ('Dividends', 'Stock Splits'):
                                    continue
                                if k == 'Date':
                                    clean_record[k] = v
                                elif k == 'Volume':
                                    try: clean_record[k] = int(float(v))
                                    except (ValueError, TypeError): clean_record[k] = v
                                else:
                                    try: clean_record[k] = round(float(v), 2)
                                    except (ValueError, TypeError): clean_record[k] = v
                            cleaned_values.append(clean_record)
                    if cleaned_values:
                        B["price"][hist_key] = cleaned_values

            # Reconstruct bar list from periods dicts
            if col_periods:
                all_dates = sorted(
                    set(d for periods in col_periods.values() for d in periods),
                    reverse=True
                )
                bars = []
                for date in all_dates:
                    bar = {"Date": date}
                    for col, cap in [("open","Open"),("high","High"),("low","Low"),("close","Close"),("volume","Volume")]:
                        v = col_periods.get(col, {}).get(date)
                        if v is not None:
                            bar[cap] = v
                    bars.append(bar)
                B["price"][hist_key] = bars
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
                    # Wrap periods with source info.
                    # yahoofin_fin:historical:annual is always consolidated annual —
                    # tag explicitly so reorganize_by_period can deduplicate against Screener.
                    _granule = r.get("granule")
                    _consol  = r.get("consolidation")
                    if not _granule and "historical:annual" in sec_key:
                        _granule = "annual"
                    if not _consol and sec_key.startswith("yahoofin_fin"):
                        _consol = "consolidated"
                    periods_data = {
                        "_periods": r.get("periods", {}),
                        "_source":  sec_key,
                        "_granule": _granule,
                        "_consolidation": _consol,
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
                    B[target_bucket][target_key] = field_val

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
    
    # Determine granularity by month pattern and date spacing
    months_sorted = sorted(months_seen)

    # Check average gap between consecutive dates
    if len(dates_list) >= 2:
        dates_sorted = sorted(dates_list)
        gaps_days = [(dates_sorted[i+1] - dates_sorted[i]).days
                     for i in range(len(dates_sorted)-1)]
        avg_gap = sum(gaps_days) / len(gaps_days)
    else:
        avg_gap = 400  # single date — assume annual

    # Annual: dates ~12 months apart (avg gap > 270 days)
    if avg_gap > 270:
        return 'annual'

    # Half-yearly: dates ~6 months apart
    if 120 < avg_gap <= 270:
        return 'half_yearly'

    # Quarterly: dates ~3 months apart
    if avg_gap <= 120:
        return 'quarterly'

    return 'annual'  # fallback


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


def clean_period_dates(date_dict: dict) -> dict:
    """
    Remove invalid period keys from a date→value dict:
      - Non-ISO keys like 'TTM', multiline labels ('Mar 2016\\n  9m')
      - Keys that are not exactly 10 chars of YYYY-MM-DD format
    Also converts any remaining string values (e.g. '20%', '90%') to float.
    Returns a new dict with only valid ISO dates, sorted desc.
    """
    cleaned = {}
    for d, v in date_dict.items():
        d_str = str(d).strip()
        if len(d_str) == 10 and d_str[4] == '-' and d_str[7] == '-':
            try:
                int(d_str[:4]); int(d_str[5:7]); int(d_str[8:])
                # Strip % strings left over from older screener_financials.json fetches
                if isinstance(v, str):
                    s = v.strip().rstrip('%')
                    try:
                        v = float(s) if s else None
                    except (ValueError, TypeError):
                        v = None
                cleaned[d_str] = v
            except ValueError:
                pass
    return dict(sorted(cleaned.items(), reverse=True))


def merge_period_dicts(existing: dict, incoming: dict) -> dict:
    """
    Merge two period dicts, keeping Screener (month-start YYYY-MM-01) as
    authoritative over Yahoo (period-end YYYY-MM-28/29/30/31) for the same
    fiscal year-month.
    Rule: if a YYYY-MM is already present in existing, skip the incoming
    entry for that same YYYY-MM. Screener is written first so it wins.
    """
    if not existing:
        return incoming
    merged = dict(existing)
    present_ym = {d[:7] for d in merged}
    for d, v in incoming.items():
        ym = d[:7]
        if ym not in present_ym:
            merged[d] = v
            present_ym.add(ym)
        # else: existing entry for this fiscal year-month wins — skip incoming
    return dict(sorted(merged.items(), reverse=True))


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
                        date_dict = clean_period_dates(
                            {k: periods_dict[k] for k in sorted(periods_dict.keys(), reverse=True)}
                        )
                        if not date_dict:
                            continue

                        # Structure: consolidation > granule > dates
                        if consol:
                            if consol not in metrics_by_name[metric_key]:
                                metrics_by_name[metric_key][consol] = {}
                            existing = metrics_by_name[metric_key][consol].get(granule, {})
                            metrics_by_name[metric_key][consol][granule] = merge_period_dicts(existing, date_dict)
                        else:
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

                    date_dict = clean_period_dates(
                        {k: periods_dict[k] for k in sorted(periods_dict.keys(), reverse=True)}
                    )
                    if not date_dict:
                        continue

                    # Structure: consolidation > granule > dates
                    if consol:
                        if consol not in metrics_by_name[metric_key]:
                            metrics_by_name[metric_key][consol] = {}
                        existing = metrics_by_name[metric_key][consol].get(granule, {})
                        metrics_by_name[metric_key][consol][granule] = merge_period_dicts(existing, date_dict)
                    else:
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
    Restructure ratios into two clear sub-groups:
      screener: time-series {date: val} from Screener (12yr history)
      ttm:      Yahoo TTM/latest scalars (single value, trailing 12 months)
    The UI can then iterate screener for charts and read ttm for KPI cards
    without checking field types.
    """
    if "ratios" not in bucketed:
        return bucketed

    ratios = bucketed["ratios"]

    SCREENER_KEYS = {
        'roce_pct', 'roe_pct', 'debtor_days', 'inventory_days',
        'days_payable', 'cash_conversion_cycle', 'working_capital_days',
        'ROCE_pct', 'ROE_pct', 'Debtor_Days', 'Inventory_Days',
        'Days_Payable', 'Cash_Conversion_Cycle', 'Working_Capital_Days',
        # Raw Screener display names from merged format
        'ROCE %', 'ROE %', 'Debtor Days', 'Inventory Days',
        'Days Payable', 'Cash Conversion Cycle', 'Working Capital Days',
    }

    RATIO_NAME_MAP = {
        'ROCE %': 'roce_pct', 'ROE %': 'roe_pct',
        'Debtor Days': 'debtor_days', 'Inventory Days': 'inventory_days',
        'Days Payable': 'days_payable', 'Cash Conversion Cycle': 'cash_conversion_cycle',
        'Working Capital Days': 'working_capital_days',
        'ROCE_pct': 'roce_pct', 'ROE_pct': 'roe_pct',
    }

    YAHOO_TTM_KEYS = {
        'net_margin_pct', 'gross_margin_pct', 'ebitda_margin_pct', 'operating_margin_pct',
        'roa_pct', 'roe_pct', 'earnings_growth_yoy', 'earnings_growth_qoq',
        'debt_to_equity_ratio', 'current_ratio', 'quick_ratio',
        'return_on_equity', 'return_on_assets',
        # revenue sub-fields
        'total_revenue', 'revenue_per_share', 'revenue_growth',
    }

    screener = {}
    ttm = {}

    for key in list(ratios.keys()):
        val = ratios[key]

        # ── Screener time-series: unwrap _periods list OR clean merged format ──
        if key in SCREENER_KEYS:
            canon = RATIO_NAME_MAP.get(key, key)
            if isinstance(val, list):
                # Old _periods list format
                merged = {}
                priority = {'consolidated': 2, 'standalone': 1}
                for item in val:
                    if isinstance(item, dict) and '_periods' in item:
                        weight = priority.get(item.get('_consolidation', ''), 0)
                        for d, v in item['_periods'].items():
                            if v is None:
                                continue
                            if isinstance(v, str):
                                try:
                                    v = float(v.strip().rstrip('%'))
                                except (ValueError, TypeError):
                                    continue
                            if d not in merged or weight > merged[d][1]:
                                merged[d] = (v, weight)
                flat = {d: v for d, (v, _) in sorted(merged.items(), reverse=True)} if merged else {}
            elif isinstance(val, dict):
                first = next(iter(val.values()), None)
                if isinstance(first, dict):
                    second = next(iter(first.values()), None)
                    if isinstance(second, dict) and any(
                        len(k) == 10 and '-' in k for k in list(second.keys())[:2]
                    ):
                        # New merged 3-level format: {consol:{gran:{date:val}}}
                        # Extract consolidated annual (prefer consolidated over standalone)
                        priority = {'consolidated': 2, 'standalone': 1}
                        merged = {}
                        for consol, gd in val.items():
                            if not isinstance(gd, dict):
                                continue
                            weight = priority.get(consol, 0)
                            ann = gd.get('annual', {})
                            for d, v in ann.items():
                                if isinstance(v, str):
                                    try: v = float(v.strip().rstrip('%'))
                                    except: v = None
                                if d not in merged or weight > merged[d][1]:
                                    merged[d] = (v, weight)
                        flat = {d: v for d, (v, _) in sorted(merged.items(), reverse=True)} if merged else {}
                    else:
                        flat = val  # already flat {date:val}
                else:
                    flat = {}  # scalar — goes to ttm
                    ttm[canon] = val
                    continue
            else:
                flat = {}
            screener[canon] = flat

        # ── Yahoo TTM scalars ─────────────────────────────────────────────────
        elif key in YAHOO_TTM_KEYS or isinstance(val, (int, float, type(None))):
            # Rename aliases
            canon = {'return_on_equity': 'roe_pct', 'return_on_assets': 'roa_pct'}.get(key, key)
            if canon not in screener:  # don't overwrite Screener time-series
                ttm[canon] = val

        # ── revenue sub-object → flatten into ttm ────────────────────────────
        elif key == 'revenue' and isinstance(val, dict):
            ttm['revenue_growth_yoy'] = val.get('revenue_growth')
            ttm['revenue_per_share']  = val.get('revenue_per_share')

        # Anything else stays flat (shouldn't happen)
        else:
            ttm[key] = val

    # ROE_pct rename: if Screener has it under old name, move to screener.roe_pct
    if 'ROE_pct' in screener:
        screener['roe_pct'] = screener.pop('ROE_pct')
    if 'ROCE_pct' in screener:
        screener['roce_pct'] = screener.pop('ROCE_pct')

    # If Yahoo roe_pct/roa_pct exists in ttm but Screener has it — drop from ttm
    for k in ('roe_pct', 'roa_pct'):
        if k in screener and k in ttm:
            ttm.pop(k)

    result = {}
    if screener:
        result['screener'] = screener
    if ttm:
        result['ttm'] = {k: v for k, v in ttm.items() if v is not None}

    bucketed["ratios"] = result
    return bucketed


def reorganize_valuation_eps_pe(bucketed: dict) -> dict:
    """
    Reorganise valuation into functional sub-groups:
      pe:      P/E and price multiples (scalars)
      eps:     EPS estimates (scalars)
      history: EPS and share count time-series {date: val}
      market:  market_cap, enterprise_value, book_value (scalars)
    No duplicates — each field appears exactly once.
    """
    if "valuation" not in bucketed:
        return bucketed

    v = bucketed["valuation"]

    # ── pe: price multiples ────────────────────────────────────────────────────
    pe = {}
    for old, new in [
        ('trailing_pe','pe_ttm'), ('pe_ttm','pe_ttm'),
        ('forward_pe','pe_forward'), ('pe_forward','pe_forward'),
        ('peg_ratio','peg'), ('peg','peg'),
        ('trailing_peg_ratio','peg_ttm'), ('peg_ttm','peg_ttm'),
        ('price_to_book','price_to_book'),
        ('price_to_sales_ttm','price_to_sales'), ('price_to_sales','price_to_sales'),
        ('ev_to_revenue','ev_to_revenue'),
        ('ev_to_ebitda','ev_to_ebitda'),
    ]:
        if old in v and new not in pe:
            pe[new] = v.pop(old)
        elif old in v:
            v.pop(old)

    # ── eps: per-share estimates ───────────────────────────────────────────────
    eps = {}
    for old, new in [
        ('trailing_eps','eps_ttm'), ('eps_ttm','eps_ttm'),
        ('forward_eps','eps_forward'), ('eps_forward','eps_forward'),
        ('eps_current_year','eps_current_year'),
        ('price_eps_current_year','pe_current_year'), ('pe_current_year','pe_current_year'),
    ]:
        if old in v and new not in eps:
            eps[new] = v.pop(old)
        elif old in v:
            v.pop(old)

    # NOTE: *_history time-series fields (yf_basic_eps, yf_diluted_eps etc.) arrive
    # via merge_yahoo_into_screener which runs AFTER this function.
    # They are grouped into valuation.history by standardize_field_names instead.

    # ── market: cap and debt metrics ───────────────────────────────────────────
    market = {}
    for key in ['market_cap', 'basic_market_cap', 'non_diluted_market_cap',
                'enterprise_value', 'ebitda', 'total_debt', 'book_value']:
        if key in v:
            canon = 'basic_market_cap' if key == 'non_diluted_market_cap' else key
            market[canon] = v.pop(key)

    if pe:      v['pe']      = pe
    if eps:     v['eps']     = eps
    if market:  v['market']  = market

    bucketed["valuation"] = v
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
    Also normalises Borrowing (bank/NBFC variant) → Borrowings so UI
    only ever needs to read one field name.
    """
    if "financials" not in bucketed:
        return bucketed

    financials = bucketed["financials"]

    # ── Normalize Borrowing → Borrowings ──────────────────────────────────
    # Banks/NBFCs use 'Borrowing' (singular), manufacturing uses 'Borrowings'.
    # Merge into 'Borrowings' so UI reads one consistent field.
    if "Borrowing" in financials and "Borrowings" not in financials:
        financials["Borrowings"] = financials.pop("Borrowing")
    elif "Borrowing" in financials and "Borrowings" in financials:
        # Both present (shouldn't happen but guard anyway) — Borrowings wins
        financials.pop("Borrowing")

    debt_keys = {
        'total_debt', 'net_debt', 'short_term_debt', 'long_term_debt', 'capital_lease_obligations'
    }

    # Extract debt metrics (using pop to remove from financials)
    debt_obj = {}
    for key in debt_keys:
        if key in financials:
            debt_obj[key] = financials.pop(key)

    # Add debt object back to financials if it has data
    if debt_obj:
        financials['debt'] = debt_obj

    bucketed["financials"] = financials
    return bucketed


def reorganize_identity_shareholding(bucketed: dict) -> dict:
    """
    Group shareholding fields under company_details.shareholding.
    MOVE (pop) fields — no top-level duplicates.
    Apply final renames inside sub-objects (runs before standardize_field_names).
    Drop company_officers — too granular for portfolio analysis.
    """
    if "company_details" not in bucketed:
        return bucketed

    cd = bucketed["company_details"]

    # ── Drop company_officers ─────────────────────────────────────────────────
    cd.pop('company_officers', None)

    # ── Shareholding pattern (time-series, MOVE from top level) ───────────────
    pattern_obj = {}
    for key in ['promoters', 'fiis', 'diis', 'public', 'government', 'others', 'no_of_shareholders']:
        if key not in cd:
            continue
        val = cd.pop(key)

        priority = {'consolidated': 2, 'standalone': 1}
        merged = {}  # date → (value, weight)

        if isinstance(val, dict) and val:
            first = next(iter(val.values()), None)
            if isinstance(first, dict):
                second = next(iter(first.values()), None)
                if isinstance(second, dict) and any(
                    len(k) == 10 and '-' in k for k in list(second.keys())[:2]
                ):
                    # New merged 3-level: {consol: {gran: {date:val}}}
                    for consol, gd in val.items():
                        weight = priority.get(consol, 0)
                        if not isinstance(gd, dict):
                            continue
                        for gran, p in gd.items():
                            if not isinstance(p, dict):
                                continue
                            for d, v in p.items():
                                if isinstance(v, str):
                                    try: v = float(v.strip().rstrip('%'))
                                    except: continue
                                if d not in merged or weight > merged[d][1]:
                                    merged[d] = (v, weight)
                elif any(len(k) == 10 and '-' in k for k in list(val.keys())[:2]):
                    # Already flat {date:val}
                    for d, v in val.items():
                        if isinstance(v, str):
                            try: v = float(v.strip().rstrip('%'))
                            except: continue
                        merged[d] = (v, 1)
            elif any(len(k) == 10 and '-' in k for k in list(val.keys())[:2]):
                # Flat {date: scalar} — values are floats/ints not dicts (e.g. 0.0 promoters)
                for d, v in val.items():
                    if isinstance(v, str):
                        try: v = float(v.strip().rstrip('%'))
                        except: continue
                    if v is None:
                        continue
                    merged[d] = (v, 1)
        elif isinstance(val, list):
            # Old _periods list format
            for item in val:
                if isinstance(item, dict) and '_periods' in item:
                    weight = priority.get(item.get('_consolidation', ''), 0)
                    for d, v in item['_periods'].items():
                        if v is None:
                            continue
                        if isinstance(v, str):
                            try: v = float(v.strip().rstrip('%'))
                            except: continue
                        if d not in merged or weight > merged[d][1]:
                            merged[d] = (v, weight)

        flat = {d: v for d, (v, _) in sorted(merged.items(), reverse=True)} if merged else {}
        if flat:
            pattern_obj[key] = flat
    
    # ── Shares (MOVE from top level, apply renames) ────────────────────────────
    shares_obj = {}
    for old, new in [
        ('float_shares',               'floating_shares'),
        ('shares_outstanding',         'shares_outstanding'),
        ('implied_shares_outstanding', 'implied_shares'),
        ('implied_shares',             'implied_shares'),       # post-rename name
        ('floating_shares',            'floating_shares'),      # post-rename name
    ]:
        if old in cd:
            shares_obj[new] = cd.pop(old)
    # Deduplicate (implied_shares may appear twice from both old+new names)
    if shares_obj:
        shares_obj = {k: v for k, v in shares_obj.items() if v is not None}

    # ── Ownership (MOVE from top level, apply renames) ─────────────────────────
    ownership_obj = {}
    for old, new in [
        ('held_pct_insiders',          'insider_holding_pct'),
        ('held_pct_institutions',      'institutional_holding_pct'),
        ('insider_holding_pct',        'insider_holding_pct'),        # post-rename
        ('institutional_holding_pct',  'institutional_holding_pct'),  # post-rename
    ]:
        if old in cd:
            ownership_obj[new] = cd.pop(old)
    if ownership_obj:
        ownership_obj = {k: v for k, v in ownership_obj.items() if v is not None}

    # ── Dividends (MOVE) ───────────────────────────────────────────────────────
    dividend_obj = {}
    for key in ['dividend_rate', 'dividend_yield', 'ex_dividend_date', 'payout_ratio',
                'trailing_annual_dividend_rate', 'trailing_annual_dividend_yield',
                'last_dividend_value', 'last_dividend_date', 'five_year_avg_dividend_yield']:
        if key in cd:
            dividend_obj[key] = cd.pop(key)

    # ── Stock splits (MOVE) ───────────────────────────────────────────────────
    split_obj = {}
    for key in ['last_split_date', 'last_split_factor']:
        if key in cd:
            split_obj[key] = cd.pop(key)

    # ── Assemble shareholding sub-object ─────────────────────────────────────
    shareholding_obj = {}
    if pattern_obj:
        shareholding_obj['pattern'] = pattern_obj
    if shares_obj:
        shareholding_obj['shares'] = shares_obj
    if ownership_obj:
        shareholding_obj['ownership'] = ownership_obj
    if dividend_obj:
        shareholding_obj['dividends'] = dividend_obj
    if split_obj:
        shareholding_obj['stock_splits'] = split_obj

    if shareholding_obj:
        cd['shareholding'] = shareholding_obj

    bucketed["company_details"] = cd
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


# ══════════════════════════════════════════════════════════════════════════════
# YAHOO → SCREENER MERGE LAYER
# ══════════════════════════════════════════════════════════════════════════════
#
# Architecture:
#   screener_fin (consolidated, 12yr)  = PRIMARY timeline
#   yahoofin_fin:historical (4-5yr)    = GAP-FILL only — same consolidation,
#                                        /1e7 already applied in flatten
#   yahoofin_fin:latest                = EXTEND if newer than Screener's last period
#   Yahoo-exclusive fields              = ADD directly (EPS, capex, R&D etc.)
#
# Screener metric names (CamelCase e.g. Net_Profit) ↔ Yahoo field names (snake_case)
# Mapping is one-directional: Yahoo fills Screener gaps, never overwrites.

# Screener canonical key → Yahoo field name (for overlapping metrics)
# Unified map: output field name → Yahoo historical field name
# Used for gap-fill: for every financials field, if Yahoo has matching data
# for periods Screener doesn't cover, fill silently.
# Fields not in this map have no Yahoo equivalent and are Screener-only.
# Yahoo-exclusive financials: fields Yahoo has that Screener never publishes.
# Added directly to consolidated.annual — no gap-fill into Screener fields.
YAHOO_EXCLUSIVE_FINANCIALS = {
    'gross_profit':        'gross_profit',
    'cost_of_revenue':     'cost_of_revenue',
    'ebitda':              'ebitda',
    'capex':               'capex',
    'accounts_receivable': 'accounts_receivable',
    'cash_and_equivalents':'cash_and_equivalents',
    'net_tangible_assets': 'net_tangible_assets',
    'working_capital':     'working_capital',
    'invested_capital':    'invested_capital',
    'lease_obligations':   'capital_lease_obligations',
    'normalized_profit':   'normalized_income',
    'exceptional_items':   'unusual_items',
    'operating_income':    'operating_income',
    'rd_expense':          'rd_expense',
    'tax_rate':            'tax_rate',
    'net_debt':            'net_debt',
    'long_term_debt':      'long_term_debt',
    'short_term_debt':     'short_term_debt',
    'minority_interest':   'minority_interest',
    'total_capitalization':'total_capitalization',
}

# Valuation history: EPS and share counts (per-share, no Screener equivalent)
YAHOO_VALUATION_FIELDS = {
    'diluted_eps':        'diluted_eps',
    'basic_eps':          'basic_eps',
    'diluted_shares':     'diluted_shares',
    'basic_shares':       'basic_shares',
    'shares_outstanding': 'shares_outstanding',
}

# Legacy stubs
OUTPUT_TO_YAHOO_FIELD  = {}
SCREENER_TO_YAHOO_OVERLAP = {}
YAHOO_EXCLUSIVE_VALUATION = {}


def _get_periods_dict(bucket_field):
    """
    Extract {iso_date: value} from a bucketed field.
    Handles post-reorganize_by_period structure:
      {consolidated: {annual: {date: val}, quarterly: {...}}, standalone: {...}}
    Returns the consolidated.annual dict (primary timeline for gap-fill).
    """
    if not isinstance(bucket_field, dict):
        return {}

    # Post-reorganize: {consolidated: {annual: {...}}, standalone: {...}}
    if 'consolidated' in bucket_field:
        consol = bucket_field['consolidated']
        if isinstance(consol, dict) and 'annual' in consol:
            return consol['annual']
        if isinstance(consol, dict):
            # return first granularity available
            for gran in ('annual', 'quarterly', 'half_yearly'):
                if gran in consol:
                    return consol[gran]

    # Granularity-nested without consolidation wrapper: {annual: {...}}
    granularity_keys = {'daily', 'monthly', 'quarterly', 'half_yearly', 'annual'}
    if set(bucket_field.keys()).issubset(granularity_keys | {'_meta'}):
        for gran in ('annual', 'half_yearly', 'quarterly', 'monthly', 'daily'):
            if gran in bucket_field and isinstance(bucket_field[gran], dict):
                return bucket_field[gran]

    # Flat time-series: {'2024-03-31': v, ...}
    keys = list(bucket_field.keys())
    if keys and len(str(keys[0])) == 10 and '-' in str(keys[0]):
        return bucket_field

    return {}


def _set_periods_into_field(bucket_field, new_periods: dict):
    """
    Write gap-fill periods back into the correct sub-dict of a bucketed field.
    Mirrors _get_periods_dict — writes into consolidated.annual if present.
    Uses merge_period_dicts to ensure Screener dates (month-start YYYY-MM-01)
    take precedence over Yahoo dates (period-end YYYY-MM-31) for the same fiscal year.
    Returns the (possibly modified) bucket_field.
    """
    if not isinstance(bucket_field, dict):
        return bucket_field

    if 'consolidated' in bucket_field:
        consol = bucket_field['consolidated']
        if isinstance(consol, dict) and 'annual' in consol:
            consol['annual'] = merge_period_dicts(consol['annual'], new_periods)
            return bucket_field
        if isinstance(consol, dict):
            for gran in ('annual', 'quarterly', 'half_yearly'):
                if gran in consol:
                    consol[gran] = merge_period_dicts(consol[gran], new_periods)
                    return bucket_field
        bucket_field['consolidated'] = {'annual': new_periods}
        return bucket_field

    granularity_keys = {'daily', 'monthly', 'quarterly', 'half_yearly', 'annual'}
    if set(bucket_field.keys()).issubset(granularity_keys | {'_meta'}):
        for gran in ('annual', 'half_yearly', 'quarterly'):
            if gran in bucket_field:
                bucket_field[gran] = merge_period_dicts(bucket_field[gran], new_periods)
                return bucket_field

    # Flat — merge directly
    bucket_field = merge_period_dicts(bucket_field, new_periods)
    return bucket_field


def _latest_period(periods_dict):
    """Return the most recent ISO date key from a periods dict."""
    if not periods_dict:
        return None
    return max(periods_dict.keys())


def merge_yahoo_into_screener(bucketed: dict, yf_historical: dict, yf_latest: dict) -> dict:
    """
    Add Yahoo-exclusive fields to financials and valuation.

    Policy: clean separation — Screener fields are never touched.
    Yahoo adds only fields that Screener doesn't publish.
    No gap-fill, no merging of the same metric from two sources.
    """
    fin = bucketed.get('financials', {})
    val = bucketed.get('valuation', {})

    # ── Yahoo-exclusive financials ─────────────────────────────────────────────
    for output_key, yahoo_field in YAHOO_EXCLUSIVE_FINANCIALS.items():
        if output_key in fin:
            continue  # Screener already has this field — don't touch
        yf_periods = {d: v for d, v in yf_historical.get(yahoo_field, {}).items()
                      if v not in (None, '')}
        if yf_periods:
            fin[output_key] = {
                'consolidated': {
                    'annual': dict(sorted(yf_periods.items(), reverse=True))
                }
            }

    # ── Valuation history: EPS and share counts ───────────────────────────────
    for output_key, yahoo_field in YAHOO_VALUATION_FIELDS.items():
        yf_periods = {d: v for d, v in yf_historical.get(yahoo_field, {}).items()
                      if v not in (None, '')}
        if yf_periods:
            val[output_key] = dict(sorted(yf_periods.items(), reverse=True))

    # ── Drop any yf_* keys that slipped through ───────────────────────────────
    for k in [k for k in list(fin.keys()) if k.startswith('yf_')]:
        fin.pop(k)

    bucketed['financials'] = fin
    bucketed['valuation']  = val
    return bucketed


def _extract_yf_fin_sections(sections: dict) -> tuple:
    """
    Pull yahoofin_fin:historical and yahoofin_fin:latest out of the raw sections dict
    before bucketing, so merge_yahoo_into_screener() has direct access.

    Flatten output structure:
      'yahoofin_fin:historical' → list of metric objects:
          [{'metric': 'net_profit', 'periods': {'2024-03-31': 17390.0, ...}}, ...]
      'yahoofin_fin:latest'     → flat dict:
          {'net_profit': 17390.0, 'revenue': ..., ...}

    Returns:
        yf_historical : {field_name: {iso_date: value_in_crores}}
        yf_latest     : {field_name: value_in_crores}
    """
    yf_historical = {}
    yf_latest = {}

    # --- historical ---
    # flatten stores as 'yahoofin_fin:historical:annual' (granule suffix appended)
    hist_section = sections.get('yahoofin_fin:historical:annual') or sections.get('yahoofin_fin:historical', [])
    if isinstance(hist_section, list):
        for item in hist_section:
            if not isinstance(item, dict):
                continue
            field = item.get('metric')
            periods = item.get('periods', {})
            if field and isinstance(periods, dict):
                yf_historical[field] = {
                    d: v for d, v in periods.items() if v not in (None, '')
                }
    elif isinstance(hist_section, dict):
        for field, val in hist_section.items():
            if isinstance(val, dict):
                yf_historical[field] = {d: v for d, v in val.items() if v not in (None, '')}

    # --- latest ---
    # Flatten stores latest as a flat dict {field_name: scalar_value}
    lat_section = sections.get('yahoofin_fin:latest', {})
    if isinstance(lat_section, dict):
        yf_latest = {k: v for k, v in lat_section.items() if v not in (None, '')}

    return yf_historical, yf_latest


def standardize_field_names(bucketed: dict) -> dict:
    """
    Rename all fields to consistent, business-friendly names.
    Eliminates Yahoo internal naming (regular_market_*, fifty_two_week_*,
    held_pct_*, etc.), camelCase in ltp, and opaque abbreviations.
    Runs as the final post-processing step so all reorganize passes are stable.
    """

    def rename_keys(obj: dict, mapping: dict) -> dict:
        """Rename top-level keys of a dict using mapping. Preserves unmatched keys."""
        return {mapping.get(k, k): v for k, v in obj.items()}

    # ── company_details ──────────────────────────────────────────────────────
    cd = bucketed.get('company_details', {})
    if cd:
        # Step 1: rename Screener sector/industry to screener_ prefix FIRST
        cd = rename_keys(cd, {
            'sector':   'screener_sector',
            'industry': 'screener_industry',
        })
        # Step 2: rename Yahoo fields and everything else
        cd = rename_keys(cd, {
            'long_name':                 'company_name',
            'short_name':                'display_name',
            'long_business_summary':     'business_description',
            'full_time_employees':       'employee_count',
            'symbol_yahoo':              'yahoo_symbol',
            'sector_yahoo':              'sector',
            'industry_yahoo':            'industry',
            'sector_disp':               'sector_label',
            'industry_disp':             'industry_label',
            'held_pct_insiders':         'insider_holding_pct',
            'held_pct_institutions':     'institutional_holding_pct',
            'float_shares':              'floating_shares',
            'implied_shares_outstanding':'implied_shares',
            'first_trade_date_ms':       'listing_date_ms',
            'regular_market_time':       'last_trade_time',
            'compensation_as_of_epoch':  'officer_compensation_date',
            'name_change_date':          'name_changed_on',
            'ir_website':                'investor_relations_url',
            'quote_type':                'instrument_type',
            'type_disp':                 'instrument_type_label',
        })
        # shareholding sub-objects
        sh = cd.get('shareholding', {})
        if isinstance(sh.get('ownership'), dict):
            sh['ownership'] = rename_keys(sh['ownership'], {
                'held_pct_insiders':    'insider_holding_pct',
                'held_pct_institutions':'institutional_holding_pct',
            })
        if isinstance(sh.get('shares'), dict):
            sh['shares'] = rename_keys(sh['shares'], {
                'float_shares':               'floating_shares',
                'implied_shares_outstanding': 'implied_shares',
            })
        bucketed['company_details'] = cd

    # ── financials ───────────────────────────────────────────────────────────
    fin = bucketed.get('financials', {})
    if fin:
        fin = rename_keys(fin, {
            # Screener P&L — PascalCase → snake_case
            'Sales':               'revenue',
            'Expenses':            'expenses',
            'Operating_Profit':    'ebit',
            'Other_Income':        'other_income',
            'Interest':            'interest',
            'Depreciation':        'depreciation',
            'Net_Profit':          'net_profit',
            'Free_Cash_Flow':      'fcf',
            'Borrowings':          'borrowings',
            'Deposits':            'deposits',
            'Reserves':            'reserves',
            'Investments':         'investments',
            'Other_Assets':        'other_assets',
            'Other_Liabilities':   'other_liabilities',
            'Total_Assets':        'total_assets',
            'Total_Liabilities':   'total_liabilities',
            'CFO':                 'operating_cash_flow',
            'CFI':                 'investing_cash_flow',
            'CFF':                 'financing_cash_flow',
            'CFO_over_OP':         'cash_conversion_ratio',
            'CWIP':                'capital_wip',
            'OPM_pct':             'operating_margin_pct',
            'EPS_Rs':              'eps',
            'Equity_Capital':      'share_capital',
            'Profit_before_tax':   'profit_before_tax',
            'Tax_pct':             'tax_rate_pct',
            'Dividend_Payout_pct': 'dividend_payout_pct',
            'Fixed_Assets':        'net_fixed_assets',
            'Net_Cash_Flow':       'net_cash_flow',
            'Financing_Profit':    'net_interest_income',
            'Financing_Margin_pct':'net_interest_margin_pct',
            'Gross_NPA_pct':       'gross_npa_pct',
            'Net_NPA_pct':         'net_npa_pct',
        })
        # Drop any yf_latest_* and yf_ prefixed keys — all Yahoo data is now clean-named
        for k in [k for k in list(fin.keys()) if k.startswith('yf_')]:
            fin.pop(k)
        bucketed['financials'] = fin

    # ── ratios ───────────────────────────────────────────────────────────────
    # ratios is now {screener: {field: {date:val}}, ttm: {field: scalar}}
    rat = bucketed.get('ratios', {})
    if rat:
        sc = rat.get('screener', {})
        if sc:
            sc = rename_keys(sc, {
                'ROCE_pct': 'roce_pct', 'ROE_pct': 'roe_pct',
                'Debtor_Days': 'debtor_days', 'Inventory_Days': 'inventory_days',
                'Days_Payable': 'days_payable', 'Cash_Conversion_Cycle': 'cash_conversion_cycle',
                'Working_Capital_Days': 'working_capital_days',
            })
            rat['screener'] = sc
        ttm = rat.get('ttm', {})
        if ttm:
            ttm = rename_keys(ttm, {
                'ebitda_margins':            'ebitda_margin_pct',
                'gross_margins':             'gross_margin_pct',
                'operating_margins':         'operating_margin_pct',
                'profit_margins':            'net_margin_pct',
                'return_on_assets':          'roa_pct',
                'return_on_equity':          'roe_pct',
                'earnings_growth':           'earnings_growth_yoy',
                'earnings_quarterly_growth': 'earnings_growth_qoq',
                'debt_to_equity':            'debt_to_equity_ratio',
                # Drop Yahoo absolute scalars — unit-ambiguous
                'free_cashflow':             '__drop__',
                'operating_cashflow':        '__drop__',
                'gross_profits':             '__drop__',
                'net_income_to_common':      '__drop__',
                'total_cash':                '__drop__',
                'total_cash_per_share':      '__drop__',
                'total_revenue':             '__drop__',
                'revenue_per_share':         '__drop__',
            })
            rat['ttm'] = {k: v for k, v in ttm.items() if k != '__drop__' and v is not None}
        bucketed['ratios'] = rat

    # ── valuation ────────────────────────────────────────────────────────────
    # reorganize_valuation_eps_pe already grouped pe/eps/market.
    # Here we group history fields (arrive late via merge_yahoo_into_screener)
    # and clean up any stray top-level fields.
    val = bucketed.get('valuation', {})
    if val:
        # Rename stray pre-rename names
        val = rename_keys(val, {
            'non_diluted_market_cap': 'basic_market_cap',
        })
        # Move history time-series into valuation.history
        history = val.get('history', {})
        for old, new in [
            ('basic_eps',              'basic_eps'),
            ('diluted_eps',            'diluted_eps'),
            ('basic_shares',           'basic_shares'),
            ('diluted_shares',         'diluted_shares'),
            ('shares_outstanding',     'shares_outstanding'),
            # legacy yf_ names — remove if still present
            ('yf_basic_eps',           'basic_eps'),
            ('yf_diluted_eps',         'diluted_eps'),
            ('yf_basic_shares',        'basic_shares'),
            ('yf_diluted_shares',      'diluted_shares'),
            ('yf_shares_outstanding',  'shares_outstanding'),
            ('basic_eps_history',      'basic_eps'),
            ('diluted_eps_history',    'diluted_eps'),
            ('basic_shares_history',   'basic_shares'),
            ('diluted_shares_history', 'diluted_shares'),
            ('shares_outstanding_history','shares_outstanding'),
        ]:
            if old in val and new not in history:
                history[new] = val.pop(old)
            elif old in val:
                val.pop(old)
        if history:
            val['history'] = history
        # Move any stray market fields into valuation.market
        market = val.get('market', {})
        for key in ['market_cap', 'basic_market_cap', 'enterprise_value',
                    'ebitda', 'total_debt', 'book_value']:
            if key in val:
                market[key] = val.pop(key)
        if market:
            val['market'] = market
        bucketed['valuation'] = val

    # ── price ────────────────────────────────────────────────────────────────
    pr = bucketed.get('price', {})
    if pr:
        # ltp sub-fields: camelCase → snake_case
        if isinstance(pr.get('ltp'), dict):
            pr['ltp'] = rename_keys(pr['ltp'], {
                'ltp':       'price',
                'changePct': 'change_pct',
                'prev':      'prev_close',
                'vol':       'day_volume',
                'w52h':      'week52_high',
                'w52l':      'week52_low',
            })
        # 52_week sub-fields
        if isinstance(pr.get('52_week'), dict):
            pr['52_week'] = rename_keys(pr['52_week'], {
                'fifty_two_week_high':      'high',
                'fifty_two_week_low':       'low',
                'fifty_two_week_change':    'change',
                'fifty_two_week_change_pct':'change_pct',
            })
        # volume sub-fields
        if isinstance(pr.get('volume'), dict):
            pr['volume'] = rename_keys(pr['volume'], {
                'volume':                    'day_volume',
                'regular_market_volume':     'market_volume',
                'average_volume':            'avg_volume',
                'average_daily_volume_10d':  'avg_volume_10d',
                'average_daily_volume_3mo':  'avg_volume_3mo',
                'average_volume_10d':        'avg_volume_10d',
            })
        # top-level price fields
        pr = rename_keys(pr, {
            'current_price':                'close_price',
            'previous_close':               'prev_close',
            'regular_market_price':         'market_price',
            'regular_market_change':        'price_change',
            'regular_market_change_pct':    'price_change_pct',
            'regular_market_day_high':      'day_high',
            'regular_market_day_low':       'day_low',
            'regular_market_day_range':     'day_range',
            'regular_market_open':          'day_open',
            'regular_market_previous_close':'regular_prev_close',
            'fifty_day_avg':                'ma_50d',
            'fifty_day_avg_change':         'ma_50d_diff',
            'fifty_day_avg_change_pct':     'ma_50d_diff_pct',
            'two_hundred_day_avg':          'ma_200d',
            'two_hundred_day_avg_change':   'ma_200d_diff',
            'two_hundred_day_avg_change_pct':'ma_200d_diff_pct',
            'fifty_two_week_range':         'week52_range',
            'fifty_two_week_high_change':   'week52_high_diff',
            'fifty_two_week_high_change_pct':'week52_high_diff_pct',
            'fifty_two_week_low_change':    'week52_low_diff',
            'fifty_two_week_low_change_pct':'week52_low_diff_pct',
            'history_6mo_1d':               'ohlcv_daily',
            'history_1wk':                  'ohlcv_weekly',
            'history_1mo':                  'ohlcv_monthly',
        })
        bucketed['price'] = pr

    # ── websignals ───────────────────────────────────────────────────────────
    ws = bucketed.get('websignals', {})
    if ws:
        ws = rename_keys(ws, {
            'recommendation_key':       'analyst_rating',
            'recommendation_mean':      'analyst_rating_score',
            'average_analyst_rating':   'analyst_rating_label',
            'number_of_analyst_opinions':'analyst_count',
            'target_high_price':        'target_high',
            'target_low_price':         'target_low',
            'target_mean_price':        'target_mean',
            'target_median_price':      'target_median',
            'audit_risk':               'governance_audit_risk',
            'board_risk':               'governance_board_risk',
            'compensation_risk':        'governance_comp_risk',
            'shareholder_rights_risk':  'governance_rights_risk',
            'overall_risk':             'governance_overall_risk',
            'governance_epoch_date':    'governance_data_date',
            'earnings_timestamp':       'next_earnings_date',
            'earnings_timestamp_start': 'earnings_date_start',
            'earnings_timestamp_end':   'earnings_date_end',
            'earnings_call_ts_start':   'earnings_call_start',
            'earnings_call_ts_end':     'earnings_call_end',
            'is_earnings_date_estimate':'earnings_date_estimated',
            'sandp_52_week_change':     'index_52w_change',
        })
        bucketed['websignals'] = ws

    # ── Fix 3: Drop duplicate price fields ───────────────────────────────────
    pr = bucketed.get('price', {})
    if pr:
        # market_price duplicates close_price; regular_prev_close duplicates prev_close
        for drop in ('market_price', 'regular_prev_close'):
            pr.pop(drop, None)
        # ltp.week52_high/low duplicate price.52_week.high/low
        if isinstance(pr.get('ltp'), dict):
            pr['ltp'].pop('week52_high', None)
            pr['ltp'].pop('week52_low', None)
        bucketed['price'] = pr

    # ── Fix 4: Drop company_details noise fields ──────────────────────────────
    cd = bucketed.get('company_details', {})
    if cd:
        # Promote Yahoo isin/ticker as fallback if unified_symbols didn't provide them
        if not cd.get('isin') and cd.get('isin_yahoo'):
            cd['isin'] = cd['isin_yahoo']
        if not cd.get('ticker') and cd.get('ticker_yahoo'):
            cd['ticker'] = cd['ticker_yahoo']
        NOISE = {
            'exchange_timezone_name', 'exchange_timezone_short', 'full_exchange_name',
            'market', 'market_state', 'last_trade_time', 'instrument_type_label',
            'sector_label', 'industry_label', 'display_name', 'name_yahoo',
            'ticker_yahoo', 'isin_yahoo', 'officer_compensation_date',
            'prev_name', 'name_changed_on', 'fax', 'zip',
            'last_fiscal_year_end', 'next_fiscal_year_end', 'most_recent_quarter',
            'data_source',
        }
        for k in NOISE:
            cd.pop(k, None)
        bucketed['company_details'] = cd

    # ── Fix 5: Drop yf_latest_* from financials — duplicates Screener latest ─
    fin = bucketed.get('financials', {})
    if fin:
        for k in [k for k in list(fin.keys()) if k.startswith('yf_latest_')]:
            fin.pop(k)
        bucketed['financials'] = fin

    # ── Drop pe_ratio/price_to_book from derived_metrics — duplicates valuation ─
    dm = bucketed.get('derived_metrics', {}).get('calculated_metrics', {})
    if dm:
        dm.pop('pe_ratio', None)
        dm.pop('price_to_book', None)

    # ── Round all floats to sensible precision ────────────────────────────────
    # fractions (|val| < 2): 4dp  e.g. 0.3408 (margin), 0.6275 (holding pct)
    # everything else:       2dp  e.g. 18.82 (PE), 16652.0 (Cr), 60.86 (%)
    # large absolute values (|val| > 1e9): untouched (market_cap, EV — already ints)
    def _round(obj):
        if isinstance(obj, dict):
            return {k: _round(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            if obj and isinstance(obj[0], dict) and 'Date' in obj[0]:
                return obj  # OHLCV bars — string values, skip
            return [_round(item) for item in obj]
        elif isinstance(obj, float):
            if abs(obj) > 1e9:
                return obj  # INR absolute (market_cap etc.) — leave as-is
            return round(obj, 4 if abs(obj) < 2 else 2)
        return obj

    bucketed = _round(bucketed)
    return bucketed


def _audit(output: dict, log) -> bool:
    """
    Post-load audit — runs immediately after output is written.
    Logs each check to the same log file. Returns False if any check fails.
    """
    ETFs = {'JUNIORBEES', 'NIFTYBEES'}
    NO_PROMOTER = {'ICICIBANK', 'ITC'}   # no promoter group in Screener — expected
    LOW_HISTORY = {'CIGNITITEC'}         # delisted/suspended — minimal bars expected
    EXPECTED_BUCKETS = {'company_details', 'financials', 'ratios', 'valuation',
                        'price', 'websignals', 'kpis', 'derived_metrics'}
    SANITY = [
        ('HCLTECH',  'net_profit', 'consolidated', 'annual', 16652.0),
        ('HDFCBANK', 'net_profit', 'consolidated', 'annual', 79219.0),
        ('INFY',     'net_profit', 'consolidated', 'annual', 29474.0),
        ('ITC',      'net_profit', 'consolidated', 'annual', 21018.0),
        ('BDL',      'net_profit', 'standalone',   'annual',   420.0),
        ('HCLTECH',  'revenue',    'consolidated', 'annual', 130144.0),
    ]

    tickers = [k for k in output if k != '_metadata']
    failures = []

    def chk(label, ok, detail=''):
        if ok:
            log.info(f"  AUDIT ✓ {label}" + (f" | {detail}" if detail else ""))
        else:
            log.warning(f"  AUDIT ✗ {label}" + (f" | {detail}" if detail else ""))
            failures.append(label)

    log.info("── Post-load audit ──────────────────────────────────────────")

    # A. Ticker count
    chk("A. Ticker count", len(tickers) == 97, f"{len(tickers)}/97")

    # B. All buckets present
    missing_b = {t: EXPECTED_BUCKETS - set(output[t].keys())
                 for t in tickers if EXPECTED_BUCKETS - set(output[t].keys())}
    chk("B. All buckets present", not missing_b,
        str(list(missing_b.items())[:3]) if missing_b else "")

    # C. net_profit present for non-ETFs
    np_issues = [t for t in tickers if t not in ETFs
                 and not any(output[t]['financials'].get('net_profit', {})
                             .get(c, {}).get('annual') for c in ('consolidated', 'standalone'))]
    chk("C. net_profit present", not np_issues,
        str(np_issues[:5]) if np_issues else "")

    # D. OHLCV bars — skip tickers listed within last 6 months (short history expected)
    import time
    now_ms = time.time() * 1000
    six_months_ms = 180 * 24 * 3600 * 1000
    ohlcv_issues = []
    for t in tickers:
        if t in ETFs | LOW_HISTORY:
            continue
        listing_ms = output[t]['company_details'].get('listing_date_ms')
        if listing_ms and (now_ms - listing_ms) < six_months_ms:
            continue  # newly listed — short history is expected
        pr = output[t]['price']
        daily = len(pr.get('ohlcv_daily', []))
        weekly = len(pr.get('ohlcv_weekly', []))
        if daily < 50:
            ohlcv_issues.append(f"{t}.ohlcv_daily:{daily}<50")
        expected_weekly = max(int(daily / 5 * 0.8), 1)
        if daily >= 50 and weekly < expected_weekly:
            ohlcv_issues.append(f"{t}.ohlcv_weekly:{weekly}<{expected_weekly}")
    chk("D. OHLCV min bars", not ohlcv_issues,
        str(ohlcv_issues[:3]) if ohlcv_issues else "")

    # E. Promoters present
    sh_issues = [t for t in tickers if t not in ETFs | NO_PROMOTER
                 and not output[t]['company_details']
                         .get('shareholding', {}).get('pattern', {}).get('promoters')]
    chk("E. Promoters present", not sh_issues,
        str(sh_issues[:5]) if sh_issues else "")

    # F. No _periods wrappers (sample 10 tickers)
    def has_wrapper(obj):
        if isinstance(obj, dict):
            if '_periods' in obj: return True
            return any(has_wrapper(v) for v in obj.values())
        if isinstance(obj, list):
            return any(has_wrapper(item) for item in obj[:2])
        return False
    wrapper_tickers = [t for t in tickers[:10] if has_wrapper(output[t])]
    chk("F. No _periods wrappers", not wrapper_tickers,
        str(wrapper_tickers) if wrapper_tickers else "")

    # G. No string values in financials period dicts
    str_count = sum(
        1 for t in tickers
        for field, val in output[t]['financials'].items()
        if isinstance(val, dict)
        for c, gd in val.items() if isinstance(gd, dict)
        for g, p in gd.items() if isinstance(p, dict)
        for v in p.values() if isinstance(v, str) and v
    )
    chk("G. No string values in financials", str_count == 0,
        f"{str_count} found" if str_count else "")

    # H. No PascalCase or yf_ field names in financials
    bad_keys = {k for t in tickers[:10] for k in output[t]['financials']
                if (k and k[0].isupper()) or k.startswith('yf_')}
    chk("H. Clean field names (no PascalCase/yf_)", not bad_keys,
        str(sorted(bad_keys)[:5]) if bad_keys else "")

    # I. Zero unmapped fields
    total_unmapped = sum(len(output[t].get('_unmapped', {})) for t in tickers)
    chk("I. Zero unmapped fields", total_unmapped == 0,
        f"{total_unmapped}" if total_unmapped else "")

    # J. Screener ratios present (roce or roe)
    ratio_issues = [t for t in tickers if t not in ETFs
                    and not output[t]['ratios'].get('screener', {}).get('roce_pct')
                    and not output[t]['ratios'].get('screener', {}).get('roe_pct')]
    chk("J. Screener ratios present", not ratio_issues,
        str(ratio_issues[:5]) if ratio_issues else "")

    # K. Valuation sub-groups
    stray = set(output.get('HCLTECH', {}).get('valuation', {}).keys()) - \
            {'pe', 'eps', 'history', 'market'}
    chk("K. Valuation sub-groups", not stray,
        f"stray: {stray}" if stray else "")

    # L. OHLCV bar value types
    bar = output.get('HCLTECH', {}).get('price', {}).get('ohlcv_weekly', [{}])[0]
    bad_bar_types = [k for k, v in bar.items() if k != 'Date' and isinstance(v, str)]
    chk("L. OHLCV bar types", not bad_bar_types,
        f"string cols: {bad_bar_types}" if bad_bar_types else "")

    # M. Sanity values
    sanity_failures = []
    for t, field, consol, gran, expected in SANITY:
        if t not in output:
            continue
        p = output[t]['financials'].get(field, {}).get(consol, {}).get(gran, {})
        latest = sorted(p.items(), reverse=True)[0] if p else None
        if not latest or latest[1] != expected:
            sanity_failures.append(f"{t}.{field}={latest} exp={expected}")
    chk("M. Sanity values", not sanity_failures,
        str(sanity_failures) if sanity_failures else "")

    total_checks = 13  # A through M
    log.info(f"── Audit: {total_checks - len(failures)}/{total_checks} passed"
             + (f" | {len(failures)} failed: {failures}" if failures else " | all clear"))

    return len(failures) == 0


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

        # Extract Yahoo fin sections BEFORE bucketing (needed for merge)
        yf_historical, yf_latest = _extract_yf_fin_sections(sections)

        bucketed = bucket_symbol(symbol, sections)
        bucketed = reorganize_by_period(bucketed)
        bucketed = clean_websignals(bucketed)
        bucketed = clean_metadata_wrapper(bucketed)
        bucketed = reorganize_financials_debt(bucketed)
        bucketed = reorganize_ratios_revenue(bucketed)
        bucketed = reorganize_valuation_eps_pe(bucketed)
        bucketed = reorganize_price_52w_volume(bucketed)
        bucketed = reorganize_identity_shareholding(bucketed)

        # Merge Yahoo data into Screener consolidated timeline
        # Must run AFTER all reorganize passes so financials bucket is stable
        bucketed = merge_yahoo_into_screener(bucketed, yf_historical, yf_latest)

        bucketed = compute_derived_metrics(bucketed)
        bucketed = reorganize_derived_metrics_guidance(bucketed)
        
        # Add guidance data from guidance.json
        if symbol in guidance_data:
            if 'derived_metrics' not in bucketed:
                bucketed['derived_metrics'] = {}
            bucketed['derived_metrics']['ai_insights_guidance'] = guidance_data[symbol]

        # Final pass — standardise all field names to business-friendly names
        bucketed = standardize_field_names(bucketed)

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
    
    # Create output with metadata
    from datetime import datetime
    import time
    
    final_output = {
        "_metadata": {
            "generated_at": datetime.now().isoformat(),
            "total_tickers": total,
            "tickers_with_guidance": len([s for s in symbols if s in guidance_data]),
            "unmapped_count": sum(len(v) for v in unmapped_summary.values()),

            # ── SCHEMA — generated at runtime from actual output ───────────────────
            # Key   = exact dot-path to the field (as accessed in JS/Python)
            # Value = unit: Cr | INR | INR_abs | pct | frac | ratio | int | epoch | str | []  | bars
            # {YYYY-MM-DD} = dict keyed by ISO date string
            # []           = list (shareholding time-series objects)
            # bars         = list of OHLCV dicts {Date, Open, High, Low, Close, Volume}
            # Cr           = Indian Rupees, Crores
            # INR_abs      = absolute INR — divide by 1e7 for Crores (market_cap, EV etc.)
            # pct          = percentage as float  (18.5 = 18.5%)
            # frac         = fraction 0–1  (0.185 = 18.5%)
            # epoch        = Unix timestamp seconds
            # ─────────────────────────────────────────────────────────────────────
            "schema": _build_schema(output),
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

    # ── Post-load audit ────────────────────────────────────────────────────────
    audit_passed = _audit(final_output, logger)
    if not audit_passed:
        logger.error("✗ AUDIT FAILED — review warnings above before deploying")
        sys.exit(1)
    logger.info("✓ AUDIT PASSED")


def _build_schema(output: dict) -> dict:
    """
    Generate _metadata.schema at runtime from the actual bucketed output.
    Walks every field path across all tickers and infers the unit/type.
    Always in sync with the real data — never stale.
    """
    UNIT_MAP = {
        # financials — Cr
        'Net_Profit':'Cr','Sales':'Cr','Expenses':'Cr','Operating_Profit':'Cr',
        'Other_Income':'Cr','Interest':'Cr','Depreciation':'Cr',
        'profit_before_tax':'Cr','share_capital':'Cr','Reserves':'Cr',
        'Borrowings':'Cr','Deposits':'Cr','Other_Liabilities':'Cr',
        'Total_Liabilities':'Cr','net_fixed_assets':'Cr','capital_wip':'Cr',
        'Investments':'Cr','Other_Assets':'Cr','Total_Assets':'Cr',
        'operating_cash_flow':'Cr','investing_cash_flow':'Cr',
        'financing_cash_flow':'Cr','net_cash_flow':'Cr','Free_Cash_Flow':'Cr',
        'net_interest_income':'Cr','yf_revenue':'Cr','yf_ebitda':'Cr',
        'yf_gross_profit':'Cr','yf_capex':'Cr','yf_free_cash_flow':'Cr',
        'yf_cash':'Cr','yf_cogs':'Cr','yf_operating_cash_flow':'Cr',
        'yf_receivables':'Cr','yf_invested_capital':'Cr','yf_working_capital':'Cr',
        'yf_lease_obligations':'Cr','yf_rd_expense':'Cr','yf_tangible_assets':'Cr',
        'yf_exceptional_items':'Cr','yf_normalized_profit':'Cr',
        'yf_latest_revenue':'Cr','yf_latest_net_profit':'Cr','yf_latest_ebit':'Cr',
        'yf_latest_operating_cash_flow':'Cr','yf_latest_fcf':'Cr',
        'yf_latest_borrowings':'Cr','yf_latest_total_assets':'Cr',
        'yf_latest_total_liabilities':'Cr','yf_latest_depreciation':'Cr',
        'yf_latest_interest':'Cr',
        'fcf_ttm':'Cr','operating_cash_flow_ttm':'Cr','gross_profit_ttm':'Cr',
        'net_profit_ttm':'Cr','cash_and_equivalents':'Cr',
        # financials — INR per share
        'eps':'INR','yf_latest_eps':'INR','cash_per_share':'INR','book_value':'INR',
        # financials — pct
        'operating_margin_pct':'pct','tax_rate_pct':'pct','dividend_payout_pct':'pct',
        'net_interest_margin_pct':'pct','gross_npa_pct':'pct','net_npa_pct':'pct',
        # financials — ratio
        'cash_conversion_ratio':'ratio',
        # ratios — days
        'debtor_days':'days','inventory_days':'days','days_payable':'days',
        'cash_conversion_cycle':'days','working_capital_days':'days',
        # ratios — pct
        'roce_pct':'pct','roe_pct':'pct','net_margin_pct':'pct',
        'gross_margin_pct':'pct','ebitda_margin_pct':'pct','operating_margin_pct':'pct',
        'roa_pct':'pct','insider_holding_pct':'pct','institutional_holding_pct':'pct',
        # ratios — frac
        'earnings_growth_yoy':'frac','earnings_growth_qoq':'frac',
        'index_52w_change':'frac',
        # ratios — ratio
        'debt_to_equity_ratio':'ratio','current_ratio':'ratio','quick_ratio':'ratio',
        # valuation — shares/eps history
        'basic_eps_history':'INR','diluted_eps_history':'INR',
        'basic_shares_history':'int','diluted_shares_history':'int',
        'shares_outstanding_history':'int',
        # company_details
        'employee_count':'int','floating_shares':'int','implied_shares':'int',
        'shares_outstanding':'int','government':'pct','others':'pct',
        'promoters':'pct','fiis':'pct','diis':'pct','public':'pct',
        'last_fiscal_year_end':'epoch','next_fiscal_year_end':'epoch',
        'most_recent_quarter':'epoch',
        # price
        'high':'INR','low':'INR','beta':'ratio',
        'all_time_high':'INR','all_time_low':'INR',
        'ask':'INR','bid':'INR','ask_size':'int','bid_size':'int',
        'avg_volume':'int','avg_volume_10d':'int','avg_volume_3mo':'int',
        'market_volume':'int','week52_high_diff':'INR','week52_low_diff':'INR',
        'enterprise_value':'INR_abs','ebitda':'INR_abs','total_debt':'INR_abs',
        'market_cap':'INR_abs','basic_market_cap':'INR_abs',
        # valuation — ratio
        'pe_ttm':'ratio','pe_forward':'ratio','peg':'ratio','peg_ttm':'ratio',
        'price_to_book':'ratio','price_to_sales':'ratio','pe_current_year':'ratio',
        'ev_to_revenue':'ratio','ev_to_ebitda':'ratio',
        # valuation — INR
        'eps_ttm':'INR','eps_forward':'INR','eps_current_year':'INR',
        # price — INR
        'price':'INR','change':'INR','prev_close':'INR','week52_high':'INR',
        'week52_low':'INR','close_price':'INR','market_price':'INR',
        'day_high':'INR','day_low':'INR','day_open':'INR','price_change':'INR',
        'ma_50d':'INR','ma_200d':'INR','ma_50d_diff':'INR','ma_200d_diff':'INR',
        'target_high':'INR','target_low':'INR','target_mean':'INR','target_median':'INR',
        # price — pct
        'change_pct':'pct','price_change_pct':'pct',
        'ma_50d_diff_pct':'pct','ma_200d_diff_pct':'pct',
        'week52_high_diff_pct':'pct','week52_low_diff_pct':'pct',
        # price — int
        'day_volume':'int','market_volume':'int',
        # websignals
        'analyst_rating_score':'float 1-5','analyst_count':'int',
        'governance_audit_risk':'int 1-10','governance_board_risk':'int 1-10',
        'governance_comp_risk':'int 1-10','governance_rights_risk':'int 1-10',
        'governance_overall_risk':'int 1-10',
        'next_earnings_date':'epoch','earnings_date_start':'epoch',
        'earnings_date_end':'epoch','earnings_call_start':'epoch',
        'earnings_call_end':'epoch','listing_date_ms':'epoch',
        'officer_compensation_date':'epoch',
    }

    def infer_unit(leaf: str, full_path: str, sample_val) -> str:
        # For nested paths (e.g. Borrowings.consolidated.annual),
        # look up by root field name first, then leaf key
        root = full_path.split('.')[0]
        for key in (root, leaf):
            if key in UNIT_MAP:
                return UNIT_MAP[key]
        if leaf.endswith('_pct') or root.endswith('_pct'):
            return 'pct'
        if leaf.endswith('_ms') or 'timestamp' in leaf:
            return 'epoch'
        if isinstance(sample_val, float) and sample_val and 0 < abs(sample_val) < 1:
            return 'frac'
        return 'str'

    buckets = ['company_details','financials','ratios','valuation','price','websignals','derived_metrics']
    schema = {}
    tickers = [k for k in output if k != '_metadata']
    if not tickers:
        return schema

    for bucket in buckets:
        paths: dict = {}

        def recurse(obj, prefix, depth):
            if not isinstance(obj, dict) or depth > 5:
                return
            for k, v in obj.items():
                full = f'{prefix}.{k}' if prefix else k
                if isinstance(v, dict):
                    sample_keys = [sk for sk in list(v.keys())[:3] if isinstance(sk, str)]
                    if sample_keys and all(len(sk) == 10 and '-' in sk for sk in sample_keys):
                        sample_v = list(v.values())[0] if v else None
                        paths[full + '.{YYYY-MM-DD}'] = infer_unit(k, full, sample_v)
                    else:
                        recurse(v, full, depth + 1)
                elif isinstance(v, list):
                    if v and isinstance(v[0], dict) and 'Date' in v[0]:
                        paths[full + '[]'] = 'bars | {Date,Open,High,Low,Close,Volume}'
                    else:
                        paths[full + '[]'] = '[]'
                else:
                    paths[full] = infer_unit(k, full, v)

        for t in tickers:
            recurse(output[t].get(bucket, {}), '', 0)

        schema[bucket] = dict(sorted(paths.items()))

    return schema


if __name__ == "__main__":
    main()
