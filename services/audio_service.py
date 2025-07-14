import os

def obtener_ultima_pista(upload_folder):
    archivos = os.listdir(upload_folder)
    mp3s = [f for f in archivos if f.endswith('.mp3') and f != 'mix_ia_final.mp3']
    if not mp3s:
        return 'audio_demo.mp3'
    mp3s.sort(key=lambda f: os.path.getmtime(os.path.join(upload_folder, f)), reverse=True)
    return mp3s[0]
