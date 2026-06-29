
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import math
import time

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np
import pandas as pd
import requests


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "dashboard" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

START_DATE = pd.Timestamp("2022-01-01")
END_DATE = pd.Timestamp("2025-12-31")
RNG = np.random.default_rng(20250625)

NAV_URL = "https://api.mfapi.in/mf/{scheme_code}"
YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"

NAVY = "#071A3D"
BLUE = "#0B63CE"
CYAN = "#17B6E6"
TEAL = "#15B8A6"
ORANGE = "#FF9F43"
RED = "#E85D75"
INK = "#15233B"
MUTED = "#65738B"
GRID = "#DDE6F2"
PAGE = "#F4F7FB"
WHITE = "#FFFFFF"
PALETTE = [BLUE, CYAN, TEAL, ORANGE, "#7C5CFC", RED, "#2E8B57", "#F1C40F"]


def fetch_json(url: str, params: dict | None = None, retries: int = 4) -> dict:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BluestockDashboard/1.0)"}
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=90)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # network retry boundary
            last_error = exc
            if attempt < retries - 1:
                time.sleep(1.5 * 2**attempt)
    raise RuntimeError(f"Unable to download {url}") from last_error


def fetch_nav(scheme_code: str, scheme_name: str) -> pd.DataFrame:
    payload = fetch_json(NAV_URL.format(scheme_code=scheme_code))
    frame = pd.DataFrame(payload.get("data", []))
    if frame.empty:
        raise ValueError(f"No NAV history for {scheme_code}")
    frame["date"] = pd.to_datetime(frame["date"], dayfirst=True, errors="coerce")
    frame["nav"] = pd.to_numeric(frame["nav"], errors="coerce")
    frame = frame.dropna(subset=["date", "nav"])
    frame = frame.loc[frame["date"].between(START_DATE, END_DATE) & frame["nav"].gt(0)]
    frame = frame.drop_duplicates("date", keep="last").sort_values("date")
    frame["amfi_code"] = str(scheme_code)
    frame["scheme_name"] = scheme_name
    return frame[["date", "amfi_code", "scheme_name", "nav"]]


def fetch_index(symbol: str, label: str) -> pd.DataFrame:
    period1 = int(pd.Timestamp(START_DATE - pd.Timedelta(days=10), tz="UTC").timestamp())
    period2 = int(pd.Timestamp(END_DATE + pd.Timedelta(days=3), tz="UTC").timestamp())
    payload = fetch_json(
        YAHOO_URL.format(symbol=requests.utils.quote(symbol, safe="")),
        {"period1": period1, "period2": period2, "interval": "1d", "events": "history"},
    )
    result = payload["chart"]["result"][0]
    dates = pd.to_datetime(result["timestamp"], unit="s", utc=True).tz_convert(None).normalize()
    indicators = result["indicators"]
    values = indicators.get("adjclose", [{}])[0].get("adjclose")
    if values is None:
        values = indicators["quote"][0]["close"]
    out = pd.DataFrame({"date": dates, label: values}).dropna().drop_duplicates("date")
    return out.loc[out["date"].between(START_DATE, END_DATE)].sort_values("date")


def make_date_dimension() -> pd.DataFrame:
    date = pd.DataFrame({"date": pd.date_range(START_DATE, END_DATE, freq="D")})
    date["date_key"] = date["date"].dt.strftime("%Y%m%d").astype(int)
    date["year"] = date["date"].dt.year
    date["quarter"] = "Q" + date["date"].dt.quarter.astype(str)
    date["month"] = date["date"].dt.month
    date["month_name"] = date["date"].dt.strftime("%b")
    date["month_year"] = date["date"].dt.strftime("%b %Y")
    date["fiscal_year"] = np.where(
        date["date"].dt.month >= 4,
        "FY" + ((date["date"].dt.year + 1) % 100).astype(str).str.zfill(2),
        "FY" + (date["date"].dt.year % 100).astype(str).str.zfill(2),
    )
    date["is_month_end"] = date["date"].dt.is_month_end
    return date


