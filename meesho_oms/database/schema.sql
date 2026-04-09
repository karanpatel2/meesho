-- ============================================================
-- Meesho Order Management System - SQLite Schema
-- ============================================================

-- Orders Table
CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id   TEXT DEFAULT '',
    category     TEXT NOT NULL,
    item_name    TEXT NOT NULL,
    qty          INTEGER NOT NULL CHECK (qty > 0),
    sell_price   REAL NOT NULL CHECK (sell_price >= 0),
    total_amount REAL AS (qty * sell_price) VIRTUAL,
    date         TEXT NOT NULL DEFAULT (date('now')),
    is_return    INTEGER DEFAULT 0,
    notes        TEXT DEFAULT '',
    created_at   TEXT DEFAULT (datetime('now'))
);

-- Stock Table
CREATE TABLE IF NOT EXISTS stock (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    category         TEXT NOT NULL,
    item_name        TEXT NOT NULL,
    qty              INTEGER NOT NULL DEFAULT 0,
    cost_per_product REAL NOT NULL CHECK (cost_per_product >= 0),
    total_cost       REAL AS (qty * cost_per_product) VIRTUAL,
    date             TEXT NOT NULL DEFAULT (date('now')),
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

-- Upload Logs Table
CREATE TABLE IF NOT EXISTS upload_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    filename     TEXT,
    file_hash    TEXT,
    status       TEXT DEFAULT 'pending',
    ocr_raw_text TEXT,
    items_found  INTEGER DEFAULT 0,
    error_msg    TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

-- Inventory Transactions (audit trail)
CREATE TABLE IF NOT EXISTS inventory_transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name    TEXT,
    category     TEXT,
    txn_type     TEXT CHECK (txn_type IN ('sale','restock','return','adjustment')),
    qty_change   INTEGER,
    ref_order_id INTEGER,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_orders_date      ON orders(date);
CREATE INDEX IF NOT EXISTS idx_orders_category  ON orders(category);
CREATE INDEX IF NOT EXISTS idx_orders_is_return ON orders(is_return);
CREATE INDEX IF NOT EXISTS idx_stock_item       ON stock(item_name);
CREATE INDEX IF NOT EXISTS idx_upload_hash      ON upload_logs(file_hash);

-- Trigger: update stock.updated_at on row change
CREATE TRIGGER IF NOT EXISTS trg_stock_updated
    AFTER UPDATE ON stock
    FOR EACH ROW
BEGIN
    UPDATE stock SET updated_at = datetime('now') WHERE id = OLD.id;
END;

-- Sample seed data (only if stock is empty)
INSERT OR IGNORE INTO stock (id, category, item_name, qty, cost_per_product, date) VALUES
    (1, 'Clothing',    'Kurti Blue M',      50, 180.00, date('now')),
    (2, 'Clothing',    'Kurti Red L',       30, 195.00, date('now')),
    (3, 'Accessories', 'Silver Earrings',  100,  45.00, date('now')),
    (4, 'Footwear',    'Sandal Black 6',    20, 280.00, date('now')),
    (5, 'Footwear',    'Sandal Brown 7',    15, 295.00, date('now')),
    (6, 'Home Decor',  'Cushion Cover Set', 40,  95.00, date('now'));