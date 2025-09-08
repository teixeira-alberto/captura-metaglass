import os, time, wave, shutil, subprocess, threading
from pathlib import Path
from typing import Optional

import numpy as np
import cv2
import mss
import soundcard as sc

# ========================= CONFIG =========================
OUTPUT_DIR = r"C:\Users\alber\OneDrive\Documentos\CEIA\Meta Glass\Captura\Output-capturas\videos"

# Região da tela (usar o código window_region_setup.py para definir a região)
MONITOR_REGION = {'left': 469, 'top': 123, 'width': 511, 'height': 889}

FPS = 30 # FPS alvo (ex.: 30 ou 60)
QUALITY_MODE = "insane"  # Qualidade do vídeo: "high" | "insane" | "lossless"

# Áudio
AUDIO_SAMPLERATE = 48000
AUDIO_BITRATE = "320k"  # AAC
NVENC_MODE = "auto"  # NVENC (encoder da NVIDIA): "auto" (detecta), "on" (força), "off" (usa x264)

# Manter arquivos temporários (para debug)
KEEP_TEMP = False 

# ========================= Utils =========================
def to_pcm16(x: np.ndarray) -> np.ndarray:
    """Converte float32 [-1,1] -> int16 PCM (N, C)."""
    x = np.clip(x, -1.0, 1.0)
    return (x * 32767.0).astype(np.int16)

def find_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg não encontrado no PATH.")
    return ffmpeg

def find_ffprobe() -> Optional[str]:
    return shutil.which("ffprobe")

def detect_nvenc() -> bool:
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"],
                             capture_output=True, text=True, check=True).stdout.lower()
        return "h264_nvenc" in out
    except Exception:
        return False

def pick_nvenc() -> bool:
    if NVENC_MODE == "on":  return True
    if NVENC_MODE == "off": return False
    return detect_nvenc()  # auto

def quality_profile(mode: str, use_nvenc: bool):
    """Retorna dict com codec/pix_fmt/opts de vídeo para FFmpeg."""
    if mode == "lossless":
        if use_nvenc:
            # NVENC "lossless-like" (cq 0 depende do driver)
            return dict(codec="h264_nvenc", pix="yuv444p",
                        opts=["-preset","p4","-cq","0","-rc-lookahead","32","-bf","3"])
        else:
            return dict(codec="libx264", pix="yuv444p",
                        opts=["-preset","slow","-crf","0","-profile:v","high444"])
    if mode == "insane":
        if use_nvenc:
            return dict(codec="h264_nvenc", pix="yuv420p",
                        opts=["-preset","p4","-cq","18","-rc-lookahead","32","-bf","3"])
        else:
            return dict(codec="libx264", pix="yuv420p",
                        opts=["-preset","slower","-crf","12","-x264-params",
                              "ref=6:bframes=6:subme=9:me=umh:rc-lookahead=60:aq-mode=2:aq-strength=1.2:deblock=-1,-1:psy-rd=1.00,0.15"])
    # "high" (padrão)
    if use_nvenc:
        return dict(codec="h264_nvenc", pix="yuv420p",
                    opts=["-preset","p4","-cq","20","-rc-lookahead","32","-bf","3"])
    else:
        return dict(codec="libx264", pix="yuv420p", opts=["-preset","slow","-crf","14"])


# ========================= Áudio (loopback) =========================
class AudioRecorder:
    def __init__(self, wav_path: Path, device, samplerate=AUDIO_SAMPLERATE):
        self.wav_path = wav_path
        self.device = device  # sem anotação de tipo para compatibilidade com soundcard
        self.samplerate = samplerate
        self.is_recording = False
        self.thread = None
        self.start_ts = None  # perf_counter do 1º chunk

    def _loop(self):
        try:
            with self.device.recorder(samplerate=self.samplerate, blocksize=1024) as mic, \
                 wave.open(str(self.wav_path), 'wb') as wf:
                first = mic.record(numframes=1024)
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
                    data = mic.record(numframes=1024)
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
    print("Procurando dispositivos de áudio...")
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


