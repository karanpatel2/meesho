"""Orders API routes."""
from flask import Blueprint, request, jsonify
from backend.db import get_cursor

orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")


@orders_bp.route("", methods=["GET"])
def list_orders():
    category  = request.args.get("category")
    date_from = request.args.get("date_from")
    date_to   = request.args.get("date_to")
    is_return = request.args.get("is_return")

    sql    = "SELECT * FROM orders WHERE 1=1"
    params = []
    if category:
        sql += " AND category = %s"; params.append(category)
    if date_from:
        sql += " AND date >= %s"; params.append(date_from)
    if date_to:
        sql += " AND date <= %s"; params.append(date_to)
    if is_return is not None:
        sql += " AND is_return = %s"; params.append(is_return.lower() == "true")
    sql += " ORDER BY date DESC, id DESC"

    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])


@orders_bp.route("", methods=["POST"])
def create_order():
    data = request.json
    required = ["category", "item_name", "qty", "sell_price", "date"]
    for f in required:
        if f not in data:
            return jsonify({"error": f"Missing field: {f}"}), 400

    # Stock check
    with get_cursor() as cur:
        cur.execute(
            "SELECT COALESCE(SUM(qty),0) AS avail FROM stock WHERE item_name = %s",
            (data["item_name"],)
        )
        avail = int(cur.fetchone()["avail"])

    is_return = data.get("is_return", False)
    if not is_return and int(data["qty"]) > avail:
        return jsonify({
            "error": f"Insufficient stock. Available: {avail}, Requested: {data['qty']}"
        }), 409

    with get_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO orders (category, item_name, qty, sell_price, date, is_return, invoice_id, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (
            data["category"], data["item_name"], data["qty"],
            data["sell_price"], data["date"],
            is_return,
            data.get("invoice_id", ""),
            data.get("notes", ""),
        ))
        order_id = cur.fetchone()["id"]

        # Update stock
        if is_return:
            cur.execute("""
                UPDATE stock SET qty = qty + %s
                WHERE item_name = %s
            """, (data["qty"], data["item_name"]))
        else:
            cur.execute("""
                UPDATE stock SET qty = qty - %s
                WHERE item_name = %s AND qty >= %s
            """, (data["qty"], data["item_name"], data["qty"]))

        # Audit log
        cur.execute("""
            INSERT INTO inventory_transactions (item_name, category, txn_type, qty_change, ref_order_id)
            VALUES (%s,%s,%s,%s,%s)
        """, (
            data["item_name"], data["category"],
            "return" if is_return else "sale",
            data["qty"] if is_return else -data["qty"],
            order_id,
        ))

    return jsonify({"id": order_id, "message": "Order created successfully"}), 201


@orders_bp.route("/bulk", methods=["POST"])
def bulk_create():
    items = request.json.get("items", [])
    created = []
    errors  = []
    for item in items:
        with get_cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(qty),0) AS avail FROM stock WHERE item_name = %s",
                (item.get("item_name", ""),)
            )
            avail = int(cur.fetchone()["avail"])
        if int(item.get("qty", 0)) > avail:
            errors.append({"item": item["item_name"], "reason": f"Stock: {avail}"})
            continue
        with get_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO orders (category, item_name, qty, sell_price, date, invoice_id)
                VALUES (%s,%s,%s,%s,%s,%s) RETURNING id
            """, (
                item["category"], item["item_name"], item["qty"],
                item["sell_price"], item["date"], item.get("invoice_id","")
            ))
            oid = cur.fetchone()["id"]
            cur.execute("UPDATE stock SET qty = qty - %s WHERE item_name = %s",
                        (item["qty"], item["item_name"]))
            created.append(oid)
    return jsonify({"created": created, "errors": errors}), 201


@orders_bp.route("/<int:order_id>", methods=["DELETE"])
def delete_order(order_id):
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT * FROM orders WHERE id=%s", (order_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        cur.execute("DELETE FROM orders WHERE id=%s", (order_id,))
        # Restore stock
        cur.execute("UPDATE stock SET qty = qty + %s WHERE item_name = %s",
                    (row["qty"], row["item_name"]))
    return jsonify({"message": "Deleted"})


@orders_bp.route("/export", methods=["GET"])
def export_orders():
    import io, csv
    from flask import Response
    with get_cursor() as cur:
        cur.execute("SELECT * FROM orders ORDER BY date DESC")
        rows = cur.fetchall()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["id","invoice_id","category","item_name",
                                              "qty","sell_price","total_amount",
                                              "date","is_return","notes","created_at"])
    writer.writeheader()
    for r in rows:
        writer.writerow(dict(r))
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=orders.csv"})