def make_fund_tables(scorecard: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    perf = scorecard.copy()
    perf["amfi_code"] = perf["scheme_code"].astype(str)
    perf = perf.drop(columns=["scheme_code"])
    perf["plan"] = "Direct Growth"

    # Estimated only because the repository's fund_aum_clean.csv has zero rows.
    ranks = perf["overall_rank"].to_numpy()
    aum = 108_000 * np.exp(-(ranks - 1) / 18) + 6_500
    aum *= 1 + RNG.normal(0, 0.08, len(perf))
    perf["aum_crore"] = np.round(np.maximum(aum, 3_000), 2)
    perf["date"] = END_DATE
    perf["risk_band"] = pd.cut(
        perf["annualized_volatility_pct"],
        bins=[-np.inf, 11, 14, 18, np.inf],
        labels=["Moderate", "Moderately High", "High", "Very High"],
    ).astype(str)
    perf["data_status"] = "Observed performance; illustrative AUM"

    dim_cols = [
        "amfi_code", "scheme_name", "fund_house", "category", "plan", "risk_band",
        "expense_ratio_pct", "expense_ratio_date",
    ]
    dim_fund = perf[dim_cols].copy().sort_values("scheme_name")
    dim_fund["amfi_code"] = dim_fund["amfi_code"].astype(str)
    dim_fund["data_status"] = "Observed fund metadata"

    fact_aum = perf[["amfi_code", "scheme_name", "fund_house", "category", "aum_crore"]].copy()
    fact_aum["date"] = END_DATE
    fact_aum["data_status"] = "Illustrative estimate; source AUM table was empty"

    keep = [
        "amfi_code", "scheme_name", "fund_house", "category", "plan", "date", "as_of_date",
        "overall_rank", "fund_score", "cagr_1y_pct", "cagr_3y_pct", "cagr_5y_pct",
        "sharpe_ratio", "sortino_ratio", "annualized_volatility_pct", "alpha_annual_pct",
        "beta", "r_squared", "expense_ratio_pct", "max_drawdown_pct", "drawdown_peak_date",
        "drawdown_trough_date", "tracking_error_nifty50_pct", "tracking_error_nifty100_pct",
        "aum_crore", "risk_band", "data_status",
    ]
    fact_performance = perf[keep].copy()
    return dim_fund, fact_aum, fact_performance


def make_nav_table(dim_fund: pd.DataFrame) -> pd.DataFrame:
    nav_frames: list[pd.DataFrame] = []
    errors: list[tuple[str, str]] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            pool.submit(fetch_nav, row.amfi_code, row.scheme_name): row.amfi_code
            for row in dim_fund.itertuples(index=False)
        }
        for future in as_completed(futures):
            try:
                nav_frames.append(future.result())
            except Exception as exc:
                errors.append((futures[future], str(exc)))
    if errors:
        raise RuntimeError(f"NAV download failures: {errors}")

    nav = pd.concat(nav_frames, ignore_index=True).sort_values(["amfi_code", "date"])
    nav["daily_return"] = nav.groupby("amfi_code")["nav"].pct_change(fill_method=None)
    nav["normalized_nav"] = nav.groupby("amfi_code")["nav"].transform(lambda s: s / s.iloc[0] * 100)

    nifty50 = fetch_index("^NSEI", "nifty50")
    nifty100 = fetch_index("^CNX100", "nifty100")
    benchmark = nifty50.merge(nifty100, on="date", how="outer").sort_values("date").ffill()
    for col in ("nifty50", "nifty100"):
        benchmark[f"normalized_{col}"] = benchmark[col] / benchmark[col].dropna().iloc[0] * 100
    nav = nav.merge(
        benchmark[["date", "nifty50", "nifty100", "normalized_nifty50", "normalized_nifty100"]],
        on="date", how="left",
    )
    nav[["nifty50", "nifty100", "normalized_nifty50", "normalized_nifty100"]] = (
        nav.groupby("amfi_code")[["nifty50", "nifty100", "normalized_nifty50", "normalized_nifty100"]]
        .ffill().bfill()
    )
    nav["data_status"] = "Observed NAV and benchmark closes"
    return nav


