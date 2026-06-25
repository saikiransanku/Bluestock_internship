from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text


DB_PATH = Path("bluestock_mf.db")
SCHEMA_PATH = Path("sql/schema.sql")
PROCESSED_DIR = Path("data/processed")
REPORT_PATH = Path("reports/sqlite_load_summary.md")


def date_key(series: pd.Series) -> pd.Series:
    dates = pd.to_datetime(series, errors="coerce")
    return dates.dt.strftime("%Y%m%d").astype("Int64")


def build_dim_date(*date_series: pd.Series) -> pd.DataFrame:
    all_dates = pd.concat([pd.to_datetime(series, errors="coerce") for series in date_series])
    all_dates = all_dates.dropna().drop_duplicates().sort_values()
    dim_date = pd.DataFrame({"date": all_dates})
    dim_date["date_key"] = dim_date["date"].dt.strftime("%Y%m%d").astype(int)
    dim_date["year"] = dim_date["date"].dt.year
    dim_date["quarter"] = dim_date["date"].dt.quarter
    dim_date["month"] = dim_date["date"].dt.month
    dim_date["month_name"] = dim_date["date"].dt.month_name()
    dim_date["day"] = dim_date["date"].dt.day
    dim_date["day_of_week"] = dim_date["date"].dt.day_name()
    dim_date["is_weekend"] = dim_date["date"].dt.dayofweek.isin([5, 6]).astype(int)
    dim_date["date"] = dim_date["date"].dt.strftime("%Y-%m-%d")
    return dim_date[
        [
            "date_key",
            "date",
            "year",
            "quarter",
            "month",
            "month_name",
            "day",
            "day_of_week",
            "is_weekend",
        ]
    ]


def read_processed_csv(name: str, columns: list[str] | None = None) -> pd.DataFrame:
    path = PROCESSED_DIR / name
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame(columns=columns or [])


def initialize_database(engine) -> None:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with engine.begin() as connection:
        for statement in schema_sql.split(";"):
            if statement.strip():
                connection.execute(text(statement))


def load_database() -> dict[str, tuple[int, int]]:
    engine = create_engine(f"sqlite:///{DB_PATH}")
    initialize_database(engine)

    fund = read_processed_csv("fund_master_clean.csv")
    nav = read_processed_csv("nav_history_clean.csv")
    transactions = read_processed_csv("investor_transactions_clean.csv")
    performance = read_processed_csv("scheme_performance_clean.csv")
    aum = read_processed_csv("fund_aum_clean.csv")

    if fund.empty:
        raise ValueError("data/processed/fund_master_clean.csv has no rows.")
    if nav.empty:
        raise ValueError("data/processed/nav_history_clean.csv has no rows.")

    dim_fund = fund[
        [
            "scheme_code",
            "requested_name",
            "scheme_name",
            "fund_house",
            "scheme_type",
            "scheme_category",
            "category_group",
            "sub_category",
            "risk_grade",
            "isin_growth",
            "isin_div_reinvestment",
            "source_url",
            "fetched_at",
            "requested_name_mismatch",
        ]
    ].copy()
    dim_fund["requested_name_mismatch"] = (
        dim_fund["requested_name_mismatch"].fillna(False).astype(bool).astype(int)
    )

    date_inputs = [nav["date"]]
    if not transactions.empty and "transaction_date" in transactions:
        date_inputs.append(transactions["transaction_date"])
    if not performance.empty and "as_of_date" in performance:
        date_inputs.append(performance["as_of_date"])
    if not aum.empty and "aum_date" in aum:
        date_inputs.append(aum["aum_date"])

    dim_date = build_dim_date(*date_inputs)
    dim_date.to_csv(PROCESSED_DIR / "dim_date_clean.csv", index=False)

    fact_nav = nav[["scheme_code", "date", "nav", "is_forward_filled"]].copy()
    fact_nav["date_key"] = date_key(fact_nav["date"])
    fact_nav["is_forward_filled"] = (
        fact_nav["is_forward_filled"].fillna(False).astype(bool).astype(int)
    )
    fact_nav = fact_nav[["scheme_code", "date_key", "nav", "is_forward_filled"]]

    fact_transactions = transactions.copy()
    if fact_transactions.empty:
        fact_transactions = pd.DataFrame(
            columns=[
                "transaction_id",
                "investor_id",
                "scheme_code",
                "date_key",
                "transaction_type",
                "amount",
                "units",
                "state",
                "kyc_status",
                "source_file",
            ]
        )
    else:
        fact_transactions["date_key"] = date_key(fact_transactions["transaction_date"])
        fact_transactions = fact_transactions[
            [
                "transaction_id",
                "investor_id",
                "scheme_code",
                "date_key",
                "transaction_type",
                "amount",
                "units",
                "state",
                "kyc_status",
                "source_file",
            ]
        ]

    fact_performance = performance.copy()
    if fact_performance.empty:
        fact_performance = pd.DataFrame(
            columns=[
                "scheme_code",
                "date_key",
                "return_1y",
                "return_3y",
                "return_5y",
                "expense_ratio",
                "anomaly_flags",
                "source_reference",
            ]
        )
    else:
        fact_performance["date_key"] = date_key(fact_performance["as_of_date"])
        fact_performance = fact_performance[
            [
                "scheme_code",
                "date_key",
                "return_1y",
                "return_3y",
                "return_5y",
                "expense_ratio",
                "anomaly_flags",
                "source_reference",
            ]
        ]

    fact_aum = aum.copy()
    if fact_aum.empty:
        fact_aum = pd.DataFrame(
            columns=["scheme_code", "date_key", "aum_crore", "source_reference"]
        )
    else:
        fact_aum["date_key"] = date_key(fact_aum["aum_date"])
        fact_aum = fact_aum[["scheme_code", "date_key", "aum_crore", "source_reference"]]

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys = ON"))
        dim_fund.to_sql("dim_fund", connection, if_exists="append", index=False)
        dim_date.to_sql("dim_date", connection, if_exists="append", index=False)
        fact_nav.to_sql("fact_nav", connection, if_exists="append", index=False)
        fact_transactions.to_sql(
            "fact_transactions", connection, if_exists="append", index=False
        )
        fact_performance.to_sql(
            "fact_performance", connection, if_exists="append", index=False
        )
        fact_aum.to_sql("fact_aum", connection, if_exists="append", index=False)

    expected = {
        "dim_fund": len(dim_fund),
        "dim_date": len(dim_date),
        "fact_nav": len(fact_nav),
        "fact_transactions": len(fact_transactions),
        "fact_performance": len(fact_performance),
        "fact_aum": len(fact_aum),
    }

    with sqlite3.connect(DB_PATH) as connection:
        actual = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in expected
        }

    return {table: (expected[table], actual[table]) for table in expected}


def write_report(counts: dict[str, tuple[int, int]]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# SQLite Load Summary",
        "",
        "| Table | Expected Rows | Loaded Rows | Match |",
        "|---|---:|---:|---|",
    ]
    for table, (expected, actual) in counts.items():
        lines.append(
            f"| {table} | {expected} | {actual} | {'yes' if expected == actual else 'no'} |"
        )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    counts = load_database()
    write_report(counts)
    for table, (expected, actual) in counts.items():
        status = "OK" if expected == actual else "MISMATCH"
        print(f"{table}: expected={expected}, loaded={actual} [{status}]")
    print(f"Created {DB_PATH}")
    print(f"Created {REPORT_PATH}")


if __name__ == "__main__":
    main()
