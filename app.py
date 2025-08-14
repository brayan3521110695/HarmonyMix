import os
import shutil
from datetime import datetime
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.utils import secure_filename
from dotenv import load_dotenv 

# --- Cargar variables de entorno desde el archivo .env ---
load_dotenv() 

from flask import (
    Flask,
    request,
    render_template,
    redirect,
    url_for,
    flash,
    session,
)

from controllers.mezcla_controller import (
    mezcla_bp,
    index as mezclador_index,
    mezclar,
    exportar,
    MIX_NAME as MIX_FINAL_NAME,
)

# --- Configuración de la Aplicación ---
app = Flask(__name__)
app.secret_key = "me_lapeasCalabaza"

# --- Configuración de la Carpeta de Uploads ---
app.config["UPLOAD_FOLDER"] = os.path.join(app.static_folder, "uploads")
app.config["ALLOWED_EXTENSIONS"] = {"mp3", "wav", "ogg"}
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# --- Conexión a MongoDB ---
MONGO_URL = os.getenv("MONGO_URL")
MONGO_DB_NAME = os.getenv("MONGO_DB")

if not MONGO_URL or not MONGO_DB_NAME:
    raise ValueError("No se encontraron las variables de entorno MONGO_URL o MONGO_DB. Asegúrate de que tu archivo .env está configurado correctamente.")

client = MongoClient(MONGO_URL)
db = client[MONGO_DB_NAME]
users_collection = db.users
tracks_collection = db.tracks
mixes_collection = db.mixes

# --- Registro del Blueprint ---
app.register_blueprint(mezcla_bp)



def allowed_file(filename):
    """Verifica si la extensión del archivo es permitida."""
    return "." in filename and \
        filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]

def _user_id_from_session():
    """Obtiene el ObjectId del usuario desde la sesión."""
    user_id_str = session.get("user_id")
    if user_id_str:
        return ObjectId(user_id_str)
    return None

# --- Rutas Principales de la Aplicación ---

