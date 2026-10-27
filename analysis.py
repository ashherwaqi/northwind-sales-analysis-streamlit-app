"""
analysis.py - data layer for the trading analysis.

Loads the seven CSV tables, validates their keys, joins them into one
line-level fact table (`build_sales`), and exposes pure pandas functions
for KPIs and breakdowns. No plotting or UI code lives here, so the same
logic powers both the static report (report.py) and the Streamlit app (app.py).

Grain of the fact table: one row per order line (orderID x productID).
Freight is stored per order, so order-level totals must count it once per
order (see `kpis` and `shipper_performance`), never once per line.
"""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd

TABLE_NAMES = [
    "categories",
    "customers",
    "employees",
    "order_details",
    "orders",
    "products",
    "shippers",
]

# (child table, column) -> (parent table, column)
FOREIGN_KEYS = [
    (("orders", "customerID"), ("customers", "customerID")),
    (("orders", "employeeID"), ("employees", "employeeID")),
    (("orders", "shipperID"), ("shippers", "shipperID")),
    (("order_details", "orderID"), ("orders", "orderID")),
    (("order_details", "productID"), ("products", "productID")),
    (("products", "categoryID"), ("categories", "categoryID")),
]

DISCOUNT_BINS = [-0.001, 0, 0.05, 0.10, 0.15, 0.20, 0.25]
DISCOUNT_LABELS = ["0%", "1-5%", "6-10%", "11-15%", "16-20%", "21-25%"]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _to_bytes(source) -> bytes:
    """Accept a path, raw bytes, or a file-like object (e.g. Streamlit upload)."""
    if isinstance(source, (str, Path)):
        return Path(source).read_bytes()
    if isinstance(source, bytes):
        return source
    if hasattr(source, "getvalue"):
        return source.getvalue()
    return source.read()


def _decode(raw: bytes) -> str:
    # customers.csv and products.csv are Latin-1 exports; the rest are ASCII/UTF-8.
    # latin-1 can decode any byte sequence, so it is a safe fallback.
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


def read_table(source) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(_decode(_to_bytes(source))))


def load_tables(data_dir) -> dict[str, pd.DataFrame]:
    data_dir = Path(data_dir)
    missing = [t for t in TABLE_NAMES if not (data_dir / f"{t}.csv").exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing CSV files in {data_dir}: " + ", ".join(f"{m}.csv" for m in missing)
        )
    return {t: read_table(data_dir / f"{t}.csv") for t in TABLE_NAMES}


def validate_tables(tables: dict[str, pd.DataFrame]) -> list[str]:
    """Return a list of human-readable data-quality problems (empty list = clean)."""
    problems = []
    for (child, ccol), (parent, pcol) in FOREIGN_KEYS:
        orphans = int((~tables[child][ccol].isin(tables[parent][pcol])).sum())
        if orphans:
            problems.append(f"{child}.{ccol}: {orphans} row(s) with no match in {parent}.{pcol}")
    dupes = int(tables["order_details"].duplicated(["orderID", "productID"]).sum())
    if dupes:
        problems.append(f"order_details: {dupes} duplicate (orderID, productID) line(s)")
    return problems


