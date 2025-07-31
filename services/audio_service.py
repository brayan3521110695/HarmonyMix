import os
import requests
from dotenv import load_dotenv

load_dotenv()

AUDIOSTACK_API_KEY = os.getenv('AUDIOSTACK_API_KEY')

def enviar_a_audiostack(ruta_mp3):
    url = ""
    headers = {
        "Authorization": f"Bearer {AUDIOSTACK_API_KEY}"
    }

    with open(ruta_mp3, 'rb') as f:
        files = {"file": f}
        data = {
            "mode": "mixing",
            "output_format": "mp3"
        }

        response = requests.post(url, headers=headers, files=files, data=data)

    if response.status_code == 200:
        salida = os.path.join(os.path.dirname(ruta_mp3), "mix_ia_final.mp3")
        with open(salida, "wb") as out_file:
            out_file.write(response.content)
        return "mix_ia_final.mp3"
    else:
        raise Exception(f"Error en Audiostack: {response.status_code} - {response.text}")
    
def obtener_ultima_pista(upload_folder):
    archivos = os.listdir(upload_folder)
    mp3s = [f for f in archivos if f.endswith('.mp3') and f != 'mix_ia_final.mp3']
    if not mp3s:
        return 'audio_demo.mp3'
    mp3s.sort(key=lambda f: os.path.getmtime(os.path.join(upload_folder, f)), reverse=True)
    return mp3s[0]
