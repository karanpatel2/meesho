from flask import Blueprint, request, jsonify
from backend.db import get_cursor

orders_bp = Blueprint("orders", __name__, url_prefix="/api/orders")

MEESHO_COMMISSION_RATE = 0.18
TDS_RATE = 0.01


@orders_bp.route("", methods=["GET"])
def list_orders():
    category      = request.args.get("category")
    date_from     = request.args.get("date_from")
    date_to       = request.args.get("date_to")
    is_return     = request.args.get("is_return")
    payment_status = request.args.get("payment_status")

    sql    = """SELECT id, invoice_id, category, item_name, qty, sell_price,
                (qty*sell_price) as total_amount, date, is_return, return_reason,
                order_status, payment_status, meesho_commission, tds_amount,
                net_payment, notes, created_at FROM orders WHERE 1=1"""
    params = []
    if category:
        sql += " AND category=?"; params.append(category)
    if date_from:
        sql += " AND date>=?"; params.append(date_from)
    if date_to:
        sql += " AND date<=?"; params.append(date_to)
    if is_return is not None:
        sql += " AND is_return=?"; params.append(1 if is_return.lower()=="true" else 0)
    if payment_status:
        sql += " AND payment_status=?"; params.append(payment_status)
    sql += " ORDER BY date DESC, id DESC"

    with get_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return jsonify([dict(r) for r in rows])


@orders_bp.route("", methods=["POST"])
def create_order():
    data     = request.json
    required = ["category","item_name","qty","sell_price","date"]
    for f in required:
        if f not in data:
            return jsonify({"error": f"Missing: {f}"}), 400

    is_return = 1 if data.get("is_return") else 0

    # Stock check
    if not is_return:
        with get_cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(qty),0) AS avail FROM stock WHERE item_name=?",
                        (data["item_name"],))
            avail = int(cur.fetchone()["avail"])
        if int(data["qty"]) > avail:
            return jsonify({"error": f"Stock kam hai. Available: {avail}"}), 409

    # Calculate Meesho commission, TDS, net payment
    total       = float(data["qty"]) * float(data["sell_price"])
    commission  = round(total * MEESHO_COMMISSION_RATE, 2)
    tds         = round(total * TDS_RATE, 2)
    net_payment = round(total - commission - tds, 2)

    with get_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO orders
            (category, item_name, qty, sell_price, date, is_return, return_reason,
             order_status, payment_status, meesho_commission, tds_amount, net_payment,
             invoice_id, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data["category"], data["item_name"], data["qty"], data["sell_price"],
            data["date"], is_return, data.get("return_reason",""),
            data.get("order_status","delivered"),
            data.get("payment_status","pending"),
            commission, tds, net_payment,
            data.get("invoice_id",""), data.get("notes","")
        ))
        order_id = cur.lastrowid

        # Update product stock
        if is_return:
            cur.execute("UPDATE stock SET qty=qty+? WHERE item_name=?",
                        (data["qty"], data["item_name"]))
        else:
            cur.execute("UPDATE stock SET qty=qty-? WHERE item_name=? AND qty>=?",
                        (data["qty"], data["item_name"], data["qty"]))

        # Deduct packaging (1 polybag + 1 label per order)
        cur.execute("UPDATE packaging SET qty=qty-1 WHERE item_name='Polybag 12x16' AND qty>0")
        cur.execute("UPDATE packaging SET qty=qty-1 WHERE item_name='Shipping Label' AND qty>0")

        # Audit log
        cur.execute("""INSERT INTO inventory_transactions
                    (item_name, category, txn_type, qty_change, ref_order_id)
                    VALUES (?,?,?,?,?)""",
                    (data["item_name"], data["category"],
                     "return" if is_return else "sale",
                     data["qty"] if is_return else -data["qty"], order_id))

    return jsonify({"id": order_id, "message": "Order saved!",
                    "commission": commission, "tds": tds, "net_payment": net_payment}), 201


@orders_bp.route("/bulk", methods=["POST"])
def bulk_create():
    items   = request.json.get("items", [])
    created, errors = [], []
    for item in items:
        with get_cursor() as cur:
            cur.execute("SELECT COALESCE(SUM(qty),0) AS avail FROM stock WHERE item_name=?",
                        (item.get("item_name",""),))
            avail = int(cur.fetchone()["avail"])
        if int(item.get("qty",0)) > avail:
            errors.append({"item": item["item_name"], "reason": f"Stock only: {avail}"}); continue

        total      = float(item["qty"]) * float(item["sell_price"])
        commission = round(total * MEESHO_COMMISSION_RATE, 2)
        tds        = round(total * TDS_RATE, 2)
        net        = round(total - commission - tds, 2)

        with get_cursor(commit=True) as cur:
            cur.execute("""INSERT INTO orders
                        (category, item_name, qty, sell_price, date, invoice_id,
                         meesho_commission, tds_amount, net_payment, payment_status)
                        VALUES (?,?,?,?,?,?,?,?,?,'pending')""",
                        (item["category"], item["item_name"], item["qty"],
                         item["sell_price"], item["date"], item.get("invoice_id",""),
                         commission, tds, net))
            oid = cur.lastrowid
            cur.execute("UPDATE stock SET qty=qty-? WHERE item_name=?",
                        (item["qty"], item["item_name"]))
            cur.execute("UPDATE packaging SET qty=qty-1 WHERE item_name='Polybag 12x16' AND qty>0")
            cur.execute("UPDATE packaging SET qty=qty-1 WHERE item_name='Shipping Label' AND qty>0")
            created.append(oid)
    return jsonify({"created": created, "errors": errors}), 201


