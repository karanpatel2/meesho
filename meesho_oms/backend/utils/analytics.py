"""
Simple ML prediction for next-month order volumes per category.
Uses linear regression on historical monthly order counts.
"""
import numpy as np
import pandas as pd
from datetime import datetime, date


def predict_next_month(orders: list[dict]) -> list[dict]:
    """
    orders: list of dicts with keys: date (str YYYY-MM-DD), category, qty, is_return
    Returns: list of {category, predicted_qty, confidence}
    """
    if not orders:
        return []

    df = pd.DataFrame(orders)
    df["date"] = pd.to_datetime(df["date"])
    df = df[~df["is_return"].astype(bool)]           # exclude returns
    df["month_num"] = (df["date"].dt.year * 12 + df["date"].dt.month)

    predictions = []
    for cat, grp in df.groupby("category"):
        monthly = (
            grp.groupby("month_num")["qty"].sum()
              .reset_index()
              .sort_values("month_num")
        )
        X = monthly["month_num"].values.reshape(-1, 1)
        y = monthly["qty"].values.astype(float)

        if len(X) < 2:
            # Not enough history — use average
            pred = float(y.mean()) if len(y) else 0.0
            conf = "low"
        else:
            # Simple linear regression
            X_norm = X - X.mean()
            slope  = float(np.dot(X_norm.flatten(), y) / np.dot(X_norm.flatten(), X_norm.flatten()))
            intercept = float(y.mean() - slope * float(X.mean()))
            next_month = int(X[-1][0]) + 1
            pred = slope * next_month + intercept
            pred = max(0.0, pred)

            # R² as confidence proxy
            y_pred_all = slope * X.flatten() + intercept
            ss_res = np.sum((y - y_pred_all) ** 2)
            ss_tot = np.sum((y - y.mean()) ** 2)
            r2 = 1 - ss_res / ss_tot if ss_tot else 0
            conf = "high" if r2 > 0.7 else "medium" if r2 > 0.4 else "low"

        predictions.append({
            "category":      cat,
            "predicted_qty": round(pred),
            "confidence":    conf,
        })

    predictions.sort(key=lambda x: x["predicted_qty"], reverse=True)
    return predictions


def get_dashboard_metrics(orders, stock, date_from=None, date_to=None, category=None):
    if not orders:
        return {
            "total_orders": 0, "return_orders": 0, "net_orders": 0,
            "total_revenue": 0, "total_cost": 0, "profit": 0,
            "real_profit": 0, "total_commission": 0, "total_tds": 0,
            "packaging_cost": 0,
            "orders_by_category": [], "orders_by_date": [],
        }

    df = pd.DataFrame(orders)
    df["date"] = pd.to_datetime(df["date"])
    df["total_amount"] = df["qty"].astype(float) * df["sell_price"].astype(float)

    # Filters
    if date_from:
        df = df[df["date"] >= pd.to_datetime(date_from)]
    if date_to:
        df = df[df["date"] <= pd.to_datetime(date_to)]
    if category and category != "all":
        df = df[df["category"] == category]

    returns = df[df["is_return"].astype(bool)]
    sales   = df[~df["is_return"].astype(bool)]

    revenue    = float(sales["total_amount"].sum())
    return_val = float(returns["total_amount"].sum())
    net_rev    = revenue - return_val

    # Commission + TDS
    total_commission = float(sales["meesho_commission"].sum()) if "meesho_commission" in sales.columns else round(net_rev * 0.18, 2)
    total_tds        = float(sales["tds_amount"].sum()) if "tds_amount" in sales.columns else round(net_rev * 0.01, 2)

    # Product cost
    stock_df = pd.DataFrame(stock) if stock else pd.DataFrame(columns=["item_name","cost_per_product"])
    cost = 0.0
    for _, row in sales.iterrows():
        match = stock_df[stock_df["item_name"] == row["item_name"]]
        if not match.empty:
            cost += float(match.iloc[0]["cost_per_product"]) * float(row["qty"])

    # Packaging cost (assume ₹2.50 per order average)
    packaging_cost = round(len(sales) * 2.50, 2)

    gross_profit = net_rev - cost
    real_profit  = net_rev - cost - total_commission - total_tds - packaging_cost

    # Orders by category
    by_cat = (
        sales.groupby("category")
             .agg(total_orders=("id","count"), total_qty=("qty","sum"), revenue=("total_amount","sum"))
             .reset_index().to_dict("records")
    )

    # Orders by date
    by_date = (
        sales.groupby(sales["date"].dt.strftime("%Y-%m-%d"))
             .agg(total_orders=("id","count"), revenue=("total_amount","sum"))
             .reset_index()
             .rename(columns={"date": "date_label"})
             .to_dict("records")
    )

    return {
        "total_orders":      int(len(sales)),
        "return_orders":     int(len(returns)),
        "net_orders":        int(len(sales) - len(returns)),
        "total_revenue":     round(net_rev, 2),
        "total_cost":        round(cost, 2),
        "profit":            round(gross_profit, 2),
        "real_profit":       round(real_profit, 2),
        "total_commission":  round(total_commission, 2),
        "total_tds":         round(total_tds, 2),
        "packaging_cost":    packaging_cost,
        "orders_by_category": by_cat,
        "orders_by_date":    by_date,
    }
