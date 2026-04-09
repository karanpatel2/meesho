"""OCR upload route."""
import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from backend.db import get_cursor
from backend.utils.ocr import process_invoice
from backend.utils.fuzzy import find_best_stock_match, fuzzy_deduplicate

ocr_bp = Blueprint("ocr", __name__, url_prefix="/api/ocr")

ALLOWED = {"png","jpg","jpeg","gif","bmp","tiff","pdf"}


def allowed_file(name):
    return "." in name and name.rsplit(".", 1)[1].lower() in ALLOWED


@ocr_bp.route("/upload", methods=["POST"])
def upload_invoice():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    f = request.files["file"]
    if not f.filename or not allowed_file(f.filename):
        return jsonify({"error": "Invalid file type"}), 400

    upload_dir = os.path.join(current_app.root_path, "..", "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    filename  = secure_filename(f.filename)
    filepath  = os.path.join(upload_dir, filename)
    f.save(filepath)

    api_key = os.getenv("GOOGLE_VISION_API_KEY", "")
    try:
        result  = process_invoice(filepath, api_key=api_key)
    except Exception as e:
        # Log and return error
        with get_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO upload_logs (filename, status, error_msg)
                VALUES (%s,'error',%s)
            """, (filename, str(e)))
        return jsonify({"error": str(e)}), 500

    fhash = result["file_hash"]

    # Duplicate detection
    with get_cursor() as cur:
        cur.execute("SELECT id FROM upload_logs WHERE file_hash=%s AND status='success'",
                    (fhash,))
        dup = cur.fetchone()
    if dup:
        return jsonify({"error": "Duplicate invoice already processed."}), 409

    # Fuzzy match items against stock
    with get_cursor() as cur:
        cur.execute("SELECT item_name FROM stock")
        stock_names = [r["item_name"] for r in cur.fetchall()]

    items = fuzzy_deduplicate(result["items"])
    for item in items:
        matched, score = find_best_stock_match(item["item_name"], stock_names)
        item["matched_stock_name"] = matched
        item["match_score"]        = score

    # Log upload
    with get_cursor(commit=True) as cur:
        cur.execute("""
            INSERT INTO upload_logs (filename, file_hash, status, ocr_raw_text, items_found)
            VALUES (%s,%s,'success',%s,%s)
        """, (filename, fhash, result["raw_text"], len(items)))

    return jsonify({
        "file_hash":  fhash,
        "confidence": result["confidence"],
        "items":      items,
        "raw_text":   result["raw_text"],
    })
