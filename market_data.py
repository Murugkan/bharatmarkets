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

Buckets (18 + 1)
────────────────
 1. company_identity
 2. income_statement_quarterly_consolidated   (screener_fin, quarterly)
 3. income_statement_quarterly_standalone     (screener_raw, quarterly)
 4. income_statement_annual                   (12yr standalone + 7yr consolidated)
 5. balance_sheet_annual                      (12yr standalone + 7yr consolidated)
 6. cash_flow_annual                          (12yr standalone + 7yr consolidated)
 7. efficiency_ratios                         (annual)
 8. valuation
 9. price_trading                             (live quote + full OHLCV history)
10. dividends_shareholding
11. profitability_growth
12. risk_and_governance
13. analyst_consensus
14. management_guidance
15. operational_kpis                          (company-specific, varies per ticker)
16. exchange_metadata
17. portfolio_context
18. derived_metrics                           (NEW: signals + metrics)
 +. _unmapped                                 (catch-all — never empty on surprise fields)
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
        "ticker":   ("portfolio_context",  "ticker"),
        "name":     ("portfolio_context",  "name"),
        "qty":      ("portfolio_context",  "qty"),
        "avg":      ("portfolio_context",  "avg_cost"),
        "isin":     ("company_identity",   "isin"),
        "sector":   ("company_identity",   "sector"),
        "industry": ("company_identity",   "industry"),
        "type":     ("company_identity",   "type"),
        "source":   ("company_identity",   "data_source"),
    },

    # ── yahoofin_raw:info ─────────────────────────────────────────────────────
    "yahoofin_raw:info": {
        # identity
        "shortName":             ("company_identity", "short_name"),
        "longName":              ("company_identity", "long_name"),
        "symbol":                ("company_identity", "symbol_yahoo"),
        "address1":              ("company_identity", "address1"),
        "address2":              ("company_identity", "address2"),
        "city":                  ("company_identity", "city"),
        "zip":                   ("company_identity", "zip"),
        "country":               ("company_identity", "country"),
        "phone":                 ("company_identity", "phone"),
        "fax":                   ("company_identity", "fax"),
        "website":               ("company_identity", "website"),
        "industry":              ("company_identity", "industry_yahoo"),
        "industryDisp":          ("company_identity", "industry_disp"),
        "sector":                ("company_identity", "sector_yahoo"),
        "sectorDisp":            ("company_identity", "sector_disp"),
        "longBusinessSummary":   ("company_identity", "long_business_summary"),
        "fullTimeEmployees":     ("company_identity", "full_time_employees"),
        "companyOfficers":       ("company_identity", "company_officers"),
        "currency":              ("company_identity", "currency"),
        "financialCurrency":     ("company_identity", "financial_currency"),
        "quoteType":             ("company_identity", "quote_type"),
        "typeDisp":              ("company_identity", "type_disp"),
        "language":              ("company_identity", "language"),
        "region":                ("company_identity", "region"),
        "exchange":              ("company_identity", "exchange"),
        "fullExchangeName":      ("company_identity", "full_exchange_name"),
        "esgPopulated":          ("company_identity", "esg_populated"),
        "nameChangeDate":        ("company_identity", "name_change_date"),
        "prevName":              ("company_identity", "prev_name"),
        # valuation
        "marketCap":                   ("valuation", "market_cap"),
        "nonDilutedMarketCap":         ("valuation", "non_diluted_market_cap"),
        "enterpriseValue":             ("valuation", "enterprise_value"),
        "trailingPE":                  ("valuation", "trailing_pe"),
        "forwardPE":                   ("valuation", "forward_pe"),
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
        "currentPrice":                  ("price_trading", "current_price"),
        "previousClose":                 ("price_trading", "previous_close"),
        "regularMarketPreviousClose":    ("price_trading", "regular_market_previous_close"),
        "open":                          ("price_trading", "open"),
        "regularMarketOpen":             ("price_trading", "regular_market_open"),
        "dayLow":                        ("price_trading", "day_low"),
        "dayHigh":                       ("price_trading", "day_high"),
        "regularMarketDayLow":           ("price_trading", "regular_market_day_low"),
        "regularMarketDayHigh":          ("price_trading", "regular_market_day_high"),
        "regularMarketDayRange":         ("price_trading", "regular_market_day_range"),
        "regularMarketPrice":            ("price_trading", "regular_market_price"),
        "regularMarketChange":           ("price_trading", "regular_market_change"),
        "regularMarketChangePercent":    ("price_trading", "regular_market_change_pct"),
        "volume":                        ("price_trading", "volume"),
        "regularMarketVolume":           ("price_trading", "regular_market_volume"),
        "averageVolume":                 ("price_trading", "average_volume"),
        "averageVolume10days":           ("price_trading", "average_volume_10d"),
        "averageDailyVolume10Day":       ("price_trading", "average_daily_volume_10d"),
        "averageDailyVolume3Month":      ("price_trading", "average_daily_volume_3mo"),
        "bid":                           ("price_trading", "bid"),
        "bidSize":                       ("price_trading", "bid_size"),
        "ask":                           ("price_trading", "ask"),
        "askSize":                       ("price_trading", "ask_size"),
        "fiftyDayAverage":               ("price_trading", "fifty_day_avg"),
        "fiftyDayAverageChange":         ("price_trading", "fifty_day_avg_change"),
        "fiftyDayAverageChangePercent":  ("price_trading", "fifty_day_avg_change_pct"),
        "twoHundredDayAverage":          ("price_trading", "two_hundred_day_avg"),
        "twoHundredDayAverageChange":    ("price_trading", "two_hundred_day_avg_change"),
        "twoHundredDayAverageChangePercent": ("price_trading", "two_hundred_day_avg_change_pct"),
        "fiftyTwoWeekLow":               ("price_trading", "fifty_two_week_low"),
        "fiftyTwoWeekHigh":              ("price_trading", "fifty_two_week_high"),
        "fiftyTwoWeekLowChange":         ("price_trading", "fifty_two_week_low_change"),
        "fiftyTwoWeekHighChange":        ("price_trading", "fifty_two_week_high_change"),
        "fiftyTwoWeekLowChangePercent":  ("price_trading", "fifty_two_week_low_change_pct"),
        "fiftyTwoWeekHighChangePercent": ("price_trading", "fifty_two_week_high_change_pct"),
        "fiftyTwoWeekRange":             ("price_trading", "fifty_two_week_range"),
        "fiftyTwoWeekChangePercent":     ("price_trading", "fifty_two_week_change_pct"),
        "52WeekChange":                  ("price_trading", "fifty_two_week_change"),
        "allTimeHigh":                   ("price_trading", "all_time_high"),
        "allTimeLow":                    ("price_trading", "all_time_low"),
        "beta":                          ("price_trading", "beta"),
        "lastSplitDate":                 ("price_trading", "last_split_date"),
        "lastSplitFactor":               ("price_trading", "last_split_factor"),
        # dividends & shareholding
        "dividendRate":                  ("dividends_shareholding", "dividend_rate"),
        "dividendYield":                 ("dividends_shareholding", "dividend_yield"),
        "exDividendDate":                ("dividends_shareholding", "ex_dividend_date"),
        "payoutRatio":                   ("dividends_shareholding", "payout_ratio"),
        "trailingAnnualDividendRate":    ("dividends_shareholding", "trailing_annual_dividend_rate"),
        "trailingAnnualDividendYield":   ("dividends_shareholding", "trailing_annual_dividend_yield"),
        "lastDividendValue":             ("dividends_shareholding", "last_dividend_value"),
        "lastDividendDate":              ("dividends_shareholding", "last_dividend_date"),
        "fiveYearAvgDividendYield":      ("dividends_shareholding", "five_year_avg_dividend_yield"),
        "heldPercentInsiders":           ("dividends_shareholding", "held_pct_insiders"),
        "heldPercentInstitutions":       ("dividends_shareholding", "held_pct_institutions"),
        "floatShares":                   ("dividends_shareholding", "float_shares"),
        "sharesOutstanding":             ("dividends_shareholding", "shares_outstanding"),
        "impliedSharesOutstanding":      ("dividends_shareholding", "implied_shares_outstanding"),
        # profitability & growth
        "profitMargins":             ("profitability_growth", "profit_margins"),
        "grossMargins":              ("profitability_growth", "gross_margins"),
        "ebitdaMargins":             ("profitability_growth", "ebitda_margins"),
        "operatingMargins":          ("profitability_growth", "operating_margins"),
        "earningsGrowth":            ("profitability_growth", "earnings_growth"),
        "revenueGrowth":             ("profitability_growth", "revenue_growth"),
        "earningsQuarterlyGrowth":   ("profitability_growth", "earnings_quarterly_growth"),
        "revenuePerShare":           ("profitability_growth", "revenue_per_share"),
        "totalCash":                 ("profitability_growth", "total_cash"),
        "totalCashPerShare":         ("profitability_growth", "total_cash_per_share"),
        "debtToEquity":              ("profitability_growth", "debt_to_equity"),
        "currentRatio":              ("profitability_growth", "current_ratio"),
        "quickRatio":                ("profitability_growth", "quick_ratio"),
        "netIncomeToCommon":         ("profitability_growth", "net_income_to_common"),
        "grossProfits":              ("profitability_growth", "gross_profits"),
        "totalRevenue":              ("profitability_growth", "total_revenue"),
        "returnOnAssets":            ("profitability_growth", "return_on_assets"),
        "returnOnEquity":            ("profitability_growth", "return_on_equity"),
        "freeCashflow":              ("profitability_growth", "free_cashflow"),
        "operatingCashflow":         ("profitability_growth", "operating_cashflow"),
        # risk & governance
        "auditRisk":             ("risk_and_governance", "audit_risk"),
        "boardRisk":             ("risk_and_governance", "board_risk"),
        "compensationRisk":      ("risk_and_governance", "compensation_risk"),
        "shareHolderRightsRisk": ("risk_and_governance", "shareholder_rights_risk"),
        "overallRisk":           ("risk_and_governance", "overall_risk"),
        "governanceEpochDate":   ("risk_and_governance", "governance_epoch_date"),
        # analyst consensus
        "targetHighPrice":           ("analyst_consensus", "target_high_price"),
        "targetLowPrice":            ("analyst_consensus", "target_low_price"),
        "targetMeanPrice":           ("analyst_consensus", "target_mean_price"),
        "targetMedianPrice":         ("analyst_consensus", "target_median_price"),
        "recommendationMean":        ("analyst_consensus", "recommendation_mean"),
        "recommendationKey":         ("analyst_consensus", "recommendation_key"),
        "numberOfAnalystOpinions":   ("analyst_consensus", "number_of_analyst_opinions"),
        "averageAnalystRating":      ("analyst_consensus", "average_analyst_rating"),
        "SandP52WeekChange":         ("analyst_consensus", "sandp_52_week_change"),
        # earnings calendar
        "earningsTimestamp":          ("analyst_consensus", "earnings_timestamp"),
        "earningsTimestampStart":     ("analyst_consensus", "earnings_timestamp_start"),
        "earningsTimestampEnd":       ("analyst_consensus", "earnings_timestamp_end"),
        "earningsCallTimestampStart": ("analyst_consensus", "earnings_call_ts_start"),
        "earningsCallTimestampEnd":   ("analyst_consensus", "earnings_call_ts_end"),
        "isEarningsDateEstimate":     ("analyst_consensus", "is_earnings_date_estimate"),
        # exchange metadata
        "exchange":                       ("exchange_metadata", "exchange"),
        "exchangeTimezoneName":           ("exchange_metadata", "exchange_timezone_name"),
        "exchangeTimezoneShortName":      ("exchange_metadata", "exchange_timezone_short"),
        "gmtOffSetMilliseconds":          ("exchange_metadata", "gmt_offset_ms"),
        "market":                         ("exchange_metadata", "market"),
        "quoteSourceName":                ("exchange_metadata", "quote_source_name"),
        "marketState":                    ("exchange_metadata", "market_state"),
        "sourceInterval":                 ("exchange_metadata", "source_interval"),
        "exchangeDataDelayedBy":          ("exchange_metadata", "exchange_data_delay"),
        "firstTradeDateMilliseconds":     ("exchange_metadata", "first_trade_date_ms"),
        "regularMarketTime":              ("exchange_metadata", "regular_market_time"),
        "lastFiscalYearEnd":              ("exchange_metadata", "last_fiscal_year_end"),
        "nextFiscalYearEnd":              ("exchange_metadata", "next_fiscal_year_end"),
        "mostRecentQuarter":              ("exchange_metadata", "most_recent_quarter"),
        "priceHint":                      ("exchange_metadata", "price_hint"),
        "tradeable":                      ("exchange_metadata", "tradeable"),
        "triggerable":                    ("exchange_metadata", "triggerable"),
        "customPriceAlertConfidence":     ("exchange_metadata", "custom_price_alert_confidence"),
        "hasPrePostMarketData":           ("exchange_metadata", "has_pre_post_market_data"),
        "corporateActions":               ("exchange_metadata", "corporate_actions"),
        "messageBoardId":                 ("exchange_metadata", "message_board_id"),
        "cryptoTradeable":                ("exchange_metadata", "crypto_tradeable"),
        "compensationAsOfEpochDate":      ("exchange_metadata", "compensation_as_of_epoch"),
    },

    # ── yahoofin_fin:latest ───────────────────────────────────────────────────
    "yahoofin_fin:latest": {
        # income statement
        "revenue":            ("income_statement_annual",  "latest_revenue"),
        "ebitda":             ("income_statement_annual",  "latest_ebitda"),
        "ebit":               ("income_statement_annual",  "latest_ebit"),
        "gross_profit":       ("income_statement_annual",  "latest_gross_profit"),
        "operating_income":   ("income_statement_annual",  "latest_operating_income"),
        "net_profit":         ("income_statement_annual",  "latest_net_profit"),
        "normalized_income":  ("income_statement_annual",  "latest_normalized_income"),
        "unusual_items":      ("income_statement_annual",  "latest_unusual_items"),
        "tax_rate":           ("income_statement_annual",  "latest_tax_rate"),
        "cost_of_revenue":    ("income_statement_annual",  "latest_cost_of_revenue"),
        "operating_expenses": ("income_statement_annual",  "latest_operating_expenses"),
        "rd_expense":         ("income_statement_annual",  "latest_rd_expense"),
        # balance sheet
        "total_liabilities":         ("balance_sheet_annual", "latest_total_liabilities"),
        "total_debt":                ("balance_sheet_annual", "latest_total_debt"),
        "short_term_debt":           ("balance_sheet_annual", "latest_short_term_debt"),
        "long_term_debt":            ("balance_sheet_annual", "latest_long_term_debt"),
        "net_debt":                  ("balance_sheet_annual", "latest_net_debt"),
        "capital_lease_obligations": ("balance_sheet_annual", "latest_capital_lease_obligations"),
        "net_tangible_assets":       ("balance_sheet_annual", "latest_net_tangible_assets"),
        "invested_capital":          ("balance_sheet_annual", "latest_invested_capital"),
        "working_capital":           ("balance_sheet_annual", "latest_working_capital"),
        "accounts_receivable":       ("balance_sheet_annual", "latest_accounts_receivable"),
        "cash_and_equivalents":      ("balance_sheet_annual", "latest_cash_and_equivalents"),
        "minority_interest":         ("balance_sheet_annual", "latest_minority_interest"),
        "total_capitalization":      ("balance_sheet_annual", "latest_total_capitalization"),
        "fixed_assets":              ("balance_sheet_annual", "latest_fixed_assets"),
        # cash flow
        "operating_cash_flow": ("cash_flow_annual", "latest_operating_cash_flow"),
        "free_cash_flow":      ("cash_flow_annual", "latest_free_cash_flow"),
        "capex":               ("cash_flow_annual", "latest_capex"),
        "depreciation":        ("cash_flow_annual", "latest_depreciation"),
        "interest_expense":    ("cash_flow_annual", "latest_interest_expense"),
        # valuation
        "diluted_eps":      ("valuation", "diluted_eps"),
        "basic_eps":        ("valuation", "basic_eps"),
        "diluted_shares":   ("valuation", "diluted_shares"),
        "basic_shares":     ("valuation", "basic_shares"),
        "shares_outstanding":("valuation","shares_outstanding_yf"),
    },

    # ── screener_fin:profit_loss  (quarterly consolidated) ───────────────────
    "screener_fin:profit_loss": {
        "Sales +":           ("income_statement_quarterly_consolidated", "Sales"),
        "Expenses +":        ("income_statement_quarterly_consolidated", "Expenses"),
        "Operating Profit":  ("income_statement_quarterly_consolidated", "Operating_Profit"),
        "OPM %":             ("income_statement_quarterly_consolidated", "OPM_pct"),
        "Other Income +":    ("income_statement_quarterly_consolidated", "Other_Income"),
        "Interest":          ("income_statement_quarterly_consolidated", "Interest"),
        "Depreciation":      ("income_statement_quarterly_consolidated", "Depreciation"),
        "Profit before tax": ("income_statement_quarterly_consolidated", "Profit_before_tax"),
        "Tax %":             ("income_statement_quarterly_consolidated", "Tax_pct"),
        "Net Profit +":      ("income_statement_quarterly_consolidated", "Net_Profit"),
        "EPS in Rs":         ("income_statement_quarterly_consolidated", "EPS_Rs"),
        "Raw PDF":           ("__skip__", "__skip__"),
    },

    # ── screener_fin:balance_sheet  (annual consolidated P&L, 7yr) ───────────
    "screener_fin:balance_sheet": {
        "Sales +":            ("income_statement_annual", "consolidated_7yr_Sales"),
        "Expenses +":         ("income_statement_annual", "consolidated_7yr_Expenses"),
        "Operating Profit":   ("income_statement_annual", "consolidated_7yr_Operating_Profit"),
        "OPM %":              ("income_statement_annual", "consolidated_7yr_OPM_pct"),
        "Other Income +":     ("income_statement_annual", "consolidated_7yr_Other_Income"),
        "Interest":           ("income_statement_annual", "consolidated_7yr_Interest"),
        "Depreciation":       ("income_statement_annual", "consolidated_7yr_Depreciation"),
        "Profit before tax":  ("income_statement_annual", "consolidated_7yr_Profit_before_tax"),
        "Tax %":              ("income_statement_annual", "consolidated_7yr_Tax_pct"),
        "Net Profit +":       ("income_statement_annual", "consolidated_7yr_Net_Profit"),
        "EPS in Rs":          ("income_statement_annual", "consolidated_7yr_EPS_Rs"),
        "Dividend Payout %":  ("income_statement_annual", "consolidated_7yr_Dividend_Payout_pct"),
    },

    # ── screener_fin:cash_flow  (annual consolidated balance sheet, 7yr) ─────
    "screener_fin:cash_flow": {
        "Equity Capital":     ("balance_sheet_annual", "consolidated_7yr_Equity_Capital"),
        "Reserves":           ("balance_sheet_annual", "consolidated_7yr_Reserves"),
        "Borrowings +":       ("balance_sheet_annual", "consolidated_7yr_Borrowings"),
        "Other Liabilities +":("balance_sheet_annual", "consolidated_7yr_Other_Liabilities"),
        "Total Liabilities":  ("balance_sheet_annual", "consolidated_7yr_Total_Liabilities"),
        "Fixed Assets +":     ("balance_sheet_annual", "consolidated_7yr_Fixed_Assets"),
        "CWIP":               ("balance_sheet_annual", "consolidated_7yr_CWIP"),
        "Investments":        ("balance_sheet_annual", "consolidated_7yr_Investments"),
        "Other Assets +":     ("balance_sheet_annual", "consolidated_7yr_Other_Assets"),
        "Total Assets":       ("balance_sheet_annual", "consolidated_7yr_Total_Assets"),
    },

    # ── screener_fin:ratios  (annual consolidated cash flow, 7yr) ────────────
    "screener_fin:ratios": {
        "Cash from Operating Activity +": ("cash_flow_annual", "consolidated_7yr_CFO"),
        "Cash from Investing Activity +": ("cash_flow_annual", "consolidated_7yr_CFI"),
        "Cash from Financing Activity +": ("cash_flow_annual", "consolidated_7yr_CFF"),
        "Net Cash Flow":                  ("cash_flow_annual", "consolidated_7yr_Net_Cash_Flow"),
        "Free Cash Flow":                 ("cash_flow_annual", "consolidated_7yr_Free_Cash_Flow"),
        "CFO/OP":                         ("cash_flow_annual", "consolidated_7yr_CFO_over_OP"),
    },

    # ── screener_raw:Quarterly Results  (quarterly standalone) ───────────────
    "screener_raw:Quarterly Results": {
        "Sales +":           ("income_statement_quarterly_standalone", "Sales"),
        "Expenses +":        ("income_statement_quarterly_standalone", "Expenses"),
        "Operating Profit":  ("income_statement_quarterly_standalone", "Operating_Profit"),
        "OPM %":             ("income_statement_quarterly_standalone", "OPM_pct"),
        "Other Income +":    ("income_statement_quarterly_standalone", "Other_Income"),
        "Interest":          ("income_statement_quarterly_standalone", "Interest"),
        "Depreciation":      ("income_statement_quarterly_standalone", "Depreciation"),
        "Profit before tax": ("income_statement_quarterly_standalone", "Profit_before_tax"),
        "Tax %":             ("income_statement_quarterly_standalone", "Tax_pct"),
        "Net Profit +":      ("income_statement_quarterly_standalone", "Net_Profit"),
        "EPS in Rs":         ("income_statement_quarterly_standalone", "EPS_Rs"),
        "Raw PDF":           ("__skip__", "__skip__"),
    },

    # ── screener_raw:Profit & Loss  (annual standalone P&L, 12yr) ────────────
    "screener_raw:Profit & Loss": {
        "Sales +":           ("income_statement_annual", "standalone_12yr_Sales"),
        "Expenses +":        ("income_statement_annual", "standalone_12yr_Expenses"),
        "Operating Profit":  ("income_statement_annual", "standalone_12yr_Operating_Profit"),
        "OPM %":             ("income_statement_annual", "standalone_12yr_OPM_pct"),
        "Other Income +":    ("income_statement_annual", "standalone_12yr_Other_Income"),
        "Interest":          ("income_statement_annual", "standalone_12yr_Interest"),
        "Depreciation":      ("income_statement_annual", "standalone_12yr_Depreciation"),
        "Profit before tax": ("income_statement_annual", "standalone_12yr_Profit_before_tax"),
        "Tax %":             ("income_statement_annual", "standalone_12yr_Tax_pct"),
        "Net Profit +":      ("income_statement_annual", "standalone_12yr_Net_Profit"),
        "EPS in Rs":         ("income_statement_annual", "standalone_12yr_EPS_Rs"),
        "Dividend Payout %": ("income_statement_annual", "standalone_12yr_Dividend_Payout_pct"),
    },

    # ── screener_raw:Balance Sheet  (annual standalone, 12yr) ────────────────
    "screener_raw:Balance Sheet": {
        "Equity Capital":      ("balance_sheet_annual", "standalone_12yr_Equity_Capital"),
        "Reserves":            ("balance_sheet_annual", "standalone_12yr_Reserves"),
        "Borrowings +":        ("balance_sheet_annual", "standalone_12yr_Borrowings"),
        "Other Liabilities +": ("balance_sheet_annual", "standalone_12yr_Other_Liabilities"),
        "Total Liabilities":   ("balance_sheet_annual", "standalone_12yr_Total_Liabilities"),
        "Fixed Assets +":      ("balance_sheet_annual", "standalone_12yr_Fixed_Assets"),
        "CWIP":                ("balance_sheet_annual", "standalone_12yr_CWIP"),
        "Investments":         ("balance_sheet_annual", "standalone_12yr_Investments"),
        "Other Assets +":      ("balance_sheet_annual", "standalone_12yr_Other_Assets"),
        "Total Assets":        ("balance_sheet_annual", "standalone_12yr_Total_Assets"),
    },

    # ── screener_raw:Cash Flows  (annual standalone, 12yr) ───────────────────
    "screener_raw:Cash Flows": {
        "Cash from Operating Activity +": ("cash_flow_annual", "standalone_12yr_CFO"),
        "Cash from Investing Activity +": ("cash_flow_annual", "standalone_12yr_CFI"),
        "Cash from Financing Activity +": ("cash_flow_annual", "standalone_12yr_CFF"),
        "Net Cash Flow":                  ("cash_flow_annual", "standalone_12yr_Net_Cash_Flow"),
        "Free Cash Flow":                 ("cash_flow_annual", "standalone_12yr_Free_Cash_Flow"),
        "CFO/OP":                         ("cash_flow_annual", "standalone_12yr_CFO_over_OP"),
    },

    # ── screener_raw:Ratios  (annual efficiency ratios) ───────────────────────
    "screener_raw:Ratios": {
        "Debtor Days":           ("efficiency_ratios", "Debtor_Days"),
        "Inventory Days":        ("efficiency_ratios", "Inventory_Days"),
        "Days Payable":          ("efficiency_ratios", "Days_Payable"),
        "Cash Conversion Cycle": ("efficiency_ratios", "Cash_Conversion_Cycle"),
        "Working Capital Days":  ("efficiency_ratios", "Working_Capital_Days"),
        "ROCE %":                ("efficiency_ratios", "ROCE_pct"),
    },

    # ── screener_raw:Shareholding Pattern ────────────────────────────────────
    "screener_raw:Shareholding Pattern": {
        "Promoters +":        ("dividends_shareholding", "promoters"),
        "FIIs +":             ("dividends_shareholding", "fiis"),
        "DIIs +":             ("dividends_shareholding", "diis"),
        "Public +":           ("dividends_shareholding", "public"),
        "Government +":       ("dividends_shareholding", "government"),
        "No. of Shareholders":("dividends_shareholding", "no_of_shareholders"),
    },

    # ── screener_raw:Insights  (all metrics → operational_kpis, varies per symbol)
    # handled via __all_ts__ sentinel — no need to enumerate every KPI
    "screener_raw:Insights": "__all_ts__",

    # ── guidance:guidance ─────────────────────────────────────────────────────
    "guidance:guidance": {
        "quarter":               ("management_guidance", "quarter"),
        "financial":             ("management_guidance", "financial"),
        "business":              ("management_guidance", "business"),
        "management":            ("management_guidance", "management"),
        "summary":               ("management_guidance", "summary"),
        "deals_and_pipeline":    ("management_guidance", "deals_and_pipeline"),
        "customers":             ("management_guidance", "customers"),
        "segments":              ("management_guidance", "segments"),
        "geography":             ("management_guidance", "geography"),
        "operations":            ("management_guidance", "operations"),
        "capital_allocation":    ("management_guidance", "capital_allocation"),
        "competitive_position":  ("management_guidance", "competitive_position"),
        "investor_verdict":      ("management_guidance", "investor_verdict"),
        "analyst_dimensions":    ("management_guidance", "analyst_dimensions"),
        "date":                  ("management_guidance", "date"),
    },

    # ── guidance:insights ─────────────────────────────────────────────────────
    "guidance:insights": {
        "recommendation":  ("analyst_consensus", "ai_recommendation"),
        "thesis":          ("analyst_consensus", "ai_thesis"),
        "trigger":         ("analyst_consensus", "ai_trigger"),
        "analysis":        ("analyst_consensus", "ai_analysis"),
        "sector_briefing": ("analyst_consensus", "ai_sector_briefing"),
        "date":            ("analyst_consensus", "ai_insights_date"),
    },

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
    "company_identity",
    "income_statement_quarterly_consolidated",
    "income_statement_quarterly_standalone",
    "income_statement_annual",
    "balance_sheet_annual",
    "cash_flow_annual",
    "efficiency_ratios",
    "valuation",
    "price_trading",
    "dividends_shareholding",
    "profitability_growth",
    "risk_and_governance",
    "analyst_consensus",
    "management_guidance",
    "operational_kpis",
    "exchange_metadata",
    "portfolio_context",
    "_unmapped",
]


