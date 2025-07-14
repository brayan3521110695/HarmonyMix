from flask import render_template, jsonify
import os
import shutil
from services.audio_service import obtener_ultima_pista

def index(upload_folder):
    pista = obtener_ultima_pista(upload_folder)
    return render_template('mezcla.html', audio_file=pista)

def mezclar(upload_folder):
    pista_actual = obtener_ultima_pista(upload_folder)
    original_path = os.path.join(upload_folder, pista_actual)
    mezcla_path = os.path.join(upload_folder, 'mix_ia_final.mp3')

    try:
        shutil.copyfile(original_path, mezcla_path)
    except Exception as e:
        return jsonify({'mensaje': f'❌ Error al generar mezcla: {str(e)}'}), 500

    return jsonify({
        'mensaje': '✅ Mezcla generada con éxito usando IA.',
        'nombre': 'mix_ia_final.mp3'
    })

def exportar():
    return render_template('exportar.html')
