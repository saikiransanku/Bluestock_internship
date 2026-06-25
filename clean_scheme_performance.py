from __future__ import annotations

from pathlib import Path

import pandas as pd


RAW_PATH = Path("data/raw/scheme_performance.csv")
NAV_CLEAN_PATH = Path("data/processed/nav_history_clean.csv")
FUND_MASTER_PATH = Path("data/processed/fund_master_clean.csv")
PROCESSED_PATH = Path("data/processed/scheme_performance_clean.csv")
REPORT_PATH = Path("reports/performance_cleaning_summary.md")

RETURN_COLUMNS = ["return_1y", "return_3y", "return_5y"]
OUTPUT_COLUMNS = [
    "scheme_code",
    "scheme_name",
    "as_of_date",
    "return_1y",
    "return_3y",
    "return_5y",
    "expense_ratio",
    "anomaly_flags",
    "source_reference",
]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )
    return df


def closest_nav_on_or_before(group: pd.DataFrame, target_date: pd.Timestamp) -> float | None:
    candidates = group[group["date"] <= target_date]
    if candidates.empty:
        return None
    return float(candidates.iloc[-1]["nav"])


def derive_from_nav() -> pd.DataFrame:
    if not NAV_CLEAN_PATH.exists():
        raise FileNotFoundError(
            "Neither data/raw/scheme_performance.csv nor "
            "data/processed/nav_history_clean.csv exists."
        )

    nav = pd.read_csv(NAV_CLEAN_PATH, parse_dates=["date"])
    fund_master = (
        pd.read_csv(FUND_MASTER_PATH)
        if FUND_MASTER_PATH.exists()
        else pd.DataFrame(columns=["scheme_code", "scheme_name"])
    )
    name_lookup = dict(
        zip(
            fund_master.get("scheme_code", pd.Series(dtype=int)),
            fund_master.get("scheme_name", pd.Series(dtype=str)),
        )
    )

    rows: list[dict[str, object]] = []
    for scheme_code, group in nav.groupby("scheme_code", sort=True):
        group = group.sort_values("date")
        latest = group.iloc[-1]
        latest_date = pd.Timestamp(latest["date"])
        latest_nav = float(latest["nav"])

        values: dict[str, float | None] = {}
        for years, column in [(1, "return_1y"), (3, "return_3y"), (5, "return_5y")]:
            base_nav = closest_nav_on_or_before(group, latest_date - pd.DateOffset(years=years))
            values[column] = (
                round(((latest_nav / base_nav) - 1) * 100, 4)
                if base_nav and base_nav > 0
                else None
            )

        flags = []
        for column in RETURN_COLUMNS:
            value = values[column]
            if value is not None and (value < -100 or value > 1000):
                flags.append(f"{column}_outlier")
        flags.append("expense_ratio_missing")

        rows.append(
            {
                "scheme_code": int(scheme_code),
                "scheme_name": name_lookup.get(scheme_code, latest.get("scheme_name")),
                "as_of_date": latest_date.strftime("%Y-%m-%d"),
                "return_1y": values["return_1y"],
                "return_3y": values["return_3y"],
                "return_5y": values["return_5y"],
                "expense_ratio": pd.NA,
                "anomaly_flags": ";".join(flags),
                "source_reference": "Derived from cleaned NAV history; expense ratio source missing.",
            }
        )

    return pd.DataFrame(rows, columns=OUTPUT_COLUMNS)


def clean_source_performance() -> pd.DataFrame:
    df = normalize_columns(pd.read_csv(RAW_PATH))
    raw_rows = len(df)

    if "scheme_code" not in df.columns:
        raise ValueError("scheme_performance.csv must include scheme_code.")

    cleaned = pd.DataFrame()
    cleaned["scheme_code"] = pd.to_numeric(df["scheme_code"], errors="coerce").astype("Int64")
    cleaned["scheme_name"] = df["scheme_name"] if "scheme_name" in df.columns else pd.NA
    cleaned["as_of_date"] = pd.to_datetime(
        df["as_of_date"] if "as_of_date" in df.columns else pd.Timestamp.today(),
        dayfirst=True,
        errors="coerce",
    )

    for column in RETURN_COLUMNS:
        cleaned[column] = pd.to_numeric(df[column], errors="coerce") if column in df else pd.NA

    cleaned["expense_ratio"] = (
        pd.to_numeric(df["expense_ratio"], errors="coerce") if "expense_ratio" in df else pd.NA
    )

    anomaly_flags = []
    for _, row in cleaned.iterrows():
        flags = []
        for column in RETURN_COLUMNS:
            value = row[column]
            if pd.isna(value):
                flags.append(f"{column}_non_numeric")
            elif value < -100 or value > 1000:
                flags.append(f"{column}_outlier")
        expense_ratio = row["expense_ratio"]
        if pd.isna(expense_ratio):
            flags.append("expense_ratio_missing")
        elif expense_ratio < 0.1 or expense_ratio > 2.5:
            flags.append("expense_ratio_out_of_range")
        anomaly_flags.append(";".join(flags))

    cleaned["anomaly_flags"] = anomaly_flags
    cleaned["source_reference"] = RAW_PATH.name
    cleaned = cleaned.dropna(subset=["scheme_code", "as_of_date"])
    cleaned["scheme_code"] = cleaned["scheme_code"].astype(int)
    cleaned["as_of_date"] = cleaned["as_of_date"].dt.strftime("%Y-%m-%d")
    cleaned = cleaned[OUTPUT_COLUMNS]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Performance Cleaning Summary",
                "",
                f"- Source: {RAW_PATH}",
                f"- Raw rows: {raw_rows}",
                f"- Clean rows: {len(cleaned)}",
                f"- Rows with anomaly flags: {(cleaned['anomaly_flags'] != '').sum()}",
                "- Expense ratio expected range: 0.1 to 2.5 percent.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return cleaned


def main() -> None:
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if RAW_PATH.exists():
        cleaned = clean_source_performance()
    else:
        cleaned = derive_from_nav()
        REPORT_PATH.write_text(
            "\n".join(
                [
                    "# Performance Cleaning Summary",
                    "",
                    "- data/raw/scheme_performance.csv is missing.",
                    "- Created return metrics from cleaned NAV history.",
                    "- expense_ratio is unavailable and flagged as expense_ratio_missing.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

    cleaned.to_csv(PROCESSED_PATH, index=False)
    print(f"Saved {PROCESSED_PATH} ({len(cleaned)} rows)")
    print(f"Created {REPORT_PATH}")


if __name__ == "__main__":
    main()
