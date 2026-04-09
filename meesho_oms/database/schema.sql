-- Meesho OMS - Complete SQLite Schema

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id    TEXT DEFAULT '',
    category      TEXT NOT NULL,
    item_name     TEXT NOT NULL,
    qty           INTEGER NOT NULL CHECK (qty > 0),
    sell_price    REAL NOT NULL CHECK (sell_price >= 0),
    date          TEXT NOT NULL DEFAULT (date('now')),
    is_return     INTEGER DEFAULT 0,
    return_reason TEXT DEFAULT '',
    order_status  TEXT DEFAULT 'delivered',
    payment_status TEXT DEFAULT 'pending',
    meesho_commission REAL DEFAULT 0,
    tds_amount    REAL DEFAULT 0,
    net_payment   REAL DEFAULT 0,
    notes         TEXT DEFAULT '',
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS stock (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    category         TEXT NOT NULL,
    item_name        TEXT NOT NULL,
    qty              INTEGER NOT NULL DEFAULT 0,
    cost_per_product REAL NOT NULL DEFAULT 0,
    low_stock_alert  INTEGER DEFAULT 10,
    date             TEXT NOT NULL DEFAULT (date('now')),
    created_at       TEXT DEFAULT (datetime('now')),
    updated_at       TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS packaging (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name       TEXT NOT NULL,
    qty             INTEGER NOT NULL DEFAULT 0,
    cost_per_unit   REAL NOT NULL DEFAULT 0,
    low_stock_alert INTEGER DEFAULT 50,
    date            TEXT NOT NULL DEFAULT (date('now')),
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS suppliers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    phone           TEXT DEFAULT '',
    category        TEXT DEFAULT '',
    pending_payment REAL DEFAULT 0,
    total_purchased REAL DEFAULT 0,
    notes           TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS supplier_purchases (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id   INTEGER,
    item_name     TEXT,
    category      TEXT,
    qty           INTEGER,
    cost_per_unit REAL,
    total_cost    REAL,
    paid_amount   REAL DEFAULT 0,
    pending       REAL DEFAULT 0,
    date          TEXT DEFAULT (date('now')),
    created_at    TEXT DEFAULT (datetime('now'))
);

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

CREATE TABLE IF NOT EXISTS inventory_transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name    TEXT,
    category     TEXT,
    txn_type     TEXT,
    qty_change   INTEGER,
    ref_order_id INTEGER,
    notes        TEXT,
    created_at   TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_orders_date      ON orders(date);
CREATE INDEX IF NOT EXISTS idx_orders_category  ON orders(category);
CREATE INDEX IF NOT EXISTS idx_orders_is_return ON orders(is_return);
CREATE INDEX IF NOT EXISTS idx_stock_item       ON stock(item_name);
CREATE INDEX IF NOT EXISTS idx_upload_hash      ON upload_logs(file_hash);

CREATE TRIGGER IF NOT EXISTS trg_stock_updated
    AFTER UPDATE ON stock FOR EACH ROW
BEGIN
    UPDATE stock SET updated_at = datetime('now') WHERE id = OLD.id;
END;

INSERT OR IGNORE INTO stock (id, category, item_name, qty, cost_per_product, date) VALUES
    (1, 'Clothing',    'Kurti Blue M',      50, 180.00, date('now')),
    (2, 'Clothing',    'Kurti Red L',       30, 195.00, date('now')),
    (3, 'Accessories', 'Silver Earrings',  100,  45.00, date('now')),
    (4, 'Footwear',    'Sandal Black 6',    20, 280.00, date('now')),
    (5, 'Footwear',    'Sandal Brown 7',    15, 295.00, date('now')),
    (6, 'Home Decor',  'Cushion Cover Set', 40,  95.00, date('now'));

INSERT OR IGNORE INTO packaging (id, item_name, qty, cost_per_unit, low_stock_alert, date) VALUES
    (1, 'Polybag 12x16',    500, 2.00,   50, date('now')),
    (2, 'Bubble Wrap Roll',  10, 120.00,  3, date('now')),
    (3, 'Brown Tape Roll',   20,  35.00,  5, date('now')),
    (4, 'Shipping Label',   500,   0.50, 50, date('now')),
    (5, 'Small Box',         50,  12.00, 10, date('now'));

-- Users Table
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT NOT NULL UNIQUE,
    password   TEXT NOT NULL,
    full_name  TEXT DEFAULT '',
    role       TEXT DEFAULT 'admin',
    created_at TEXT DEFAULT (datetime('now'))
);

-- Default admin user (password: admin123)
INSERT OR IGNORE INTO users (id, username, password, full_name, role)
VALUES (1, 'admin', 'admin123', 'Admin User', 'admin');