from __future__ import annotations

from pathlib import Path

import pandas as pd


RAW_PATH = Path("data/raw/investor_transactions.csv")
PROCESSED_PATH = Path("data/processed/investor_transactions_clean.csv")
REPORT_PATH = Path("reports/transactions_cleaning_summary.md")

OUTPUT_COLUMNS = [
    "transaction_id",
    "investor_id",
    "scheme_code",
    "transaction_date",
    "transaction_type",
    "amount",
    "units",
    "state",
    "kyc_status",
    "source_file",
]

TRANSACTION_TYPE_MAP = {
    "sip": "SIP",
    "systematic investment plan": "SIP",
    "lumpsum": "Lumpsum",
    "lump sum": "Lumpsum",
    "purchase": "Lumpsum",
    "buy": "Lumpsum",
    "investment": "Lumpsum",
    "redemption": "Redemption",
    "redeem": "Redemption",
    "sell": "Redemption",
    "withdrawal": "Redemption",
}

KYC_STATUS_MAP = {
    "verified": "Verified",
    "valid": "Verified",
    "approved": "Verified",
    "yes": "Verified",
    "pending": "Pending",
    "in progress": "Pending",
    "rejected": "Rejected",
    "invalid": "Rejected",
    "no": "Rejected",
    "unknown": "Unknown",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )
    return df


def first_existing(df: pd.DataFrame, candidates: list[str]) -> str | None:
    return next((column for column in candidates if column in df.columns), None)


def empty_output(reason: str) -> None:
    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(columns=OUTPUT_COLUMNS).to_csv(PROCESSED_PATH, index=False)
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Transactions Cleaning Summary",
                "",
                f"- {reason}",
                "- Created schema-only data/processed/investor_transactions_clean.csv.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(reason)
    print(f"Created {PROCESSED_PATH} with 0 rows")


def clean_transactions() -> pd.DataFrame:
    if not RAW_PATH.exists():
        empty_output("data/raw/investor_transactions.csv is missing.")
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    df = normalize_columns(pd.read_csv(RAW_PATH))
    raw_rows = len(df)

    date_col = first_existing(df, ["transaction_date", "date", "txn_date", "trade_date"])
    type_col = first_existing(df, ["transaction_type", "txn_type", "type"])
    amount_col = first_existing(df, ["amount", "transaction_amount", "txn_amount"])
    kyc_col = first_existing(df, ["kyc_status", "kyc", "kyc_flag"])

    required_missing = [
        name
        for name, value in {
            "transaction_date": date_col,
            "transaction_type": type_col,
            "amount": amount_col,
        }.items()
        if value is None
    ]
    if required_missing:
        empty_output(
            "investor_transactions.csv is present but missing required columns: "
            + ", ".join(required_missing)
            + "."
        )
        return pd.DataFrame(columns=OUTPUT_COLUMNS)

    transaction_id_col = first_existing(df, ["transaction_id", "txn_id", "id"])
    investor_id_col = first_existing(df, ["investor_id", "customer_id", "client_id"])
    scheme_col = first_existing(df, ["scheme_code", "amfi_code", "amfi_scheme_code"])

    cleaned = pd.DataFrame()
    cleaned["transaction_id"] = (
        df[transaction_id_col]
        if transaction_id_col
        else [f"TXN{i + 1:08d}" for i in range(len(df))]
    )
    cleaned["investor_id"] = (
        df[investor_id_col]
        if investor_id_col
        else pd.NA
    )
    cleaned["scheme_code"] = (
        pd.to_numeric(df[scheme_col], errors="coerce").astype("Int64")
        if scheme_col
        else pd.Series([pd.NA] * len(df), dtype="Int64")
    )
    cleaned["transaction_date"] = pd.to_datetime(
        df[date_col], dayfirst=True, errors="coerce"
    )
    cleaned["transaction_type"] = (
        df[type_col]
        .astype(str)
        .str.strip()
        .str.lower()
        .map(TRANSACTION_TYPE_MAP)
        .fillna("Unknown")
    )
    cleaned["amount"] = pd.to_numeric(df[amount_col], errors="coerce")
    units_col = first_existing(df, ["units", "unit", "nav_units"])
    cleaned["units"] = pd.to_numeric(df[units_col], errors="coerce") if units_col else pd.NA
    state_col = first_existing(df, ["state", "investor_state", "region"])
    cleaned["state"] = df[state_col].astype(str).str.strip() if state_col else pd.NA
    cleaned["kyc_status"] = (
        df[kyc_col].astype(str).str.strip().str.lower().map(KYC_STATUS_MAP).fillna("Unknown")
        if kyc_col
        else "Unknown"
    )
    cleaned["source_file"] = RAW_PATH.name

    invalid_dates = int(cleaned["transaction_date"].isna().sum())
    invalid_amounts = int((cleaned["amount"].isna() | (cleaned["amount"] <= 0)).sum())
    invalid_types = int((cleaned["transaction_type"] == "Unknown").sum())
    invalid_kyc = int((cleaned["kyc_status"] == "Unknown").sum())

    cleaned = cleaned.dropna(subset=["transaction_date", "amount"])
    cleaned = cleaned[cleaned["amount"] > 0].copy()
    cleaned = cleaned[cleaned["transaction_type"].isin(["SIP", "Lumpsum", "Redemption"])]
    cleaned["transaction_date"] = cleaned["transaction_date"].dt.strftime("%Y-%m-%d")
    cleaned = cleaned[OUTPUT_COLUMNS]

    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(PROCESSED_PATH, index=False)

    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Transactions Cleaning Summary",
                "",
                f"- Raw rows: {raw_rows}",
                f"- Clean rows: {len(cleaned)}",
                f"- Invalid dates removed: {invalid_dates}",
                f"- Invalid/non-positive amounts removed: {invalid_amounts}",
                f"- Unknown transaction types flagged/removed: {invalid_types}",
                f"- Unknown KYC status values: {invalid_kyc}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return cleaned


def main() -> None:
    cleaned = clean_transactions()
    print(f"Saved {PROCESSED_PATH} ({len(cleaned)} rows)")
    print(f"Created {REPORT_PATH}")


if __name__ == "__main__":
    main()
