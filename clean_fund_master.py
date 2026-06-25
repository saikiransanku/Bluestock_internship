from __future__ import annotations

from pathlib import Path

import pandas as pd


RAW_PATH = Path("data/raw/fund_master.csv")
PROCESSED_PATH = Path("data/processed/fund_master_clean.csv")
AUM_PATH = Path("data/processed/fund_aum_clean.csv")
REPORT_PATH = Path("reports/fund_master_cleaning_summary.md")

FUND_COLUMNS = [
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

AUM_COLUMNS = ["scheme_code", "aum_date", "aum_crore", "source_reference"]


def split_scheme_category(category: object) -> tuple[str | None, str | None]:
    if not isinstance(category, str) or not category.strip():
        return None, None

    parts = [part.strip() for part in category.split(" - ", maxsplit=1)]
    return parts[0], parts[1] if len(parts) > 1 else None


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )
    return df


def main() -> None:
    if not RAW_PATH.exists():
        raise FileNotFoundError("data/raw/fund_master.csv is required.")

    PROCESSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    df = normalize_columns(pd.read_csv(RAW_PATH))
    raw_rows = len(df)
    df["scheme_code"] = pd.to_numeric(df["scheme_code"], errors="coerce").astype("Int64")

    if "scheme_category" in df.columns:
        category_parts = df["scheme_category"].apply(split_scheme_category)
        df["category_group"] = category_parts.apply(lambda value: value[0])
        df["sub_category"] = category_parts.apply(lambda value: value[1])
    else:
        df["scheme_category"] = pd.NA
        df["category_group"] = pd.NA
        df["sub_category"] = pd.NA

    if "risk_grade" not in df.columns:
        df["risk_grade"] = "Unavailable"

    if "requested_name_mismatch" not in df.columns:
        df["requested_name_mismatch"] = False

    for column in FUND_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA

    invalid_codes = int(df["scheme_code"].isna().sum())
    duplicate_codes = int(df.duplicated("scheme_code").sum())

    df = df.dropna(subset=["scheme_code"]).copy()
    df["scheme_code"] = df["scheme_code"].astype(int)
    df = df.drop_duplicates("scheme_code", keep="last")
    df = df[FUND_COLUMNS].sort_values("scheme_code")
    df.to_csv(PROCESSED_PATH, index=False)

    if not AUM_PATH.exists():
        pd.DataFrame(columns=AUM_COLUMNS).to_csv(AUM_PATH, index=False)

    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Fund Master Cleaning Summary",
                "",
                f"- Raw rows: {raw_rows}",
                f"- Clean rows: {len(df)}",
                f"- Invalid scheme codes removed: {invalid_codes}",
                f"- Duplicate scheme codes removed: {duplicate_codes}",
                "- risk_grade was not available in mfapi metadata; set to Unavailable.",
                "- Created schema-only fund_aum_clean.csv because no AUM source file was present.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Saved {PROCESSED_PATH} ({len(df)} rows)")
    print(f"Saved {AUM_PATH} (0 rows unless an AUM source is later supplied)")
    print(f"Created {REPORT_PATH}")


if __name__ == "__main__":
    main()
