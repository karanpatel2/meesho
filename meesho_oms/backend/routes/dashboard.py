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
    return jsonify(predict_next_month(orders))


@dashboard_bp.route("/categories", methods=["GET"])
def categories():
    with get_cursor() as cur:
        cur.execute("SELECT DISTINCT category FROM orders ORDER BY category")
        cats = [r["category"] for r in cur.fetchall()]
    return jsonify(cats)


@dashboard_bp.route("/alerts", methods=["GET"])
def alerts():
    with get_cursor() as cur:
        cur.execute("SELECT item_name, qty, low_stock_alert FROM stock WHERE qty <= low_stock_alert")
        low_stock = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT item_name, qty, low_stock_alert FROM packaging WHERE qty <= low_stock_alert")
        low_packaging = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) as cnt FROM orders WHERE payment_status='pending' AND is_return=0")
        pending_payment = cur.fetchone()["cnt"]

    return jsonify({
        "low_stock":       low_stock,
        "low_packaging":   low_packaging,
        "pending_payments": pending_payment
    })


@dashboard_bp.route("/payment-summary", methods=["GET"])
def payment_summary():
    with get_cursor() as cur:
        cur.execute("""SELECT
            SUM(CASE WHEN payment_status='pending' AND is_return=0 THEN net_payment ELSE 0 END) as pending_amount,
            SUM(CASE WHEN payment_status='received' AND is_return=0 THEN net_payment ELSE 0 END) as received_amount,
            SUM(CASE WHEN is_return=0 THEN meesho_commission ELSE 0 END) as total_commission,
            SUM(CASE WHEN is_return=0 THEN tds_amount ELSE 0 END) as total_tds
            FROM orders""")
        row = cur.fetchone()
    return jsonify(dict(row))


@dashboard_bp.route("/logs", methods=["GET"])
def logs():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM upload_logs ORDER BY created_at DESC LIMIT 100")
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])


# Packaging routes
@dashboard_bp.route("/packaging", methods=["GET"])
def list_packaging():
    with get_cursor() as cur:
        cur.execute("SELECT *, (qty*cost_per_unit) as total_cost FROM packaging ORDER BY item_name")
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])


@dashboard_bp.route("/packaging", methods=["POST"])
def add_packaging():
    data = request.json
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM packaging WHERE item_name=?", (data["item_name"],))
        existing = cur.fetchone()
        if existing:
            cur.execute("UPDATE packaging SET qty=qty+?, cost_per_unit=? WHERE item_name=?",
                        (data["qty"], data["cost_per_unit"], data["item_name"]))
            sid = existing["id"]; action = "updated"
        else:
            cur.execute("""INSERT INTO packaging (item_name, qty, cost_per_unit, low_stock_alert, date)
                        VALUES (?,?,?,?,?)""",
                        (data["item_name"], data["qty"], data["cost_per_unit"],
                         data.get("low_stock_alert", 50), data["date"]))
            sid = cur.lastrowid; action = "created"
    return jsonify({"id": sid, "action": action}), 201


@dashboard_bp.route("/packaging/<int:pid>", methods=["DELETE"])
def delete_packaging(pid):
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM packaging WHERE id=?", (pid,))
    return jsonify({"message": "Deleted"})

@dashboard_bp.route("/best-selling", methods=["GET"])
def best_selling():
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")

    sql    = """SELECT item_name, category,
                SUM(qty) as total_qty,
                SUM(qty*sell_price) as total_revenue,
                COUNT(*) as order_count
                FROM orders WHERE is_return=0"""
    params = []
    if date_from:
        sql += " AND date>=?"; params.append(date_from)
    if date_to:
        sql += " AND date<=?"; params.append(date_to)
    sql += " GROUP BY item_name ORDER BY total_qty DESC LIMIT 10"

    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])

@dashboard_bp.route("/dead-stock", methods=["GET"])
def dead_stock():
    days = int(request.args.get("days", 30))
    with get_cursor() as cur:
        cur.execute("""
            SELECT s.id, s.category, s.item_name, s.qty,
                   s.cost_per_product,
                   (s.qty * s.cost_per_product) as stuck_value,
                   MAX(o.date) as last_sold_date,
                   s.date as stocked_date
            FROM stock s
            LEFT JOIN orders o
                ON o.item_name = s.item_name AND o.is_return = 0
            WHERE s.qty > 0
            GROUP BY s.id
            HAVING last_sold_date IS NULL
                OR last_sold_date <= date('now', '-' || ? || ' days')
            ORDER BY stuck_value DESC
        """, (days,))
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])