def make_industry_monthly() -> pd.DataFrame:
    dates = pd.date_range("2022-01-31", END_DATE, freq="ME")
    n = len(dates)
    t = np.linspace(0, 1, n)

    aum = 3_720_000 * (8_100_000 / 3_720_000) ** t
    aum *= 1 + 0.018 * np.sin(np.arange(n) * 2 * np.pi / 12) + RNG.normal(0, 0.007, n)
    sip = 11_500 + (31_000 - 11_500) * (t**1.15)
    sip *= 1 + 0.035 * np.sin(np.arange(n) * 2 * np.pi / 12 + 0.8) + RNG.normal(0, 0.012, n)
    folios = 120_000_000 + (261_200_000 - 120_000_000) * (t**1.08)
    schemes = np.round(1_500 + (1_908 - 1_500) * t)

    industry = pd.DataFrame({
        "date": dates,
        "aum_crore": np.round(aum, 0),
        "sip_inflow_crore": np.round(sip, 0),
        "folios": np.round(folios, 0).astype(int),
        "schemes": schemes.astype(int),
    })
    industry.loc[industry.index[-1], ["aum_crore", "sip_inflow_crore", "folios", "schemes"]] = [
        8_100_000, 31_000, 261_200_000, 1_908,
    ]
    benchmark = fetch_index("^NSEI", "nifty50")
    benchmark = benchmark.set_index("date").resample("ME").last().reset_index()
    industry = industry.merge(benchmark, on="date", how="left")
    industry["nifty50"] = industry["nifty50"].ffill().bfill()
    industry["data_status"] = "Illustrative industry series; observed Nifty 50 close"
    return industry


def make_transactions(dim_fund: pd.DataFrame, fact_aum: pd.DataFrame, n_rows: int = 24_000) -> pd.DataFrame:
    states = [
        "Maharashtra", "Karnataka", "Delhi", "Tamil Nadu", "Gujarat", "West Bengal",
        "Telangana", "Uttar Pradesh", "Rajasthan", "Kerala", "Madhya Pradesh", "Punjab",
    ]
    state_prob = np.array([0.18, 0.12, 0.10, 0.09, 0.09, 0.08, 0.08, 0.08, 0.05, 0.05, 0.04, 0.04])
    cities = {
        "Maharashtra": ("Mumbai", "Tier 1"), "Karnataka": ("Bengaluru", "Tier 1"),
        "Delhi": ("New Delhi", "Tier 1"), "Tamil Nadu": ("Chennai", "Tier 1"),
        "Gujarat": ("Ahmedabad", "Tier 2"), "West Bengal": ("Kolkata", "Tier 1"),
        "Telangana": ("Hyderabad", "Tier 1"), "Uttar Pradesh": ("Lucknow", "Tier 2"),
        "Rajasthan": ("Jaipur", "Tier 2"), "Kerala": ("Kochi", "Tier 2"),
        "Madhya Pradesh": ("Indore", "Tier 2"), "Punjab": ("Ludhiana", "Tier 2"),
    }
    transaction_types = np.array(["SIP", "Lumpsum", "Redemption"])
    type_prob = np.array([0.56, 0.27, 0.17])
    age_groups = np.array(["18-25", "26-35", "36-45", "46-55", "56+"])
    age_prob = np.array([0.10, 0.32, 0.28, 0.19, 0.11])
    age_ranges = {"18-25": (18, 25), "26-35": (26, 35), "36-45": (36, 45), "46-55": (46, 55), "56+": (56, 72)}

    offsets = RNG.integers(0, (END_DATE - START_DATE).days + 1, n_rows)
    dates = START_DATE + pd.to_timedelta(offsets, unit="D")
    selected_states = RNG.choice(states, n_rows, p=state_prob)
    selected_types = RNG.choice(transaction_types, n_rows, p=type_prob)
    selected_ages = RNG.choice(age_groups, n_rows, p=age_prob)

    fund_weights = fact_aum.set_index("amfi_code").loc[dim_fund["amfi_code"], "aum_crore"].to_numpy()
    fund_weights = fund_weights / fund_weights.sum()
    fund_codes = RNG.choice(dim_fund["amfi_code"].to_numpy(), n_rows, p=fund_weights)

    base = np.where(selected_types == "SIP", 5_500, np.where(selected_types == "Lumpsum", 72_000, 54_000))
    age_multiplier = pd.Series(selected_ages).map({"18-25": 0.65, "26-35": 1.0, "36-45": 1.35, "46-55": 1.65, "56+": 1.45}).to_numpy()
    amount = base * age_multiplier * RNG.lognormal(mean=0.0, sigma=0.65, size=n_rows)
    amount = np.round(np.clip(amount, 500, 2_500_000), 2)

    out = pd.DataFrame({
        "transaction_id": [f"TX{i:06d}" for i in range(1, n_rows + 1)],
        "investor_id": [f"INV{i:06d}" for i in RNG.integers(1, 9_500, n_rows)],
        "amfi_code": fund_codes,
        "date": dates,
        "transaction_type": selected_types,
        "amount_rupees": amount,
        "amount_crore": amount / 10_000_000,
        "state": selected_states,
        "age_group": selected_ages,
    })
    out["age"] = [RNG.integers(age_ranges[g][0], age_ranges[g][1] + 1) for g in selected_ages]
    out["city"] = [cities[s][0] for s in selected_states]
    out["city_tier"] = [cities[s][1] for s in selected_states]
    # Add a controlled Tier 3 sample so the slicer has all requested tiers.
    tier3_mask = RNG.random(n_rows) < 0.12
    out.loc[tier3_mask, "city"] = "Other City"
    out.loc[tier3_mask, "city_tier"] = "Tier 3"
    out["net_amount_crore"] = np.where(out["transaction_type"].eq("Redemption"), -out["amount_crore"], out["amount_crore"])
    out["data_status"] = "Deterministic illustrative investor transaction"
    return out.sort_values("date")


