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
    # in main(). Keeping them here would cause double-processing:
    #   bucket_symbol() → puts scalar (latest) and time-series (historical) into
    #                      the same financials keys → scalar overwrites time-series.
    # The merge layer is the single owner of all yahoofin_fin data.

    # ââ screener_fin:quarterly_results  (quarterly consolidated P&L) ââââââ
    "screener_fin:quarterly_results": {
        "SalesÂ +":           ("financials", "Sales"),
        "Sales +":             ("financials", "Sales"),
        "RevenueÂ +":         ("financials", "Sales"),
        "Revenue +":           ("financials", "Sales"),
        "ExpensesÂ +":        ("financials", "Expenses"),
        "Expenses +":          ("financials", "Expenses"),
        "Operating Profit":    ("financials", "Operating_Profit"),
        "OPM %":               ("financials", "OPM_pct"),
        "Other IncomeÂ +":    ("financials", "Other_Income"),
        "Other Income +":      ("financials", "Other_Income"),
        "Interest":            ("financials", "Interest"),
        "Depreciation":        ("financials", "Depreciation"),
        "Profit before tax":   ("financials", "Profit_before_tax"),
        "Tax %":               ("financials", "Tax_pct"),
        "Net ProfitÂ +":      ("financials", "Net_Profit"),
        "Net Profit +":        ("financials", "Net_Profit"),
        "EPS in Rs":           ("financials", "EPS_Rs"),
        "Financing Profit":    ("financials", "Financing_Profit"),
        "Financing Margin %":  ("financials", "Financing_Margin_pct"),
        "Gross NPA %":         ("financials", "Gross_NPA_pct"),
        "Net NPA %":           ("financials", "Net_NPA_pct"),
    },

    # ââ screener_fin:profit_loss  (annual consolidated P&L, 12yr) ââââââââ
    "screener_fin:profit_loss": {
        "RevenueÂ +":         ("financials", "Sales"),
        "Revenue +":           ("financials", "Sales"),
        "SalesÂ +":           ("financials", "Sales"),
        "Sales +":             ("financials", "Sales"),
        "ExpensesÂ +":        ("financials", "Expenses"),
        "Expenses +":          ("financials", "Expenses"),
        "Operating Profit":    ("financials", "Operating_Profit"),
        "OPM %":               ("financials", "OPM_pct"),
        "Other IncomeÂ +":    ("financials", "Other_Income"),
        "Other Income +":      ("financials", "Other_Income"),
        "Interest":            ("financials", "Interest"),
        "Depreciation":        ("financials", "Depreciation"),
        "Profit before tax":   ("financials", "Profit_before_tax"),
        "Tax %":               ("financials", "Tax_pct"),
        "Net ProfitÂ +":      ("financials", "Net_Profit"),
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
        "BorrowingsÂ +":        ("financials", "Borrowings"),
        "Borrowings +":            ("financials", "Borrowings"),
        "Borrowing":               ("financials", "Borrowing"),
        "Deposits":                ("financials", "Deposits"),
        "Other LiabilitiesÂ +": ("financials", "Other_Liabilities"),
        "Other Liabilities +":     ("financials", "Other_Liabilities"),
        "Total Liabilities":       ("financials", "Total_Liabilities"),
        "Fixed AssetsÂ +":      ("financials", "Fixed_Assets"),
        "Fixed Assets +":          ("financials", "Fixed_Assets"),
        "CWIP":                    ("financials", "CWIP"),
        "Investments":             ("financials", "Investments"),
        "Other AssetsÂ +":      ("financials", "Other_Assets"),
        "Other Assets +":          ("financials", "Other_Assets"),
        "Total Assets":            ("financials", "Total_Assets"),
    },

    # ââ screener_fin:cash_flow  (annual consolidated CF, 12yr) ââââââââââ
    "screener_fin:cash_flow": {
        "Cash from Operating ActivityÂ +": ("financials", "CFO"),
        "Cash from Operating Activity +":   ("financials", "CFO"),
        "Cash from Investing ActivityÂ +": ("financials", "CFI"),
        "Cash from Investing Activity +":   ("financials", "CFI"),
        "Cash from Financing ActivityÂ +": ("financials", "CFF"),
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
        "PromotersÂ +":      ("company_details", "promoters"),
        "Promoters +":         ("company_details", "promoters"),
        "FIIsÂ +":           ("company_details", "fiis"),
        "FIIs +":              ("company_details", "fiis"),
        "DIIsÂ +":           ("company_details", "diis"),
        "DIIs +":              ("company_details", "diis"),
        "GovernmentÂ +":     ("company_details", "government"),
        "Government +":        ("company_details", "government"),
        "PublicÂ +":         ("company_details", "public"),
        "Public +":            ("company_details", "public"),
        "OthersÂ +":         ("company_details", "others"),
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
SCREENER_TO_YAHOO_OVERLAP = {
    "Sales":             "revenue",
    "Net_Profit":        "net_profit",
    "Depreciation":      "depreciation",
    "Interest":          "interest_expense",
    "EPS_Rs":            "basic_eps",
    "Operating_Profit":  "ebit",
    "CFO":               "operating_cash_flow",
    "Free_Cash_Flow":    "free_cash_flow",
    # Balance sheet
    "Total_Assets":      "total_assets",
    "Total_Liabilities": "total_liabilities",
    "Borrowing":         "total_debt",
    "Borrowings":        "total_debt",
}

# Yahoo fields that have NO Screener equivalent — add directly to financials bucket
YAHOO_EXCLUSIVE_FINANCIALS = {
    "revenue":              "yf_revenue",
    "cost_of_revenue":      "yf_cost_of_revenue",
    "gross_profit":         "yf_gross_profit",
    "ebitda":               "yf_ebitda",
    "rd_expense":           "yf_rd_expense",
    "operating_cash_flow":  "yf_operating_cash_flow",
    "free_cash_flow":       "yf_free_cash_flow",
    "capex":                "yf_capex",
    "accounts_receivable":  "yf_accounts_receivable",
    "cash_and_equivalents": "yf_cash_and_equivalents",
    "net_tangible_assets":  "yf_net_tangible_assets",
    "working_capital":      "yf_working_capital",
    "invested_capital":     "yf_invested_capital",
    "capital_lease_obligations": "yf_capital_lease_obligations",
    "normalized_income":    "yf_normalized_income",
    "unusual_items":        "yf_unusual_items",
}

# Yahoo per-share / share count fields — route to valuation bucket
YAHOO_EXCLUSIVE_VALUATION = {
    "diluted_eps":       "yf_diluted_eps",
    "basic_eps":         "yf_basic_eps",
    "diluted_shares":    "yf_diluted_shares",
    "basic_shares":      "yf_basic_shares",
    "shares_outstanding":"yf_shares_outstanding",
}


def _get_periods_dict(bucket_field):
    """Extract {iso_date: value} from a bucketed field (handles both flat and nested)."""
    if not isinstance(bucket_field, dict):
        return {}
    # Granularity-nested: {'annual': {'2024-03-31': v, ...}, ...}
    if any(k in bucket_field for k in ('annual', 'quarterly', 'half_yearly', 'monthly', 'daily')):
        return bucket_field.get('annual', {})
    # Flat time-series: {'2024-03-31': v, ...}
    keys = list(bucket_field.keys())
    if keys and len(str(keys[0])) == 10 and '-' in str(keys[0]):
        return bucket_field
    return {}


def _latest_period(periods_dict):
    """Return the most recent ISO date key from a periods dict."""
    if not periods_dict:
        return None
    return max(periods_dict.keys())


def merge_yahoo_into_screener(bucketed: dict, yf_historical: dict, yf_latest: dict) -> dict:
    """
    Merge Yahoo Finance data into the already-bucketed Screener data.

    Rules:
    1. Screener consolidated = primary — never overwrite existing Screener periods.
    2. Yahoo historical → fill gaps in Screener consolidated annual timeline.
    3. Yahoo latest → add as most-recent point if its period is newer than Screener's last.
    4. Yahoo-exclusive fields → add under yf_* keys in financials/valuation buckets.

    Args:
        bucketed     : output of bucket_symbol() + reorganize passes
        yf_historical: {field_name: {iso_date: value_in_crores}} from yahoofin_fin:historical
        yf_latest    : {field_name: value_in_crores} from yahoofin_fin:latest

    Returns:
        bucketed dict with Yahoo data merged in.
    """
    fin = bucketed.get('financials', {})
    val = bucketed.get('valuation', {})

    # ── 1 & 2: Gap-fill overlapping metrics ───────────────────────────────────
    for screener_key, yahoo_field in SCREENER_TO_YAHOO_OVERLAP.items():
        yf_periods = yf_historical.get(yahoo_field, {})
        if not yf_periods:
            continue

        existing = fin.get(screener_key)
        sr_periods = _get_periods_dict(existing) if existing else {}

        filled = 0
        for iso_date, yf_val in yf_periods.items():
            if iso_date not in sr_periods and yf_val not in (None, ''):
                sr_periods[iso_date] = yf_val
                filled += 1

        if filled and sr_periods:
            # Write back — preserve existing nested structure or create flat
            if isinstance(existing, dict) and 'annual' in existing:
                existing['annual'].update(
                    {d: v for d, v in yf_periods.items() if d not in existing['annual']}
                )
            else:
                fin[screener_key] = dict(sorted(sr_periods.items(), reverse=True))

    # ── 3: Extend with Yahoo latest if newer than Screener's last period ──────
    for screener_key, yahoo_field in SCREENER_TO_YAHOO_OVERLAP.items():
        latest_val = yf_latest.get(yahoo_field)
        if latest_val in (None, ''):
            continue

        existing = fin.get(screener_key)
        sr_periods = _get_periods_dict(existing) if existing else {}
        sr_last = _latest_period(sr_periods)

        # Yahoo latest doesn't carry an explicit date — use today's fiscal year end
        # as a sentinel only if it's strictly newer than Screener's last period.
        # We skip this if Screener already has data within the last 6 months.
        from datetime import date
        today = date.today().isoformat()
        if sr_last and sr_last >= today[:7]:
            continue  # Screener is already current
        
        # Tag as yf_latest_ prefixed key to avoid collision
        yf_latest_key = f"yf_latest_{screener_key}"
        fin[yf_latest_key] = latest_val

    # ── 4a: Yahoo-exclusive financials (time-series) ──────────────────────────
    for yahoo_field, output_key in YAHOO_EXCLUSIVE_FINANCIALS.items():
        yf_periods = yf_historical.get(yahoo_field, {})
        yf_lat = yf_latest.get(yahoo_field)

        if yf_periods:
            fin[output_key] = dict(sorted(
                {d: v for d, v in yf_periods.items() if v not in (None, '')}.items(),
                reverse=True
            ))
        elif yf_lat not in (None, ''):
            fin[output_key] = yf_lat

    # ── 4b: Yahoo-exclusive per-share / valuation fields ─────────────────────
    for yahoo_field, output_key in YAHOO_EXCLUSIVE_VALUATION.items():
        yf_periods = yf_historical.get(yahoo_field, {})
        yf_lat = yf_latest.get(yahoo_field)

        if yf_periods:
            val[output_key] = dict(sorted(
                {d: v for d, v in yf_periods.items() if v not in (None, '')}.items(),
                reverse=True
            ))
        elif yf_lat not in (None, ''):
            val[output_key] = yf_lat

    bucketed['financials'] = fin
    bucketed['valuation'] = val
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
            "data_sources": [
                "screener_raw_data.json (97 tickers)",
                "screener_financials.json (97 tickers)",
                "yahoofin_raw_data.json (97 tickers)",
                "yahoofin_financials.json (97 tickers)",
                "guidance.json (29 tickers)",
                "prices.json (98 tickers)",
                "unified-symbols.json (97 tickers)"
            ],
            "buckets": {
                "company_details": {
                    "sub_sections": ["promoters", "fiis", "diis", "government", "public", "shareholding { pattern, shares, ownership, fiscal_dates, dividends, stock_splits }"],
                    "description": "Company profile, ownership, shareholding pattern, dividends, stock splits"
                },
                "financials": {
                    "sub_sections": ["Sales", "Revenue", "Expenses", "Operating_Profit", "Net_Profit", "Free_Cash_Flow", "Total_Debt", "Equity_Capital", "..."],
                    "description": "Revenue, expenses, profitability, cash flows, debt metrics - with consolidated/standalone > quarterly/annual structure"
                },
                "ratios": {
                    "sub_sections": ["Return_on_Equity_pct", "Return_on_Assets_pct", "Net_Margin_pct", "Operating_Margin_pct", "..."],
                    "description": "Financial ratios - profitability, efficiency, leverage"
                },
                "valuation": {
                    "sub_sections": ["pe { trailing_pe, forward_pe, peg_ratio }", "eps { basic_eps, diluted_eps, trailing_eps, forward_eps, ... }", "enterprise_value", "market_cap", "price_to_book"],
                    "description": "Valuation metrics grouped by PE and EPS sub-groups"
                },
                "price": {
                    "sub_sections": ["current_price", "ltp", "52_week { high, low, change }", "volume { daily, average }", "history_6mo_1d", "history_1wk", "history_1mo"],
                    "description": "Price data - current, 52-week range, volume, OHLCV history (history_1wk/history_1mo populated from 5yr or 10yr source, structure identical either way)"
                },
                "websignals": {
                    "sub_sections": ["ai_insights_date", "recommendation_key", "recommendation_mean", "number_of_analyst_opinions", "target_high_price", "target_low_price", "raw_pdf_*"],
                    "description": "Analyst sentiment, recommendations, price targets"
                },
                "kpis": {
                    "sub_sections": ["Capacity_Utilization_Factor", "Plant_Availability", "Power_Generation", "... (company-specific)"],
                    "description": "Key performance indicators from screener_raw:Insights - varies by company"
                },
                "derived_metrics": {
                    "sub_sections": ["calculated_metrics { scores, ratings, sector_weights }", "ai_insights_guidance { guidance + insights }"],
                    "description": "Computed metrics with sector weightage and AI insights"
                },
                "_unmapped": {
                    "sub_sections": [],
                    "description": "Fields that couldn't be mapped to any bucket (0 fields in this output)"
                }
            },
            "derived_metrics_structure": {
                "calculated_metrics": "Sector-weighted financial scores (fundamental, technical, valuation, sentiment, composite) with rating",
                "ai_insights_guidance": "AI-extracted guidance (15 topics) + insights (only for 29 tickers in guidance.json)"
            },
            "unmapped_count": sum(len(v) for v in unmapped_summary.values()),
            "unmapped_tickers": list(unmapped_summary.keys()),
            "notes": "Each ticker has 9 buckets. Guidance presence depends on data availability."
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
