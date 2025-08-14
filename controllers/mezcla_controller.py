import os
from datetime import datetime
from flask import (
    Blueprint,
    request,
    jsonify,
    current_app,
    render_template,
    send_file,
    session,
    redirect,
    url_for,
    flash
)
from bson import ObjectId
from pymongo import MongoClient
from werkzeug.utils import secure_filename

try:
    from services.audio_service import enviar_a_audiostack, smart_dj_mix
    from services.file_utils import sha256_fileobj, save_unique
    from services.feature_service import extract_features, calc_duration_seconds
    SERVICES_AVAILABLE = True
except ImportError:
    SERVICES_AVAILABLE = False
    def smart_dj_mix(names, out_dir):
        raise NotImplementedError("El servicio 'smart_dj_mix' no está disponible.")
    def enviar_a_audiostack(paths, out_dir):
        raise NotImplementedError("El servicio 'enviar_a_audiostack' no está disponible.")

# --- Configuración del Blueprint ---
mezcla_bp = Blueprint('mezcla', __name__)

ALLOWED_EXTS = {'.mp3', '.wav', '.m4a', '.flac', '.aac', '.ogg'}
MIX_NAME = 'mix_ia_final.mp3'

# --- Funciones Auxiliares ---
def _uploads_dir():
    uploads = os.path.join(current_app.static_folder, 'uploads')
    os.makedirs(uploads, exist_ok=True)
    return uploads

def _get_db_connection():
    """Centraliza la conexión a la base de datos usando las variables de entorno."""
    MONGO_URL = os.getenv("MONGO_URL") 
    MONGO_DB_NAME = os.getenv("MONGO_DB") 
    if not MONGO_URL or not MONGO_DB_NAME:
        raise ValueError("Variables de entorno MONGO_URL o MONGO_DB no encontradas.")
    client = MongoClient(MONGO_URL)
    return client[MONGO_DB_NAME]

def _ensure_final_name(uploads_dir: str, produced_name_or_path: str) -> str:
    """Asegura que el archivo de mezcla final se llame MIX_NAME."""
    final_path = os.path.join(uploads_dir, MIX_NAME)
    if os.path.exists(final_path):
        return MIX_NAME
    candidate = produced_name_or_path or ""
    if not os.path.isabs(candidate):
        candidate = os.path.join(uploads_dir, os.path.basename(candidate))
    if os.path.exists(candidate):
        os.replace(candidate, final_path)
        return MIX_NAME
    raise FileNotFoundError(f"No se encontró la mezcla generada '{produced_name_or_path}' para normalizarla.")


# --- Rutas del Blueprint ---

@mezcla_bp.route('/mezcla', methods=['GET'])
def vista_mezcla():
    """Muestra el mezclador con las pistas del usuario que ha iniciado sesión."""
    if "user_id" not in session:
        flash("Por favor, inicia sesión para usar el mezclador.", "info")
        return redirect(url_for("login"))

    user_id_obj = ObjectId(session["user_id"])
    # 1. Conectarse a la base de datos(Atlas).
    db = _get_db_connection()
    # 2. Buscar en la colección 'tracks' solo los documentos del usuario actual.
    user_tracks = list(db.tracks.find({"user_id": user_id_obj}).sort("created_at", -1))

    uploads_dir = _uploads_dir()
    audio_file = MIX_NAME if os.path.exists(os.path.join(uploads_dir, MIX_NAME)) else None
    return render_template('mezcla.html', pistas_usuario=user_tracks, audio_file=audio_file)


