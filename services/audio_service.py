# services/audio_service.py
import os
import subprocess
import requests
from dotenv import load_dotenv

# Opcionales para el modo "smart"
import librosa
import numpy as np

load_dotenv()

AUDIOSTACK_API_KEY = (os.getenv("AUDIOSTACK_API_KEY") or "").strip().strip("'\"")
AUDIOSTACK_ENDPOINT = (os.getenv("AUDIOSTACK_ENDPOINT") or "").strip().strip("'\"")
MIX_NAME = "mix_ia_final.mp3"


# -------------------- Utilidades FFmpeg --------------------
def _ffmpeg_exists():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False

def _ffmpeg_has_filter(name: str) -> bool:
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        return name in out.stdout
    except Exception:
        return False

def _endpoint_valido(url: str) -> bool:
    if not url:
        return False
    u = url.lower()
    return u.startswith("http") and "tu-endpoint" not in u and not u.startswith("<")


# -------------------- Mezcla local simple (amix) --------------------
def mix_tracks_local(file_names, uploads_dir):
    """
    Mezcla N archivos usando FFmpeg (amix) y devuelve mix_ia_final.mp3
    """
    if not file_names or len(file_names) < 2:
        raise ValueError("Selecciona al menos dos pistas para mezclar.")

    if not _ffmpeg_exists():
        raise RuntimeError("FFmpeg no está instalado o no está en el PATH.")

    input_args = []
    for name in file_names:
        path = os.path.join(uploads_dir, name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"No se encontró {name}")
        input_args += ["-i", path]

    n = len(file_names)
    out_path = os.path.join(uploads_dir, MIX_NAME)

    # amix + normalización dinámica suave
    cmd = [
        "ffmpeg", *input_args, "-y",
        "-filter_complex", f"amix=inputs={n}:weights=1|1:duration=longest, dynaudnorm=f=75:g=15, alimiter=limit=0.95",
        "-c:a", "libmp3lame", "-q:a", "2",
        out_path
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg falló:\n{proc.stderr}")

    return MIX_NAME


# -------------------- Audiostack (fallback a local) --------------------
def enviar_a_audiostack(file_paths, uploads_dir):
    """
    Envía N pistas a Audiostack si hay configuración válida; si no, mezcla local con FFmpeg.
    file_paths: rutas absolutas a archivos en uploads_dir
    """
    # Fallback local si falta config o endpoint "placeholder"
    if not AUDIOSTACK_API_KEY or not _endpoint_valido(AUDIOSTACK_ENDPOINT):
        file_names = [os.path.basename(p) for p in file_paths]
        return mix_tracks_local(file_names, uploads_dir)

    headers = {"Authorization": f"Bearer {AUDIOSTACK_API_KEY}"}

    files = []
    try:
        for p in file_paths:
            f = open(p, "rb")
            files.append(("files", (os.path.basename(p), f, "audio/mpeg")))
        data = {"mode": "mixing", "output_format": "mp3"}
        resp = requests.post(AUDIOSTACK_ENDPOINT, headers=headers, files=files, data=data, timeout=120)
    finally:
        for _, (name, fobj, _) in files:
            try:
                fobj.close()
            except Exception:
                pass

    if resp.status_code == 200:
        out_path = os.path.join(uploads_dir, MIX_NAME)
        with open(out_path, "wb") as out_file:
            out_file.write(resp.content)
        return MIX_NAME
    else:
        # Si falla, vuelve a la mezcla local
        file_names = [os.path.basename(p) for p in file_paths]
        try:
            return mix_tracks_local(file_names, uploads_dir)
        except Exception:
            raise Exception(f"Error en Audiostack: {resp.status_code} - {resp.text}")


# -------------------- Smart DJ Mix (2 pistas) --------------------
KEYS = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

def _estimate_bpm(path):
    y, sr = librosa.load(path, mono=True, duration=120)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    return float(tempo) if tempo > 0 else 120.0

def _estimate_key(path):
    y, sr = librosa.load(path, mono=True, duration=90)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)
    key_idx = int(np.argmax(chroma_mean))
    return KEYS[key_idx]

def _semitone_diff(k_from, k_to):
    i_from = KEYS.index(k_from)
    i_to   = KEYS.index(k_to)
    diff = i_to - i_from
    if diff > 6:  diff -= 12
    if diff < -6: diff += 12
    return diff

def _rubberband_or_fallback_filter(tempo_ratio: float, semitones: int, use_rubberband: bool) -> str:
    if use_rubberband:
        return f"rubberband=tempo={tempo_ratio:.5f}:pitch={semitones}"
    # Fallback: asetrate (para pitch) + aresample + atempo (0.5–2.0)
    tempo_ratio = max(0.5, min(2.0, tempo_ratio))
    pitch_fac = 2 ** (semitones / 12.0)
    new_rate = int(round(44100 * pitch_fac))
    return f"asetrate={new_rate},aresample=44100,atempo={tempo_ratio:.5f}"



