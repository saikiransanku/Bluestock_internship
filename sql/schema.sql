PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS fact_aum;
DROP TABLE IF EXISTS fact_performance;
DROP TABLE IF EXISTS fact_transactions;
DROP TABLE IF EXISTS fact_nav;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_fund;

CREATE TABLE dim_fund (
    scheme_code INTEGER PRIMARY KEY,
    requested_name TEXT,
    scheme_name TEXT NOT NULL,
    fund_house TEXT,
    scheme_type TEXT,
    scheme_category TEXT,
    category_group TEXT,
    sub_category TEXT,
    risk_grade TEXT,
    isin_growth TEXT,
    isin_div_reinvestment TEXT,
    source_url TEXT,
    fetched_at TEXT,
    requested_name_mismatch INTEGER NOT NULL DEFAULT 0 CHECK (requested_name_mismatch IN (0, 1))
);

CREATE TABLE dim_date (
    date_key INTEGER PRIMARY KEY,
    date TEXT NOT NULL UNIQUE,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name TEXT NOT NULL,
    day INTEGER NOT NULL,
    day_of_week TEXT NOT NULL,
    is_weekend INTEGER NOT NULL CHECK (is_weekend IN (0, 1))
);

CREATE TABLE fact_nav (
    nav_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    nav REAL NOT NULL CHECK (nav > 0),
    is_forward_filled INTEGER NOT NULL DEFAULT 0 CHECK (is_forward_filled IN (0, 1)),
    FOREIGN KEY (scheme_code) REFERENCES dim_fund (scheme_code),
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key),
    UNIQUE (scheme_code, date_key)
);

CREATE TABLE fact_transactions (
    transaction_id TEXT PRIMARY KEY,
    investor_id TEXT,
    scheme_code INTEGER,
    date_key INTEGER,
    transaction_type TEXT CHECK (transaction_type IN ('SIP', 'Lumpsum', 'Redemption')),
    amount REAL CHECK (amount > 0),
    units REAL,
    state TEXT,
    kyc_status TEXT CHECK (kyc_status IN ('Verified', 'Pending', 'Rejected', 'Unknown')),
    source_file TEXT,
    FOREIGN KEY (scheme_code) REFERENCES dim_fund (scheme_code),
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key)
);

CREATE TABLE fact_performance (
    performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    return_1y REAL,
    return_3y REAL,
    return_5y REAL,
    expense_ratio REAL CHECK (expense_ratio IS NULL OR expense_ratio BETWEEN 0.1 AND 2.5),
    anomaly_flags TEXT,
    source_reference TEXT,
    FOREIGN KEY (scheme_code) REFERENCES dim_fund (scheme_code),
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key),
    UNIQUE (scheme_code, date_key)
);

CREATE TABLE fact_aum (
    aum_id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code INTEGER NOT NULL,
    date_key INTEGER NOT NULL,
    aum_crore REAL NOT NULL CHECK (aum_crore >= 0),
    source_reference TEXT,
    FOREIGN KEY (scheme_code) REFERENCES dim_fund (scheme_code),
    FOREIGN KEY (date_key) REFERENCES dim_date (date_key),
    UNIQUE (scheme_code, date_key)
);
