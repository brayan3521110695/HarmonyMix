import io, json, librosa, numpy as np, soundfile as sf

def calc_duration_seconds(path: str) -> float:
    f = sf.SoundFile(path)
    return float(len(f) / f.samplerate)

def extract_features(path: str):
    # 44.1kHz mono para análisis (no altera archivo original)
    y, sr = librosa.load(path, sr=44100, mono=True)
    # BPM
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(tempo)
    # Chroma (para tonalidad aproximada)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    chroma_mean = chroma.mean(axis=1)
    # heurística simple de key (índice máx del chroma)
    pitch_classes = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
    key_idx = int(np.argmax(chroma_mean))
    musical_key = pitch_classes[key_idx]  # mayor aproximado (suficiente para demo)
    # Energía RMS normalizada
    rms = librosa.feature.rms(y=y).mean()
    energy = float(np.clip(rms / (np.max(np.abs(y)) + 1e-9), 0, 1))
    # MFCC medios
    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    mfcc_mean = mfcc.mean(axis=1)

    return {
        "bpm": bpm,
        "musicalKey": musical_key,
        "energy": energy,
        "mfccMean": [float(x) for x in mfcc_mean],
        "chromaMean": [float(x) for x in chroma_mean],
    }
