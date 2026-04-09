import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "meesho_oms.db")


def dict_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_cursor(commit=False):
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def init_db():
    """Tables banao agar exist nahi karti."""
    schema_path = os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")
    
    # Check karo schema file hai
    if not os.path.exists(schema_path):
        print(f"ERROR: schema.sql nahi mila: {schema_path}")
        return
    
    with open(schema_path, "r") as f:
        sql = f.read()
    
    conn = get_connection()
    try:
        conn.executescript(sql)
        conn.commit()
        print("✅ SQLite database initialized successfully.")
        print(f"📁 DB location: {os.path.abspath(DB_PATH)}")
    except Exception as e:
        print(f"❌ DB Error: {e}")
    finally:
        conn.close()