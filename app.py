"""
app.py - interactive sales analysis dashboard.

Run:
    streamlit run app.py

Data source (sidebar):
    - "Data folder": reads the seven CSVs from ./data (default)
    - "Upload CSVs": drop in the seven files directly in the browser
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

import analysis as an

DATA_DIR = Path(__file__).parent / "data"
MONEY = "$,.0f"

st.set_page_config(page_title="Sales Analysis", page_icon="📊", layout="wide")


# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Joining the seven tables...")
def sales_from_folder(folder: str) -> pd.DataFrame:
    return an.build_sales(an.load_tables(folder))


@st.cache_data(show_spinner="Joining the uploaded tables...")
def sales_from_bytes(files: tuple[tuple[str, bytes], ...]) -> pd.DataFrame:
    tables = {name: an.read_table(raw) for name, raw in files}
    return an.build_sales(tables)


def _fmt_money(x: float) -> str:
    return f"${x:,.0f}"


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _style(fig, height: int = 420):
    fig.update_layout(
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(size=13),
    )
    fig.update_yaxes(gridcolor="#eeeeee")
    return fig


# ---------------------------------------------------------------------------
# Sidebar: data source and filters
# ---------------------------------------------------------------------------
st.sidebar.header("Data source")
source = st.sidebar.radio("Load data from", ["Data folder", "Upload CSVs"], horizontal=True)

df_all: pd.DataFrame | None = None
if source == "Data folder":
    if not DATA_DIR.exists() or not all((DATA_DIR / f"{t}.csv").exists() for t in an.TABLE_NAMES):
        st.error(f"Expected the seven CSV files in `{DATA_DIR}`. Switch to 'Upload CSVs' or add them.")
        st.stop()
    df_all = sales_from_folder(str(DATA_DIR))
else:
    uploads = st.sidebar.file_uploader(
        "Upload: categories, customers, employees, order_details, orders, products, shippers (.csv)",
        type="csv", accept_multiple_files=True,
    )
    provided = {Path(u.name).stem: u.getvalue() for u in uploads or []}
    missing = [t for t in an.TABLE_NAMES if t not in provided]
    if missing:
        st.info("Upload all seven files to continue. Still missing: " + ", ".join(f"{m}.csv" for m in missing))
        st.stop()
    df_all = sales_from_bytes(tuple(sorted((k, v) for k, v in provided.items() if k in an.TABLE_NAMES)))

st.sidebar.header("Filters")
min_d, max_d = an.data_date_range(df_all)
date_range = st.sidebar.date_input(
    "Order date range", value=(min_d.date(), max_d.date()),
    min_value=min_d.date(), max_value=max_d.date(),
)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
else:
    start, end = min_d.date(), max_d.date()

countries = st.sidebar.multiselect("Customer country", sorted(df_all["customerCountry"].dropna().unique()))
categories = st.sidebar.multiselect("Category", sorted(df_all["categoryName"].dropna().unique()))
employees = st.sidebar.multiselect("Sales employee", sorted(df_all["employeeName"].dropna().unique()))
shippers = st.sidebar.multiselect("Shipper", sorted(df_all["shipperName"].dropna().unique()))

df = an.apply_filters(df_all, start, end, countries, categories, employees, shippers)

st.title("Sales Analysis Dashboard")
st.caption(
    f"Showing {len(df):,} order lines from {df['orderDate'].min():%d %b %Y} to "
    f"{df['orderDate'].max():%d %b %Y}" if not df.empty else "No data for the selected filters."
)

if df.empty:
    st.warning("No rows match the current filters. Widen the date range or clear a filter.")
    st.stop()

k = an.kpis(df)

tab_over, tab_prod, tab_cust, tab_team, tab_log, tab_data = st.tabs(
    ["Overview", "Products & categories", "Customers & geography",
     "Sales team", "Logistics & discounts", "Data & export"]
)

# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------
with tab_over:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Net revenue", _fmt_money(k["net_revenue"]))
    c2.metric("Orders", f"{k['orders']:,}")
    c3.metric("Average order value", _fmt_money(k["avg_order_value"]))
    c4.metric("Customers", f"{k['customers']}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Units sold", f"{k['units']:,}")
    c6.metric("Discounts given", _fmt_money(k["discount_given"]))
    c7.metric("Freight", _fmt_money(k["freight"]))
    c8.metric("Late shipments", _fmt_pct(k["late_rate"]))

    monthly = an.monthly_sales(df)
    fig = px.line(monthly, x="orderMonth", y="netRevenue", markers=True,
                  labels={"orderMonth": "Month", "netRevenue": "Net revenue"},
                  title="Monthly net revenue")
    fig.update_traces(line_color="#2E6F95")
    st.plotly_chart(_style(fig))
    st.caption("First (Jul 2013) and last (May 2015) months are partial in the source data.")

    left, right = st.columns(2)
    with left:
        fig = px.bar(monthly, x="orderMonth", y="orders", title="Orders per month",
                     labels={"orderMonth": "Month", "orders": "Orders"})
        fig.update_traces(marker_color="#2E6F95")
        st.plotly_chart(_style(fig, 360))
    with right:
        yearly = an.yearly_sales(df).copy()
        st.markdown("**Yearly summary**")
        st.dataframe(
            yearly.assign(
                netRevenue=yearly["netRevenue"].map(_fmt_money),
                avgOrderValue=yearly["avgOrderValue"].map(_fmt_money),
                firstOrder=yearly["firstOrder"].dt.date,
                lastOrder=yearly["lastOrder"].dt.date,
            ).rename(columns={"orderYear": "Year", "netRevenue": "Net revenue", "orders": "Orders",
                              "units": "Units", "avgOrderValue": "Avg order value",
                              "firstOrder": "First order", "lastOrder": "Last order"}),
            hide_index=True,
        )
        st.caption("Only 2014 is a full calendar year. Compare years on full periods.")

# ---------------------------------------------------------------------------
# Products & categories
# ---------------------------------------------------------------------------
with tab_prod:
    top_n = st.slider("Number of products to show", 5, 25, 10, key="top_n_products")
    prod = an.product_sales(df)

    fig = px.bar(prod.head(top_n).iloc[::-1], x="netRevenue", y="productName", orientation="h",
                 color="categoryName", title=f"Top {top_n} products by net revenue",
                 labels={"netRevenue": "Net revenue", "productName": ""})
    st.plotly_chart(_style(fig, 40 * top_n + 120))

    left, right = st.columns(2)
    with left:
        cat = an.category_sales(df)
        fig = px.pie(cat, names="categoryName", values="netRevenue", hole=0.45,
                     title="Revenue share by category")
        st.plotly_chart(_style(fig, 380))
    with right:
        fig = px.bar(cat, x="categoryName", y="units", title="Units sold by category",
                     labels={"categoryName": "Category", "units": "Units"})
        fig.update_traces(marker_color="#2E6F95")
        st.plotly_chart(_style(fig, 380))

    st.markdown("**All products**")
    show = prod.assign(
        netRevenue=prod["netRevenue"].map(_fmt_money),
        revenueShare=prod["revenueShare"].map(_fmt_pct),
        discontinued=prod["discontinued"].map({0: "No", 1: "Yes"}),
    ).rename(columns={"productName": "Product", "categoryName": "Category", "units": "Units",
                      "orders": "Orders", "netRevenue": "Net revenue", "revenueShare": "Share",
                      "discontinued": "Discontinued"})
    st.dataframe(show[["Product", "Category", "Units", "Orders", "Net revenue", "Share", "Discontinued"]],
                 hide_index=True)

# ---------------------------------------------------------------------------
# Customers & geography
# ---------------------------------------------------------------------------
with tab_cust:
    top_c = st.slider("Number of customers to show", 5, 25, 10, key="top_n_customers")
    cust = an.customer_sales(df)
    fig = px.bar(cust.head(top_c).iloc[::-1], x="netRevenue", y="customerName", orientation="h",
                 color="customerCountry", title=f"Top {top_c} customers by net revenue",
                 labels={"netRevenue": "Net revenue", "customerName": ""})
    st.plotly_chart(_style(fig, 40 * top_c + 120))

    left, right = st.columns(2)
    with left:
        ctry = an.country_sales(df)
        fig = px.bar(ctry, x="customerCountry", y="netRevenue", title="Net revenue by country",
                     labels={"customerCountry": "Country", "netRevenue": "Net revenue"})
        fig.update_traces(marker_color="#2E6F95")
        st.plotly_chart(_style(fig, 380))
    with right:
        fig = px.scatter(ctry, x="orders", y="avgOrderValue", size="netRevenue", hover_name="customerCountry",
                         title="Orders vs average order value by country",
                         labels={"orders": "Orders", "avgOrderValue": "Avg order value"})
        st.plotly_chart(_style(fig, 380))

    st.markdown("**All customers**")
    st.dataframe(
        cust.assign(netRevenue=cust["netRevenue"].map(_fmt_money),
                    avgOrderValue=cust["avgOrderValue"].map(_fmt_money))
        .rename(columns={"customerName": "Customer", "customerCountry": "Country", "orders": "Orders",
                         "netRevenue": "Net revenue", "avgOrderValue": "Avg order value"})
        [["Customer", "Country", "Orders", "Net revenue", "Avg order value"]],
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# Sales team
# ---------------------------------------------------------------------------
with tab_team:
    emp = an.employee_sales(df)
    fig = px.bar(emp, x="employeeName", y="netRevenue", color="orders",
                 title="Net revenue by sales employee (colour = orders)",
                 labels={"employeeName": "Employee", "netRevenue": "Net revenue", "orders": "Orders"})
    st.plotly_chart(_style(fig))

    emp_month = (
        df.groupby(["orderMonth", "employeeName"], as_index=False)["netRevenue"].sum()
    )
    fig = px.line(emp_month, x="orderMonth", y="netRevenue", color="employeeName",
                  title="Monthly net revenue by employee",
                  labels={"orderMonth": "Month", "netRevenue": "Net revenue", "employeeName": "Employee"})
    st.plotly_chart(_style(fig, 460))

    st.dataframe(
        emp.assign(netRevenue=emp["netRevenue"].map(_fmt_money),
                   avgOrderValue=emp["avgOrderValue"].map(_fmt_money))
        .rename(columns={"employeeName": "Employee", "employeeTitle": "Title", "orders": "Orders",
                         "customers": "Customers", "netRevenue": "Net revenue",
                         "avgOrderValue": "Avg order value"}),
        hide_index=True,
    )

# ---------------------------------------------------------------------------
# Logistics & discounts
# ---------------------------------------------------------------------------
with tab_log:
    ship = an.shipper_performance(df)
    ship = ship.assign(latePct=ship["lateRate"] * 100)
    left, right = st.columns(2)
    with left:
        fig = px.bar(ship, x="shipperName", y="orders", title="Orders by shipper",
                     labels={"shipperName": "Shipper", "orders": "Orders"})
        fig.update_traces(marker_color="#2E6F95")
        st.plotly_chart(_style(fig, 380))
    with right:
        fig = px.bar(ship, x="shipperName", y="latePct", title="Late shipment rate (%)",
                     labels={"shipperName": "Shipper", "latePct": "% late"})
        fig.update_traces(marker_color="#E07A5F")
        st.plotly_chart(_style(fig, 380))

    shipped = df.drop_duplicates("orderID")
    shipped = shipped[shipped["isShipped"]]
    fig = px.histogram(shipped, x="shipDays", nbins=20, title="Days from order to shipment",
                       labels={"shipDays": "Days"})
    fig.update_traces(marker_color="#2E6F95")
    st.plotly_chart(_style(fig, 340))

    st.markdown("**Discounts**")
    disc = an.discount_analysis(df)
    left, right = st.columns(2)
    with left:
        fig = px.bar(disc, x="discountBand", y="avgQuantity", title="Avg units per order line by discount",
                     labels={"discountBand": "Discount", "avgQuantity": "Avg units per line"})
        fig.update_traces(marker_color="#2E6F95")
        st.plotly_chart(_style(fig, 360))
    with right:
        fig = px.bar(disc, x="discountBand", y="discountGiven", title="Discount value given",
                     labels={"discountBand": "Discount", "discountGiven": "Discount given"})
        fig.update_traces(marker_color="#E07A5F")
        st.plotly_chart(_style(fig, 360))
    st.caption("Discounted lines have larger average quantities. This is a correlation, not proof that discounts caused the larger orders.")

# ---------------------------------------------------------------------------
# Data & export
# ---------------------------------------------------------------------------
with tab_data:
    st.markdown("The joined fact table: one row per order line, with order, customer, product, category, employee and shipper fields.")
    preview_cols = ["orderID", "orderDate", "customerName", "customerCountry", "employeeName",
                    "shipperName", "productName", "categoryName", "unitPrice", "quantity",
                    "discount", "netRevenue", "shippedDate", "shippedLate"]
    st.dataframe(df[preview_cols].head(500), hide_index=True)
    st.caption(f"Showing the first 500 of {len(df):,} rows.")

    st.download_button(
        "Download filtered data (CSV)",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="sales_filtered.csv",
        mime="text/csv",
    )
