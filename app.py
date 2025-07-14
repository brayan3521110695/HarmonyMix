from flask import Flask, request, render_template, redirect, url_for, jsonify
from controllers.mezcla_controller import index, mezclar, exportar
import os

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Página principal (mezclador)
@app.route('/', endpoint='index')
def mostrar_index():
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
    return redirect(url_for('index'))

# Dashboard principal (solo si decides usarlo más adelante)
@app.route('/dashboard')
def dashboard():
    mezclas = [
        {'nombre': 'Mix 01', 'fecha': '28/06/2025'},
        {'nombre': 'Mix 02', 'fecha': '26/06/2025'}
    ]
    return render_template('dashboard.html', mezclas=mezclas)

# Página en construcción para "Mis pistas"
@app.route('/pistas')
def pistas():
    return "<h1 style='color:white;background:#111;padding:20px;'>🎵 Página de pistas en construcción</h1>"

if __name__ == '__main__':
    app.run(debug=True)