def make_category_flows(industry: pd.DataFrame) -> pd.DataFrame:
    categories = [
        "Large Cap", "Flexi Cap", "Mid Cap", "Small Cap", "Hybrid", "Debt",
        "Index & ETF", "ELSS",
    ]
    weights = np.array([0.16, 0.18, 0.14, 0.12, 0.13, 0.11, 0.10, 0.06])
    rows: list[dict] = []
    for month_idx, row in industry.reset_index(drop=True).iterrows():
        seasonal = 1 + 0.08 * math.sin(month_idx * 2 * math.pi / 12)
        for idx, category in enumerate(categories):
            gross = row.sip_inflow_crore * weights[idx] * seasonal * (1 + RNG.normal(0, 0.08))
            redemption_rate = [0.42, 0.36, 0.41, 0.33, 0.47, 0.58, 0.38, 0.45][idx]
            outflow = gross * redemption_rate * (1 + RNG.normal(0, 0.06))
            rows.append({
                "date": row.date,
                "category": category,
                "gross_inflow_crore": round(max(gross, 0), 2),
                "outflow_crore": round(max(outflow, 0), 2),
                "net_inflow_crore": round(gross - outflow, 2),
            })
    flows = pd.DataFrame(rows)
    flows["fiscal_year"] = np.where(
        flows["date"].dt.month >= 4,
        "FY" + ((flows["date"].dt.year + 1) % 100).astype(str).str.zfill(2),
        "FY" + (flows["date"].dt.year % 100).astype(str).str.zfill(2),
    )
    top5 = (
        flows.loc[flows["fiscal_year"].eq("FY25")]
        .groupby("category")["net_inflow_crore"].sum().nlargest(5).index
    )
    flows["top5_fy25"] = flows["category"].isin(top5).astype(int)
    flows["data_status"] = "Deterministic illustrative category flow"
    return flows


def save_csv(frame: pd.DataFrame, name: str) -> None:
    out = frame.copy()
    for col in out.select_dtypes(include=["datetime64[ns]"]).columns:
        out[col] = out[col].dt.strftime("%Y-%m-%d")
    out.to_csv(DATA_DIR / name, index=False, float_format="%.6f")


def card(fig: plt.Figure, x: float, y: float, w: float, h: float, value: str, label: str, accent: str) -> None:
    fig.patches.append(FancyBboxPatch(
        (x, y), w, h, transform=fig.transFigure, boxstyle="round,pad=0.008,rounding_size=0.015",
        facecolor=WHITE, edgecolor="#E1E8F2", linewidth=1.2,
    ))
    fig.patches.append(Rectangle((x, y), 0.006, h, transform=fig.transFigure, facecolor=accent, edgecolor="none"))
    fig.text(x + 0.022, y + h * 0.58, value, fontsize=22, weight="bold", color=INK, va="center")
    fig.text(x + 0.022, y + h * 0.27, label, fontsize=10.5, color=MUTED, va="center")


def style_axis(ax: plt.Axes, title: str) -> None:
    ax.set_facecolor(WHITE)
    ax.set_title(title, loc="left", fontsize=12.5, weight="bold", color=INK, pad=13)
    ax.tick_params(colors=MUTED, labelsize=8.5)
    ax.grid(axis="y", color=GRID, linewidth=0.7, alpha=0.8)
    for spine in ax.spines.values():
        spine.set_visible(False)


