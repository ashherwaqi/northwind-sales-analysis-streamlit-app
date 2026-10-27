"""
report.py - generate static charts and a Markdown sales report.

Usage:
    python report.py --data ./data --out ./reports

Outputs (in --out):
    sales_report.md          headline KPIs, findings, and tables
    charts/*.png             one chart per analysis area
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no display needed
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

import analysis as an

PALETTE = "#2E6F95"
ACCENT = "#E07A5F"
GRID = "#DDDDDD"


def _money(x: float) -> str:
    return f"${x:,.0f}"


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _style_axes(ax, title: str, xlabel: str = "", ylabel: str = "") -> None:
    ax.set_title(title, fontsize=13, weight="bold", loc="left")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)


def _save(fig, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def chart_monthly(df: pd.DataFrame, path: Path) -> None:
    m = an.monthly_sales(df)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(m["orderMonth"], m["netRevenue"], color=PALETTE, marker="o", linewidth=2)
    ax.fill_between(m["orderMonth"], m["netRevenue"], color=PALETTE, alpha=0.1)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k"))
    _style_axes(ax, "Monthly net revenue", ylabel="Net revenue")
    ax.text(0, -0.18, "First (Jul 2013) and last (May 2015) months are partial in the source data.",
            transform=ax.transAxes, fontsize=8, color="#666")
    _save(fig, path)


def chart_top_products(df: pd.DataFrame, path: Path, n: int = 10) -> None:
    p = an.product_sales(df).head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(p["productName"], p["netRevenue"], color=PALETTE)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k"))
    _style_axes(ax, f"Top {n} products by net revenue", xlabel="Net revenue")
    ax.grid(axis="x", color=GRID, linewidth=0.7)
    ax.grid(axis="y", visible=False)
    _save(fig, path)


def chart_categories(df: pd.DataFrame, path: Path) -> None:
    c = an.category_sales(df)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    bars = ax.bar(c["categoryName"], c["netRevenue"], color=PALETTE)
    for bar, share in zip(bars, c["revenueShare"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), _pct(share),
                ha="center", va="bottom", fontsize=9)
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k"))
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")
    _style_axes(ax, "Net revenue by category (labels = share of total)", ylabel="Net revenue")
    _save(fig, path)


def chart_countries(df: pd.DataFrame, path: Path, n: int = 10) -> None:
    c = an.country_sales(df).head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(c["customerCountry"], c["netRevenue"], color=PALETTE)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k"))
    _style_axes(ax, f"Top {n} countries by net revenue", xlabel="Net revenue")
    ax.grid(axis="x", color=GRID, linewidth=0.7)
    ax.grid(axis="y", visible=False)
    _save(fig, path)


def chart_customers(df: pd.DataFrame, path: Path, n: int = 10) -> None:
    c = an.customer_sales(df).head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.barh(c["customerName"], c["netRevenue"], color=PALETTE)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k"))
    _style_axes(ax, f"Top {n} customers by net revenue", xlabel="Net revenue")
    ax.grid(axis="x", color=GRID, linewidth=0.7)
    ax.grid(axis="y", visible=False)
    _save(fig, path)


def chart_employees(df: pd.DataFrame, path: Path) -> None:
    e = an.employee_sales(df).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.barh(e["employeeName"], e["netRevenue"], color=PALETTE)
    ax.xaxis.set_major_formatter(mtick.FuncFormatter(lambda v, _: f"${v/1000:,.0f}k"))
    _style_axes(ax, "Net revenue by sales employee", xlabel="Net revenue")
    ax.grid(axis="x", color=GRID, linewidth=0.7)
    ax.grid(axis="y", visible=False)
    _save(fig, path)


def chart_shippers(df: pd.DataFrame, path: Path) -> None:
    s = an.shipper_performance(df)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    ax1.bar(s["shipperName"], s["orders"], color=PALETTE)
    _style_axes(ax1, "Orders shipped", ylabel="Orders")
    ax2.bar(s["shipperName"], s["lateRate"] * 100, color=ACCENT)
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    _style_axes(ax2, "Late shipments (shipped after required date)", ylabel="% of shipped orders")
    for ax in (ax1, ax2):
        plt.setp(ax.get_xticklabels(), rotation=15, ha="right")
    _save(fig, path)


def chart_discounts(df: pd.DataFrame, path: Path) -> None:
    d = an.discount_analysis(df)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(d["discountBand"].astype(str), d["avgQuantity"], color=PALETTE)
    for i, v in enumerate(d["avgQuantity"]):
        ax.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
    _style_axes(ax, "Average units per order line, by discount band",
                xlabel="Discount band", ylabel="Avg units per line")
    _save(fig, path)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------
def _md_table(frame: pd.DataFrame) -> str:
    cols = list(frame.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, row in frame.iterrows():
        lines.append("| " + " | ".join(str(v) for v in row.values) + " |")
    return "\n".join(lines)


def key_findings(df: pd.DataFrame) -> list[str]:
    """Findings computed from the data, so the text always matches the numbers."""
    k = an.kpis(df)
    prod = an.product_sales(df)
    cat = an.category_sales(df)
    ctry = an.country_sales(df)
    emp = an.employee_sales(df)
    ship = an.shipper_performance(df)
    disc = an.discount_analysis(df)
    yearly = an.yearly_sales(df).set_index("orderYear")

    top_prod = prod.iloc[0]
    top3_share = prod.head(3)["revenueShare"].sum()
    top_cat = cat.iloc[0]
    top_ctry = ctry.iloc[0]
    top_emp = emp.iloc[0]
    worst_ship = ship.sort_values("lateRate", ascending=False).iloc[0]

    no_disc = disc.loc[disc["discountBand"].astype(str) == "0%", "avgQuantity"].iloc[0]
    with_disc = disc.loc[disc["discountBand"].astype(str) != "0%"]
    disc_qty = (with_disc["avgQuantity"] * with_disc["lines"]).sum() / with_disc["lines"].sum()

    findings = [
        f"Total net revenue is {_money(k['net_revenue'])} across {k['orders']:,} orders "
        f"and {k['customers']} customers, after {_money(k['discount_given'])} in discounts.",
        f"**{top_prod['productName']}** is the top product at {_money(top_prod['netRevenue'])} "
        f"({_pct(top_prod['revenueShare'])} of revenue). The top three products make up "
        f"{_pct(top3_share)} of revenue.",
        f"**{top_cat['categoryName']}** is the leading category with {_pct(top_cat['revenueShare'])} "
        f"of net revenue.",
        f"**{top_ctry['customerCountry']}** is the top customer country at "
        f"{_money(top_ctry['netRevenue'])}, followed by "
        f"{', '.join(ctry['customerCountry'].iloc[1:3])}.",
        f"**{top_emp['employeeName']}** ({top_emp['employeeTitle']}) generated the most revenue, "
        f"{_money(top_emp['netRevenue'])} from {int(top_emp['orders'])} orders.",
        f"Overall, {_pct(k['late_rate'])} of shipped orders arrived after the required date, "
        f"averaging {k['avg_ship_days']:.1f} days from order to shipment. "
        f"{worst_ship['shipperName']} has the highest late rate ({_pct(worst_ship['lateRate'])}).",
        f"Discounted order lines average {disc_qty:.1f} units versus {no_disc:.1f} for undiscounted "
        f"lines. Discounts appear to be used on larger orders. This is a correlation and does not "
        f"show that discounts caused the larger orders.",
    ]
    if 2014 in yearly.index:
        findings.append(
            f"2014 is the only full calendar year in the data, with {_money(yearly.loc[2014, 'netRevenue'])} "
            f"net revenue. Compare years only on full periods, because 2013 and 2015 are partial."
        )
    return findings


def write_markdown(df: pd.DataFrame, out_dir: Path, problems: list[str], chart_dir_name: str = "charts") -> Path:
    k = an.kpis(df)
    start, end = an.data_date_range(df)

    kpi_table = pd.DataFrame([
        ("Net revenue", _money(k["net_revenue"])),
        ("Gross revenue (before discounts)", _money(k["gross_revenue"])),
        ("Discounts given", _money(k["discount_given"])),
        ("Orders", f"{k['orders']:,}"),
        ("Units sold", f"{k['units']:,}"),
        ("Active customers", f"{k['customers']}"),
        ("Products sold", f"{k['products_sold']}"),
        ("Average order value", _money(k["avg_order_value"])),
        ("Freight (per order, counted once)", _money(k["freight"])),
        ("Late shipments (of shipped)", _pct(k["late_rate"])),
        ("Avg days order to shipment", f"{k['avg_ship_days']:.1f}"),
    ], columns=["Metric", "Value"])

    yearly = an.yearly_sales(df).copy()
    yearly["netRevenue"] = yearly["netRevenue"].map(_money)
    yearly["avgOrderValue"] = yearly["avgOrderValue"].map(_money)
    yearly["firstOrder"] = yearly["firstOrder"].dt.date
    yearly["lastOrder"] = yearly["lastOrder"].dt.date
    yearly = yearly.rename(columns={
        "orderYear": "Year", "netRevenue": "Net revenue", "orders": "Orders",
        "units": "Units", "avgOrderValue": "Avg order value",
        "firstOrder": "First order", "lastOrder": "Last order",
    })

    top_products = an.product_sales(df).head(10).copy()
    top_products["netRevenue"] = top_products["netRevenue"].map(_money)
    top_products["revenueShare"] = top_products["revenueShare"].map(_pct)
    top_products = top_products[["productName", "categoryName", "units", "orders",
                                 "netRevenue", "revenueShare"]].rename(columns={
        "productName": "Product", "categoryName": "Category", "units": "Units",
        "orders": "Orders", "netRevenue": "Net revenue", "revenueShare": "Share"})

    cats = an.category_sales(df).copy()
    cats["netRevenue"] = cats["netRevenue"].map(_money)
    cats["revenueShare"] = cats["revenueShare"].map(_pct)
    cats = cats[["categoryName", "products", "units", "netRevenue", "revenueShare"]].rename(columns={
        "categoryName": "Category", "products": "Products", "units": "Units",
        "netRevenue": "Net revenue", "revenueShare": "Share"})

    ctry = an.country_sales(df).head(10).copy()
    ctry["netRevenue"] = ctry["netRevenue"].map(_money)
    ctry["avgOrderValue"] = ctry["avgOrderValue"].map(_money)
    ctry = ctry[["customerCountry", "customers", "orders", "netRevenue", "avgOrderValue"]].rename(columns={
        "customerCountry": "Country", "customers": "Customers", "orders": "Orders",
        "netRevenue": "Net revenue", "avgOrderValue": "Avg order value"})

    custs = an.customer_sales(df).head(10).copy()
    custs["netRevenue"] = custs["netRevenue"].map(_money)
    custs["avgOrderValue"] = custs["avgOrderValue"].map(_money)
    custs = custs[["customerName", "customerCountry", "orders", "netRevenue", "avgOrderValue"]].rename(columns={
        "customerName": "Customer", "customerCountry": "Country", "orders": "Orders",
        "netRevenue": "Net revenue", "avgOrderValue": "Avg order value"})

    emps = an.employee_sales(df).copy()
    emps["netRevenue"] = emps["netRevenue"].map(_money)
    emps["avgOrderValue"] = emps["avgOrderValue"].map(_money)
    emps = emps[["employeeName", "employeeTitle", "orders", "customers", "netRevenue", "avgOrderValue"]].rename(columns={
        "employeeName": "Employee", "employeeTitle": "Title", "orders": "Orders",
        "customers": "Customers", "netRevenue": "Net revenue", "avgOrderValue": "Avg order value"})

    ships = an.shipper_performance(df).copy()
    ships["freight"] = ships["freight"].map(_money)
    ships["avgShipDays"] = ships["avgShipDays"].map(lambda v: f"{v:.1f}")
    ships["lateRate"] = ships["lateRate"].map(_pct)
    ships = ships.rename(columns={
        "shipperName": "Shipper", "orders": "Orders", "freight": "Freight",
        "avgShipDays": "Avg days to ship", "lateRate": "Late rate"})

    disc = an.discount_analysis(df).copy()
    disc["netRevenue"] = disc["netRevenue"].map(_money)
    disc["discountGiven"] = disc["discountGiven"].map(_money)
    disc["avgQuantity"] = disc["avgQuantity"].map(lambda v: f"{v:.1f}")
    disc = disc.rename(columns={
        "discountBand": "Discount", "lines": "Order lines", "avgQuantity": "Avg units per line",
        "netRevenue": "Net revenue", "discountGiven": "Discount given"})

    findings = "\n".join(f"- {f}" for f in key_findings(df))
    quality = "\n".join(f"- {p}" for p in problems) if problems else "- No referential-integrity or duplicate-key issues found."

    md = f"""# Sales Analysis Report

