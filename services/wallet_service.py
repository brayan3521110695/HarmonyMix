# services/wallet_service.py
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "harmony.db"

def _ensure_schema(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS wallet (
            user_id INTEGER PRIMARY KEY,
            credits INTEGER NOT NULL DEFAULT 0
        )
    """)

def wallet_get_credits(user_id: int) -> int:
    with sqlite3.connect(DB_PATH) as con:
        _ensure_schema(con)
        cur = con.execute("SELECT credits FROM wallet WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        return int(row[0]) if row else 0

def wallet_add_credits(user_id: int, amount: int) -> int:
    with sqlite3.connect(DB_PATH) as con:
        _ensure_schema(con)
        cur = con.execute("SELECT credits FROM wallet WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        current = int(row[0]) if row else 0
        newval = max(0, current + int(amount))
        con.execute("""
            INSERT INTO wallet(user_id, credits) VALUES(?, ?)
            ON CONFLICT(user_id) DO UPDATE SET credits=excluded.credits
        """, (user_id, newval))
        return newval