# ========================= Vídeo (CFR) =========================
def record_video(region, fps, temp_mp4: Path):
    """Captura CFR com mss + OpenCV; retorna start_ts_video (perf_counter)."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    vw = cv2.VideoWriter(str(temp_mp4), fourcc, fps, (region['width'], region['height']))
    sct = mss.mss()

    start_ts_video = None
    last_idx = -1
    t0 = time.perf_counter()
    frames = 0

    print("\n>>> GRAVANDO (CTRL+C para parar)")
    try:
        while True:
            now = time.perf_counter()
            target_idx = int((now - t0) * fps)
            if target_idx <= last_idx:
                time.sleep(0.001)
                continue
            img = sct.grab(region)
            frame = np.array(img)
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            if start_ts_video is None:
                start_ts_video = time.perf_counter()
            vw.write(frame_bgr)
            frames += 1
            last_idx = target_idx
    except KeyboardInterrupt:
        pass
    finally:
        vw.release()
        cv2.destroyAllWindows()
        dur = max(time.perf_counter() - t0, 1e-6)
        print("Gravação finalizada! ✅")
        print(f"Duração: {dur:.2f}s | FPS efetivo: {frames/dur:.2f}")
    return start_ts_video


# ========================= Mux (FFmpeg) =========================
def mux_ffmpeg(ffmpeg, video_mp4: Path, audio_wav: Path, out_mp4: Path,
               fps: int, audio_rate: int, audio_bitrate: str,
               offset_sec: float, qprof: dict):
    """Junta vídeo+áudio com offset e correção de drift."""
    codec = qprof["codec"]; pix = qprof["pix"]; vopts = qprof["opts"]
    base = [ffmpeg, "-y"]

    if offset_sec > 0:
        base += ["-i", str(video_mp4), "-itsoffset", f"{offset_sec:.6f}", "-i", str(audio_wav)]
        map_v, map_a = "0:v:0", "1:a:0"
    elif offset_sec < 0:
        base += ["-itsoffset", f"{(-offset_sec):.6f}", "-i", str(video_mp4), "-i", str(audio_wav)]
        map_v, map_a = "0:v:0", "1:a:0"
    else:
        base += ["-i", str(video_mp4), "-i", str(audio_wav)]
        map_v, map_a = "0:v:0", "1:a:0"

    cmd = base + [
        "-map", map_v, "-map", map_a,
        "-c:v", codec, *vopts,
        "-pix_fmt", pix,
        "-r", str(fps),
        "-vsync", "1",
        "-c:a", "aac",
        "-b:a", audio_bitrate,
        "-ar", str(audio_rate),
        "-ac", "2",
        "-af", "aresample=async=1:first_pts=0",
        "-shortest",
        "-movflags", "+faststart",
        str(out_mp4)
    ]

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg falhou ({proc.returncode}). Saída:\n{proc.stdout}")

def verify_audio(ffprobe: Optional[str], path: Path):
    if not ffprobe:
        print("Aviso: ffprobe não encontrado; pulando verificação de áudio.")
        return True
    try:
        out = subprocess.run([ffprobe, "-v","error", "-select_streams","a",
                              "-show_entries","stream=index", "-of","csv=p=0", str(path)],
                             capture_output=True, text=True, check=True).stdout
        ok = any(l.strip() for l in out.splitlines())
        return ok
    except Exception as e:
        print(f"Aviso: verificação de áudio falhou: {e}")
        return True


# ========================= Main =========================
def main():
    outdir = Path(OUTPUT_DIR); outdir.mkdir(parents=True, exist_ok=True)
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe()

    loopback = find_loopback_device()
    if not loopback:
        print("ERRO: nenhum dispositivo de loopback encontrado.")
        return

    use_nvenc = pick_nvenc()
    qprof = quality_profile(QUALITY_MODE, use_nvenc)

    ts = time.strftime("%d-%m-%Y_%H-%M")   # ex.: 07-09-2025_17-13
    base = f"video_{ts}"
    tmp_video = outdir / f"temp_{base}.mp4"
    tmp_audio = outdir / f"temp_{base}.wav"
    out_mp4   = outdir / f"{base}.mp4"

    # Inicia áudio
    rec = AudioRecorder(tmp_audio, loopback, samplerate=AUDIO_SAMPLERATE)
    rec.start()

    print(f"Config: Encoder: {'NVENC' if use_nvenc else 'x264'} | Qualidade: {QUALITY_MODE} | FPS: {FPS}")
    print(f"Saída: {out_mp4}")

    # Vídeo (CFR)
    v0 = record_video(MONITOR_REGION, FPS, tmp_video)

    # Para áudio
    rec.stop()
    a0 = rec.start_ts or time.perf_counter()

    # Sanidade
    if not tmp_video.exists() or tmp_video.stat().st_size == 0:
        print(f"ERRO: vídeo temporário vazio: {tmp_video}"); return
    if not tmp_audio.exists() or tmp_audio.stat().st_size == 0:
        print(f"ERRO: áudio temporário vazio: {tmp_audio}"); return

    # Offset e mux
    offset = (v0 or a0) - a0
    print(f"Offset medido (video - audio): {offset:+.4f}s")

    try:
        mux_ffmpeg(ffmpeg, tmp_video, tmp_audio, out_mp4,
                   FPS, AUDIO_SAMPLERATE, AUDIO_BITRATE, offset, qprof)
        verify_audio(ffprobe, out_mp4)
        print("Junção de áudio e vídeo concluída! ✅")
    except Exception as e:
        print(f"\n❌ Erro no FFmpeg:\n{e}\n")
        print(f"Temporários preservados:\n  {tmp_video}\n  {tmp_audio}")
        return
    finally:
        if not KEEP_TEMP:
            for p in (tmp_video, tmp_audio):
                try:
                    if p.exists(): p.unlink()
                except Exception as e:
                    print(f"Aviso: não foi possível remover {p}: {e}")

    print(f"\nVídeo salvo em: {out_mp4}")

if __name__ == "__main__":
    main()