# ---------------------------------------------------------------------------
# Joining
# ---------------------------------------------------------------------------
def build_sales(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Join all seven tables into one line-level fact table with derived measures."""
    od = tables["order_details"].copy()

    orders = tables["orders"].copy()
    for col in ["orderDate", "requiredDate", "shippedDate"]:
        orders[col] = pd.to_datetime(orders[col], errors="coerce")

    # Renames avoid column clashes: products.unitPrice is the list price today,
    # order_details.unitPrice is the price actually charged on that order.
    products = tables["products"][
        ["productID", "productName", "categoryID", "discontinued", "unitPrice"]
    ].rename(columns={"unitPrice": "listPrice"})
    categories = tables["categories"][["categoryID", "categoryName"]]
    customers = tables["customers"].rename(columns={
        "companyName": "customerName",
        "contactName": "customerContact",
        "contactTitle": "customerContactTitle",
        "city": "customerCity",
        "country": "customerCountry",
    })
    employees = tables["employees"][["employeeID", "employeeName", "title", "country"]].rename(
        columns={"title": "employeeTitle", "country": "employeeCountry"}
    )
    shippers = tables["shippers"].rename(columns={"companyName": "shipperName"})

    df = (
        od.merge(orders, on="orderID", how="inner", validate="many_to_one")
        .merge(products, on="productID", how="left", validate="many_to_one")
        .merge(categories, on="categoryID", how="left", validate="many_to_one")
        .merge(customers, on="customerID", how="left", validate="many_to_one")
        .merge(employees, on="employeeID", how="left", validate="many_to_one")
        .merge(shippers, on="shipperID", how="left", validate="many_to_one")
    )

    # Revenue measures (line level)
    df["grossRevenue"] = df["unitPrice"] * df["quantity"]
    df["discountAmount"] = df["grossRevenue"] * df["discount"]
    df["netRevenue"] = df["grossRevenue"] - df["discountAmount"]

    # Time dimensions
    df["orderYear"] = df["orderDate"].dt.year
    df["orderMonth"] = df["orderDate"].dt.to_period("M").dt.to_timestamp()

    # Logistics measures (order level, repeated on each line)
    df["isShipped"] = df["shippedDate"].notna()
    df["shipDays"] = (df["shippedDate"] - df["orderDate"]).dt.days
    df["shippedLate"] = df["isShipped"] & (df["shippedDate"] > df["requiredDate"])

    df["discountBand"] = pd.cut(
        df["discount"], bins=DISCOUNT_BINS, labels=DISCOUNT_LABELS
    )

    return df.sort_values(["orderDate", "orderID", "productID"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------
def apply_filters(
    df: pd.DataFrame,
    start=None,
    end=None,
    countries=None,
    categories=None,
    employees=None,
    shippers=None,
) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if start is not None:
        mask &= df["orderDate"] >= pd.Timestamp(start)
    if end is not None:
        mask &= df["orderDate"] <= pd.Timestamp(end)
    if countries:
        mask &= df["customerCountry"].isin(countries)
    if categories:
        mask &= df["categoryName"].isin(categories)
    if employees:
        mask &= df["employeeName"].isin(employees)
    if shippers:
        mask &= df["shipperName"].isin(shippers)
    return df[mask]


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------
def kpis(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "net_revenue": 0.0, "gross_revenue": 0.0, "discount_given": 0.0,
            "orders": 0, "customers": 0, "products_sold": 0, "units": 0,
            "avg_order_value": 0.0, "freight": 0.0,
            "late_rate": 0.0, "avg_ship_days": 0.0,
        }
    orders = df.drop_duplicates("orderID")          # one row per order
    shipped = orders[orders["isShipped"]]
    n_orders = orders["orderID"].nunique()
    net = float(df["netRevenue"].sum())
    return {
        "net_revenue": net,
        "gross_revenue": float(df["grossRevenue"].sum()),
        "discount_given": float(df["discountAmount"].sum()),
        "orders": int(n_orders),
        "customers": int(df["customerID"].nunique()),
        "products_sold": int(df["productID"].nunique()),
        "units": int(df["quantity"].sum()),
        "avg_order_value": net / n_orders if n_orders else 0.0,
        "freight": float(orders["freight"].sum()),
        "late_rate": float(shipped["shippedLate"].mean()) if len(shipped) else 0.0,
        "avg_ship_days": float(shipped["shipDays"].mean()) if len(shipped) else 0.0,
    }


# ---------------------------------------------------------------------------
# Breakdowns
# ---------------------------------------------------------------------------
def monthly_sales(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("orderMonth", as_index=False)
        .agg(netRevenue=("netRevenue", "sum"),
             orders=("orderID", "nunique"),
             units=("quantity", "sum"))
        .sort_values("orderMonth")
    )


def yearly_sales(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby("orderYear", as_index=False)
        .agg(netRevenue=("netRevenue", "sum"),
             orders=("orderID", "nunique"),
             units=("quantity", "sum"),
             firstOrder=("orderDate", "min"),
             lastOrder=("orderDate", "max"))
        .sort_values("orderYear")
    )
    g["avgOrderValue"] = g["netRevenue"] / g["orders"]
    return g


def product_sales(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby(["productID", "productName", "categoryName", "discontinued"], as_index=False)
        .agg(netRevenue=("netRevenue", "sum"),
             units=("quantity", "sum"),
             orders=("orderID", "nunique"))
        .sort_values("netRevenue", ascending=False)
    )
    total = g["netRevenue"].sum()
    g["revenueShare"] = g["netRevenue"] / total if total else 0.0
    return g


def category_sales(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby("categoryName", as_index=False)
        .agg(netRevenue=("netRevenue", "sum"),
             units=("quantity", "sum"),
             products=("productID", "nunique"))
        .sort_values("netRevenue", ascending=False)
    )
    total = g["netRevenue"].sum()
    g["revenueShare"] = g["netRevenue"] / total if total else 0.0
    return g


def country_sales(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby("customerCountry", as_index=False)
        .agg(netRevenue=("netRevenue", "sum"),
             orders=("orderID", "nunique"),
             customers=("customerID", "nunique"))
        .sort_values("netRevenue", ascending=False)
    )
    g["avgOrderValue"] = g["netRevenue"] / g["orders"]
    return g


def customer_sales(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby(["customerID", "customerName", "customerCountry"], as_index=False)
        .agg(netRevenue=("netRevenue", "sum"),
             orders=("orderID", "nunique"))
        .sort_values("netRevenue", ascending=False)
    )
    g["avgOrderValue"] = g["netRevenue"] / g["orders"]
    return g


def employee_sales(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby(["employeeName", "employeeTitle"], as_index=False)
        .agg(netRevenue=("netRevenue", "sum"),
             orders=("orderID", "nunique"),
             customers=("customerID", "nunique"))
        .sort_values("netRevenue", ascending=False)
    )
    g["avgOrderValue"] = g["netRevenue"] / g["orders"]
    return g


def shipper_performance(df: pd.DataFrame) -> pd.DataFrame:
    orders = df.drop_duplicates("orderID")
    shipped = orders[orders["isShipped"]]
    counts = orders.groupby("shipperName", as_index=False).agg(
        orders=("orderID", "count"), freight=("freight", "sum")
    )
    perf = shipped.groupby("shipperName", as_index=False).agg(
        avgShipDays=("shipDays", "mean"), lateRate=("shippedLate", "mean")
    )
    out = counts.merge(perf, on="shipperName", how="left")
    return out.sort_values("orders", ascending=False)


def discount_analysis(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby("discountBand", observed=True, as_index=False)
        .agg(lines=("productID", "count"),
             avgQuantity=("quantity", "mean"),
             netRevenue=("netRevenue", "sum"),
             discountGiven=("discountAmount", "sum"))
    )


def data_date_range(df: pd.DataFrame):
    return df["orderDate"].min(), df["orderDate"].max()
