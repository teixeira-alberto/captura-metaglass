# Captura de Lives e Chamadas de Vídeo

Repositório destinado à captura de **lives do Instagram** ou **ligações de vídeo no WhatsApp** utilizando **scripts em Python**.

## Funcionalidades
- Capturar **vídeo completo** (imagem + áudio)  
- Capturar apenas o **áudio**

## Objetivo
O objetivo é oferecer uma forma prática de gravar lives ou chamadas, seja em vídeo (com áudio) ou apenas o áudio.

## Scripts

### 1) `roi_selector.py` - Definir área da captura
Exibe uma janela transparente para posicionar e redimensionar **sobre a área** da tela a ser capturada.

### 2) `roi_preview.py` — Pré-visualização da captura
Mostra, em tempo real, **exatamente a região** que será capturada.

### 3) `yolo_roi_detect.py` — Inferência usando YOLOv8 na ROI (region of interest)
Roda o **YOLOv8** apenas dentro da ROI definida.

### 4) `captura_audio.py` — Gravação apenas do áudio (loopback do sistema)
Captura o áudio do sistema via **WASAPI loopback** e salva em **M4A (AAC)**; se o FFmpeg não estiver disponível, mantém **WAV (PCM16)**. Configurações principais no topo: `OUTPUT_DIR`, `AUDIO_SAMPLERATE`, `AUDIO_BITRATE`.

### 5) `captura_video.py` — Gravação (vídeo + áudio do sistema)
Captura a ROI em **CFR** (FPS constante), grava o **áudio de loopback** do Windows e, ao finalizar, **sincroniza** A/V via FFmpeg (corrige offset/drift) gerando **MP4** com AAC. Configurações principais no topo: `OUTPUT_DIR`, `MONITOR_REGION`, `FPS`, `QUALITY_MODE` (`high|insane|lossless`) e `NVENC_MODE` (`auto|on|off`).

---

**Importante:** antes de executar os scripts, consultar o `requirements.txt` e instalar todas as dependências. O FFmpeg deve estar instalado no sistema e acessível pelo `PATH`.

**Observações:**
- Funciona com múltiplos monitores: a ROI pode ser definida em qualquer tela e será respeitada na captura.
- Compatibilidade: os scripts foram **testados no Windows**. Em **Linux/macOS** podem ser necessários ajustes.
- Pronto para adaptação: partindo destes arquivos, é possível criar pipelines que subam áudio para modelos (Ex: ASR), vídeo para modelos de visão computacional e façam integrações com APIs.
