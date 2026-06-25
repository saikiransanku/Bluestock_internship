from __future__ import annotations

from pathlib import Path

import pandas as pd


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
        .str.strip("_")
    )
    return df


def clean_nav_frame(df: pd.DataFrame, source_name: str) -> tuple[pd.DataFrame, dict[str, int]]:
    df = normalize_columns(df)
    required = {"date", "nav", "scheme_code"}
    missing_required = sorted(required - set(df.columns))
    if missing_required:
        raise ValueError(f"{source_name} is missing required columns: {missing_required}")

    raw_rows = len(df)
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")
    df["scheme_code"] = pd.to_numeric(df["scheme_code"], errors="coerce").astype("Int64")

    invalid_dates = int(df["date"].isna().sum())
    invalid_nav = int((df["nav"].isna() | (df["nav"] <= 0)).sum())
    invalid_codes = int(df["scheme_code"].isna().sum())

    df = df.dropna(subset=["date", "nav", "scheme_code"])
    df = df[df["nav"] > 0].copy()
    df["scheme_code"] = df["scheme_code"].astype(int)

    df = df.sort_values(["scheme_code", "date"])
    duplicate_scheme_dates = int(df.duplicated(["scheme_code", "date"]).sum())
    df = df.drop_duplicates(["scheme_code", "date"], keep="last")

    metadata_columns = [
        column for column in df.columns if column not in {"date", "nav", "scheme_code"}
    ]

    filled_frames: list[pd.DataFrame] = []
    for scheme_code, group in df.groupby("scheme_code", sort=True):
        group = group.sort_values("date").copy()
        original_dates = set(group["date"])
        date_index = pd.date_range(group["date"].min(), group["date"].max(), freq="D")

        filled = group.set_index("date").reindex(date_index)
        filled.index.name = "date"
        filled = filled.reset_index()
        filled["scheme_code"] = int(scheme_code)
        filled["nav"] = filled["nav"].ffill()

        for column in metadata_columns:
            filled[column] = filled[column].ffill().bfill()

        filled["is_forward_filled"] = ~filled["date"].isin(original_dates)
        filled_frames.append(filled)

    cleaned = pd.concat(filled_frames, ignore_index=True)
    cleaned = cleaned.sort_values(["scheme_code", "date"]).reset_index(drop=True)
    cleaned["date"] = cleaned["date"].dt.strftime("%Y-%m-%d")
    cleaned["nav"] = cleaned["nav"].round(6)
    cleaned["is_forward_filled"] = cleaned["is_forward_filled"].astype(bool)

    preferred_columns = [
        "date",
        "nav",
        "scheme_code",
        "scheme_name",
        "requested_name",
        "fund_house",
        "scheme_type",
        "scheme_category",
        "source_url",
        "fetched_at",
        "is_forward_filled",
    ]
    ordered_columns = [column for column in preferred_columns if column in cleaned.columns]
    ordered_columns.extend(column for column in cleaned.columns if column not in ordered_columns)
    cleaned = cleaned[ordered_columns]

    metrics = {
        "raw_rows": raw_rows,
        "clean_rows": len(cleaned),
        "invalid_dates": invalid_dates,
        "invalid_nav": invalid_nav,
        "invalid_codes": invalid_codes,
        "duplicate_scheme_dates": duplicate_scheme_dates,
        "forward_filled_rows": int(cleaned["is_forward_filled"].sum()),
    }
    return cleaned, metrics


def clean_file(input_path: Path, output_path: Path) -> dict[str, int | str]:
    raw_df = pd.read_csv(input_path)
    cleaned, metrics = clean_nav_frame(raw_df, input_path.name)
    cleaned.to_csv(output_path, index=False)
    return {"file": input_path.name, "output": output_path.name, **metrics}


def write_report(results: list[dict[str, int | str]]) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NAV Cleaning Summary",
        "",
        "| Source | Output | Raw Rows | Clean Rows | Invalid Dates | Invalid NAV | "
        "Duplicate Scheme Dates | Forward-Filled Rows |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for result in results:
        lines.append(
            f"| {result['file']} | {result['output']} | {result['raw_rows']} | "
            f"{result['clean_rows']} | {result['invalid_dates']} | "
            f"{result['invalid_nav']} | {result['duplicate_scheme_dates']} | "
            f"{result['forward_filled_rows']} |"
        )

    (REPORTS_DIR / "nav_cleaning_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, int | str]] = []
    nav_history_path = RAW_DIR / "nav_history.csv"
    if nav_history_path.exists():
        results.append(
            clean_file(nav_history_path, PROCESSED_DIR / "nav_history_clean.csv")
        )
    else:
        raise FileNotFoundError("data/raw/nav_history.csv is required for NAV cleaning.")

    for nav_path in sorted(RAW_DIR.glob("*_nav.csv")):
        output_path = PROCESSED_DIR / f"{nav_path.stem}_clean.csv"
        results.append(clean_file(nav_path, output_path))

    write_report(results)
    for result in results:
        print(
            f"Saved data/processed/{result['output']} "
            f"({result['clean_rows']} rows, {result['forward_filled_rows']} filled)"
        )
    print("Created reports/nav_cleaning_summary.md")


if __name__ == "__main__":
    main()
