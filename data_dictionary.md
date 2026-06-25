# Bluestock Mutual Fund Data Dictionary

## Source Files

| File | Source | Grain | Notes |
|---|---|---|---|
| `data/raw/fund_master.csv` | mfapi metadata from `live_nav_fetch.py` | One row per AMFI scheme code | Includes requested label and API-returned scheme name. |
| `data/raw/nav_history.csv` | mfapi NAV endpoint | One row per scheme per reported NAV date | Combined history for the six requested scheme codes. |
| `data/raw/*_nav.csv` | mfapi NAV endpoint | One row per scheme per reported NAV date | Individual scheme extracts. |
| `data/raw/investor_transactions.csv` | Provided source file | One row per investor transaction | Missing in the current workspace. |
| `data/raw/scheme_performance.csv` | Provided source file | One row per scheme performance snapshot | Missing in the current workspace; returns are derived from NAV history. |
| AUM source file | Provided source file | One row per scheme per AUM date | Missing in the current workspace; AUM table is schema-only. |

## Processed Files

| File | Definition |
|---|---|
| `fund_master_clean.csv` | Cleaned fund dimension with category split and risk grade placeholder. |
| `nav_history_clean.csv` | Cleaned combined NAV history, sorted by scheme/date and daily forward-filled for holidays/weekends. |
| `*_nav_clean.csv` | Cleaned individual NAV histories for each fetched scheme. |
| `investor_transactions_clean.csv` | Cleaned transaction fact source; schema-only until raw transactions are supplied. |
| `scheme_performance_clean.csv` | Performance snapshot; derived from cleaned NAV when raw performance is missing. |
| `fund_aum_clean.csv` | AUM fact source; schema-only until raw AUM is supplied. |
| `dim_date_clean.csv` | Date dimension generated from processed fact dates. |

## SQLite Tables

### `dim_fund`

| Column | Type | Business Definition | Source |
|---|---|---|---|
| `scheme_code` | INTEGER | AMFI scheme identifier and primary key. | mfapi `meta.scheme_code` |
| `requested_name` | TEXT | Human-readable scheme label requested in the assignment. | `live_nav_fetch.py` scheme list |
| `scheme_name` | TEXT | Scheme name returned by mfapi. | mfapi `meta.scheme_name` |
| `fund_house` | TEXT | Asset management company or fund house. | mfapi `meta.fund_house` |
| `scheme_type` | TEXT | Open-ended/close-ended scheme type. | mfapi `meta.scheme_type` |
| `scheme_category` | TEXT | Full scheme category string returned by mfapi. | mfapi `meta.scheme_category` |
| `category_group` | TEXT | Category before the first separator, for example `Equity Scheme`. | Derived |
| `sub_category` | TEXT | Category after the first separator, for example `Large Cap Fund`. | Derived |
| `risk_grade` | TEXT | Risk grade from source, or `Unavailable` when absent. | Source/placeholder |
| `isin_growth` | TEXT | ISIN for growth option when available. | mfapi metadata |
| `isin_div_reinvestment` | TEXT | ISIN for dividend reinvestment option when available. | mfapi metadata |
| `source_url` | TEXT | API endpoint used to fetch the scheme. | Derived |
| `fetched_at` | TEXT | UTC timestamp of fetch. | Derived |
| `requested_name_mismatch` | INTEGER | 1 when requested label differs from API-returned scheme name. | Derived |

### `dim_date`

| Column | Type | Business Definition | Source |
|---|---|---|---|
| `date_key` | INTEGER | Calendar key in `YYYYMMDD` format. | Derived |
| `date` | TEXT | Calendar date in ISO format. | Derived |
| `year` | INTEGER | Calendar year. | Derived |
| `quarter` | INTEGER | Calendar quarter. | Derived |
| `month` | INTEGER | Calendar month number. | Derived |
| `month_name` | TEXT | Calendar month name. | Derived |
| `day` | INTEGER | Day of month. | Derived |
| `day_of_week` | TEXT | Day name. | Derived |
| `is_weekend` | INTEGER | 1 for Saturday/Sunday, else 0. | Derived |

### `fact_nav`

| Column | Type | Business Definition | Source |
|---|---|---|---|
| `nav_id` | INTEGER | Surrogate primary key. | SQLite |
| `scheme_code` | INTEGER | Fund foreign key. | `nav_history_clean.csv` |
| `date_key` | INTEGER | Date foreign key. | Derived from NAV date |
| `nav` | REAL | Net asset value; must be greater than 0. | mfapi NAV data |
| `is_forward_filled` | INTEGER | 1 when a holiday/weekend row was generated from prior NAV. | Derived |

### `fact_transactions`

| Column | Type | Business Definition | Source |
|---|---|---|---|
| `transaction_id` | TEXT | Unique transaction identifier. | Raw transactions or generated when missing |
| `investor_id` | TEXT | Investor/customer identifier. | Raw transactions |
| `scheme_code` | INTEGER | Fund foreign key. | Raw transactions |
| `date_key` | INTEGER | Transaction date foreign key. | Raw transactions |
| `transaction_type` | TEXT | Standardized transaction type: `SIP`, `Lumpsum`, or `Redemption`. | Raw transactions |
| `amount` | REAL | Transaction amount; must be greater than 0. | Raw transactions |
| `units` | REAL | Mutual fund units involved in transaction. | Raw transactions |
| `state` | TEXT | Investor state/region. | Raw transactions |
| `kyc_status` | TEXT | Standardized KYC status: `Verified`, `Pending`, `Rejected`, or `Unknown`. | Raw transactions |
| `source_file` | TEXT | Source file name. | Derived |

### `fact_performance`

| Column | Type | Business Definition | Source |
|---|---|---|---|
| `performance_id` | INTEGER | Surrogate primary key. | SQLite |
| `scheme_code` | INTEGER | Fund foreign key. | Performance source or NAV-derived output |
| `date_key` | INTEGER | Performance as-of date foreign key. | Derived |
| `return_1y` | REAL | One-year return percentage. | Source or derived from NAV |
| `return_3y` | REAL | Three-year return percentage. | Source or derived from NAV |
| `return_5y` | REAL | Five-year return percentage. | Source or derived from NAV |
| `expense_ratio` | REAL | Expense ratio percentage; expected range is 0.1 to 2.5. | Raw performance when available |
| `anomaly_flags` | TEXT | Semicolon-separated data quality flags. | Derived |
| `source_reference` | TEXT | Source or derivation note. | Derived |

### `fact_aum`

| Column | Type | Business Definition | Source |
|---|---|---|---|
| `aum_id` | INTEGER | Surrogate primary key. | SQLite |
| `scheme_code` | INTEGER | Fund foreign key. | Raw AUM source |
| `date_key` | INTEGER | AUM date foreign key. | Raw AUM source |
| `aum_crore` | REAL | Assets under management in crore rupees. | Raw AUM source |
| `source_reference` | TEXT | Source file or note. | Derived |