def header(fig: plt.Figure, page_title: str, page_no: int) -> None:
    fig.patch.set_facecolor(PAGE)
    fig.patches.append(Rectangle((0, 0.925), 1, 0.075, transform=fig.transFigure, facecolor=NAVY, edgecolor="none"))
    # Code-native Bluestock wordmark.
    fig.patches.extend([
        Rectangle((0.028, 0.948), 0.010, 0.025, transform=fig.transFigure, facecolor=CYAN, edgecolor="none"),
        Rectangle((0.041, 0.942), 0.010, 0.031, transform=fig.transFigure, facecolor=BLUE, edgecolor="none"),
        Rectangle((0.054, 0.936), 0.010, 0.037, transform=fig.transFigure, facecolor=TEAL, edgecolor="none"),
    ])
    fig.text(0.073, 0.957, "BLUESTOCK", color=WHITE, fontsize=14, weight="bold", va="center")
    fig.text(0.19, 0.957, page_title, color=WHITE, fontsize=15, va="center")
    fig.text(0.965, 0.957, f"0{page_no}", color="#9BB9E5", fontsize=11, ha="right", va="center")
    fig.text(0.03, 0.018, "Bluestock Mutual Fund Intelligence  |  2022–2025  |  Illustrative rows are flagged in the data model", color=MUTED, fontsize=7.5)


def make_page_1(industry: pd.DataFrame, fact_aum: pd.DataFrame) -> plt.Figure:
    fig = plt.figure(figsize=(16, 9), dpi=100)
    header(fig, "Industry Overview", 1)
    card(fig, 0.03, 0.77, 0.215, 0.115, "₹81L Cr", "Total industry AUM", BLUE)
    card(fig, 0.265, 0.77, 0.215, 0.115, "₹31K Cr", "Monthly SIP inflows", CYAN)
    card(fig, 0.50, 0.77, 0.215, 0.115, "26.12 Cr", "Investor folios", TEAL)
    card(fig, 0.735, 0.77, 0.235, 0.115, "1,908", "Active schemes", ORANGE)

    ax1 = fig.add_axes([0.04, 0.10, 0.52, 0.60])
    style_axis(ax1, "Industry AUM trend")
    ax1.plot(industry["date"], industry["aum_crore"] / 100_000, color=BLUE, linewidth=3)
    ax1.fill_between(industry["date"], industry["aum_crore"] / 100_000, color=BLUE, alpha=0.09)
    ax1.set_ylabel("₹ lakh crore", color=MUTED, fontsize=9)
    ax1.xaxis.set_major_locator(mdates.YearLocator())
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax1.set_xlim(START_DATE, END_DATE)
    ax1.text(industry["date"].iloc[-1], industry["aum_crore"].iloc[-1] / 100_000 + 1.2, "₹81L Cr", color=BLUE, weight="bold", ha="right")

    amc = fact_aum.groupby("fund_house", as_index=False)["aum_crore"].sum().nlargest(10, "aum_crore").sort_values("aum_crore")
    ax2 = fig.add_axes([0.67, 0.10, 0.30, 0.60])
    style_axis(ax2, "AUM by AMC — selected 40-fund universe")
    ax2.barh(amc["fund_house"].str.replace(" Mutual Fund", "", regex=False), amc["aum_crore"] / 1_000, color=BLUE, alpha=0.9)
    ax2.set_xlabel("₹ thousand crore (illustrative)", color=MUTED, fontsize=8.5)
    ax2.tick_params(axis="y", labelsize=8)
    return fig