@dashboard_bp.route("/daily-summary", methods=["GET"])
def daily_summary():
    today = request.args.get("date", "")
    if not today:
        from datetime import date
        today = date.today().isoformat()

    with get_cursor() as cur:
        # Aaj ke orders
        cur.execute("""
            SELECT COUNT(*) as total_orders,
                   SUM(CASE WHEN is_return=0 THEN qty*sell_price ELSE 0 END) as revenue,
                   SUM(CASE WHEN is_return=1 THEN 1 ELSE 0 END) as returns,
                   SUM(CASE WHEN is_return=0 THEN qty ELSE 0 END) as items_sold,
                   SUM(CASE WHEN is_return=0 THEN net_payment ELSE 0 END) as net_payment,
                   SUM(CASE WHEN is_return=0 THEN meesho_commission ELSE 0 END) as commission
            FROM orders WHERE date=?
        """, (today,))
        today_data = dict(cur.fetchone())

        # Kal ke orders (comparison ke liye)
        cur.execute("""
            SELECT COUNT(*) as total_orders,
                   SUM(CASE WHEN is_return=0 THEN qty*sell_price ELSE 0 END) as revenue
            FROM orders WHERE date=date(?,' -1 days')
        """, (today,))
        yesterday_data = dict(cur.fetchone())

        # Aaj ke top items
        cur.execute("""
            SELECT item_name, SUM(qty) as qty, SUM(qty*sell_price) as revenue
            FROM orders WHERE date=? AND is_return=0
            GROUP BY item_name ORDER BY qty DESC LIMIT 5
        """, (today,))
        top_items = [dict(r) for r in cur.fetchall()]

        # Is hafte ka summary
        cur.execute("""
            SELECT date,
                   COUNT(*) as orders,
                   SUM(CASE WHEN is_return=0 THEN qty*sell_price ELSE 0 END) as revenue
            FROM orders
            WHERE date >= date(?, '-6 days') AND date <= ?
            GROUP BY date ORDER BY date ASC
        """, (today, today))
        weekly = [dict(r) for r in cur.fetchall()]

    return jsonify({
        "date":           today,
        "today":          today_data,
        "yesterday":      yesterday_data,
        "top_items":      top_items,
        "weekly":         weekly,
    })

# ── Supplier Routes ────────────────────────────────

@dashboard_bp.route("/suppliers", methods=["GET"])
def list_suppliers():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM suppliers ORDER BY name")
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])


@dashboard_bp.route("/suppliers", methods=["POST"])
def add_supplier():
    data = request.json
    if not data.get("name"):
        return jsonify({"error": "Name required"}), 400
    with get_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO suppliers (name, phone, category, notes)
            VALUES (?,?,?,?)
        """, (data["name"], data.get("phone",""),
              data.get("category",""), data.get("notes","")))
        sid = cur.lastrowid
    return jsonify({"id": sid, "message": "Supplier added!"}), 201


@dashboard_bp.route("/suppliers/<int:sid>", methods=["DELETE"])
def delete_supplier(sid):
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM suppliers WHERE id=?", (sid,))
    return jsonify({"message": "Deleted"})


@dashboard_bp.route("/suppliers/purchases", methods=["GET"])
def list_purchases():
    with get_cursor() as cur:
        cur.execute("""
            SELECT sp.*, s.name as supplier_name
            FROM supplier_purchases sp
            LEFT JOIN suppliers s ON s.id = sp.supplier_id
            ORDER BY sp.date DESC
        """)
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])


@dashboard_bp.route("/suppliers/purchases", methods=["POST"])
def add_purchase():
    data = request.json
    total     = float(data["qty"]) * float(data["cost_per_unit"])
    paid      = float(data.get("paid_amount", 0))
    pending   = total - paid
    with get_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO supplier_purchases
            (supplier_id, item_name, category, qty, cost_per_unit,
             total_cost, paid_amount, pending, date)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (data["supplier_id"], data["item_name"], data["category"],
              data["qty"], data["cost_per_unit"], total, paid, pending,
              data["date"]))
        pid = cur.lastrowid

        # Update supplier pending payment
        cur.execute("""
            UPDATE suppliers
            SET pending_payment = pending_payment + ?,
                total_purchased = total_purchased + ?
            WHERE id=?
        """, (pending, total, data["supplier_id"]))

        # Auto add to stock
        cur.execute("SELECT id FROM stock WHERE item_name=?", (data["item_name"],))
        existing = cur.fetchone()
        if existing:
            cur.execute("UPDATE stock SET qty=qty+? WHERE item_name=?",
                        (data["qty"], data["item_name"]))
        else:
            cur.execute("""
                INSERT INTO stock (category, item_name, qty, cost_per_product, date)
                VALUES (?,?,?,?,?)
            """, (data["category"], data["item_name"],
                  data["qty"], data["cost_per_unit"], data["date"]))

    return jsonify({"id": pid, "message": "Purchase added & stock updated!"}), 201


@dashboard_bp.route("/suppliers/purchases/<int:pid>/pay", methods=["PUT"])
def pay_supplier(pid):
    amount = float(request.json.get("amount", 0))
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT * FROM supplier_purchases WHERE id=?", (pid,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        new_paid    = float(row["paid_amount"]) + amount
        new_pending = float(row["total_cost"]) - new_paid
        cur.execute("""
            UPDATE supplier_purchases
            SET paid_amount=?, pending=? WHERE id=?
        """, (new_paid, new_pending, pid))
        cur.execute("""
            UPDATE suppliers
            SET pending_payment = pending_payment - ?
            WHERE id=?
        """, (amount, row["supplier_id"]))
    return jsonify({"message": "Payment recorded!"})