import sqlite3
from flask import session
from flask import Flask, request, render_template, redirect, url_for, jsonify, flash
from controllers.mezcla_controller import index, mezclar, exportar
import os

app = Flask(__name__)
app.secret_key = 'me_lapeasCalabaza'
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Simular index route
@app.route('/')
def index():
    return render_template('index.html')



#login y registro
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
            session['usuario'] = usuario
            return redirect(url_for('dashboard'))  # <- usa tu función ya existente
        else:
            flash('Credenciales incorrectas')
    return render_template('login.html')



# Página principal: Dashboard
@app.route('/dashboard')
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    mezclas = [
        {'nombre': 'Mix 01', 'fecha': '28/06/2025'},
        {'nombre': 'Mix 02', 'fecha': '26/06/2025'}
    ]
    return render_template('dashboard.html', mezclas=mezclas)


# Mezclador (antes era la página principal)
@app.route('/mezclador')
def mostrar_mezclador():
    return index(app.config['UPLOAD_FOLDER'])

# Generar mezcla por IA
@app.route('/mezclar', methods=['POST'], endpoint='mezclar')
def generar_mezcla():
    return mezclar(app.config['UPLOAD_FOLDER'])

# Página de exportación
@app.route('/exportar', endpoint='exportar')
def mostrar_exportar():
    return exportar()

# Simular logout
@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))


# Página en construcción para "Mis pistas"
@app.route('/pistas')
def pistas():
    return "<h1 style='color:white;background:#111;padding:20px;'>🎵 Página de pistas en construcción</h1>"

if __name__ == '__main__':
    app.run(debug=True)
