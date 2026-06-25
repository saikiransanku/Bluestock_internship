# Data Ingestion Summary

Raw CSV files found: 8

## Dataset Inventory

| File | Rows | Columns | Duplicate Rows | Missing Cells |
|---|---:|---:|---:|---:|
| axis_bluechip_nav.csv | 3582 | 10 | 0 | 0 |
| fund_master.csv | 6 | 14 | 0 | 11 |
| hdfc_top_100_nav.csv | 3108 | 10 | 0 | 0 |
| icici_bluechip_nav.csv | 3324 | 10 | 0 | 0 |
| kotak_bluechip_nav.csv | 3318 | 10 | 0 | 0 |
| nav_history.csv | 19900 | 10 | 0 | 0 |
| nippon_large_cap_nav.csv | 3315 | 10 | 0 | 0 |
| sbi_bluechip_nav.csv | 3253 | 10 | 0 | 0 |

## Notes

- Expected 10 raw CSV datasets, but found 8. Missing source files must be supplied before those datasets can be cleaned.
- fund_master.csv: 11 missing cell(s).
- icici_bluechip_nav.csv: 1 invalid NAV value(s).
- nav_history.csv: 1 invalid NAV value(s).
- Fund houses: 6 unique value(s).
- Categories: 6 unique value(s).
- Sub-categories: 6 unique value(s).
- Risk grades: 0 unique value(s).
- AMFI scheme codes in this dataset are numeric identifiers. 6/6 are numeric and 6/6 are six digits. The sample does not show an embedded fund-house/category pattern.
- AMFI validation passed: every fund_master code exists in nav_history.