@app.route("/")
def index():
    """Página de inicio."""
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Página de registro de nuevos usuarios."""
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        if users_collection.find_one({"usuario": usuario}):
            flash("Ese nombre de usuario ya existe", "warning")
            return redirect(url_for("register"))

        users_collection.insert_one({"usuario": usuario, "password": password})
        flash("Usuario registrado con éxito. Ahora puedes iniciar sesión.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Página de inicio de sesión."""
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        user = users_collection.find_one({"usuario": usuario, "password": password})

        if user:
            session["usuario"] = user["usuario"]
            session["user_id"] = str(user["_id"])
            
            next_url = session.pop("next_url", None)
            return redirect(next_url or url_for("dashboard"))
        else:
            flash("Credenciales incorrectas. Inténtalo de nuevo.", "error")
            return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Cierra la sesión del usuario."""
    session.pop("usuario", None)
    session.pop("user_id", None)
    flash("Has cerrado sesión.", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    """Panel principal del usuario."""
    if "usuario" not in session:
        session["next_url"] = request.path
        flash("Por favor, inicia sesión para ver tu panel.", "info")
        return redirect(url_for("login"))

    user_id = _user_id_from_session()
    if not user_id:
        return redirect(url_for("login"))

    user_mixes = list(mixes_collection.find({"user_id": user_id}).sort("created_at", -1).limit(8))
    
    mezclas_para_template = [
        {
            "nombre": mix.get("name", "Sin Nombre"),
            "path": mix.get("filepath", ""),
            "fecha": mix.get("created_at").strftime("%Y-%m-%d %H:%M") if mix.get("created_at") else "N/A"
        } for mix in user_mixes
    ]

    return render_template("dashboard.html", mezclas=mezclas_para_template, user_id=str(user_id))


# --- Rutas para la Gestión de Pistas (Tracks) ---

@app.route("/pistas")
def pistas():
    """Muestra la lista de pistas del usuario."""
    if "usuario" not in session:
        session["next_url"] = request.path
        return redirect(url_for("login"))

    user_id = _user_id_from_session()
    if not user_id:
        return redirect(url_for("login"))

    user_tracks = list(tracks_collection.find({"user_id": user_id}).sort("created_at", -1))
    
    for track in user_tracks:
        track["id"] = str(track["_id"])

    return render_template("pistas.html", pistas=user_tracks, user_id=str(user_id))


@app.route("/upload", methods=["GET", "POST"])
def upload():
    """Página y lógica para subir nuevas pistas."""
    if "usuario" not in session:
        flash("Debes iniciar sesión para subir pistas.", "info")
        return redirect(url_for("login"))

    if request.method == "POST":
        if 'file' not in request.files:
            flash('No se encontró el archivo.', 'error')
            return redirect(request.url)

        file = request.files['file']
        if file.filename == '':
            flash('No se seleccionó ningún archivo.', 'warning')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            user_id = _user_id_from_session()
            track_data = {
                "user_id": user_id,
                "filename": filename,
                "name": os.path.splitext(filename)[0],
                "url": url_for('static', filename=f'uploads/{filename}'),
                "ext": filename.rsplit(".", 1)[1].lower(),
                "size": f"{os.path.getsize(filepath) / 1024 / 1024:.2f} MB",
                "created_at": datetime.utcnow()
            }
            tracks_collection.insert_one(track_data)

            flash(f'Pista "{filename}" subida con éxito.', 'success')
            return redirect(url_for('pistas'))
        else:
            flash('Tipo de archivo no permitido.', 'error')
            return redirect(request.url)

    return redirect(url_for('pistas'))


@app.route("/pistas/delete/<track_id>", methods=["GET", "POST"])
def delete_track(track_id):
    """Elimina una pista de la base de datos y del sistema de archivos."""
    if "usuario" not in session:
        return redirect(url_for("login"))

    user_id = _user_id_from_session()
    track_to_delete = tracks_collection.find_one({"_id": ObjectId(track_id), "user_id": user_id})

    if track_to_delete:
        try:
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], track_to_delete["filename"])
            if os.path.exists(filepath):
                os.remove(filepath)

            tracks_collection.delete_one({"_id": ObjectId(track_id)})
            flash("Pista eliminada correctamente.", "success")

        except Exception as e:
            flash(f"Error al eliminar la pista: {e}", "error")
    else:
        flash("No se encontró la pista o no tienes permiso para eliminarla.", "error")

    return redirect(url_for("pistas"))


# --- Rutas para el Mezclador y Exportación ---

@app.route("/mezclador", endpoint="mezclador_index")
def mostrar_mezclador():
    """Muestra la interfaz del mezclador."""
    try:
        return mezclador_index(app.config["UPLOAD_FOLDER"])
    except TypeError:
        return mezclador_index()


@app.route("/mezclar", methods=["POST"], endpoint="mezclar")
def generar_mezcla():
    """Genera la mezcla usando la IA."""
    try:
        return mezclar(app.config["UPLOAD_FOLDER"])
    except TypeError:
        return mezclar()


@app.route("/exportar", endpoint="exportar")
def mostrar_exportar():
    """Muestra la página de exportación."""
    return exportar()


@app.post("/mezclas/guardar")
def guardar_mezcla():
    """Guarda la mezcla final en el perfil del usuario."""
    if "usuario" not in session:
        return redirect(url_for("login"))

    user_id = _user_id_from_session()
    if not user_id:
        flash("No pude identificar tu usuario. Inicia sesión de nuevo.", "error")
        return redirect(url_for("login"))

    final_mix_path = os.path.join(app.config["UPLOAD_FOLDER"], MIX_FINAL_NAME)
    if not os.path.exists(final_mix_path):
        flash("Aún no hay una mezcla final para guardar. Genera una primero.", "warning")
        return redirect(url_for("dashboard"))

    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_filename = f"mix_{user_id}_{ts}.mp3"
        dest_path = os.path.join(app.config["UPLOAD_FOLDER"], new_filename)
        shutil.copyfile(final_mix_path, dest_path)

        mix_data = {
            "user_id": user_id,
            "name": f"Mix {ts}",
            "filepath": url_for('static', filename=f'uploads/{new_filename}'),
            "created_at": datetime.utcnow()
        }
        mixes_collection.insert_one(mix_data)
        flash("Mezcla guardada en tu panel.", "success")

    except Exception as e:
        flash(f"No se pudo guardar la mezcla: {e}", "error")

    return redirect(url_for("dashboard"))


# --- Rutas Legado---
@app.route("/precios")
@app.route("/precios/historial")
def _legacy_costos_removed():
    flash("La sección de costos fue removida.", "info")
    return redirect(url_for("dashboard"))


# --- Punto de Entrada de la Aplicación ---
if __name__ == "__main__":
    app.run(debug=True, port=5001)
