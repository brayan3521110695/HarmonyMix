import hashlib, os, time
from werkzeug.utils import secure_filename

def sha256_fileobj(fobj):
    pos = fobj.tell()
    fobj.seek(0)
    h = hashlib.sha256()
    for chunk in iter(lambda: fobj.read(8192), b""):
        h.update(chunk)
    fobj.seek(pos)
    return h.hexdigest()

def save_unique(file_storage, uploads_dir: str) -> tuple[str, str]:
    # retorna (stored_name, full_path)
    ts = int(time.time())
    stored = f"{ts}_{secure_filename(file_storage.filename)}"
    full = os.path.join(uploads_dir, stored)
    os.makedirs(uploads_dir, exist_ok=True)
    file_storage.save(full)
    return stored, full
