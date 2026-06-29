"""Generate an editable Power BI Project (PBIP) from the eight dashboard CSVs.

The report uses Microsoft's PBIR JSON format and a TMDL semantic model, so the
relationships, measures, pages, visuals, slicers, tooltip behavior, and
drillthrough target remain source-controllable and can be opened by Power BI
Desktop before packaging as PBIX.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import uuid

import pandas as pd


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "dashboard" / "powerbi"
REPORT = PROJECT / "bluestock_mf_dashboard.Report"
MODEL = PROJECT / "bluestock_mf_dashboard.SemanticModel"
DATA = ROOT / "dashboard" / "data"

VISUAL_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.7.0/schema.json"
PAGE_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.0.0/schema.json"
REPORT_SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/3.0.0/schema.json"

NAVY = "#071A3D"
BLUE = "#0B63CE"
CYAN = "#17B6E6"
TEAL = "#15B8A6"
ORANGE = "#FF9F43"
INK = "#15233B"
MUTED = "#65738B"
PAGE = "#F4F7FB"
WHITE = "#FFFFFF"


TABLE_SPECS = {
    "Dim_Date": {
        "file": "dim_date.csv",
        "types": {
            "date": "date", "date_key": "int", "year": "int", "quarter": "text",
            "month": "int", "month_name": "text", "month_year": "text",
            "fiscal_year": "text", "is_month_end": "bool",
        },
    },
    "Dim_Fund": {
        "file": "dim_fund.csv",
        "types": {
            "amfi_code": "text", "scheme_name": "text", "fund_house": "text",
            "category": "text", "plan": "text", "risk_band": "text",
            "expense_ratio_pct": "number", "expense_ratio_date": "date", "data_status": "text",
        },
    },
    "Fact_NAV": {
        "file": "fact_nav.csv",
        "types": {
            "date": "date", "amfi_code": "text", "scheme_name": "text", "nav": "number",
            "daily_return": "number", "normalized_nav": "number", "nifty50": "number",
            "nifty100": "number", "normalized_nifty50": "number",
            "normalized_nifty100": "number", "data_status": "text",
        },
    },
    "Fact_Performance": {
        "file": "fact_performance.csv",
        "types": {
            "amfi_code": "text", "scheme_name": "text", "fund_house": "text", "category": "text",
            "plan": "text", "date": "date", "as_of_date": "date", "overall_rank": "int",
            "fund_score": "number", "cagr_1y_pct": "number", "cagr_3y_pct": "number",
            "cagr_5y_pct": "number", "sharpe_ratio": "number", "sortino_ratio": "number",
            "annualized_volatility_pct": "number", "alpha_annual_pct": "number", "beta": "number",
            "r_squared": "number", "expense_ratio_pct": "number", "max_drawdown_pct": "number",
            "drawdown_peak_date": "date", "drawdown_trough_date": "date",
            "tracking_error_nifty50_pct": "number", "tracking_error_nifty100_pct": "number",
            "aum_crore": "number", "risk_band": "text", "data_status": "text",
        },
    },
    "Fact_Fund_AUM": {
        "file": "fact_fund_aum.csv",
        "types": {
            "amfi_code": "text", "scheme_name": "text", "fund_house": "text", "category": "text",
            "aum_crore": "number", "date": "date", "data_status": "text",
        },
    },
    "Fact_Investor_Transactions": {
        "file": "fact_investor_transactions.csv",
        "types": {
            "transaction_id": "text", "investor_id": "text", "amfi_code": "text", "date": "date",
            "transaction_type": "text", "amount_rupees": "number", "amount_crore": "number",
            "state": "text", "age_group": "text", "age": "int", "city": "text",
            "city_tier": "text", "net_amount_crore": "number", "data_status": "text",
        },
    },
    "Fact_Industry_Monthly": {
        "file": "fact_industry_monthly.csv",
        "types": {
            "date": "date", "aum_crore": "number", "sip_inflow_crore": "number",
            "folios": "int", "schemes": "int", "nifty50": "number", "data_status": "text",
        },
    },
    "Fact_Category_Flows": {
        "file": "fact_category_flows.csv",
        "types": {
            "date": "date", "category": "text", "gross_inflow_crore": "number",
            "outflow_crore": "number", "net_inflow_crore": "number", "fiscal_year": "text",
            "top5_fy25": "int", "data_status": "text",
        },
    },
}


MEASURES = {
    "Fact_Industry_Monthly": [
        ("Industry AUM Cr", "MAX(Fact_Industry_Monthly[aum_crore])", "₹#,0"),
        ("SIP Inflow Cr", "MAX(Fact_Industry_Monthly[sip_inflow_crore])", "₹#,0"),
        ("Folios Count", "MAX(Fact_Industry_Monthly[folios])", "#,0"),
        ("Schemes Count", "MAX(Fact_Industry_Monthly[schemes])", "#,0"),
        ("Nifty 50", "MAX(Fact_Industry_Monthly[nifty50])", "#,0"),
        ("AUM Display", '"₹" & FORMAT([Industry AUM Cr] / 100000, "0") & "L Cr"', None),
        ("SIP Display", '"₹" & FORMAT([SIP Inflow Cr] / 1000, "0") & "K Cr"', None),
        ("Folios Display", 'FORMAT([Folios Count] / 10000000, "0.00") & " Cr"', None),
        ("Schemes Display", 'FORMAT([Schemes Count], "#,0")', None),
    ],
    "Fact_Fund_AUM": [
        ("Total Fund AUM", "SUM(Fact_Fund_AUM[aum_crore])", "₹#,0 Cr"),
    ],
    "Fact_Performance": [
        ("Fund Rank", "MIN(Fact_Performance[overall_rank])", "0"),
        ("Fund Score", "MAX(Fact_Performance[fund_score])", "0.00"),
        ("3Y CAGR", "MAX(Fact_Performance[cagr_3y_pct])", "0.00%"),
        ("Sharpe", "MAX(Fact_Performance[sharpe_ratio])", "0.00"),
        ("Sortino", "MAX(Fact_Performance[sortino_ratio])", "0.00"),
        ("Alpha", "MAX(Fact_Performance[alpha_annual_pct])", "0.00%"),
        ("Max Drawdown", "MAX(Fact_Performance[max_drawdown_pct])", "0.00%"),
        ("Avg 3Y Return", "AVERAGE(Fact_Performance[cagr_3y_pct])", "0.00%"),
        ("Avg Risk", "AVERAGE(Fact_Performance[annualized_volatility_pct])", "0.00%"),
        ("AUM Size", "SUM(Fact_Performance[aum_crore])", "₹#,0 Cr"),
    ],
    "Fact_NAV": [
        ("NAV Value", "AVERAGE(Fact_NAV[nav])", "0.0000"),
        ("Daily Return", "AVERAGE(Fact_NAV[daily_return])", "0.00%"),
        ("Fund Growth Index", "AVERAGE(Fact_NAV[normalized_nav])", "0.0"),
        ("Nifty 50 Growth Index", "AVERAGE(Fact_NAV[normalized_nifty50])", "0.0"),
        ("Nifty 100 Growth Index", "AVERAGE(Fact_NAV[normalized_nifty100])", "0.0"),
    ],
    "Fact_Investor_Transactions": [
        ("Transaction Amount", "SUM(Fact_Investor_Transactions[amount_crore])", "₹#,0.00 Cr"),
        ("Transaction Volume", "COUNTROWS(Fact_Investor_Transactions)", "#,0"),
        ("Avg SIP Amount", 'CALCULATE(AVERAGE(Fact_Investor_Transactions[amount_rupees]), Fact_Investor_Transactions[transaction_type] = "SIP")', "₹#,0"),
    ],
    "Fact_Category_Flows": [
        ("Net Inflow", "SUM(Fact_Category_Flows[net_inflow_crore])", "₹#,0 Cr"),
        ("FY25 Top 5 Net Inflow", 'CALCULATE([Net Inflow], Fact_Category_Flows[fiscal_year] = "FY25", Fact_Category_Flows[top5_fy25] = 1)', "₹#,0 Cr"),
    ],
}


RELATIONSHIPS = [
    ("Fact_NAV", "amfi_code", "Dim_Fund", "amfi_code"),
    ("Fact_Performance", "amfi_code", "Dim_Fund", "amfi_code"),
    ("Fact_Fund_AUM", "amfi_code", "Dim_Fund", "amfi_code"),
    ("Fact_Investor_Transactions", "amfi_code", "Dim_Fund", "amfi_code"),
    ("Fact_NAV", "date", "Dim_Date", "date"),
    ("Fact_Performance", "date", "Dim_Date", "date"),
    ("Fact_Fund_AUM", "date", "Dim_Date", "date"),
    ("Fact_Investor_Transactions", "date", "Dim_Date", "date"),
    ("Fact_Industry_Monthly", "date", "Dim_Date", "date"),
    ("Fact_Category_Flows", "date", "Dim_Date", "date"),
]


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def tmdl_name(name: str) -> str:
    if name.replace("_", "").isalnum() and not name[0].isdigit():
        return name
    return "'" + name.replace("'", "''") + "'"


def m_type(kind: str) -> str:
    return {"text": "type text", "date": "type date", "int": "Int64.Type", "number": "type number", "bool": "type logical"}[kind]


def tmdl_type(kind: str) -> str:
    return {"text": "string", "date": "dateTime", "int": "int64", "number": "double", "bool": "boolean"}[kind]


def column_format(column: str, kind: str) -> str | None:
    if kind == "date":
        return "yyyy-mm-dd"
    if column in {"daily_return"}:
        return "0.00%"
    if column.endswith("_pct") or column in {"fund_score", "sharpe_ratio", "sortino_ratio", "beta", "r_squared"}:
        return "0.00"
    if column in {"nav"}:
        return "0.0000"
    if "crore" in column or column == "aum_crore":
        return "₹#,0.00"
    if column == "amount_rupees":
        return "₹#,0"
    if kind == "int":
        return "#,0"
    return None


def build_table_tmdl(table: str, spec: dict) -> str:
    csv_path = (DATA / spec["file"]).resolve()
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    actual_columns = pd.read_csv(csv_path, nrows=0).columns.tolist()
    missing = [c for c in spec["types"] if c not in actual_columns]
    extra = [c for c in actual_columns if c not in spec["types"]]
    if missing or extra:
        raise ValueError(f"{table} schema mismatch; missing={missing}; extra={extra}")

    lines = [f"table {tmdl_name(table)}"]
    for column, kind in spec["types"].items():
        lines.extend([
            "",
            f"\tcolumn {tmdl_name(column)}",
            f"\t\tdataType: {tmdl_type(kind)}",
        ])
        fmt = column_format(column, kind)
        if fmt:
            lines.append(f"\t\tformatString: {fmt}")
        lines.extend([
            "\t\tsummarizeBy: none" if kind in {"text", "date", "bool"} else "\t\tsummarizeBy: sum",
            f"\t\tsourceColumn: {column}",
            "",
            "\t\tannotation SummarizationSetBy = Automatic",
        ])

    for name, expression, fmt in MEASURES.get(table, []):
        lines.extend(["", f"\tmeasure {tmdl_name(name)} = {expression}"])
        if fmt:
            lines.append(f"\t\tformatString: {fmt}")

    transforms = ", ".join(f'{{"{col}", {m_type(kind)}}}' for col, kind in spec["types"].items())
    lines.extend([
        "",
        f"\tpartition {tmdl_name(table)} = m",
        "\t\tmode: import",
        "\t\tsource =",
        "\t\t\t\tlet",
        f'\t\t\t\t    Source = Csv.Document(File.Contents("{csv_path}"), [Delimiter=",", Columns={len(actual_columns)}, Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
        '\t\t\t\t    #"Promoted Headers" = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),',
        f'\t\t\t\t    #"Changed Type" = Table.TransformColumnTypes(#"Promoted Headers", {{{transforms}}}, "en-US")',
        "\t\t\t\tin",
        '\t\t\t\t    #"Changed Type"',
        "",
        "\tannotation PBI_NavigationStepName = Navigation",
        "",
        "\tannotation PBI_ResultType = Table",
        "",
    ])
    return "\n".join(lines)


def build_model() -> None:
    definition = MODEL / "definition"
    (definition / "tables").mkdir(parents=True, exist_ok=True)
    write_json(MODEL / "definition.pbism", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
        "version": "4.2",
        "settings": {"qnaEnabled": True},
    })
    (definition / "database.tmdl").write_text(
        "database BluestockMF\n\tcompatibilityLevel: 1702\n\tcompatibilityMode: powerBI\n\tlanguage: 1033\n",
        encoding="utf-8",
    )
    refs = "\n".join(f"ref table {tmdl_name(t)}" for t in TABLE_SPECS)
    query_order = json.dumps(list(TABLE_SPECS), ensure_ascii=False)
    model_text = (
        "model BluestockMF\n"
        "\tculture: en-US\n"
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
        "\tsourceQueryCulture: en-US\n"
        "\tdataAccessOptions\n"
        "\t\tlegacyRedirects\n"
        "\t\treturnErrorValuesAsNull\n\n"
        "annotation __PBI_TimeIntelligenceEnabled = 0\n\n"
        f"annotation PBI_QueryOrder = {query_order}\n\n"
        f"{refs}\n"
    )
    (definition / "model.tmdl").write_text(model_text, encoding="utf-8")
    for table, spec in TABLE_SPECS.items():
        (definition / "tables" / f"{table}.tmdl").write_text(build_table_tmdl(table, spec), encoding="utf-8")

    rel_lines: list[str] = []
    for from_table, from_col, to_table, to_col in RELATIONSHIPS:
        rid = uuid.uuid5(uuid.NAMESPACE_URL, f"bluestock:{from_table}.{from_col}->{to_table}.{to_col}")
        rel_lines.extend([
            f"relationship {rid}",
            f"\tfromColumn: {tmdl_name(from_table)}.{tmdl_name(from_col)}",
            f"\ttoColumn: {tmdl_name(to_table)}.{tmdl_name(to_col)}",
            "",
        ])
    (definition / "relationships.tmdl").write_text("\n".join(rel_lines), encoding="utf-8")
    write_json(MODEL / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": "Bluestock MF Dashboard"},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid5(uuid.NAMESPACE_URL, "bluestock:model"))},
    })


def literal(value: str | bool | int | float) -> dict:
    if isinstance(value, bool):
        encoded = "true" if value else "false"
    elif isinstance(value, int):
        encoded = f"{value}D"
    elif isinstance(value, float):
        encoded = f"{value}D"
    else:
        encoded = "'" + value.replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": encoded}}}


def solid(color: str) -> dict:
    return {"solid": {"color": literal(color)}}


def col_expr(table: str, column: str) -> dict:
    return {"Column": {"Expression": {"SourceRef": {"Entity": table}}, "Property": column}}


def measure_expr(table: str, measure: str) -> dict:
    return {"Measure": {"Expression": {"SourceRef": {"Entity": table}}, "Property": measure}}


def projection(kind: str, table: str, field: str, display_name: str | None = None, active: bool = True) -> dict:
    expr = measure_expr(table, field) if kind == "measure" else col_expr(table, field)
    item = {
        "field": expr,
        "queryRef": f"{table}.{field}",
        "nativeQueryRef": field,
        "active": active,
    }
    if display_name:
        item["displayName"] = display_name
    return item


def container_objects(title: str | None = None, background: str = WHITE, tooltip: bool = True) -> dict:
    objects: dict = {
        "background": [{"properties": {"show": literal(True), "color": solid(background), "transparency": literal(0)}}],
        "border": [{"properties": {"show": literal(True), "color": solid("#DDE6F2"), "radius": literal(8)}}],
    }
    if title:
        objects["title"] = [{"properties": {
            "show": literal(True), "text": literal(title), "fontColor": solid(INK),
            "fontSize": literal(13), "fontFamily": literal("Segoe UI Semibold"),
        }}]
    if tooltip:
        objects["visualTooltip"] = [{"properties": {"show": literal(True)}}]
    return objects


def make_visual(name: str, visual_type: str, x: float, y: float, w: float, h: float,
                roles: dict[str, list[dict]] | None = None, title: str | None = None,
                objects: dict | None = None, sort: tuple[str, str, str] | None = None,
                z: int = 1) -> dict:
    visual: dict = {"visualType": visual_type}
    if roles is not None:
        query: dict = {"queryState": {role: {"projections": items} for role, items in roles.items()}}
        if sort:
            table, field, direction = sort
            query["sortDefinition"] = {
                "sort": [{"field": measure_expr(table, field), "direction": direction}],
                "isDefaultSort": False,
            }
        visual["query"] = query
    if objects:
        visual["objects"] = objects
    visual["visualContainerObjects"] = container_objects(title)
    visual["drillFilterOtherVisuals"] = True
    return {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": visual,
        "howCreated": "Default",
    }


def textbox(name: str, text: str, x: float, y: float, w: float, h: float,
            size: int = 18, color: str = INK, background: str | None = None,
            weight: str = "Semibold", z: int = 100) -> dict:
    visual = {
        "$schema": VISUAL_SCHEMA,
        "name": name,
        "position": {"x": x, "y": y, "z": z, "height": h, "width": w, "tabOrder": z},
        "visual": {
            "visualType": "textbox",
            "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": [{
                "value": text,
                "textStyle": {"fontFamily": f"Segoe UI {weight}", "fontSize": f"{size}pt", "color": color},
            }]}]}}]},
            "visualContainerObjects": {
                "title": [{"properties": {"show": literal(False)}}],
                "background": [{"properties": {"show": literal(background is not None), "color": solid(background or WHITE), "transparency": literal(0)}}],
                "border": [{"properties": {"show": literal(False)}}],
            },
            "drillFilterOtherVisuals": True,
        },
    }
    return visual


def header_visual(page_slug: str, title: str) -> dict:
    return textbox(f"{page_slug}_header", f"▮ ▮ ▮   BLUESTOCK     {title}", 0, 0, 1280, 56, 19, WHITE, NAVY, "Semibold", 100)


def footer_visual(page_slug: str) -> dict:
    return textbox(
        f"{page_slug}_footer",
        "Bluestock Mutual Fund Intelligence  |  2022–2025  |  Illustrative source rows are flagged in data_status",
        24, 690, 1180, 22, 8, MUTED, None, "Regular", 99,
    )


def card_visual(name: str, measure_table: str, measure: str, label: str, x: float, accent: str) -> dict:
    v = make_visual(
        name, "card", x, 74, 285, 104,
        {"Values": [projection("measure", measure_table, measure, label)]},
        label, {"labels": [{"properties": {"fontSize": literal(31), "color": solid(INK)}}]}, z=2,
    )
    v["visual"]["visualContainerObjects"]["border"][0]["properties"]["color"] = solid(accent)
    return v


def slicer_visual(name: str, table: str, column: str, label: str, x: float, y: float, w: float = 190) -> dict:
    return make_visual(
        name, "slicer", x, y, w, 55,
        {"Values": [projection("column", table, column)]},
        label,
        {
            "data": [{"properties": {"mode": literal("Dropdown")}}],
            "selection": [{"properties": {"singleSelect": literal(False)}}],
        }, z=3,
    )


def build_pages() -> dict[str, list[dict]]:
    pages: dict[str, list[dict]] = {}

    p1 = [header_visual("Industry_Overview", "Industry Overview")]
    p1 += [
        card_visual("p1_total_aum", "Fact_Industry_Monthly", "AUM Display", "Total AUM", 30, BLUE),
        card_visual("p1_sip", "Fact_Industry_Monthly", "SIP Display", "SIP Inflows", 335, CYAN),
        card_visual("p1_folios", "Fact_Industry_Monthly", "Folios Display", "Folios", 640, TEAL),
        card_visual("p1_schemes", "Fact_Industry_Monthly", "Schemes Display", "Schemes", 945, ORANGE),
        make_visual(
            "p1_aum_trend", "lineChart", 30, 205, 760, 465,
            {
                "Category": [projection("column", "Fact_Industry_Monthly", "date")],
                "Y": [projection("measure", "Fact_Industry_Monthly", "Industry AUM Cr")],
                "Tooltips": [projection("measure", "Fact_Industry_Monthly", "SIP Inflow Cr")],
            }, "Industry AUM trend | 2022–2025",
            {"legend": [{"properties": {"show": literal(False)}}]}, z=4,
        ),
        make_visual(
            "p1_amc_aum", "barChart", 815, 205, 435, 465,
            {
                "Category": [projection("column", "Dim_Fund", "fund_house")],
                "Y": [projection("measure", "Fact_Fund_AUM", "Total Fund AUM")],
                "Tooltips": [projection("column", "Dim_Fund", "category")],
            }, "AUM by AMC — selected fund universe",
            {"legend": [{"properties": {"show": literal(False)}}]},
            sort=("Fact_Fund_AUM", "Total Fund AUM", "Descending"), z=5,
        ),
        footer_visual("Industry_Overview"),
    ]
    pages["Industry_Overview"] = p1

    p2 = [header_visual("Fund_Performance", "Fund Performance")]
    p2 += [
        slicer_visual("p2_fund_house", "Dim_Fund", "fund_house", "Fund house", 30, 68, 210),
        slicer_visual("p2_category", "Dim_Fund", "category", "Category", 255, 68, 190),
        slicer_visual("p2_plan", "Dim_Fund", "plan", "Plan", 460, 68, 170),
        make_visual(
            "p2_scatter", "scatterChart", 30, 140, 560, 250,
            {
                "Category": [projection("column", "Dim_Fund", "scheme_name")],
                "Series": [projection("column", "Dim_Fund", "category")],
                "X": [projection("measure", "Fact_Performance", "Avg 3Y Return")],
                "Y": [projection("measure", "Fact_Performance", "Avg Risk")],
                "Size": [projection("measure", "Fact_Performance", "AUM Size")],
                "Tooltips": [
                    projection("measure", "Fact_Performance", "Fund Score"),
                    projection("measure", "Fact_Performance", "Sharpe"),
                    projection("measure", "Fact_Performance", "Alpha"),
                ],
            }, "Return (X) vs risk (Y) | Bubble size = AUM",
            {"legend": [{"properties": {"show": literal(True), "position": literal("Top")}}]}, z=4,
        ),
        make_visual(
            "p2_nav_benchmark", "lineChart", 610, 140, 640, 250,
            {
                "Category": [projection("column", "Fact_NAV", "date")],
                "Y": [
                    projection("measure", "Fact_NAV", "Fund Growth Index"),
                    projection("measure", "Fact_NAV", "Nifty 50 Growth Index"),
                    projection("measure", "Fact_NAV", "Nifty 100 Growth Index"),
                ],
                "Tooltips": [projection("measure", "Fact_NAV", "NAV Value")],
            }, "NAV vs benchmarks | Growth of 100",
            {"legend": [{"properties": {"show": literal(True), "position": literal("Top")}}]}, z=5,
        ),
        make_visual(
            "p2_scorecard", "tableEx", 30, 415, 1220, 255,
            {"Values": [
                projection("column", "Dim_Fund", "scheme_name", "Fund"),
                projection("column", "Dim_Fund", "fund_house", "AMC"),
                projection("column", "Dim_Fund", "category", "Category"),
                projection("measure", "Fact_Performance", "Fund Rank", "Rank"),
                projection("measure", "Fact_Performance", "Fund Score", "Score"),
                projection("measure", "Fact_Performance", "3Y CAGR"),
                projection("measure", "Fact_Performance", "Sharpe"),
                projection("measure", "Fact_Performance", "Alpha"),
                projection("measure", "Fact_Performance", "Max Drawdown"),
            ]}, "Sortable fund scorecard | Right-click a fund to drill through",
            {"grid": [{"properties": {"rowPadding": literal(3)}}]},
            sort=("Fact_Performance", "Fund Rank", "Ascending"), z=6,
        ),
        footer_visual("Fund_Performance"),
    ]
    pages["Fund_Performance"] = p2

    p3 = [header_visual("Investor_Analytics", "Investor Analytics")]
    p3 += [
        slicer_visual("p3_state", "Fact_Investor_Transactions", "state", "State", 30, 68, 200),
        slicer_visual("p3_age", "Fact_Investor_Transactions", "age_group", "Age group", 245, 68, 180),
        slicer_visual("p3_tier", "Fact_Investor_Transactions", "city_tier", "City tier", 440, 68, 180),
        make_visual(
            "p3_state_amount", "barChart", 30, 140, 500, 260,
            {
                "Category": [projection("column", "Fact_Investor_Transactions", "state")],
                "Y": [projection("measure", "Fact_Investor_Transactions", "Transaction Amount")],
                "Tooltips": [projection("measure", "Fact_Investor_Transactions", "Transaction Volume")],
            }, "Transaction amount by state", None,
            sort=("Fact_Investor_Transactions", "Transaction Amount", "Descending"), z=4,
        ),
        make_visual(
            "p3_transaction_mix", "donutChart", 550, 140, 310, 260,
            {
                "Category": [projection("column", "Fact_Investor_Transactions", "transaction_type")],
                "Y": [projection("measure", "Fact_Investor_Transactions", "Transaction Amount")],
                "Tooltips": [projection("measure", "Fact_Investor_Transactions", "Transaction Volume")],
            }, "SIP / Lumpsum / Redemption split",
            {"legend": [{"properties": {"show": literal(True), "position": literal("Bottom")}}]}, z=5,
        ),
        make_visual(
            "p3_age_sip", "columnChart", 880, 140, 370, 260,
            {
                "Category": [projection("column", "Fact_Investor_Transactions", "age_group")],
                "Y": [projection("measure", "Fact_Investor_Transactions", "Avg SIP Amount")],
                "Tooltips": [projection("measure", "Fact_Investor_Transactions", "Transaction Volume")],
            }, "Age group vs average SIP amount", None, z=6,
        ),
        make_visual(
            "p3_monthly_volume", "lineChart", 30, 425, 1220, 245,
            {
                "Category": [projection("column", "Fact_Investor_Transactions", "date")],
                "Y": [projection("measure", "Fact_Investor_Transactions", "Transaction Volume")],
                "Tooltips": [projection("measure", "Fact_Investor_Transactions", "Transaction Amount")],
            }, "Monthly transaction volume", None, z=7,
        ),
        footer_visual("Investor_Analytics"),
    ]
    pages["Investor_Analytics"] = p3

    p4 = [header_visual("SIP_Market_Trends", "SIP & Market Trends")]
    p4 += [
        make_visual(
            "p4_sip_nifty", "lineStackedColumnComboChart", 30, 75, 1220, 300,
            {
                "Category": [projection("column", "Fact_Industry_Monthly", "date")],
                "Y": [projection("measure", "Fact_Industry_Monthly", "SIP Inflow Cr")],
                "Y2": [projection("measure", "Fact_Industry_Monthly", "Nifty 50")],
                "Tooltips": [projection("measure", "Fact_Industry_Monthly", "Industry AUM Cr")],
            }, "SIP inflow (bar) + Nifty 50 (line) | 2022–2025",
            {"legend": [{"properties": {"show": literal(True), "position": literal("Top")}}]}, z=4,
        ),
        make_visual(
            "p4_heatmap", "pivotTable", 30, 400, 730, 270,
            {
                "Rows": [projection("column", "Fact_Category_Flows", "category")],
                "Columns": [projection("column", "Fact_Category_Flows", "fiscal_year")],
                "Values": [projection("measure", "Fact_Category_Flows", "Net Inflow")],
            }, "Category inflow heatmap",
            {"grid": [{"properties": {"rowPadding": literal(4)}}]}, z=5,
        ),
        make_visual(
            "p4_top5", "barChart", 785, 400, 465, 270,
            {
                "Category": [projection("column", "Fact_Category_Flows", "category")],
                "Y": [projection("measure", "Fact_Category_Flows", "FY25 Top 5 Net Inflow")],
                "Tooltips": [projection("measure", "Fact_Category_Flows", "Net Inflow")],
            }, "Top 5 categories by net inflow — FY25", None,
            sort=("Fact_Category_Flows", "FY25 Top 5 Net Inflow", "Descending"), z=6,
        ),
        footer_visual("SIP_Market_Trends"),
    ]
    pages["SIP_Market_Trends"] = p4

    detail = [header_visual("NAV_Detail", "NAV Detail — Drillthrough")]
    detail += [
        textbox("nav_detail_help", "Use the Back command or page tabs to return. This page receives the selected fund filter.", 30, 65, 900, 30, 10, MUTED, None, "Regular", 3),
        make_visual(
            "detail_nav_line", "lineChart", 30, 110, 1220, 330,
            {
                "Category": [projection("column", "Fact_NAV", "date")],
                "Y": [
                    projection("measure", "Fact_NAV", "Fund Growth Index"),
                    projection("measure", "Fact_NAV", "Nifty 50 Growth Index"),
                    projection("measure", "Fact_NAV", "Nifty 100 Growth Index"),
                ],
                "Tooltips": [projection("measure", "Fact_NAV", "NAV Value"), projection("measure", "Fact_NAV", "Daily Return")],
            }, "Daily NAV vs benchmarks | Growth of 100", None, z=4,
        ),
        make_visual(
            "detail_nav_table", "tableEx", 30, 465, 1220, 205,
            {"Values": [
                projection("column", "Dim_Fund", "scheme_name", "Fund"),
                projection("column", "Fact_NAV", "date", "Date"),
                projection("measure", "Fact_NAV", "NAV Value", "NAV"),
                projection("measure", "Fact_NAV", "Daily Return"),
            ]}, "Daily NAV detail", None, z=5,
        ),
        footer_visual("NAV_Detail"),
    ]
    pages["NAV_Detail"] = detail
    return pages


def page_payload(slug: str, display_name: str, drillthrough: bool = False) -> dict:
    payload = {
        "$schema": PAGE_SCHEMA,
        "name": slug,
        "displayName": display_name,
        "displayOption": "FitToPage",
        "height": 720,
        "width": 1280,
        "objects": {
            "background": [{"properties": {"color": solid(PAGE), "transparency": literal(0)}}],
        },
    }
    if drillthrough:
        payload["visibility"] = "HiddenInViewMode"
        payload["filterConfig"] = {"filters": [{
            "name": "nav_detail_fund_filter",
            "field": col_expr("Dim_Fund", "scheme_name"),
            "type": "Categorical",
            "howCreated": "User",
        }]}
        payload["pageBinding"] = {
            "name": str(uuid.uuid5(uuid.NAMESPACE_URL, "bluestock:nav-detail")),
            "type": "Drillthrough",
            "referenceScope": "Default",
            "acceptsFilterContext": "Default",
            "parameters": [{"name": "fund", "boundFilter": "nav_detail_fund_filter"}],
        }
    return payload


def build_report() -> None:
    definition = REPORT / "definition"
    pages_dir = definition / "pages"
    resources = REPORT / "StaticResources" / "RegisteredResources"
    resources.mkdir(parents=True, exist_ok=True)

    write_json(REPORT / "definition.pbir", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definitionProperties/2.0.0/schema.json",
        "version": "4.0",
        "datasetReference": {"byPath": {"path": "../bluestock_mf_dashboard.SemanticModel"}},
    })
    write_json(REPORT / ".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": "Bluestock MF Dashboard"},
        "config": {"version": "2.0", "logicalId": str(uuid.uuid5(uuid.NAMESPACE_URL, "bluestock:report"))},
    })
    write_json(definition / "version.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/versionMetadata/1.0.0/schema.json",
        "version": "2.0.0",
    })

    theme = {
        "$schema": "https://powerbi.com/product/schema#reportTheme",
        "name": "Bluestock",
        "dataColors": [BLUE, CYAN, TEAL, ORANGE, "#7C5CFC", "#E85D75", "#2E8B57", "#F1C40F"],
        "good": TEAL, "neutral": ORANGE, "bad": "#E85D75",
        "background": PAGE, "foreground": INK, "tableAccent": BLUE,
        "textClasses": {
            "title": {"fontFace": "Segoe UI Semibold", "fontSize": 13, "color": INK},
            "label": {"fontFace": "Segoe UI", "fontSize": 9, "color": MUTED},
            "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 30, "color": INK},
            "header": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": INK},
        },
    }
    write_json(resources / "BluestockTheme.json", theme)
    write_json(definition / "report.json", {
        "$schema": REPORT_SCHEMA,
        "themeCollection": {
            "customTheme": {
                "name": "BluestockTheme.json",
                "reportVersionAtImport": {"visual": "2.1.0", "report": "2.1.0", "page": "2.0.0"},
                "type": "RegisteredResources",
            }
        },
        "filterConfig": {"filters": []},
        "resourcePackages": [{
            "name": "RegisteredResources", "type": "RegisteredResources",
            "items": [{"name": "BluestockTheme.json", "path": "BluestockTheme.json", "type": "CustomTheme"}],
        }],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useDefaultAggregateDisplayName": True,
        },
        "annotations": [{"name": "dataProvenance", "value": "Observed performance/NAV; explicitly flagged illustrative industry, AUM, and investor rows"}],
    })

    display_names = {
        "Industry_Overview": "Industry Overview",
        "Fund_Performance": "Fund Performance",
        "Investor_Analytics": "Investor Analytics",
        "SIP_Market_Trends": "SIP & Market Trends",
        "NAV_Detail": "NAV Detail",
    }
    all_pages = build_pages()
    for slug, visuals in all_pages.items():
        page_dir = pages_dir / slug
        write_json(page_dir / "page.json", page_payload(slug, display_names[slug], slug == "NAV_Detail"))
        for visual in visuals:
            write_json(page_dir / "visuals" / visual["name"] / "visual.json", visual)
    write_json(pages_dir / "pages.json", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": list(all_pages),
        "activePageName": "Industry_Overview",
    })


def validate_contract() -> None:
    csvs = sorted(DATA.glob("*.csv"))
    if len(csvs) != 8:
        raise AssertionError(f"Expected 8 dashboard CSVs, found {len(csvs)}")
    for json_file in REPORT.rglob("*.json"):
        json.loads(json_file.read_text(encoding="utf-8"))
    pages = json.loads((REPORT / "definition" / "pages" / "pages.json").read_text(encoding="utf-8"))
    assert len(pages["pageOrder"]) == 5
    assert set(TABLE_SPECS) == {p.stem for p in (MODEL / "definition" / "tables").glob("*.tmdl")}
    rel_text = (MODEL / "definition" / "relationships.tmdl").read_text(encoding="utf-8")
    assert rel_text.count("relationship ") == 10
    assert rel_text.count(".amfi_code") == 8
    assert rel_text.count(".date") == 12


def main() -> None:
    if PROJECT.exists():
        shutil.rmtree(PROJECT)
    PROJECT.mkdir(parents=True)
    build_model()
    build_report()
    write_json(PROJECT / "bluestock_mf_dashboard.pbip", {
        "version": "1.0",
        "artifacts": [{"report": {"path": "bluestock_mf_dashboard.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    validate_contract()
    print(f"Created Power BI project: {PROJECT / 'bluestock_mf_dashboard.pbip'}")
    print("Semantic model: 8 tables, 10 relationships")
    print("Report: 4 visible pages + hidden NAV drillthrough page")


if __name__ == "__main__":
    main()