@orders_bp.route("/<int:order_id>", methods=["DELETE"])
def delete_order(order_id):
    with get_cursor(commit=True) as cur:
        cur.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        row = cur.fetchone()
        if not row:
            return jsonify({"error": "Not found"}), 404
        cur.execute("DELETE FROM orders WHERE id=?", (order_id,))
        cur.execute("UPDATE stock SET qty=qty+? WHERE item_name=?",
                    (row["qty"], row["item_name"]))
    return jsonify({"message": "Deleted"})


@orders_bp.route("/<int:order_id>/payment", methods=["PUT"])
def update_payment(order_id):
    status = request.json.get("payment_status","received")
    with get_cursor(commit=True) as cur:
        cur.execute("UPDATE orders SET payment_status=? WHERE id=?", (status, order_id))
    return jsonify({"message": "Payment status updated"})


@orders_bp.route("/export", methods=["GET"])
def export_orders():
    import io, csv
    from flask import Response
    with get_cursor() as cur:
        cur.execute("""SELECT id, invoice_id, category, item_name, qty, sell_price,
                    (qty*sell_price) as total_amount, meesho_commission, tds_amount,
                    net_payment, date, is_return, return_reason, order_status,
                    payment_status, notes FROM orders ORDER BY date DESC""")
        rows = cur.fetchall()
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["id","invoice_id","category","item_name",
                                              "qty","sell_price","total_amount",
                                              "meesho_commission","tds_amount","net_payment",
                                              "date","is_return","return_reason",
                                              "order_status","payment_status","notes"])
    writer.writeheader()
    for r in rows: writer.writerow(dict(r))
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=orders.csv"})

@orders_bp.route("/import-csv", methods=["POST"])
def import_csv():
    import csv, io
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    
    f = request.files["file"]
    if not f.filename.endswith(".csv"):
        return jsonify({"error": "Only CSV files allowed"}), 400

    content  = f.read().decode("utf-8-sig")
    reader   = csv.DictReader(io.StringIO(content))
    
    created  = []
    errors   = []
    skipped  = 0

    # Meesho CSV column mapping
    COLUMN_MAP = {
        # Meesho column name : our field
        "Sub Order No."         : "invoice_id",
        "Order ID"              : "invoice_id",
        "Product Name"          : "item_name",
        "Item Name"             : "item_name",
        "SKU"                   : "item_name",
        "Selling Price"         : "sell_price",
        "Sale Price"            : "sell_price",
        "Price"                 : "sell_price",
        "Quantity"              : "qty",
        "Qty"                   : "qty",
        "Order Date"            : "date",
        "Date"                  : "date",
        "Category"              : "category",
        "Sub Category"          : "category",
        "Status"                : "order_status",
        "Order Status"          : "order_status",
    }

    for row in reader:
        try:
            # Map columns
            mapped = {}
            for col, val in row.items():
                col_clean = col.strip()
                if col_clean in COLUMN_MAP:
                    mapped[COLUMN_MAP[col_clean]] = val.strip()

            # Required fields check
            item_name  = mapped.get("item_name", "").strip()
            sell_price = mapped.get("sell_price", "0").replace("₹","").replace(",","").strip()
            qty        = mapped.get("qty", "1").strip()
            date       = mapped.get("date", "").strip()
            category   = mapped.get("category", "Uncategorized").strip()
            invoice_id = mapped.get("invoice_id", "").strip()
            status     = mapped.get("order_status", "delivered").strip().lower()

            if not item_name:
                skipped += 1
                continue

            # Parse date
            from datetime import datetime
            parsed_date = None
            for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y",
                        "%m/%d/%Y", "%d %b %Y", "%d-%b-%Y"]:
                try:
                    parsed_date = datetime.strptime(date, fmt).strftime("%Y-%m-%d")
                    break
                except:
                    continue
            if not parsed_date:
                from datetime import date as dt
                parsed_date = dt.today().isoformat()

            # Is return?
            is_return = 1 if "return" in status or "cancel" in status else 0

            try:
                qty_int   = int(float(qty))
                price_flt = float(sell_price) if sell_price else 0.0
            except:
                skipped += 1
                continue

            # Commission calc
            total      = qty_int * price_flt
            commission = round(total * 0.18, 2)
            tds        = round(total * 0.01, 2)
            net        = round(total - commission - tds, 2)

            # Duplicate check
            with get_cursor() as cur:
                cur.execute("""SELECT id FROM orders
                            WHERE invoice_id=? AND item_name=? AND date=?""",
                            (invoice_id, item_name, parsed_date))
                dup = cur.fetchone()
            if dup:
                skipped += 1
                continue

            with get_cursor(commit=True) as cur:
                cur.execute("""
                    INSERT INTO orders
                    (category, item_name, qty, sell_price, date, is_return,
                     invoice_id, order_status, payment_status,
                     meesho_commission, tds_amount, net_payment)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """, (category, item_name, qty_int, price_flt,
                      parsed_date, is_return, invoice_id,
                      "returned" if is_return else "delivered",
                      "pending", commission, tds, net))
                oid = cur.lastrowid

                # Update stock
                if not is_return:
                    cur.execute("""UPDATE stock SET qty=qty-?
                                WHERE item_name=? AND qty>=?""",
                                (qty_int, item_name, qty_int))
                else:
                    cur.execute("UPDATE stock SET qty=qty+? WHERE item_name=?",
                                (qty_int, item_name))

                created.append(oid)

        except Exception as e:
            errors.append({"row": str(row), "error": str(e)})

    return jsonify({
        "imported": len(created),
        "skipped":  skipped,
        "errors":   len(errors),
        "message":  f"{len(created)} orders imported, {skipped} skipped, {len(errors)} errors"
    }), 201