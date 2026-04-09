"""Dashboard analytics route."""
from flask import Blueprint, request, jsonify
from backend.db import get_cursor
from backend.utils.analytics import get_dashboard_metrics, predict_next_month

dashboard_bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@dashboard_bp.route("/metrics", methods=["GET"])
def metrics():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")
    category  = request.args.get("category")

    with get_cursor() as cur:
        cur.execute("SELECT * FROM orders")
        orders = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM stock")
        stock  = [dict(r) for r in cur.fetchall()]

    result = get_dashboard_metrics(orders, stock, date_from, date_to, category)
    return jsonify(result)


@dashboard_bp.route("/predict", methods=["GET"])
def predict():
    with get_cursor() as cur:
        cur.execute("SELECT date, category, qty, is_return FROM orders")
        orders = [dict(r) for r in cur.fetchall()]
    preds = predict_next_month(orders)
    return jsonify(preds)


@dashboard_bp.route("/categories", methods=["GET"])
def categories():
    with get_cursor() as cur:
        cur.execute("SELECT DISTINCT category FROM orders ORDER BY category")
        cats = [r["category"] for r in cur.fetchall()]
    return jsonify(cats)


@dashboard_bp.route("/logs", methods=["GET"])
def logs():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM upload_logs ORDER BY created_at DESC LIMIT 100")
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])
