"""Stock API routes."""
from flask import Blueprint, request, jsonify
from backend.db import get_cursor

stock_bp = Blueprint("stock", __name__, url_prefix="/api/stock")


@stock_bp.route("", methods=["GET"])
def list_stock():
    category = request.args.get("category")
    sql = "SELECT * FROM stock WHERE 1=1"
    params = []
    if category:
        sql += " AND category=%s"; params.append(category)
    sql += " ORDER BY item_name"
    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])


@stock_bp.route("", methods=["POST"])
def add_stock():
    data = request.json
    required = ["category","item_name","qty","cost_per_product","date"]
    for f in required:
        if f not in data:
            return jsonify({"error": f"Missing: {f}"}), 400

    with get_cursor(commit=True) as cur:
        # Upsert: if item already exists, increase qty
        cur.execute("SELECT id FROM stock WHERE item_name=%s", (data["item_name"],))
        existing = cur.fetchone()
        if existing:
            cur.execute("""
                UPDATE stock SET qty = qty + %s, cost_per_product=%s, date=%s
                WHERE item_name=%s RETURNING id
            """, (data["qty"], data["cost_per_product"], data["date"], data["item_name"]))
            sid = cur.fetchone()["id"]
            action = "updated"
        else:
            cur.execute("""
                INSERT INTO stock (category, item_name, qty, cost_per_product, date)
                VALUES (%s,%s,%s,%s,%s) RETURNING id
            """, (data["category"], data["item_name"], data["qty"],
                  data["cost_per_product"], data["date"]))
            sid = cur.fetchone()["id"]
            action = "created"

        cur.execute("""
            INSERT INTO inventory_transactions (item_name, category, txn_type, qty_change)
            VALUES (%s,%s,'restock',%s)
        """, (data["item_name"], data["category"], data["qty"]))

    return jsonify({"id": sid, "action": action}), 201


@stock_bp.route("/<int:stock_id>", methods=["PUT"])
def update_stock(stock_id):
    data = request.json
    with get_cursor(commit=True) as cur:
        cur.execute("""
            UPDATE stock SET category=%s, item_name=%s, qty=%s, cost_per_product=%s, date=%s
            WHERE id=%s
        """, (data["category"], data["item_name"], data["qty"],
              data["cost_per_product"], data["date"], stock_id))
    return jsonify({"message": "Updated"})


@stock_bp.route("/<int:stock_id>", methods=["DELETE"])
def delete_stock(stock_id):
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM stock WHERE id=%s", (stock_id,))
    return jsonify({"message": "Deleted"})


@stock_bp.route("/export", methods=["GET"])
def export_stock():
    import io, csv
    from flask import Response
    with get_cursor() as cur:
        cur.execute("SELECT * FROM stock ORDER BY category, item_name")
        rows = cur.fetchall()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["id","category","item_name","qty",
                                              "cost_per_product","total_cost","date"])
    writer.writeheader()
    for r in rows:
        writer.writerow(dict(r))
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=stock.csv"})
