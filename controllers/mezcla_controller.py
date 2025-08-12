# controllers/mezcla_controller.py
import os
from flask import Blueprint, request, jsonify, current_app, render_template
from werkzeug.utils import secure_filename
from services.audio_service import enviar_a_audiostack, smart_dj_mix, mix_tracks_local

mezcla_bp = Blueprint('mezcla', __name__)

# Extensiones válidas (las mismas que aceptas al subir)
ALLOWED_EXTS = {'.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg'}
MIX_NAME = 'mix_ia_final.mp3'


@mezcla_bp.route('/mezcla', methods=['GET'])
def vista_mezcla():
    uploads_dir = os.path.join(current_app.static_folder, 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)

    # Listar TODO lo permitido y excluir el mix final
    files = [
        f for f in os.listdir(uploads_dir)
        if os.path.splitext(f)[1].lower() in ALLOWED_EXTS and f != MIX_NAME
    ]

    # Mostrar reproductor si ya existe la mezcla final
    audio_file = MIX_NAME if os.path.exists(os.path.join(uploads_dir, MIX_NAME)) else None

    return render_template('mezcla.html', files=files, audio_file=audio_file)


@mezcla_bp.route('/mezclar', methods=['POST'])
def mezclar():
    data = request.get_json(silent=True) or {}
    files = data.get('files', [])
    mode  = (data.get('mode') or '').lower()  # 'smart' | 'simple' | ''

    if not files or len(files) < 2:
        return jsonify({"ok": False, "mensaje": "Selecciona al menos dos pistas."}), 400

    # Carpeta absoluta de uploads
    uploads_dir = os.path.join(current_app.static_folder, "uploads")

    # Seguridad: quedarnos solo con el nombre base (evitar '../')
    safe_names = [os.path.basename(name) for name in files]

    # Verificar existencia
    file_paths = [os.path.join(uploads_dir, name) for name in safe_names]
    not_found = [p for p in file_paths if not os.path.exists(p)]
    if not_found:
        return jsonify({"ok": False, "mensaje": f"Archivo no encontrado: {os.path.basename(not_found[0])}"}), 404

    try:
        if mode == 'smart' and len(safe_names) == 2:
            # Mezcla tipo DJ: BPM + key + crossfade
            out_name = smart_dj_mix(safe_names, uploads_dir)
        else:
            # Mezcla normal: Audiostack si está configurado; si no, FFmpeg (fallback interno)
            out_name = enviar_a_audiostack(file_paths, uploads_dir)

        return jsonify({"ok": True, "archivo": out_name, "mensaje": "Mezcla generada correctamente."})
    except Exception as e:
        return jsonify({"ok": False, "mensaje": f"Error: {e}"}), 500


@mezcla_bp.route('/mezcla/upload', methods=['POST'])
def upload_tracks():
    uploads_dir = os.path.join(current_app.static_folder, 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)

    if 'files' not in request.files:
        return jsonify({"ok": False, "mensaje": "No se recibieron archivos."}), 400

    files = request.files.getlist('files')
    if not files:
        return jsonify({"ok": False, "mensaje": "Selecciona al menos un archivo."}), 400

    guardados, rechazados = [], []

    for f in files:
        if not f.filename:
            continue
        ext = os.path.splitext(f.filename)[1].lower()
        if ext not in ALLOWED_EXTS:
            rechazados.append(f.filename)
            continue
        name = secure_filename(f.filename)
        f.save(os.path.join(uploads_dir, name))
        guardados.append(name)

    return jsonify({"ok": True, "guardados": guardados, "rechazados": rechazados})
