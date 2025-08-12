import sqlite3
from flask import session
from flask import Flask, request, render_template, redirect, url_for, jsonify, flash
from controllers.mezcla_controller import index as mezclador_index, mezclar, exportar
import os

# === Costos (créditos) ===
from db import init_cost_tables, wallet_get_credits, wallet_add_credits, wallet_consume_credit, wallet_get_history

app = Flask(__name__)
app.secret_key = 'me_lapeasCalabaza'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Inicializar tabla wallet al arrancar (Flask 3.x)
try:
    init_cost_tables()
except Exception:
    pass

# Helper: obtener id de usuario desde la sesión (usa id directo si existe)
def _user_id_from_session():
    uid = session.get('user_id')
    if uid:
        return uid

    usuario = session.get('usuario')
    if not usuario:
        return None
    conn = sqlite3.connect('harmony.db')
    cur = conn.cursor()
    cur.execute("SELECT id FROM usuarios WHERE usuario=?", (usuario,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']

        conn = sqlite3.connect('harmony.db')
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO usuarios (usuario, password) VALUES (?, ?)", (usuario, password))
            conn.commit()
            flash('Usuario registrado con éxito')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Ese nombre de usuario ya existe')
        finally:
            conn.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']

        conn = sqlite3.connect('harmony.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE usuario=? AND password=?", (usuario, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            # Guarda también el id del usuario en sesión
            session['usuario'] = usuario
            session['user_id'] = int(user[0])  # id es la 1a columna del SELECT (*)

            # Si venías de una página protegida, redirige ahí
            next_url = session.pop('next_url', None)
            if next_url:
                return redirect(next_url)

            return redirect(url_for('dashboard'))
        else:
            flash('Credenciales incorrectas')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    mezclas = [
        {'nombre': 'Mix 01', 'fecha': '28/06/2025'},
        {'nombre': 'Mix 02', 'fecha': '26/06/2025'}
    ]
    return render_template('dashboard.html', mezclas=mezclas)

@app.route('/mezclador')
def mostrar_mezclador():
    return mezclador_index(app.config['UPLOAD_FOLDER'])

@app.route('/mezclar', methods=['POST'], endpoint='mezclar')
def generar_mezcla():
    # Debe haber sesión
    if 'usuario' not in session:
        return redirect(url_for('login'))

    # Obtener ID del usuario
    user_id = session.get('user_id') or _user_id_from_session()
    if not user_id:
        flash('Vuelve a iniciar sesión.')
        return redirect(url_for('login'))

    # Consumir 1 crédito antes de mezclar
    if not wallet_consume_credit(user_id):
        flash('No tienes créditos. Compra un pack en Precios.')
        return redirect(url_for('precios'))

    # Si quieres, si la mezcla falla podrías devolver el crédito aquí.
    return mezclar(app.config['UPLOAD_FOLDER'])

@app.route('/exportar', endpoint='exportar')
def mostrar_exportar():
    return exportar()

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/pistas')
def pistas():
    return "<h1 style='color:white;background:#111;padding:20px;'>🎵 Página de pistas en construcción</h1>"

# === Rutas de precios / créditos (demo) ===
@app.route('/precios')
def precios():
    print(">>> HIT /precios, session =", dict(session))  # Log de diagnóstico

    # Si no hay sesión, recuerda a dónde querías ir y manda a login
    if 'usuario' not in session:
        session['next_url'] = request.path
        return redirect(url_for('login'))

    # Usa primero el id directo guardado en sesión; si no, búscalo por nombre
    user_id = session.get('user_id') or _user_id_from_session()

    if not user_id:
        flash('No pude identificar tu usuario. Vuelve a iniciar sesión.')
        session['next_url'] = request.path
        return redirect(url_for('login'))

    credits = wallet_get_credits(user_id)
    return render_template('precios.html', credits=credits)
@app.route('/precios/historial')
def precios_historial():
    if 'usuario' not in session:
        session['next_url'] = request.path
        return redirect(url_for('login'))
    user_id = _user_id_from_session()
    if not user_id:
        session['next_url'] = request.path
        return redirect(url_for('login'))
    events = wallet_get_history(user_id, limit=100)
    return render_template('historial_creditos.html', events=events)

@app.post('/comprar-demo')
def comprar_demo():
    if 'usuario' not in session:
        session['next_url'] = request.path
        return redirect(url_for('login'))
    user_id = _user_id_from_session()
    if not user_id:
        session['next_url'] = url_for('precios')
        return redirect(url_for('login'))

    # Registra como COMPRA real
    wallet_add_credits(user_id, 5, reason='purchase', note='Compra de créditos (Pack 5)')

    flash('Se agregaron 5 créditos.')
    return redirect(url_for('precios'))
@app.context_processor
def inject_credits_badge():
    uid = session.get('user_id')
    try:
        count = wallet_get_credits(uid) if uid else None
    except Exception:
        count = None
    return {"credits_badge": count}

# Diagnóstico de sesión local (temporal)
@app.route('/_debug_session')
def _debug_session():
    return jsonify(dict(session))

if __name__ == '__main__':
    app.run(debug=True)
