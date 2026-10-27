# Sales Analysis: Joined Trading Dataset

A pandas analysis pipeline and Streamlit dashboard for the seven-table trading dataset
(orders, order details, customers, products, categories, employees, shippers).

## Files

| File | Purpose |
|---|---|
| `analysis.py` | Data layer: loads and validates the tables, joins them into one fact table, computes KPIs and breakdowns |
| `report.py` | Generates 8 PNG charts, `sales_report.md`, and `joined_sales.csv` |
| `app.py` | Streamlit dashboard with filters, interactive charts, and CSV export |
| `data/` | The seven source CSV files |
| `reports/` | Output from `report.py` (already generated) |

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

**Static report** (charts and Markdown, no browser needed):

```bash
python report.py --data data --out reports
```

**Interactive dashboard:**

```bash
streamlit run app.py
```

The dashboard reads from `data/` by default. In the sidebar you can switch to
"Upload CSVs" to load the seven files directly in the browser.

## Data model

```
orders ──┬── customers   (customerID)
         ├── employees   (employeeID)
         ├── shippers    (shipperID)
         └── order_details (orderID) ── products (productID) ── categories (categoryID)
```

The fact table in `analysis.build_sales()` has one row per order line (2,155 rows).
Each row carries its order, customer, product, category, employee, and shipper attributes.

Integrity checks run on load. All foreign keys resolve, and there are no duplicate
order-product lines.

## Metric definitions

| Metric | Definition |
|---|---|
| Gross revenue | unit price x quantity |
| Discount given | gross revenue x discount |
| Net revenue | gross revenue - discount given |
| Average order value | net revenue / distinct orders |
| Freight | counted once per order, never per line |
| Late shipment | shipped date after required date (shipped orders only) |
| Days to ship | shipped date - order date (shipped orders only) |

Unit price comes from `order_details`, which is the price charged on that order.
`products.unitPrice` is the current list price and is kept as `listPrice`. The two
differ on 658 lines because prices changed over time, so the order-level price is
the correct basis for revenue.

## Caveats

- The data covers 4 Jul 2013 to 6 May 2015. **2014 is the only full calendar year.**
  2013 and 2015 are partial, so compare years only on full periods.
- The discount analysis shows that discounted lines are larger on average. This is a
  correlation and does not establish that discounts caused the larger orders.
- 73 order lines belong to orders that have no shipped date. They are excluded from
  logistics metrics but included in revenue.

## Extending

- Add a KPI: write a function in `analysis.py` that takes the filtered fact table and
  returns a DataFrame or dict. Then call it from `report.py` and `app.py`.
- Add a table: join it through `build_sales()` and add a `FOREIGN_KEYS` entry so it is
  validated on load.
"# northwind-sales-analysis-streamlit-app" 
"# northwind-sales-analysis-streamlit-app" 