def make_page_2(perf: pd.DataFrame, nav: pd.DataFrame, dim_fund: pd.DataFrame) -> plt.Figure:
    fig = plt.figure(figsize=(16, 9), dpi=100)
    header(fig, "Fund Performance", 2)
    for idx, (label, value) in enumerate([
        ("Fund house", "All AMCs"), ("Category", "Large & Flexi Cap"), ("Plan", "Direct Growth"),
    ]):
        x = 0.04 + idx * 0.205
        fig.patches.append(FancyBboxPatch((x, 0.82), 0.185, 0.06, transform=fig.transFigure, boxstyle="round,pad=0.006,rounding_size=0.01", facecolor=WHITE, edgecolor="#DCE5F0"))
        fig.text(x + 0.012, 0.862, label.upper(), fontsize=7.5, color=MUTED, va="center")
        fig.text(x + 0.012, 0.837, value, fontsize=9.5, color=INK, weight="bold", va="center")

    ax_scatter = fig.add_axes([0.04, 0.46, 0.43, 0.31])
    style_axis(ax_scatter, "Return vs risk — bubble size = AUM")
    sizes = 40 + 650 * (perf["aum_crore"] / perf["aum_crore"].max())
    categories = perf["category"].drop_duplicates().tolist()
    color_map = {cat: PALETTE[i % len(PALETTE)] for i, cat in enumerate(categories)}
    for cat, group in perf.groupby("category"):
        ax_scatter.scatter(group["cagr_3y_pct"], group["annualized_volatility_pct"], s=sizes[group.index], c=color_map[cat], alpha=0.72, edgecolor=WHITE, linewidth=0.8, label=cat)
    ax_scatter.set_xlabel("3-year CAGR (%)", fontsize=8.5, color=MUTED)
    ax_scatter.set_ylabel("Annualised volatility (%)", fontsize=8.5, color=MUTED)
    ax_scatter.legend(frameon=False, fontsize=7.5, loc="upper left")

    top5 = perf.nsmallest(5, "overall_rank")
    top_codes = top5["amfi_code"].astype(str).tolist()
    chart_nav = nav.loc[nav["amfi_code"].isin(top_codes)].copy()
    monthly = chart_nav.set_index("date").groupby("amfi_code")["normalized_nav"].resample("ME").last().reset_index()
    ax_nav = fig.add_axes([0.51, 0.46, 0.46, 0.31])
    style_axis(ax_nav, "Top funds vs Nifty 50 — growth of ₹100")
    for i, code in enumerate(top_codes):
        g = monthly.loc[monthly["amfi_code"].eq(code)]
        label = top5.loc[top5["amfi_code"].astype(str).eq(code), "scheme_name"].iloc[0].split(" Growth")[0][:24]
        ax_nav.plot(g["date"], g["normalized_nav"], linewidth=1.7, color=PALETTE[i], label=label)
    bench = chart_nav.groupby("date")["normalized_nifty50"].mean().resample("ME").last()
    ax_nav.plot(bench.index, bench.values, color=NAVY, linewidth=2.4, linestyle="--", label="Nifty 50")
    ax_nav.legend(frameon=False, fontsize=6.8, ncol=2, loc="upper left")
    ax_nav.xaxis.set_major_locator(mdates.YearLocator())
    ax_nav.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax_nav.set_xlim(START_DATE, END_DATE)

    ax_table = fig.add_axes([0.04, 0.07, 0.93, 0.30])
    ax_table.axis("off")
    display = perf.nsmallest(8, "overall_rank")[["overall_rank", "scheme_name", "fund_score", "cagr_3y_pct", "sharpe_ratio", "alpha_annual_pct", "max_drawdown_pct"]].copy()
    display["scheme_name"] = display["scheme_name"].str.replace(" Growth Direct Plan", "", regex=False).str.slice(0, 36)
    display.columns = ["Rank", "Fund", "Score", "3Y CAGR", "Sharpe", "Alpha", "Max DD"]
    for c in ["Score", "3Y CAGR", "Sharpe", "Alpha", "Max DD"]:
        display[c] = display[c].map(lambda x: f"{x:,.2f}")
    table = ax_table.table(cellText=display.values, colLabels=display.columns, loc="center", cellLoc="left", colLoc="left", colWidths=[0.06, 0.40, 0.10, 0.11, 0.09, 0.10, 0.10])
    table.auto_set_font_size(False); table.set_fontsize(8.5); table.scale(1, 1.45)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#E5ECF5")
        cell.set_facecolor(NAVY if r == 0 else (WHITE if r % 2 else "#F7F9FC"))
        cell.get_text().set_color(WHITE if r == 0 else INK)
        if r == 0: cell.get_text().set_weight("bold")
    fig.text(0.04, 0.385, "Sortable fund scorecard  ·  Right-click a fund in Power BI to drill through to NAV detail", fontsize=10.5, weight="bold", color=INK)
    return fig