@mezcla_bp.route('/mezclar', methods=['POST'])
def mezclar():
    """Recibe nombres de archivo y llama al servicio de IA para mezclarlos."""
    if "user_id" not in session:
        return jsonify({"ok": False, "mensaje": "Sesión expirada."}), 401
        
    if not SERVICES_AVAILABLE:
        return jsonify({"ok": False, "mensaje": "Los servicios de audio no están disponibles."}), 503

    data = request.get_json(silent=True) or {}
    files = data.get('files', [])
    mode = (data.get('mode') or '').lower()

    if not files or len(files) < 2:
        return jsonify({"ok": False, "mensaje": "Selecciona al menos dos pistas."}), 400

    uploads_dir = _uploads_dir()
    safe_names = [os.path.basename(name) for name in files]
    file_paths = [os.path.join(uploads_dir, name) for name in safe_names]

    if any(not os.path.exists(p) for p in file_paths):
        return jsonify({"ok": False, "mensaje": "Uno de los archivos no fue encontrado."}), 404

    try:
        if mode == 'smart' and len(safe_names) == 2:
            produced = smart_dj_mix(safe_names, uploads_dir)
        else:
            produced = enviar_a_audiostack(file_paths, uploads_dir)
        final_name = _ensure_final_name(uploads_dir, produced)
        return jsonify({"ok": True, "archivo": final_name, "mensaje": "Mezcla generada correctamente."})
    except Exception as e:
        print(f"ERROR al mezclar: {e}")
        return jsonify({"ok": False, "mensaje": f"Error al generar la mezcla: {e}"}), 500

@mezcla_bp.route('/mezcla/upload', methods=['POST'])
def upload_tracks():
    """Sube archivos y los asocia al usuario de la sesión."""
    if 'user_id' not in session:
        return jsonify({"ok": False, "mensaje": "Sesión no válida."}), 401
    
    if not SERVICES_AVAILABLE:
        return jsonify({"ok": False, "mensaje": "Los servicios de análisis de audio no están disponibles."}), 503

    if 'files' not in request.files:
        return jsonify({"ok": False, "mensaje": "No se recibieron archivos."}), 400

    files = request.files.getlist('files')
    if not files:
        return jsonify({"ok": False, "mensaje": "Selecciona al menos un archivo."}), 400
    
    user_id = ObjectId(session['user_id']) 
    uploads_dir = _uploads_dir()
    db = _get_db_connection()
    
    guardados, rechazados, duplicados = [], [], []

    for f in files:
        if not f.filename or os.path.splitext(f.filename)[1].lower() not in ALLOWED_EXTS:
            rechazados.append({"name": f.filename, "reason": "extensión no permitida"})
            continue
        try:
            file_hash = sha256_fileobj(f.stream)
            if db.tracks.find_one({"sha256": file_hash, "userId": user_id}):
                duplicados.append(f.filename)
                continue
            
            stored_name, full_path = save_unique(f, uploads_dir)
            duration = calc_duration_seconds(full_path)
            feats = extract_features(full_path)

            track_doc = {
                "userId": user_id, "originalName": f.filename, "storedName": stored_name,
                "sha256": file_hash, "storage": {"provider": "local", "url": None},
                "durationSec": duration, "uploadedAt": datetime.utcnow()
            }
            ins = db.tracks.insert_one(track_doc)
            db.trackFeatures.insert_one({"trackId": ins.inserted_id, **feats, "createdAt": datetime.utcnow()})
            guardados.append({"originalName": f.filename, "storedName": stored_name, "durationSec": duration, **feats})
        except Exception as e:
            rechazados.append({"name": f.filename, "reason": str(e)})

    return jsonify({"ok": True, "guardados": guardados, "duplicados": duplicados, "rechazados": rechazados})


# =========================
# Capa de compatibilidad para que app.py pueda llamar a estas funciones
# =========================
def index(*args, **kwargs):
    return vista_mezcla()

def exportar(*args, **kwargs):
    uploads_dir = _uploads_dir()
    mix_path = os.path.join(uploads_dir, MIX_NAME)
    if not os.path.exists(mix_path):
        flash("Aún no existe una mezcla para exportar. Genérala primero.", "warning")
        return redirect(url_for('mezcla.vista_mezcla'))
    return send_file(mix_path, as_attachment=True, download_name=f"HarmonyMind_Mix_{datetime.now().strftime('%Y%m%d')}.mp3")
