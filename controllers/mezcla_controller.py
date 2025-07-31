from flask import render_template, jsonify
import os
from services.audio_service import obtener_ultima_pista, enviar_a_audiostack

def index(upload_folder):
    pista = obtener_ultima_pista(upload_folder)
    return render_template('mezcla.html', audio_file=pista)

def mezclar(upload_folder):
    pista_actual = obtener_ultima_pista(upload_folder)
    original_path = os.path.join(upload_folder, pista_actual)

    try:
        mezcla_generada = enviar_a_audiostack(original_path)
    except Exception as e:
        return jsonify({'mensaje': f'❌ Error al usar Audiostack: {str(e)}'}), 500

    return jsonify({
        'mensaje': '✅ Mezcla generada con Audiostack.',
        'nombre': mezcla_generada
    })

def exportar():
    return render_template('exportar.html')
