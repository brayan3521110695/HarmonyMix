import sqlite3

DB_PATH = "harmony.db"

def get_db():
    """Conexión con acceso por nombre de columna."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# =========================
#  Costos: wallet + ledger
# =========================
def init_cost_tables():
    """Crea tablas de costos si no existen."""
    with get_db() as conn:
        c = conn.cursor()
        # Billetera de créditos
        c.execute("""
        CREATE TABLE IF NOT EXISTS wallet(
            user_id INTEGER PRIMARY KEY,
            credits INTEGER NOT NULL DEFAULT 0
        )
        """)
        # Historial de movimientos (ledger)
        c.execute("""
        CREATE TABLE IF NOT EXISTS credit_ledger(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            delta INTEGER NOT NULL,
            reason TEXT NOT NULL,         -- 'purchase','demo_purchase','consume','refund','admin'
            note TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()

def _wallet_log(user_id: int, delta: int, reason: str, note: str | None = None) -> None:
    """Registra un movimiento en el ledger."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO credit_ledger(user_id, delta, reason, note) VALUES (?,?,?,?)",
            (user_id, delta, reason, note)
        )
        conn.commit()

def wallet_get_credits(user_id: int) -> int:
    """Obtiene créditos del usuario. Si no existe, lo crea con 0."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("SELECT credits FROM wallet WHERE user_id=?", (user_id,))
        row = c.fetchone()
        if not row:
            c.execute("INSERT INTO wallet(user_id, credits) VALUES(?, 0)", (user_id,))
            conn.commit()
            return 0
        return row["credits"]

def wallet_add_credits(user_id: int, qty: int, reason: str = "admin", note: str | None = None) -> None:
    """
    Suma o resta créditos y registra en el ledger.
    Usa qty negativo para restar (p.ej. ajustes/admin).
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO wallet(user_id, credits) VALUES(?, 0)", (user_id,))
        c.execute("UPDATE wallet SET credits = credits + ? WHERE user_id=?", (qty, user_id))
        conn.commit()
    _wallet_log(user_id, qty, reason, note)

def wallet_consume_credit(user_id: int, reason: str = "consume", note: str | None = None) -> bool:
    """
    Descuenta 1 crédito de forma ATÓMICA (no baja de 0).
    Devuelve True si logró descontar, False si no tenía saldo.
    """
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE wallet
            SET credits = credits - 1
            WHERE user_id = ? AND credits > 0
        """, (user_id,))
        conn.commit()
        ok = (c.rowcount == 1)
    if ok:
        _wallet_log(user_id, -1, reason, note)
    return ok

def wallet_get_history(user_id: int, limit: int = 100):
    """Devuelve los últimos movimientos del ledger para el usuario."""
    with get_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, delta, reason, note, created_at
            FROM credit_ledger
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (user_id, limit))
        rows = c.fetchall()
        return [dict(r) for r in rows]
