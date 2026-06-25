from __future__ import annotations

from pathlib import Path

import pandas as pd


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
NOTEBOOKS_DIR = Path("notebooks")
SQL_DIR = Path("sql")
DASHBOARD_DIR = Path("dashboard")
EXPECTED_RAW_CSV_COUNT = 10


def ensure_project_structure() -> None:
    for directory in [
        RAW_DIR,
        PROCESSED_DIR,
        NOTEBOOKS_DIR,
        SQL_DIR,
        DASHBOARD_DIR,
        REPORTS_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def load_csvs() -> dict[str, pd.DataFrame]:
    csv_paths = sorted(RAW_DIR.glob("*.csv"))
    datasets: dict[str, pd.DataFrame] = {}

    print(f"Raw CSV files found: {len(csv_paths)}")
    if len(csv_paths) != EXPECTED_RAW_CSV_COUNT:
        print(
            f"Anomaly: expected {EXPECTED_RAW_CSV_COUNT} raw CSV files, "
            f"found {len(csv_paths)}."
        )

    for csv_path in csv_paths:
        df = pd.read_csv(csv_path)
        datasets[csv_path.name] = df

        print("\n" + "=" * 80)
        print(f"Dataset: {csv_path.name}")
        print(f"Shape: {df.shape}")
        print("Dtypes:")
        print(df.dtypes)
        print("Head:")
        print(df.head())
        print("Missing values:")
        print(df.isna().sum())
        print(f"Duplicate rows: {df.duplicated().sum()}")

    return datasets


def explore_fund_master(datasets: dict[str, pd.DataFrame]) -> list[str]:
    notes: list[str] = []
    fund_master = datasets.get("fund_master.csv")
    if fund_master is None:
        return ["fund_master.csv is missing, so fund master exploration was skipped."]

    print("\n" + "=" * 80)
    print("Fund Master Exploration")

    for column, label in [
        ("fund_house", "Fund houses"),
        ("scheme_category", "Categories"),
        ("sub_category", "Sub-categories"),
        ("risk_grade", "Risk grades"),
    ]:
        if column in fund_master.columns:
            values = sorted(fund_master[column].dropna().astype(str).unique())
            print(f"\nUnique {label}:")
            print(values)
            notes.append(f"{label}: {len(values)} unique value(s).")
        else:
            print(f"\n{label}: column '{column}' is not available.")
            notes.append(f"{label}: unavailable in fund_master.csv.")

    if "scheme_code" in fund_master.columns:
        codes = fund_master["scheme_code"].dropna().astype(str)
        numeric_codes = codes.str.fullmatch(r"\d+").sum()
        six_digit_codes = codes.str.fullmatch(r"\d{6}").sum()
        note = (
            "AMFI scheme codes in this dataset are numeric identifiers. "
            f"{numeric_codes}/{len(codes)} are numeric and "
            f"{six_digit_codes}/{len(codes)} are six digits. "
            "The sample does not show an embedded fund-house/category pattern."
        )
        print("\nAMFI scheme code structure:")
        print(note)
        notes.append(note)

    return notes


def validate_amfi_codes(datasets: dict[str, pd.DataFrame]) -> list[str]:
    fund_master = datasets.get("fund_master.csv")
    nav_history = datasets.get("nav_history.csv")
    notes: list[str] = []

    print("\n" + "=" * 80)
    print("AMFI Validation")

    if fund_master is None or nav_history is None:
        note = "AMFI validation skipped because fund_master.csv or nav_history.csv is missing."
        print(note)
        return [note]

    if "scheme_code" not in fund_master.columns or "scheme_code" not in nav_history.columns:
        note = "AMFI validation skipped because scheme_code is missing in a required file."
        print(note)
        return [note]

    fund_codes = set(fund_master["scheme_code"].dropna().astype(int))
    nav_codes = set(nav_history["scheme_code"].dropna().astype(int))
    missing_in_nav = sorted(fund_codes - nav_codes)
    extra_in_nav = sorted(nav_codes - fund_codes)

    print(f"Total fund_master codes: {len(fund_codes)}")
    print(f"Total nav_history codes: {len(nav_codes)}")
    print(f"Codes missing in nav_history: {missing_in_nav}")
    print(f"Codes present in nav_history but absent from fund_master: {extra_in_nav}")

    if missing_in_nav:
        notes.append(f"AMFI validation failed: missing in nav_history: {missing_in_nav}.")
    else:
        notes.append("AMFI validation passed: every fund_master code exists in nav_history.")

    if extra_in_nav:
        notes.append(f"Extra nav_history codes not in fund_master: {extra_in_nav}.")

    return notes


def collect_anomaly_notes(datasets: dict[str, pd.DataFrame]) -> list[str]:
    notes: list[str] = []
    if len(datasets) != EXPECTED_RAW_CSV_COUNT:
        notes.append(
            f"Expected {EXPECTED_RAW_CSV_COUNT} raw CSV datasets, but found {len(datasets)}. "
            "Missing source files must be supplied before those datasets can be cleaned."
        )

    for name, df in datasets.items():
        duplicate_rows = int(df.duplicated().sum())
        missing_cells = int(df.isna().sum().sum())
        if duplicate_rows:
            notes.append(f"{name}: {duplicate_rows} duplicate row(s).")
        if missing_cells:
            notes.append(f"{name}: {missing_cells} missing cell(s).")
        if "nav" in df.columns:
            nav_numeric = pd.to_numeric(df["nav"], errors="coerce")
            invalid_nav = int((nav_numeric <= 0).sum() + nav_numeric.isna().sum())
            if invalid_nav:
                notes.append(f"{name}: {invalid_nav} invalid NAV value(s).")

    return notes


def write_report(datasets: dict[str, pd.DataFrame], notes: list[str]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Data Ingestion Summary",
        "",
        f"Raw CSV files found: {len(datasets)}",
        "",
        "## Dataset Inventory",
        "",
        "| File | Rows | Columns | Duplicate Rows | Missing Cells |",
        "|---|---:|---:|---:|---:|",
    ]

    for name, df in datasets.items():
        lines.append(
            f"| {name} | {len(df)} | {len(df.columns)} | "
            f"{int(df.duplicated().sum())} | {int(df.isna().sum().sum())} |"
        )

    lines.extend(["", "## Notes", ""])
    if notes:
        lines.extend(f"- {note}" for note in notes)
    else:
        lines.append("- No anomalies detected.")

    (REPORTS_DIR / "data_ingestion_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    ensure_project_structure()
    datasets = load_csvs()
    notes = []
    notes.extend(collect_anomaly_notes(datasets))
    notes.extend(explore_fund_master(datasets))
    notes.extend(validate_amfi_codes(datasets))
    write_report(datasets, notes)
    print("\nCreated reports/data_ingestion_summary.md")


if __name__ == "__main__":
    main()