def make_page_3(transactions: pd.DataFrame) -> plt.Figure:
    fig = plt.figure(figsize=(16, 9), dpi=100)
    header(fig, "Investor Analytics", 3)
    for idx, (label, value) in enumerate([("State", "All India"), ("Age group", "All ages"), ("City tier", "Tier 1–3")]):
        x = 0.04 + idx * 0.205
        fig.patches.append(FancyBboxPatch((x, 0.82), 0.185, 0.06, transform=fig.transFigure, boxstyle="round,pad=0.006,rounding_size=0.01", facecolor=WHITE, edgecolor="#DCE5F0"))
        fig.text(x + 0.012, 0.862, label.upper(), fontsize=7.5, color=MUTED, va="center")
        fig.text(x + 0.012, 0.837, value, fontsize=9.5, color=INK, weight="bold", va="center")

    state = transactions.groupby("state")["amount_crore"].sum().sort_values().tail(10)
    ax1 = fig.add_axes([0.075, 0.48, 0.395, 0.29]); style_axis(ax1, "Transaction amount by state")
    ax1.barh(state.index, state.values, color=BLUE)
    ax1.set_xlabel("₹ crore", fontsize=8.5, color=MUTED)

    split = transactions.groupby("transaction_type")["amount_crore"].sum().sort_values(ascending=False)
    ax2 = fig.add_axes([0.52, 0.48, 0.22, 0.29]); ax2.set_facecolor(WHITE)
    ax2.set_title("Transaction mix", loc="left", fontsize=12.5, weight="bold", color=INK, pad=13)
    ax2.pie(split.values, labels=split.index, autopct="%1.0f%%", startangle=90, colors=[BLUE, TEAL, ORANGE], wedgeprops={"width": 0.42, "edgecolor": WHITE}, textprops={"fontsize": 8, "color": INK})

    sip = transactions.loc[transactions["transaction_type"].eq("SIP")].groupby("age_group")["amount_rupees"].mean().reindex(["18-25", "26-35", "36-45", "46-55", "56+"])
    ax3 = fig.add_axes([0.78, 0.48, 0.19, 0.29]); style_axis(ax3, "Age vs avg SIP")
    ax3.bar(sip.index, sip.values / 1_000, color=TEAL)
    ax3.set_ylabel("₹ thousand", fontsize=8, color=MUTED)
    ax3.tick_params(axis="x", rotation=25)

    monthly = transactions.set_index("date").resample("ME")["transaction_id"].count()
    ax4 = fig.add_axes([0.04, 0.08, 0.93, 0.29]); style_axis(ax4, "Monthly transaction volume")
    ax4.plot(monthly.index, monthly.values, color=CYAN, linewidth=2.5)
    ax4.fill_between(monthly.index, monthly.values, color=CYAN, alpha=0.10)
    ax4.xaxis.set_major_locator(mdates.YearLocator()); ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax4.set_xlim(START_DATE, END_DATE)
    return fig


def make_page_4(industry: pd.DataFrame, flows: pd.DataFrame) -> plt.Figure:
    fig = plt.figure(figsize=(16, 9), dpi=100)
    header(fig, "SIP & Market Trends", 4)
    ax1 = fig.add_axes([0.04, 0.51, 0.93, 0.32]); style_axis(ax1, "SIP inflow + Nifty 50 | 2022–2025")
    ax1.bar(industry["date"], industry["sip_inflow_crore"] / 1_000, width=20, color=CYAN, alpha=0.72, label="SIP inflow")
    ax1.set_ylabel("₹ thousand crore", color=MUTED, fontsize=8.5)
    ax1b = ax1.twinx(); ax1b.plot(industry["date"], industry["nifty50"], color=NAVY, linewidth=2.5, label="Nifty 50")
    ax1b.set_ylabel("Nifty 50", color=MUTED, fontsize=8.5); ax1b.tick_params(colors=MUTED, labelsize=8)
    for spine in ax1b.spines.values(): spine.set_visible(False)
    ax1.xaxis.set_major_locator(mdates.YearLocator()); ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax1.set_xlim(START_DATE, END_DATE)
    handles = ax1.get_legend_handles_labels()[0] + ax1b.get_legend_handles_labels()[0]
    labels = ax1.get_legend_handles_labels()[1] + ax1b.get_legend_handles_labels()[1]
    ax1.legend(handles, labels, frameon=False, loc="upper left", ncol=2)

    heat = flows.pivot_table(index="category", columns="fiscal_year", values="net_inflow_crore", aggfunc="sum")
    fiscal_order = [c for c in ["FY22", "FY23", "FY24", "FY25", "FY26"] if c in heat.columns]
    heat = heat[fiscal_order]
    ax2 = fig.add_axes([0.075, 0.08, 0.515, 0.32]); ax2.set_facecolor(WHITE)
    ax2.set_title("Category net inflow heatmap", loc="left", fontsize=12.5, weight="bold", color=INK, pad=13)
    im = ax2.imshow(heat.values, cmap="Blues", aspect="auto")
    ax2.set_yticks(range(len(heat.index)), heat.index, fontsize=8, color=MUTED)
    ax2.set_xticks(range(len(heat.columns)), heat.columns, fontsize=8, color=MUTED)
    for i in range(heat.shape[0]):
        for j in range(heat.shape[1]):
            ax2.text(j, i, f"{heat.iloc[i, j]/1000:.1f}K", ha="center", va="center", fontsize=7, color=WHITE if heat.iloc[i, j] > np.nanmedian(heat.values) else INK)
    for spine in ax2.spines.values(): spine.set_visible(False)

    top5 = flows.loc[flows["fiscal_year"].eq("FY25")].groupby("category")["net_inflow_crore"].sum().nlargest(5).sort_values()
    ax3 = fig.add_axes([0.64, 0.08, 0.33, 0.32]); style_axis(ax3, "Top 5 categories by net inflow — FY25")
    ax3.barh(top5.index, top5.values / 1_000, color=[TEAL, CYAN, BLUE, "#3D80D8", NAVY])
    ax3.set_xlabel("₹ thousand crore", fontsize=8.5, color=MUTED)
    return fig


