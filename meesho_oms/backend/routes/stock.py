from flask import Blueprint, request, jsonify
from backend.db import get_cursor

stock_bp = Blueprint("stock", __name__, url_prefix="/api/stock")


@stock_bp.route("", methods=["GET"])
def list_stock():
    with get_cursor() as cur:
        cur.execute("""SELECT id, category, item_name, qty, cost_per_product,
                    (qty*cost_per_product) as total_cost,
                    low_stock_alert, date FROM stock ORDER BY item_name""")
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])


@stock_bp.route("", methods=["POST"])
def add_stock():
    data = request.json
    for f in ["category","item_name","qty","cost_per_product","date"]:
        if f not in data:
            return jsonify({"error": f"Missing: {f}"}), 400

    with get_cursor(commit=True) as cur:
        cur.execute("SELECT id FROM stock WHERE item_name=?", (data["item_name"],))
        existing = cur.fetchone()
        if existing:
            cur.execute("UPDATE stock SET qty=qty+?, cost_per_product=?, date=? WHERE item_name=?",
                        (data["qty"], data["cost_per_product"], data["date"], data["item_name"]))
            sid = existing["id"]; action = "updated"
        else:
            cur.execute("""INSERT INTO stock (category, item_name, qty, cost_per_product,
                        low_stock_alert, date) VALUES (?,?,?,?,?,?)""",
                        (data["category"], data["item_name"], data["qty"],
                         data["cost_per_product"], data.get("low_stock_alert",10), data["date"]))
            sid = cur.lastrowid; action = "created"
        cur.execute("INSERT INTO inventory_transactions (item_name, category, txn_type, qty_change) VALUES (?,?,'restock',?)",
                    (data["item_name"], data["category"], data["qty"]))
    return jsonify({"id": sid, "action": action}), 201


@stock_bp.route("/<int:stock_id>", methods=["DELETE"])
def delete_stock(stock_id):
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM stock WHERE id=?", (stock_id,))
    return jsonify({"message": "Deleted"})


@stock_bp.route("/low", methods=["GET"])
def low_stock():
    with get_cursor() as cur:
        cur.execute("SELECT * FROM stock WHERE qty <= low_stock_alert ORDER BY qty ASC")
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])


@stock_bp.route("/export", methods=["GET"])
def export_stock():
    import io, csv
    from flask import Response
    with get_cursor() as cur:
        cur.execute("SELECT id, category, item_name, qty, cost_per_product, (qty*cost_per_product) as total_cost, date FROM stock ORDER BY category, item_name")
        rows = cur.fetchall()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["id","category","item_name","qty","cost_per_product","total_cost","date"])
    writer.writeheader()
    for r in rows: writer.writerow(dict(r))
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=stock.csv"})