def smart_dj_mix(file_names, uploads_dir):
    """
    Mezcla inteligente para 2 pistas:
      - Detecta BPM y Key con librosa
      - Ajusta tempo/pitch (rubberband si está disponible; fallback si no)
      - Normaliza loudness
      - Hace crossfade por beats
    Devuelve MIX_NAME (por defecto: mix_ia_final.mp3)
    """
    if len(file_names) != 2:
        # Por ahora el modo smart es para 2 pistas; más de 2 -> mezcla simple
        return mix_tracks_local(file_names, uploads_dir)

    a_in = os.path.join(uploads_dir, file_names[0])
    b_in = os.path.join(uploads_dir, file_names[1])

    if not _ffmpeg_exists():
        raise RuntimeError("FFmpeg no está instalado o no está en el PATH.")

    # --- Análisis (BPM y Key) ---
    bpm_a = _estimate_bpm(a_in)
    bpm_b = _estimate_bpm(b_in)
    key_a = _estimate_key(a_in)
    key_b = _estimate_key(b_in)

    # Objetivo: BPM promedio (limitado a 70–180)
    target_bpm = max(70, min(180, round((bpm_a + bpm_b) / 2)))
    tempo_a = target_bpm / bpm_a if bpm_a > 0 else 1.0
    tempo_b = target_bpm / bpm_b if bpm_b > 0 else 1.0

    # Ajuste de tono: llevamos B hacia A
    semi_a = 0
    semi_b = _semitone_diff(key_b, key_a)

    # Crossfade de 8 beats (clamp 4–16s) y una intro de A antes del cruce
    beat_sec = 60.0 / target_bpm
    xfade = max(4.0, min(16.0, 8 * beat_sec))
    intro_a = max(xfade + 2.0, 30.0)

    # ¿Tenemos rubberband?
    prefer_rb = _ffmpeg_has_filter("rubberband")

    # --- 1ª pasada: procesar cada pista a WAV temporal ---
    a_proc = os.path.join(uploads_dir, "_a_proc.wav")
    b_proc = os.path.join(uploads_dir, "_b_proc.wav")

    def _fa(tempo, semi, use_rb):
        base = _rubberband_or_fallback_filter(tempo, semi, use_rb)
        return f"{base},loudnorm=I=-14:TP=-1.5:LRA=11"

    # Procesar A
    fa = _fa(tempo_a, semi_a, prefer_rb)
    cmd_a = ["ffmpeg", "-y", "-i", a_in, "-filter:a", fa, "-ac", "2", "-ar", "44100", a_proc]
    pa = subprocess.run(cmd_a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if pa.returncode != 0 and prefer_rb:
        # Reintento sin rubberband (fallback)
        fa = _fa(tempo_a, semi_a, False)
        cmd_a = ["ffmpeg", "-y", "-i", a_in, "-filter:a", fa, "-ac", "2", "-ar", "44100", a_proc]
        pa = subprocess.run(cmd_a, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if pa.returncode != 0:
        raise RuntimeError(f"FFmpeg pre-procesado A falló.\nCMD: {' '.join(cmd_a)}\nERR:\n{pa.stderr}")

    # Procesar B
    fb = _fa(tempo_b, semi_b, prefer_rb)
    cmd_b = ["ffmpeg", "-y", "-i", b_in, "-filter:a", fb, "-ac", "2", "-ar", "44100", b_proc]
    pb = subprocess.run(cmd_b, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if pb.returncode != 0 and prefer_rb:
        fb = _fa(tempo_b, semi_b, False)
        cmd_b = ["ffmpeg", "-y", "-i", b_in, "-filter:a", fb, "-ac", "2", "-ar", "44100", b_proc]
        pb = subprocess.run(cmd_b, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if pb.returncode != 0:
        raise RuntimeError(f"FFmpeg pre-procesado B falló.\nCMD: {' '.join(cmd_b)}\nERR:\n{pb.stderr}")

    # --- 2ª pasada: crossfade y export ---
    out_path = os.path.join(uploads_dir, MIX_NAME)
    filter_complex = (
        f"[0:a]atrim=0:{intro_a:.3f},afade=t=out:st={intro_a - xfade:.3f}:d={xfade:.3f}[A];"
        f"[1:a]afade=t=in:st=0:d={xfade:.3f}[B];"
        f"[A][B]acrossfade=d={xfade:.3f}:curve1=tri:curve2=tri,alimiter=limit=0.95"
    )

    cmd_mix = [
        "ffmpeg", "-y",
        "-i", a_proc, "-i", b_proc,
        "-filter_complex", filter_complex,
        "-c:a", "libmp3lame", "-q:a", "2",
        out_path
    ]
    pm = subprocess.run(cmd_mix, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Limpieza de temporales
    try:
        if os.path.exists(a_proc):
            os.remove(a_proc)
        if os.path.exists(b_proc):
            os.remove(b_proc)
    except Exception:
        pass

    if pm.returncode != 0:
        raise RuntimeError(f"FFmpeg smart mix falló.\nCMD: {' '.join(cmd_mix)}\nERR:\n{pm.stderr}")

    return MIX_NAME