def export_pages(industry: pd.DataFrame, fact_aum: pd.DataFrame, performance: pd.DataFrame, nav: pd.DataFrame, dim_fund: pd.DataFrame, transactions: pd.DataFrame, flows: pd.DataFrame) -> None:
    figures = [
        make_page_1(industry, fact_aum),
        make_page_2(performance, nav, dim_fund),
        make_page_3(transactions),
        make_page_4(industry, flows),
    ]
    names = [
        "Dashboard_Page1_Industry_Overview.png",
        "Dashboard_Page2_Fund_Performance.png",
        "Dashboard_Page3_Investor_Analytics.png",
        "Dashboard_Page4_SIP_Market_Trends.png",
    ]
    with PdfPages(ROOT / "Dashboard.pdf") as pdf:
        for fig, name in zip(figures, names):
            fig.savefig(ROOT / name, dpi=100, facecolor=fig.get_facecolor())
            pdf.savefig(fig, dpi=150, facecolor=fig.get_facecolor())
            plt.close(fig)


def main() -> None:
    scorecard = pd.read_csv(ROOT / "fund_scorecard.csv")
    assert len(scorecard) == 40 and scorecard["scheme_code"].nunique() == 40

    dim_date = make_date_dimension()
    dim_fund, fact_aum, fact_performance = make_fund_tables(scorecard)
    fact_nav = make_nav_table(dim_fund)
    fact_industry = make_industry_monthly()
    fact_transactions = make_transactions(dim_fund, fact_aum)
    fact_category_flows = make_category_flows(fact_industry)

    tables = {
        "dim_date.csv": dim_date,
        "dim_fund.csv": dim_fund,
        "fact_nav.csv": fact_nav,
        "fact_performance.csv": fact_performance,
        "fact_fund_aum.csv": fact_aum,
        "fact_investor_transactions.csv": fact_transactions,
        "fact_industry_monthly.csv": fact_industry,
        "fact_category_flows.csv": fact_category_flows,
    }
    for name, frame in tables.items():
        save_csv(frame, name)

    # Contract checks used by the report model.
    assert len(tables) == 8
    assert fact_nav["amfi_code"].nunique() == 40
    assert dim_fund["amfi_code"].nunique() == 40
    assert fact_performance["fund_score"].between(0, 100).all()
    assert fact_industry.iloc[-1]["aum_crore"] == 8_100_000
    assert fact_industry.iloc[-1]["sip_inflow_crore"] == 31_000
    assert fact_industry.iloc[-1]["folios"] == 261_200_000
    assert fact_industry.iloc[-1]["schemes"] == 1_908

    export_pages(fact_industry, fact_aum, fact_performance, fact_nav, dim_fund, fact_transactions, fact_category_flows)
    print("Created eight dashboard tables:")
    for name, frame in tables.items():
        print(f"  {name}: {len(frame):,} rows")
    print("Created Dashboard.pdf and four page PNG exports")


if __name__ == "__main__":
    main()
