from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import shutil

app = Flask(__name__)

# Carpeta donde están los archivos de audio
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Función para obtener la última pista agregada
def obtener_ultima_pista():
    archivos = os.listdir(app.config['UPLOAD_FOLDER'])
    mp3s = [f for f in archivos if f.endswith('.mp3') and f != 'mix_ia_final.mp3']
    if not mp3s:
        return 'audio_demo.mp3'
    mp3s.sort(key=lambda f: os.path.getmtime(os.path.join(app.config['UPLOAD_FOLDER'], f)), reverse=True)
    return mp3s[0]

# Página principal del mezclador
@app.route('/')
def index():
    pista = obtener_ultima_pista()
    return render_template('mezcla.html', audio_file=pista)

# Ruta que simula la aplicación de IA (copia el archivo actual)
@app.route('/mezclar', methods=['POST'])
def mezclar():
    pista_actual = obtener_ultima_pista()
    original_path = os.path.join(app.config['UPLOAD_FOLDER'], pista_actual)
    mezcla_path = os.path.join(app.config['UPLOAD_FOLDER'], 'mix_ia_final.mp3')

    try:
        shutil.copyfile(original_path, mezcla_path)
    except Exception as e:
        return jsonify({'mensaje': f'❌ Error al generar mezcla: {str(e)}'}), 500

    return jsonify({
        'mensaje': '✅ Mezcla generada con éxito usando IA.',
        'nombre': 'mix_ia_final.mp3'
    })

# Ruta para exportar
@app.route('/exportar')
def exportar():
    return render_template('exportar.html')

if __name__ == '__main__':
    app.run(debug=True)
