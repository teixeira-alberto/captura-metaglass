import os, time, wave, shutil, subprocess, threading
from pathlib import Path
from typing import Optional

import numpy as np
import soundcard as sc

# ========================= CONFIG =========================
OUTPUT_DIR = r"C:\Users\alber\OneDrive\Documentos\CEIA\Meta Glass\Captura\Output-capturas\audios"

AUDIO_SAMPLERATE = 48000
AUDIO_BITRATE = "320k"   # alvo do AAC (m4a) via FFmpeg
KEEP_TEMP = False        # manter WAV temporário para debug

# ========================= Utils =========================
def to_pcm16(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, -1.0, 1.0)
    return (x * 32767.0).astype(np.int16)

def find_ffmpeg() -> Optional[str]:
    ffmpeg = shutil.which("ffmpeg")
    return ffmpeg  

def find_ffprobe() -> Optional[str]:
    return shutil.which("ffprobe")

def verify_audio(ffprobe: Optional[str], path: Path) -> bool:
    if not ffprobe:
        print("Aviso: ffprobe não encontrado; pulando verificação de áudio.")
        return True
    try:
        out = subprocess.run(
            [ffprobe, "-v","error", "-select_streams","a",
             "-show_entries","stream=index", "-of","csv=p=0", str(path)],
            capture_output=True, text=True, check=True
        ).stdout
        ok = any(l.strip() for l in out.splitlines())
        return ok
    except Exception as e:
        print(f"Aviso: verificação de áudio falhou: {e}")
        return True

# ========================= Áudio (loopback) =========================
class AudioRecorder:
    def __init__(self, wav_path: Path, device, samplerate=AUDIO_SAMPLERATE):
        self.wav_path = wav_path
        self.device = device  # objeto soundcard Microphone (loopback)
        self.samplerate = samplerate
        self.is_recording = False
        self.thread = None
        self.start_ts = None  

    def _loop(self):
        try:
            block = 1024
            with self.device.recorder(samplerate=self.samplerate, blocksize=block) as mic, \
                 wave.open(str(self.wav_path), 'wb') as wf:

                first = mic.record(numframes=block)
                if first.ndim == 1:
                    channels = 1
                    first = first[:, None]
                else:
                    channels = first.shape[1]

                wf.setnchannels(channels)
                wf.setsampwidth(2)  # PCM16
                wf.setframerate(self.samplerate)

                wf.writeframes(to_pcm16(first).tobytes())
                if self.start_ts is None:
                    self.start_ts = time.perf_counter()

                while self.is_recording:
                    data = mic.record(numframes=block)
                    if data.ndim == 1:
                        data = data[:, None]
                    wf.writeframes(to_pcm16(data).tobytes())
        except Exception as e:
            print(f"[Áudio] ERRO: {e}")

    def start(self):
        self.is_recording = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_recording = False
        if self.thread:
            self.thread.join()

def find_loopback_device():
    mics = sc.all_microphones(include_loopback=True)
    if not mics:
        return None
    try:
        spk = sc.default_speaker()
        for m in mics:
            if getattr(m, "isloopback", False) and m.name == spk.name:
                print(f"Dispositivo encontrado: '{m.name}'")
                return m
    except Exception:
        pass
    for m in mics:
        if getattr(m, "isloopback", False):
            print(f"Dispositivo encontrado: '{m.name}'")
            return m
    return None

# ========================= Transcodificação (FFmpeg) =========================
def transcode_to_m4a(ffmpeg: Optional[str], wav_path: Path, out_m4a: Path,
                     audio_rate: int, audio_bitrate: str) -> bool:
    """
    Converte WAV PCM16 para M4A (AAC). Retorna True se sucesso.
    Se ffmpeg for None, retorna False (sem transcodificar).
    """
    if not ffmpeg:
        return False

    cmd = [
        ffmpeg, "-y",
        "-i", str(wav_path),
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-ar", str(audio_rate),
        "-ac", "2",
        "-movflags", "+faststart",
        str(out_m4a)
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return proc.returncode == 0

# ========================= Main =========================
def main():
    outdir = Path(OUTPUT_DIR); outdir.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe()

    loopback = find_loopback_device()
    if not loopback:
        print("ERRO: nenhum dispositivo de loopback encontrado.")
        return

    ts = time.strftime("%d-%m-%Y_%H-%M")   # ex.: 07-09-2025_17-13
    base = f"audio_{ts}"
    tmp_wav = outdir / f"temp_{base}.wav"
    out_m4a = outdir / f"{base}.m4a"

    print(f"Config: Sample Rate: {AUDIO_SAMPLERATE} | Bitrate: {AUDIO_BITRATE}")
    print(f"Saída: {out_m4a if ffmpeg else tmp_wav}")

    # Inicia áudio
    rec = AudioRecorder(tmp_wav, loopback, samplerate=AUDIO_SAMPLERATE)
    print("\n>>> GRAVANDO ÁUDIO (CTRL+C para parar) ...")
    rec.start()

    try:
        while True:
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass

    # Finaliza
    rec.stop()
    dur = 0.0
    if rec.start_ts:
        dur = max(time.perf_counter() - rec.start_ts, 0.0)
    print(f"\nGravação finalizada! ✅")
    print(f"Duração: {dur:.2f}s")

    # Sanidade
    if not tmp_wav.exists() or tmp_wav.stat().st_size == 0:
        print(f"ERRO: WAV temporário vazio: {tmp_wav}")
        return

    # Transcodificação (se FFmpeg disponível)
    if ffmpeg:
        ok = transcode_to_m4a(ffmpeg, tmp_wav, out_m4a, AUDIO_SAMPLERATE, AUDIO_BITRATE)
        if not ok:
            print("⚠️  FFmpeg falhou; mantendo WAV.")
            final_path = tmp_wav
        else:
            verify_audio(ffprobe, out_m4a)
            final_path = out_m4a
    else:
        print("⚠️  FFmpeg não encontrado; saída final será WAV (sem compressão).")
        final_path = tmp_wav

    # Limpeza de temporários
    if final_path != tmp_wav and not KEEP_TEMP:
        try:
            if tmp_wav.exists():
                tmp_wav.unlink()
        except Exception as e:
            print(f"Aviso: não foi possível remover {tmp_wav}: {e}")

    print(f"\nÁudio salvo em: {final_path}")

if __name__ == "__main__":
    main()