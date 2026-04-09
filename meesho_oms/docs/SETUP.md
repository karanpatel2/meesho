# Meesho OMS — Setup & Deployment Guide

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.10+ | python.org |
| PostgreSQL | 14+ | postgresql.org |
| Tesseract OCR | 5.x | See below |
| poppler-utils | Latest | For PDF support |

---

## 1. Install System Dependencies

### Ubuntu / Debian
```bash
sudo apt update
sudo apt install -y tesseract-ocr tesseract-ocr-eng poppler-utils
```

### macOS (Homebrew)
```bash
brew install tesseract poppler
```

### Windows
1. Download Tesseract installer: https://github.com/UB-Mannheim/tesseract/wiki
2. Download poppler for Windows: https://github.com/oschwartz10612/poppler-windows
3. Add both to PATH environment variable.

---

## 2. Set Up PostgreSQL

```bash
# Create database
psql -U postgres -c "CREATE DATABASE meesho_oms;"

# Run schema
psql -U postgres -d meesho_oms -f database/schema.sql
```

---

## 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your DB credentials and optional Google Vision API key
```

---

## 4. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

---

## 5. Run the Application

### Development
```bash
# From project root
python app.py
```
Then open: http://localhost:5000

### Production (Gunicorn)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 "app:create_app()"
```

---

## 6. Optional: Google Vision API (Higher OCR Accuracy)

1. Go to https://console.cloud.google.com
2. Enable **Cloud Vision API**
3. Create an API key
4. Set in `.env`:
   ```
   GOOGLE_VISION_API_KEY=your_key_here
   ```

---

## 7. Project Structure

```
meesho_oms/
├── app.py                    # Flask entry point
├── .env.example              # Config template
├── database/
│   └── schema.sql            # PostgreSQL schema + seed data
├── backend/
│   ├── db.py                 # DB connection
│   ├── requirements.txt
│   ├── routes/
│   │   ├── orders.py         # Orders CRUD + export
│   │   ├── stock.py          # Stock CRUD + export
│   │   ├── ocr_route.py      # File upload + OCR
│   │   └── dashboard.py      # Analytics + prediction
│   └── utils/
│       ├── ocr.py            # OCR engine (Tesseract / Vision)
│       ├── fuzzy.py          # Fuzzy item matching
│       └── analytics.py      # ML prediction + KPIs
├── frontend/
│   ├── templates/
│   │   └── index.html        # Single-page app
│   └── static/
│       ├── css/app.css
│       └── js/app.js
└── uploads/                  # Auto-created on first upload
```

---

## 8. API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/orders` | GET | List orders (filterable) |
| `/api/orders` | POST | Create order |
| `/api/orders/bulk` | POST | Bulk create (from OCR) |
| `/api/orders/{id}` | DELETE | Delete + restore stock |
| `/api/orders/export` | GET | Download CSV |
| `/api/stock` | GET/POST | List / add stock |
| `/api/stock/{id}` | PUT/DELETE | Update / delete |
| `/api/stock/export` | GET | Download CSV |
| `/api/ocr/upload` | POST | Upload invoice file |
| `/api/dashboard/metrics` | GET | KPI metrics |
| `/api/dashboard/predict` | GET | ML predictions |
| `/api/dashboard/categories` | GET | Distinct categories |
| `/api/dashboard/logs` | GET | Upload logs |

---

## 9. Troubleshooting

**Tesseract not found:**
```bash
which tesseract   # Verify it's installed
# In backend/utils/ocr.py, set path manually:
# pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
```

**PDF conversion fails:**
```bash
which pdfinfo   # Verify poppler is installed
```

**DB connection error:**
- Check `.env` DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
- Ensure PostgreSQL is running: `sudo service postgresql start`
