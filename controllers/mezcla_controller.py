# controllers/mezcla_controller.py
import os
from flask import Blueprint, request, jsonify, current_app, render_template, send_file

from werkzeug.utils import secure_filename
from services.audio_service import enviar_a_audiostack, smart_dj_mix, mix_tracks_local

mezcla_bp = Blueprint('mezcla', __name__)

# Extensiones válidas (las mismas que aceptas al subir)
ALLOWED_EXTS = {'.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg'}

# >>> NOMBRE QUE ESPERA app.py <<<
MIX_NAME = 'mix_ia_final.mp3'


def _uploads_dir():
    uploads = os.path.join(current_app.static_folder, 'uploads')
    os.makedirs(uploads, exist_ok=True)
    return uploads


def _ensure_final_name(uploads_dir: str, produced_name_or_path: str) -> str:
    """
    Asegura que el archivo final exista como uploads/MIX_NAME.
    Si el servicio devolvió otro nombre o una ruta absoluta, lo movemos/renombramos.
    Devuelve siempre MIX_NAME.
    """
    final_path = os.path.join(uploads_dir, MIX_NAME)

    # ¿Ya existe con el nombre correcto? perfecto.
    if os.path.exists(final_path):
        return MIX_NAME

    # Resolver la ruta del producido
    candidate = produced_name_or_path or ""
    # Si vino solo el nombre, asumir que está en uploads_dir
    if not os.path.isabs(candidate):
        candidate = os.path.join(uploads_dir, os.path.basename(candidate))

    # Si existe, lo movemos/renombramos a MIX_NAME
    if os.path.exists(candidate):
        # Crear/limpiar destino
        if os.path.abspath(candidate) != os.path.abspath(final_path):
            # Reemplaza si existiera algo anterior
            try:
                os.replace(candidate, final_path)
            except Exception:
                # Si falla replace (p.ej. distinto disco), hacemos copy+remove
                import shutil
                shutil.copyfile(candidate, final_path)
                try:
                    os.remove(candidate)
                except Exception:
                    pass
        return MIX_NAME

    # Como último intento, quizá el servicio ya grabó exactamente MIX_NAME pero no lo vimos arriba
    if os.path.exists(final_path):
        return MIX_NAME

    # No se encontró ningún archivo válido
    raise FileNotFoundError("No se encontró la mezcla generada para normalizarla como MIX_NAME.")


@mezcla_bp.route('/mezcla', methods=['GET'])
def vista_mezcla():
    uploads_dir = _uploads_dir()

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
    mode = (data.get('mode') or '').lower()  # 'smart' | 'simple' | ''

    if not files or len(files) < 2:
        return jsonify({"ok": False, "mensaje": "Selecciona al menos dos pistas."}), 400

    uploads_dir = _uploads_dir()

    # Seguridad: quedarnos solo con el nombre base (evitar '../')
    safe_names = [os.path.basename(name) for name in files]

    # Verificar existencia
    file_paths = [os.path.join(uploads_dir, name) for name in safe_names]
    not_found = [p for p in file_paths if not os.path.exists(p)]
    if not_found:
        return jsonify({"ok": False, "mensaje": f"Archivo no encontrado: {os.path.basename(not_found[0])}"}), 404

    try:
        # --- Generar mezcla (puede devolver nombre o ruta distinta) ---
        if mode == 'smart' and len(safe_names) == 2:
            produced = smart_dj_mix(safe_names, uploads_dir)
        else:
            produced = enviar_a_audiostack(file_paths, uploads_dir)

        # --- Normalizar al nombre que espera app.py ---
        final_name = _ensure_final_name(uploads_dir, produced)

        return jsonify({"ok": True, "archivo": final_name, "mensaje": "Mezcla generada correctamente."})
    except Exception as e:
        return jsonify({"ok": False, "mensaje": f"Error: {e}"}), 500


@mezcla_bp.route('/mezcla/upload', methods=['POST'])
def upload_tracks():
    uploads_dir = _uploads_dir()

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


# =========================
# Capa de compat sin romper nada
# (solo añade funciones que app.py espera)
# =========================
def index():
    # Reutiliza tu vista principal existente
    return vista_mezcla()

def exportar_route():
    uploads_dir = _uploads_dir()
    mix_path = os.path.join(uploads_dir, MIX_NAME)
    if not os.path.exists(mix_path):
        return jsonify({"ok": False, "mensaje": "Aún no existe una mezcla para exportar."}), 404
    return send_file(mix_path, as_attachment=True, download_name=MIX_NAME)

def exportar():
    # Reutiliza la lógica de exportar
    return exportar_route()
