# Live NAV Fetch Summary

Fetched schemes: 6
NAV rows fetched: 19906

## Requested vs API Metadata

| Scheme Code | Requested Name | API Scheme Name | Fund House | Scheme Category | Name Mismatch |
|---:|---|---|---|---|---|
| 125497 | HDFC Top 100 Direct | SBI Small Cap Fund - Direct Plan - Growth | SBI Mutual Fund | Equity Scheme - Small Cap Fund | True |
| 119551 | SBI Bluechip | Aditya Birla Sun Life Banking & PSU Debt Fund  - DIRECT - IDCW | Aditya Birla Sun Life Mutual Fund | Debt Scheme - Banking and PSU Fund | True |
| 120503 | ICICI Bluechip | Axis ELSS Tax Saver Fund - Direct Plan - Growth Option | Axis Mutual Fund | Equity Scheme - ELSS | True |
| 118632 | Nippon Large Cap | Nippon India Large Cap Fund - Direct Plan Growth Plan - Growth Option | Nippon India Mutual Fund | Equity Scheme - Large Cap Fund | False |
| 119092 | Axis Bluechip | HDFC Money Market Fund - Growth Option - Direct Plan | HDFC Mutual Fund | Debt Scheme - Money Market Fund | True |
| 120841 | Kotak Bluechip | quant Mid Cap Fund - Growth Option - Direct Plan | quant Mutual Fund | Equity Scheme - Mid Cap Fund | True |

## Data Quality Notes

- Requested labels do not match mfapi metadata for these scheme codes:
  - 125497: requested 'HDFC Top 100 Direct', API returned 'SBI Small Cap Fund - Direct Plan - Growth'.
  - 119551: requested 'SBI Bluechip', API returned 'Aditya Birla Sun Life Banking & PSU Debt Fund  - DIRECT - IDCW'.
  - 120503: requested 'ICICI Bluechip', API returned 'Axis ELSS Tax Saver Fund - Direct Plan - Growth Option'.
  - 119092: requested 'Axis Bluechip', API returned 'HDFC Money Market Fund - Growth Option - Direct Plan'.
  - 120841: requested 'Kotak Bluechip', API returned 'quant Mid Cap Fund - Growth Option - Direct Plan'.
