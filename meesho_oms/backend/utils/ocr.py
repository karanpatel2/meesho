"""
OCR Processing Module for Meesho Invoices
Supports: Tesseract OCR (default) + Google Vision API (optional)
"""
import os
import re
import hashlib
import json
import logging
from pathlib import Path
from datetime import datetime

try:
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False

logger = logging.getLogger(__name__)

# ── Meesho-specific regex patterns ────────────────────────────────────────────

PATTERNS = {
    "order_id":    re.compile(r"(?:Order\s*(?:ID|No|#)[\s:]*)([\w-]+)", re.I),
    "date":        re.compile(
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
        r"|(\d{4}-\d{2}-\d{2})"
        r"|((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s*\d{4})",
        re.I
    ),
    "price":       re.compile(r"(?:Rs\.?|₹|INR)\s*([\d,]+(?:\.\d{1,2})?)"),
    "qty":         re.compile(r"(?:Qty|Quantity|Q\.?ty)[\s:]*(\d+)", re.I),
    "category":    re.compile(
        r"\b(Kurti|Saree|Dress|Top|Legging|Pant|Shirt|Shoes?|Sandal|Slipper|"
        r"Bag|Purse|Jewel|Earring|Necklace|Bracelet|Kurta|Suit|Dupatta|"
        r"Bedsheet|Curtain|Cushion|Pillow|Towel|Nightwear|Lingerie|Bra|"
        r"Ethnic|Western|Accessori|Footwear|Home Decor|Clothing)\w*",
        re.I
    ),
}

CATEGORY_MAP = {
    "kurti": "Clothing", "kurta": "Clothing", "saree": "Clothing",
    "dress": "Clothing", "top": "Clothing", "legging": "Clothing",
    "pant": "Clothing", "shirt": "Clothing", "suit": "Clothing",
    "dupatta": "Clothing", "ethnic": "Clothing", "western": "Clothing",
    "nightwear": "Clothing", "lingerie": "Clothing", "bra": "Clothing",
    "shoes": "Footwear", "shoe": "Footwear", "sandal": "Footwear",
    "slipper": "Footwear", "footwear": "Footwear",
    "bag": "Bags", "purse": "Bags",
    "jewel": "Accessories", "earring": "Accessories", "necklace": "Accessories",
    "bracelet": "Accessories", "accessori": "Accessories",
    "bedsheet": "Home Decor", "curtain": "Home Decor", "cushion": "Home Decor",
    "pillow": "Home Decor", "towel": "Home Decor", "home decor": "Home Decor",
}


# ── Image pre-processing ──────────────────────────────────────────────────────

def preprocess_image(img: "Image.Image") -> "Image.Image":
    """Enhance image quality for better OCR accuracy."""
    img = img.convert("L")                                    # grayscale
    img = img.filter(ImageFilter.MedianFilter(size=3))        # noise reduction
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.5)
    return img


# ── File helpers ──────────────────────────────────────────────────────────────

def file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_images(filepath: str) -> list:
    """Return list of PIL images from a PDF or image file."""
    ext = Path(filepath).suffix.lower()
    if ext == ".pdf":
        if not PDF2IMAGE_AVAILABLE:
            raise RuntimeError("pdf2image not installed. Install poppler-utils.")
        pages = convert_from_path(filepath, dpi=300)
        return pages
    else:
        return [Image.open(filepath)]


# ── OCR engines ──────────────────────────────────────────────────────────────

def ocr_tesseract(img: "Image.Image") -> tuple[str, float]:
    """Return (text, confidence)."""
    if not TESSERACT_AVAILABLE:
        raise RuntimeError("pytesseract not installed.")
    processed = preprocess_image(img)
    config = "--oem 3 --psm 6"
    data = pytesseract.image_to_data(processed, config=config,
                                     output_type=pytesseract.Output.DICT)
    words  = [w for w in data["text"] if w.strip()]
    confs  = [c for c, w in zip(data["conf"], data["text"])
              if w.strip() and c != -1]
    text   = pytesseract.image_to_string(processed, config=config)
    avg_conf = sum(confs) / len(confs) if confs else 0.0
    return text, avg_conf