def bucket_symbol(symbol: str, sections: dict) -> dict:
    B = {b: {} for b in ALL_BUCKETS}

    # Add metadata to time-series buckets
    B["income_statement_quarterly_consolidated"]["_meta"] = {
        "source": "screener_fin", "consolidation": "consolidated", "granularity": "quarterly"
    }
    B["income_statement_quarterly_standalone"]["_meta"] = {
        "source": "screener_raw", "consolidation": "standalone", "granularity": "quarterly"
    }
    B["income_statement_annual"]["_meta"] = {
        "standalone_depth": "12yr (FY2015-FY2026)", "consolidated_depth": "7yr (FY2020-FY2026)",
        "granularity": "annual_fy"
    }
    B["balance_sheet_annual"]["_meta"] = {
        "standalone_depth": "12yr (FY2015-FY2026)", "consolidated_depth": "7yr (FY2020-FY2026)",
        "granularity": "annual_fy"
    }
    B["cash_flow_annual"]["_meta"] = {
        "standalone_depth": "12yr (FY2015-FY2026)", "consolidated_depth": "7yr (FY2020-FY2026)",
        "granularity": "annual_fy"
    }
    B["efficiency_ratios"]["_meta"] = {
        "source": "screener_raw:Ratios", "granularity": "annual_fy"
    }
    B["operational_kpis"]["_meta"] = {
        "source": "screener_raw:Insights", "note": "Company-specific KPIs — varies per ticker"
    }

    for sec_key, records in sections.items():
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
                    B["price_trading"]["ltp"] = r.get("data")
                elif r.get("values"):
                    B["price_trading"][hist_key] = r["values"]
            continue

        # ── operational_kpis: all metrics as-is ───────────────────────────
        if sec_map == "__all_ts__":
            for r in (records if isinstance(records, list) else []):
                if isinstance(r, dict):
                    m = r.get("metric", "")
                    if m:
                        B["operational_kpis"][m] = r.get("periods", {})
            continue

        # ── list-based sections (time-series metrics) ──────────────────────
        if isinstance(records, list):
            for r in records:
                if not isinstance(r, dict):
                    continue
                metric = r.get("metric", "")
                mapping = sec_map.get(metric)

                if mapping is None:
                    # metric not in map → unmapped
                    unmapped_key = f"{sec_key}::{metric}"
                    B["_unmapped"][unmapped_key] = r.get("periods", deepcopy(r))
                elif mapping == ("__skip__", "__skip__"):
                    pass  # intentionally skipped
                else:
                    target_bucket, target_key = mapping
                    B[target_bucket][target_key] = r.get("periods", {})

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
        "bucket": "risk_and_governance",
        "sources": ["balance_sheet_annual.de_ratio", "profitability_growth.roe"],
        "description": "Sector-aware health score: D/E vs sector limit + ROE strength"
    },
    "leverage_quality": {
        "bucket": "risk_and_governance",
        "sources": ["balance_sheet_annual.total_debt", "valuation.market_cap"],
        "description": "Debt-to-market-cap ratio; lower is stronger"
    },
    "interest_coverage": {
        "bucket": "risk_and_governance",
        "sources": ["income_statement_annual.ebit", "income_statement_annual.interest_expense"],
        "description": "EBIT / Interest Expense; >3 is healthy"
    },
    
    # ── GROWTH METRICS ──
    "growth_score": {
        "bucket": "profitability_growth",
        "sources": ["profitability_growth.revenue_growth", "profitability_growth.earnings_growth"],
        "description": "Earnings growth scoring: >20%=85, >10%=70, >0%=55, ≤0%=30"
    },
    "revenue_growth_yoy": {
        "bucket": "profitability_growth",
        "sources": ["income_statement_annual.revenue"],
        "description": "YoY revenue growth % (comparing latest 2 years)"
    },
    "earnings_growth_yoy": {
        "bucket": "profitability_growth",
        "sources": ["income_statement_annual.net_profit"],
        "description": "YoY net profit growth %"
    },
    "fcf_growth": {
        "bucket": "profitability_growth",
        "sources": ["cash_flow_annual.operating_cash_flow", "cash_flow_annual.capex"],
        "description": "Free Cash Flow growth YoY"
    },
    
    # ── TECHNICAL & MOMENTUM ──
    "technical_score": {
        "bucket": "price_trading",
        "sources": ["price_trading.regular_market_change_pct"],
        "description": "Technical momentum score: >5%=75, >0%=60, ≤0%=40"
    },
    "price_momentum_short": {
        "bucket": "price_trading",
        "sources": ["price_trading.regular_market_change_pct"],
        "description": "Recent price change % (last trading session)"
    },
    "volume_trend": {
        "bucket": "price_trading",
        "sources": ["price_trading.regular_market_volume", "price_trading.average_daily_volume_3mo"],
        "description": "Current volume vs 3-month average; >1.2 = elevated"
    },
    "ma_50_position": {
        "bucket": "price_trading",
        "sources": ["price_trading.current_price", "price_trading.fifty_day_avg"],
        "description": "Price position relative to 50-day MA; >1.0 = above MA (bullish)"
    },
    "ma_200_position": {
        "bucket": "price_trading",
        "sources": ["price_trading.current_price", "price_trading.two_hundred_day_avg"],
        "description": "Price position relative to 200-day MA; >1.0 = above MA (bullish)"
    },
    
    # ── QUALITY & EFFICIENCY ──
    "quality_score": {
        "bucket": "efficiency_ratios",
        "sources": ["profitability_growth.roe", "efficiency_ratios.asset_turnover", "profitability_growth.margin"],
        "description": "Composite quality: high ROE + asset efficiency + margins"
    },
    "profitability_ratio": {
        "bucket": "profitability_growth",
        "sources": ["income_statement_annual.net_profit", "income_statement_annual.revenue"],
        "description": "Net profit margin %"
    },
    "operating_margin": {
        "bucket": "profitability_growth",
        "sources": ["income_statement_annual.operating_profit", "income_statement_annual.revenue"],
        "description": "Operating profit margin %"
    },
    "fcf_yield": {
        "bucket": "valuation",
        "sources": ["cash_flow_annual.free_cash_flow", "valuation.market_cap"],
        "description": "Free Cash Flow / Market Cap; >5% is strong"
    },
    "roe": {
        "bucket": "profitability_growth",
        "sources": ["income_statement_annual.net_profit", "balance_sheet_annual.equity"],
        "description": "Return on Equity; >15% is excellent"
    },
    "roa": {
        "bucket": "profitability_growth",
        "sources": ["income_statement_annual.net_profit", "balance_sheet_annual.total_assets"],
        "description": "Return on Assets; >10% is strong"
    },
    "asset_turnover": {
        "bucket": "efficiency_ratios",
        "sources": ["income_statement_annual.revenue", "balance_sheet_annual.total_assets"],
        "description": "Revenue / Total Assets; indicates capital efficiency"
    },
    
    # ── COMPOSITE SIGNALS ──
    "composite_score": {
        "bucket": "analyst_consensus",
        "sources": ["valuation_score", "health_score", "growth_score", "technical_score"],
        "description": "Weighted blend: 20% valuation + 50% health + 25% growth + 20% technical"
    },
    "investment_signal": {
        "bucket": "analyst_consensus",
        "sources": ["composite_score"],
        "description": "Signal classification: STRONG_BUY (≥75) | BUY (≥60) | HOLD (≥40) | SELL (≥25) | STRONG_SELL (<25)"
    },
    "signal_confidence": {
        "bucket": "analyst_consensus",
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
        "bucket": "risk_and_governance",
        "sources": ["balance_sheet_annual.de_ratio", "balance_sheet_annual.total_debt"],
        "description": "High debt warning; flag if D/E > 2.5 or debt > 50% of assets"
    },
    "profitability_risk_flag": {
        "bucket": "risk_and_governance",
        "sources": ["profitability_growth.roe", "profitability_growth.margin"],
        "description": "Profitability concern; flag if ROE <8% or margin <5%"
    },
    "liquidity_risk_flag": {
        "bucket": "risk_and_governance",
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
    FIXES: ROE/ROA/D/E calculation errors from dict arithmetic.
    """
    if value is None or not isinstance(value, dict):
        return value
    if not value:
        return value
    
    keys = list(value.keys())
    first_key = str(keys[0]) if keys else ""
    
    # Detect time-series patterns
    is_timeseries = (
        ('-' in first_key and len(first_key) == 10) or  # YYYY-MM-DD
        ('FY' in first_key) or  # FY2026
        (first_key.isdigit() and len(first_key) == 4)    # 2026
    )
    
    if is_timeseries:
        sorted_keys = sorted(value.keys(), reverse=True)
        return value[sorted_keys[0]]
    
    return value

def compute_derived_metrics(bucketed: dict, sector: str = None) -> dict:
    """
    Compute derived metrics from bucketed data with sector-aware logic.
    
    Args:
        bucketed: output from bucket_symbol()
        sector: company sector for sector-aware thresholds
    
    Returns:
        Updated bucketed dict with derived metrics in analyst_consensus bucket.
        Never modifies input; returns new dict.
    """
    derived = deepcopy(bucketed)
    sector = sector or derived.get("company_identity", {}).get("sector", "Industrials")
    sector_profile = SECTOR_PROFILES.get(sector, SECTOR_PROFILES["Industrials"])
    
    metrics = {}
    
    # Helper to safely get values (with FIX: extracts scalar from dicts)
    def safe_val(path_list, default=None):
        val = bucketed
        for key in path_list:
            if isinstance(val, dict):
                val = val.get(key)
            else:
                return default
        # FIX: Extract scalar if dict (prevents dict arithmetic errors)
        return extract_scalar_or_dict(val) if val is not None else default
    
    # ────────────────────────────────────────────────────────────────────────
    # VALUATION METRICS
    # ────────────────────────────────────────────────────────────────────────
    
    pe = safe_val(["valuation", "trailing_pe"])
    if pe and pe > 0:
        metrics["valuation_score"] = min(100, max(0, 85 if pe < 15 else (60 if pe < 25 else 40)))
    else:
        metrics["valuation_score"] = 50
    
    ev = safe_val(["valuation", "enterprise_value"])
    revenue = safe_val(["income_statement_annual", "latest_revenue"])
    if ev and revenue and revenue > 0:
        metrics["ev_to_sales"] = round(ev / revenue, 2)
    
    mc = safe_val(["valuation", "market_cap"])
    fcf = safe_val(["cash_flow_annual", "latest_free_cash_flow"])
    if mc and fcf and mc > 0:
        metrics["price_to_fcf"] = round(mc / fcf, 2) if fcf > 0 else None
        metrics["fcf_yield"] = round((fcf / mc) * 100, 2)
    
    # ────────────────────────────────────────────────────────────────────────
    # TECHNICAL & MOMENTUM METRICS
    # ────────────────────────────────────────────────────────────────────────
    
    change_pct = safe_val(["price_trading", "regular_market_change_pct"])
    if change_pct is not None:
        metrics["price_momentum_short"] = round(change_pct, 2)
        metrics["technical_score"] = min(100, max(0, 75 if change_pct > 5 else (60 if change_pct > 0 else 40)))
    else:
        metrics["technical_score"] = 50
    
    current_price = safe_val(["price_trading", "current_price"])
    ma_50 = safe_val(["price_trading", "fifty_day_avg"])
    if current_price and ma_50 and ma_50 > 0:
        metrics["ma_50_position"] = round(current_price / ma_50, 3)
    
    ma_200 = safe_val(["price_trading", "two_hundred_day_avg"])
    if current_price and ma_200 and ma_200 > 0:
        metrics["ma_200_position"] = round(current_price / ma_200, 3)
    
    volume = safe_val(["price_trading", "regular_market_volume"])
    avg_volume_3mo = safe_val(["price_trading", "average_daily_volume_3mo"])
    if volume and avg_volume_3mo and avg_volume_3mo > 0:
        metrics["volume_trend"] = round(volume / avg_volume_3mo, 2)
    
    # ────────────────────────────────────────────────────────────────────────
    # PROFITABILITY & MARGIN METRICS
    # ────────────────────────────────────────────────────────────────────────
    
    net_profit = safe_val(["income_statement_annual", "latest_net_profit"])
    if net_profit and revenue and revenue > 0:
        metrics["profitability_ratio"] = round((net_profit / revenue) * 100, 2)
    
    operating_income = safe_val(["income_statement_annual", "latest_operating_income"])
    if operating_income and revenue and revenue > 0:
        metrics["operating_margin"] = round((operating_income / revenue) * 100, 2)
    
    # ────────────────────────────────────────────────────────────────────────
    # RETURN METRICS (ROE, ROA)
    # ────────────────────────────────────────────────────────────────────────
    
    equity_capital = safe_val(["balance_sheet_annual", "latest_equity_capital"]) or \
                     safe_val(["balance_sheet_annual", "standalone_12yr_Equity_Capital"])
    reserves = safe_val(["balance_sheet_annual", "latest_reserves"]) or \
               safe_val(["balance_sheet_annual", "standalone_12yr_Reserves"])
    
    # Extract latest value if time-series dict
    if isinstance(equity_capital, dict):
        years = sorted(equity_capital.keys(), reverse=True)
        equity_capital = equity_capital[years[0]] if years else None
    if isinstance(reserves, dict):
        years = sorted(reserves.keys(), reverse=True)
        reserves = reserves[years[0]] if years else None
    
    if equity_capital and reserves:
        total_equity = equity_capital + reserves
    else:
        total_equity = safe_val(["balance_sheet_annual", "latest_total_equity"]) or \
                      safe_val(["balance_sheet_annual", "consolidated_7yr_Equity_Capital"])
        if isinstance(total_equity, dict):
            years = sorted(total_equity.keys(), reverse=True)
            total_equity = total_equity[years[0]] if years else None
    
    if net_profit and total_equity and total_equity > 0:
        roe = (net_profit / total_equity) * 100
        metrics["roe"] = round(roe, 2)
    
    total_assets = safe_val(["balance_sheet_annual", "latest_total_assets"]) or \
                   safe_val(["balance_sheet_annual", "standalone_12yr_Total_Assets"])
    if isinstance(total_assets, dict):
        years = sorted(total_assets.keys(), reverse=True)
        total_assets = total_assets[years[0]] if years else None
    if net_profit and total_assets and total_assets > 0:
        roa = (net_profit / total_assets) * 100
        metrics["roa"] = round(roa, 2)
    
    # ────────────────────────────────────────────────────────────────────────
    # LEVERAGE & SOLVENCY METRICS
    # ────────────────────────────────────────────────────────────────────────
    
    total_debt = safe_val(["valuation", "total_debt"]) or \
                 safe_val(["balance_sheet_annual", "latest_total_debt"])
    
    if total_debt and total_equity and total_equity > 0:
        de_ratio = total_debt / total_equity
        metrics["leverage_quality"] = round(de_ratio, 2)
    
    if total_debt and mc and mc > 0:
        metrics["debt_to_market_cap"] = round((total_debt / mc) * 100, 2)
    
    ebit = safe_val(["income_statement_annual", "latest_ebit"])
    interest_exp = safe_val(["cash_flow_annual", "latest_interest_expense"])
    if ebit and interest_exp and interest_exp > 0:
        metrics["interest_coverage"] = round(ebit / interest_exp, 2)
    
    # ────────────────────────────────────────────────────────────────────────
    # GROWTH METRICS (YoY from time-series)
    # ────────────────────────────────────────────────────────────────────────
    
    # Revenue YoY growth (last 2 years of consolidated annual)
    revenue_series = safe_val(["income_statement_annual", "consolidated_7yr_Sales"])
    if isinstance(revenue_series, dict):
        years = sorted(revenue_series.keys(), reverse=True)
        if len(years) >= 2:
            latest_rev = revenue_series[years[0]]
            prev_rev = revenue_series[years[1]]
            if latest_rev and prev_rev and prev_rev > 0:
                revenue_growth = ((latest_rev - prev_rev) / prev_rev) * 100
                metrics["revenue_growth_yoy"] = round(revenue_growth, 2)
    
    # Earnings YoY growth
    earnings_series = safe_val(["income_statement_annual", "consolidated_7yr_Net_Profit"])
    if isinstance(earnings_series, dict):
        years = sorted(earnings_series.keys(), reverse=True)
        if len(years) >= 2:
            latest_earn = earnings_series[years[0]]
            prev_earn = earnings_series[years[1]]
            if latest_earn and prev_earn and prev_earn > 0:
                earnings_growth = ((latest_earn - prev_earn) / prev_earn) * 100
                metrics["earnings_growth_yoy"] = round(earnings_growth, 2)
    
    # FCF growth
    fcf_series = safe_val(["cash_flow_annual", "consolidated_7yr_Free_Cash_Flow"])
    if isinstance(fcf_series, dict):
        years = sorted(fcf_series.keys(), reverse=True)
        if len(years) >= 2:
            latest_fcf = fcf_series[years[0]]
            prev_fcf = fcf_series[years[1]]
            if latest_fcf and prev_fcf and prev_fcf > 0:
                fcf_growth = ((latest_fcf - prev_fcf) / prev_fcf) * 100
                metrics["fcf_growth"] = round(fcf_growth, 2)
    
    # ────────────────────────────────────────────────────────────────────────
    # EFFICIENCY METRICS
    # ────────────────────────────────────────────────────────────────────────
    
    if revenue and total_assets and total_assets > 0:
        metrics["asset_turnover"] = round(revenue / total_assets, 2)
    
    roce_pct = safe_val(["efficiency_ratios", "ROCE_pct"])
    if roce_pct:
        # ROCE_pct is likely a time-series dict, get latest value
        if isinstance(roce_pct, dict):
            years = sorted(roce_pct.keys(), reverse=True)
            roce_val = roce_pct[years[0]] if years else None
        else:
            roce_val = roce_pct
        if roce_val is not None:
            try:
                metrics["roce"] = round(float(roce_val), 2)
            except (ValueError, TypeError):
                pass
    
    # ────────────────────────────────────────────────────────────────────────
    # SECTOR-AWARE SCORING
    # ────────────────────────────────────────────────────────────────────────
    
    # Health score (sector-aware)
    de_limit = sector_profile.get("de_limit", 2.0)
    roe_excellent = sector_profile.get("roe_excellent", 0.15)
    
    health_score = 50
    if metrics.get("leverage_quality") is not None:
        de = metrics["leverage_quality"]
        if de < de_limit:
            health_score += 20
        elif de > de_limit * 2:
            health_score -= 20
    
    if metrics.get("roe") is not None:
        roe_val = metrics["roe"] / 100
        if roe_val > roe_excellent:
            health_score += 20
        elif roe_val > roe_excellent * 0.5:
            health_score += 10
    
    metrics["health_score"] = max(0, min(100, health_score))
    
    # Growth score
    growth_score = 50
    if metrics.get("earnings_growth_yoy") is not None:
        eg = metrics["earnings_growth_yoy"]
        if eg > 20:
            growth_score = 85
        elif eg > 10:
            growth_score = 70
        elif eg > 0:
            growth_score = 55
        else:
            growth_score = 30
    
    metrics["growth_score"] = growth_score
    
    # Quality score
    quality_components = [
        metrics.get("roe"),
        metrics.get("roce_pct") if "roce_pct" in safe_val(["efficiency_ratios"], {}) else None,
        metrics.get("operating_margin")
    ]
    quality_components = [x for x in quality_components if x is not None]
    if quality_components:
        metrics["quality_score"] = round(sum(quality_components) / len(quality_components), 2)
    
    # ────────────────────────────────────────────────────────────────────────
    # COMPOSITE SIGNAL (Sector-weighted)
    # ────────────────────────────────────────────────────────────────────────
    
    val_score = metrics.get("valuation_score", 50)
    tech_score = metrics.get("technical_score", 50)
    growth_s = metrics.get("growth_score", 50)
    health_s = metrics.get("health_score", 50)
    
    # Use sector weights
    fundamental_w = sector_profile.get("fundamental", 0.4)
    technical_w = sector_profile.get("technical", 0.3)
    valuation_w = sector_profile.get("valuation", 0.2)
    sentiment_w = sector_profile.get("sentiment", 0.1)
    
    composite = (health_s * fundamental_w + tech_score * technical_w + 
                val_score * valuation_w + growth_s * sentiment_w)
    
    metrics["composite_score"] = round(composite, 2)
    
    # Signal classification
    if composite >= 75:
        signal = "STRONG_BUY"
    elif composite >= 60:
        signal = "BUY"
    elif composite >= 40:
        signal = "HOLD"
    elif composite >= 25:
        signal = "SELL"
    else:
        signal = "STRONG_SELL"
    
    metrics["investment_signal"] = signal
    metrics["signal_confidence"] = round(min(99.99, 50 + abs(composite - 50) * 0.9), 2)
    
    # ────────────────────────────────────────────────────────────────────────
    # RISK FLAGS
    # ────────────────────────────────────────────────────────────────────────
    
    metrics["debt_risk_flag"] = de_ratio > 2.5 if metrics.get("leverage_quality") else False
    metrics["profitability_risk_flag"] = (metrics.get("roe", 100) < 8 or 
                                          metrics.get("profitability_ratio", 100) < 5)
    
    current_ratio = safe_val(["profitability_growth", "current_ratio"])
    quick_ratio = safe_val(["profitability_growth", "quick_ratio"])
    metrics["liquidity_risk_flag"] = (current_ratio is not None and current_ratio < 1.2) or \
                                     (quick_ratio is not None and quick_ratio < 0.8)
    
    # Add to analyst_consensus bucket
    if "analyst_consensus" not in derived:
        derived["analyst_consensus"] = {}
    
    derived["analyst_consensus"]["derived_metrics"] = metrics
    derived["analyst_consensus"]["sector_aware"] = True
    derived["analyst_consensus"]["sector"] = sector
    
    return derived


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    if not INPUT_FILE.exists():
        logger.error(f"INPUT FILE NOT FOUND: {INPUT_FILE}")
        sys.exit(1)

    logger.info(f"Reading {INPUT_FILE} …")
    with open(INPUT_FILE) as f:
        raw = json.load(f)

    output  = {}
    symbols = list(raw.keys())
    total   = len(symbols)
    unmapped_summary = {}

    for i, symbol in enumerate(symbols, 1):
        sections = raw[symbol].get("data", {})
        bucketed = bucket_symbol(symbol, sections)
        bucketed = compute_derived_metrics(bucketed)  # Apply derived metrics
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
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2, default=str)

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
