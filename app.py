import os
import sqlite3
import shutil
from datetime import datetime

from flask import Flask, request, render_template, redirect, url_for, jsonify, flash, session

# Mezclador (NO tocamos la lógica de IA)
from controllers.mezcla_controller import (
    mezcla_bp,
    index as mezclador_index,
    mezclar,
    exportar,
    MIX_NAME as MIX_FINAL_NAME,
)

# Wallet real (tu archivo ya existe)
from services.wallet_service import wallet_get_credits, wallet_add_credits
# wallet_get_history puede no existir en tu módulo -> ponemos fallback
try:
    from services.wallet_service import wallet_get_history
except Exception:
    def wallet_get_history(user_id: int, limit: int = 100):
        return []

app = Flask(__name__)
app.secret_key = "me_lapeasCalabaza"

# === Carpeta de uploads ===
app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# === DB (SQLite local) ===
DB_PATH = os.path.join(os.path.dirname(__file__), "harmony.db")

# === Registrar blueprint del mezclador ===
app.register_blueprint(mezcla_bp)

# =============================================================================
#                Mezclas guardadas (para mostrar en el dashboard)
# =============================================================================
def _init_mixes_table():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mixes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            filepath TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.commit()
    con.close()

def _user_id_from_session():
    uid = session.get("user_id")
    if uid:
        return int(uid)
    usuario = session.get("usuario")
    if not usuario:
        return None
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT id FROM usuarios WHERE usuario = ?", (usuario,))
    row = cur.fetchone()
    con.close()
    return int(row[0]) if row else None

def save_mix_for_user(user_id: int, src_path: str) -> str:
    """
    Copia la mezcla final generada por la IA (MIX_FINAL_NAME) a un archivo con timestamp
    y la registra en BD para mostrarla en el dashboard.
    Devuelve la ruta relativa 'static/uploads/archivo.mp3'
    """
    if not os.path.exists(src_path):
        raise FileNotFoundError("No existe mezcla final para guardar.")

    uploads_dir = app.config["UPLOAD_FOLDER"]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    rel_name = f"mix_{ts}.mp3"
    dest_path = os.path.join(uploads_dir, rel_name)

    shutil.copyfile(src_path, dest_path)

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO mixes(user_id, name, filepath) VALUES(?, ?, ?)",
        (user_id, f"Mix {ts}", f"static/uploads/{rel_name}")
    )
    con.commit()
    con.close()

    return f"static/uploads/{rel_name}"

def get_user_mixes(user_id: int, limit: int = 8):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        SELECT name, filepath, datetime(created_at,'localtime')
        FROM mixes
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (user_id, int(limit)))
    rows = cur.fetchall()
    con.close()
    return [{"nombre": r[0], "path": r[1], "fecha": r[2]} for r in rows]

# Inicializa tabla de mixes
try:
    _init_mixes_table()
except Exception:
    pass

# =============================================================================
#                                   Rutas base
# =============================================================================
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        try:
            cur.execute("INSERT INTO usuarios (usuario, password) VALUES (?, ?)", (usuario, password))
            con.commit()
            flash("Usuario registrado con éxito")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Ese nombre de usuario ya existe")
        finally:
            con.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        cur.execute("SELECT * FROM usuarios WHERE usuario=? AND password=?", (usuario, password))
        user = cur.fetchone()
        con.close()
        if user:
            session["usuario"] = usuario
            session["user_id"] = int(user[0])  # id es la 1a columna del SELECT (*)
            return redirect(session.pop("next_url", None) or url_for("dashboard"))
        else:
            flash("Credenciales incorrectas")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "usuario" not in session:
        session["next_url"] = request.path
        return redirect(url_for("login"))
    user_id = _user_id_from_session()
    mezclas = get_user_mixes(user_id, limit=8)
    return render_template("dashboard.html", mezclas=mezclas)

# =================== Puentes al mezclador (compat firmas) =====================
@app.route("/mezclador")
def mostrar_mezclador():
    try:
        return mezclador_index(app.config["UPLOAD_FOLDER"])
    except TypeError:
        return mezclador_index()

@app.route("/mezclar", methods=["POST"], endpoint="mezclar")
def generar_mezcla():
    try:
        return mezclar(app.config["UPLOAD_FOLDER"])
    except TypeError:
        return mezclar()

@app.route("/exportar", endpoint="exportar")
def mostrar_exportar():
    return exportar()

# ======================== Guardar mezcla en el panel ==========================
@app.post("/mezclas/guardar")
def guardar_mezcla():
    if "usuario" not in session:
        session["next_url"] = request.path
        return redirect(url_for("login"))

    user_id = _user_id_from_session()
    if not user_id:
        flash("No pude identificar tu usuario. Inicia sesión de nuevo.")
        return redirect(url_for("login"))

    # Usamos SIEMPRE el nombre oficial definido en el controller (MIX_NAME)
    final_mix_path = os.path.join(app.config["UPLOAD_FOLDER"], MIX_FINAL_NAME)

    try:
        _ = save_mix_for_user(user_id, final_mix_path)
        flash("Mezcla guardada en tu panel 👌", "success")
    except FileNotFoundError:
        flash("Aún no hay una mezcla final para guardar. Genera una primero.", "warning")
    except Exception as e:
        flash(f"No se pudo guardar la mezcla: {e}", "error")

    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.pop("usuario", None)
    session.pop("user_id", None)
    return redirect(url_for("login"))

@app.route("/pistas")
def pistas():
    return "<h1 style='color:white;background:#111;padding:20px;'>🎵 Página de pistas en construcción</h1>"

# ========================= Costos / Precios (usa tu wallet) ===================
@app.route("/precios")
def precios():
    if "usuario" not in session:
        session["next_url"] = request.path
        return redirect(url_for("login"))
    user_id = _user_id_from_session()
    credits = wallet_get_credits(user_id) if user_id else 0
    return render_template("precios.html", credits_badge=credits)

@app.route("/precios/historial")
def precios_historial():
    if "usuario" not in session:
        session["next_url"] = request.path
        return redirect(url_for("login"))
    user_id = _user_id_from_session()
    events = wallet_get_history(user_id, limit=100) if user_id else []
    credits = wallet_get_credits(user_id) if user_id else 0
    return render_template("historial_creditos.html", events=events, credits_badge=credits)

@app.post("/comprar-demo")
def comprar_demo():
    if "usuario" not in session:
        session["next_url"] = request.path
        return redirect(url_for("login"))

    user_id = _user_id_from_session()
    if user_id:
        try:
            # tu wallet_add_credits acepta (user_id, amount) solamente
            wallet_add_credits(user_id, 5)
            flash("Se agregaron +5 créditos demo.", "success")
        except Exception as e:
            flash(f"No se pudieron agregar créditos: {e}", "error")

    return redirect(url_for("precios"))

# Badge global (para que el sidebar muestre créditos)
@app.context_processor
def inject_credits_badge():
    uid = session.get("user_id")
    try:
        count = wallet_get_credits(uid) if uid else None
    except Exception:
        count = None
    return {"credits_badge": count}

# ================================== Main ======================================
if __name__ == "__main__":
    app.run(debug=True)