def ocr_google_vision(img: "Image.Image", api_key: str) -> tuple[str, float]:
    """Return (text, confidence) via Google Vision REST API."""
    import io, base64, urllib.request, urllib.error
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    payload = json.dumps({
        "requests": [{
            "image": {"content": b64},
            "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]
        }]
    }).encode()
    url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        annotation = result["responses"][0].get("fullTextAnnotation", {})
        text = annotation.get("text", "")
        pages = annotation.get("pages", [])
        conf  = pages[0].get("property", {}).get("detectedLanguages", [{}])[0]\
                        .get("confidence", 0.9) if pages else 0.9
        return text, float(conf) * 100
    except Exception as e:
        logger.error("Google Vision error: %s", e)
        return "", 0.0


# ── Text parsing ──────────────────────────────────────────────────────────────

def parse_date(text: str) -> str:
    """Try to extract and normalise a date to YYYY-MM-DD."""
    m = PATTERNS["date"].search(text)
    if not m:
        return datetime.today().strftime("%Y-%m-%d")
    raw = next(g for g in m.groups() if g)
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d",
                "%d/%m/%y", "%d-%m-%y", "%B %d, %Y",
                "%b %d, %Y", "%B %d %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return datetime.today().strftime("%Y-%m-%d")


def infer_category(text: str) -> str:
    m = PATTERNS["category"].search(text)
    if m:
        word = m.group(0).lower()
        for key, cat in CATEGORY_MAP.items():
            if key in word:
                return cat
    return "Uncategorized"


def extract_items_from_text(raw_text: str) -> list[dict]:
    """
    Parse raw OCR text into a list of order items.
    Strategy:
      1. Try to find structured table rows (qty + price on same line).
      2. Fall back to block-level heuristics.
    """
    lines = [l.strip() for l in raw_text.splitlines() if l.strip()]
    items = []
    order_date = parse_date(raw_text)
    invoice_match = PATTERNS["order_id"].search(raw_text)
    invoice_id = invoice_match.group(1) if invoice_match else ""

    # --- Strategy 1: table-row pattern  ---------------------------------
    # Line like: "Kurti Blue M   2   ₹350.00" or "1  Blue Kurti  M  1  350"
    row_pattern = re.compile(
        r"(.+?)\s+"              # item description
        r"(\d+)\s+"              # qty
        r"(?:Rs\.?|₹|INR)?\s*"
        r"([\d,]+(?:\.\d{1,2})?)",  # price
        re.I
    )
    for line in lines:
        m = row_pattern.search(line)
        if m:
            name_raw = m.group(1).strip()
            qty      = int(m.group(2))
            price    = float(m.group(3).replace(",", ""))
            if qty <= 0 or price <= 0 or len(name_raw) < 3:
                continue
            items.append({
                "item_name":   name_raw,
                "qty":         qty,
                "sell_price":  price,
                "category":    infer_category(name_raw + " " + raw_text),
                "date":        order_date,
                "invoice_id":  invoice_id,
                "confidence":  85,
            })

    # --- Strategy 2: block heuristics if nothing found ------------------
    if not items:
        prices = [float(p.replace(",", ""))
                  for p in PATTERNS["price"].findall(raw_text)]
        qty_m  = PATTERNS["qty"].search(raw_text)
        qty    = int(qty_m.group(1)) if qty_m else 1
        # best-guess item name: longest non-numeric line in first 15 lines
        candidate = max(
            (l for l in lines[:15] if not re.fullmatch(r"[\d\s₹Rs.,/-]+", l)),
            key=len, default="Unknown Item"
        )
        price = prices[0] if prices else 0.0
        items.append({
            "item_name":   candidate[:80],
            "qty":         qty,
            "sell_price":  price,
            "category":    infer_category(raw_text),
            "date":        order_date,
            "invoice_id":  invoice_id,
            "confidence":  50,
        })

    return items


# ── Public API ────────────────────────────────────────────────────────────────

def process_invoice(filepath: str, api_key: str = "") -> dict:
    """
    Main entry point. Returns:
    {
        "file_hash": str,
        "raw_text":  str,
        "confidence": float,
        "items": [ {item_name, qty, sell_price, category, date, invoice_id, confidence} ]
    }
    """
    fhash  = file_hash(filepath)
    images = load_images(filepath)
    all_text = ""
    total_conf = 0.0

    for img in images:
        if api_key:
            text, conf = ocr_google_vision(img, api_key)
        else:
            text, conf = ocr_tesseract(img)
        all_text    += "\n" + text
        total_conf  += conf

    avg_conf = total_conf / len(images) if images else 0.0
    items    = extract_items_from_text(all_text)

    return {
        "file_hash":  fhash,
        "raw_text":   all_text.strip(),
        "confidence": round(avg_conf, 1),
        "items":      items,
    }
