from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests


RAW_DIR = Path("data/raw")
REPORTS_DIR = Path("reports")
MFAPI_URL = "https://api.mfapi.in/mf/{scheme_code}"

SCHEMES = [
    {
        "file_stem": "hdfc_top_100",
        "requested_name": "HDFC Top 100 Direct",
        "scheme_code": 125497,
    },
    {
        "file_stem": "sbi_bluechip",
        "requested_name": "SBI Bluechip",
        "scheme_code": 119551,
    },
    {
        "file_stem": "icici_bluechip",
        "requested_name": "ICICI Bluechip",
        "scheme_code": 120503,
    },
    {
        "file_stem": "nippon_large_cap",
        "requested_name": "Nippon Large Cap",
        "scheme_code": 118632,
    },
    {
        "file_stem": "axis_bluechip",
        "requested_name": "Axis Bluechip",
        "scheme_code": 119092,
    },
    {
        "file_stem": "kotak_bluechip",
        "requested_name": "Kotak Bluechip",
        "scheme_code": 120841,
    },
]


def split_scheme_category(category: str | None) -> tuple[str | None, str | None]:
    if not isinstance(category, str) or not category.strip():
        return None, None

    parts = [part.strip() for part in category.split(" - ", maxsplit=1)]
    category_group = parts[0]
    sub_category = parts[1] if len(parts) > 1 else None
    return category_group, sub_category


def is_name_mismatch(requested_name: str, api_name: str | None) -> bool:
    if not api_name:
        return True

    requested_tokens = [
        token.lower()
        for token in requested_name.replace("&", " ").replace("-", " ").split()
    ]
    requested_house_token = requested_tokens[0] if requested_tokens else ""
    api_text = api_name.lower()
    return requested_house_token not in api_text


def fetch_scheme(scheme: dict[str, object]) -> tuple[pd.DataFrame, dict[str, object]]:
    scheme_code = int(scheme["scheme_code"])
    url = MFAPI_URL.format(scheme_code=scheme_code)
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    payload = response.json()
    meta = payload.get("meta", {})
    nav_rows = payload.get("data", [])

    fetched_at = datetime.now(timezone.utc).isoformat()
    nav_df = pd.DataFrame(nav_rows)
    if nav_df.empty:
        nav_df = pd.DataFrame(columns=["date", "nav"])

    nav_df["scheme_code"] = int(meta.get("scheme_code", scheme_code))
    nav_df["scheme_name"] = meta.get("scheme_name")
    nav_df["requested_name"] = scheme["requested_name"]
    nav_df["fund_house"] = meta.get("fund_house")
    nav_df["scheme_type"] = meta.get("scheme_type")
    nav_df["scheme_category"] = meta.get("scheme_category")
    nav_df["source_url"] = url
    nav_df["fetched_at"] = fetched_at

    nav_columns = [
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
    ]
    nav_df = nav_df.reindex(columns=nav_columns)

    category_group, sub_category = split_scheme_category(meta.get("scheme_category"))
    master_row = {
        "scheme_code": int(meta.get("scheme_code", scheme_code)),
        "requested_name": scheme["requested_name"],
        "scheme_name": meta.get("scheme_name"),
        "fund_house": meta.get("fund_house"),
        "scheme_type": meta.get("scheme_type"),
        "scheme_category": meta.get("scheme_category"),
        "category_group": category_group,
        "sub_category": sub_category,
        "risk_grade": None,
        "isin_growth": meta.get("isin_growth"),
        "isin_div_reinvestment": meta.get("isin_div_reinvestment"),
        "source_url": url,
        "fetched_at": fetched_at,
        "requested_name_mismatch": is_name_mismatch(
            str(scheme["requested_name"]), meta.get("scheme_name")
        ),
    }

    return nav_df, master_row


def write_summary(master_df: pd.DataFrame, nav_history_df: pd.DataFrame) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    mismatches = master_df[master_df["requested_name_mismatch"]]
    metadata_rows = [
        "| Scheme Code | Requested Name | API Scheme Name | Fund House | Scheme Category | Name Mismatch |",
        "|---:|---|---|---|---|---|",
    ]
    for row in master_df.itertuples(index=False):
        metadata_rows.append(
            f"| {row.scheme_code} | {row.requested_name} | {row.scheme_name} | "
            f"{row.fund_house} | {row.scheme_category} | {row.requested_name_mismatch} |"
        )
    lines = [
        "# Live NAV Fetch Summary",
        "",
        f"Fetched schemes: {len(master_df)}",
        f"NAV rows fetched: {len(nav_history_df)}",
        "",
        "## Requested vs API Metadata",
        "",
        *metadata_rows,
        "",
        "## Data Quality Notes",
        "",
    ]

    if mismatches.empty:
        lines.append("- No requested-label/API-name mismatches detected.")
    else:
        lines.append(
            "- Requested labels do not match mfapi metadata for these scheme codes:"
        )
        for row in mismatches.itertuples(index=False):
            lines.append(
                f"  - {row.scheme_code}: requested '{row.requested_name}', "
                f"API returned '{row.scheme_name}'."
            )

    (REPORTS_DIR / "live_nav_fetch_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    nav_frames: list[pd.DataFrame] = []
    fund_master_rows: list[dict[str, object]] = []

    for scheme in SCHEMES:
        nav_df, master_row = fetch_scheme(scheme)
        file_stem = str(scheme["file_stem"])
        output_path = RAW_DIR / f"{file_stem}_nav.csv"
        nav_df.to_csv(output_path, index=False)

        nav_frames.append(nav_df)
        fund_master_rows.append(master_row)
        print(f"Saved {output_path} ({len(nav_df)} rows)")

    fund_master_df = pd.DataFrame(fund_master_rows)
    nav_history_df = pd.concat(nav_frames, ignore_index=True)

    fund_master_df.to_csv(RAW_DIR / "fund_master.csv", index=False)
    nav_history_df.to_csv(RAW_DIR / "nav_history.csv", index=False)
    write_summary(fund_master_df, nav_history_df)

    print("Created data/raw/fund_master.csv")
    print("Created data/raw/nav_history.csv")
    print("Created reports/live_nav_fetch_summary.md")


if __name__ == "__main__":
    main()