**Period covered:** {start:%d %b %Y} to {end:%d %b %Y}
**Grain:** one row per order line, joined across orders, order details, customers, products, categories, employees and shippers.

## Headline KPIs

{_md_table(kpi_table)}

## Key findings

{findings}

## Yearly performance

{_md_table(yearly)}

## Monthly trend

![Monthly net revenue]({chart_dir_name}/monthly_revenue.png)

## Products

![Top products]({chart_dir_name}/top_products.png)

{_md_table(top_products)}

## Categories

![Categories]({chart_dir_name}/categories.png)

{_md_table(cats)}

## Geography

![Countries]({chart_dir_name}/countries.png)

{_md_table(ctry)}

## Customers

![Customers]({chart_dir_name}/top_customers.png)

{_md_table(custs)}

## Sales team

![Employees]({chart_dir_name}/employees.png)

{_md_table(emps)}

## Logistics

![Shippers]({chart_dir_name}/shippers.png)

{_md_table(ships)}

## Discounts

![Discounts]({chart_dir_name}/discounts.png)

{_md_table(disc)}

## Data quality checks

{quality}

## Method notes

- Net revenue = unit price x quantity x (1 - discount). Unit price is the price charged on the order, not the current list price.
- Freight is stored per order, so it is counted once per order and never repeated per line.
- Late shipment = shipped date after required date. Orders with no shipped date are excluded from late and ship-time metrics.
"""
    path = out_dir / "sales_report.md"
    path.write_text(md, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser(description="Generate charts and a Markdown sales report.")
    parser.add_argument("--data", default="data", help="folder containing the seven CSV files")
    parser.add_argument("--out", default="reports", help="output folder")
    args = parser.parse_args()

    out = Path(args.out)
    charts = out / "charts"
    charts.mkdir(parents=True, exist_ok=True)

    tables = an.load_tables(args.data)
    problems = an.validate_tables(tables)
    df = an.build_sales(tables)

    chart_monthly(df, charts / "monthly_revenue.png")
    chart_top_products(df, charts / "top_products.png")
    chart_categories(df, charts / "categories.png")
    chart_countries(df, charts / "countries.png")
    chart_customers(df, charts / "top_customers.png")
    chart_employees(df, charts / "employees.png")
    chart_shippers(df, charts / "shippers.png")
    chart_discounts(df, charts / "discounts.png")

    joined_path = out / "joined_sales.csv"
    df.to_csv(joined_path, index=False)

    md_path = write_markdown(df, out, problems)
    print(f"Report written to {md_path}")
    print(f"Joined fact table written to {joined_path}")
    print(f"Charts written to {charts} ({len(list(charts.glob('*.png')))} files)")
    if problems:
        print("Data-quality warnings:")
        for p in problems:
            print(" -", p)


if __name__ == "__main__":
    main()
