# Captura de Lives e Chamadas de Vídeo

Repositório destinado à captura de **lives do Instagram** ou **ligações de vídeo no WhatsApp** utilizando **scripts em Python**.

## Funcionalidades
- Capturar **vídeo completo** (imagem + áudio)  
- Capturar apenas o **áudio**

## Objetivo
O objetivo é oferecer uma forma prática de gravar lives ou chamadas, seja em vídeo (com áudio) ou apenas o áudio.

## Scripts

### 1) `window_region_setup.py` - Definir área da captura
Exibe uma janela transparente para posicionar e redimensionar **sobre a área** da tela a ser capturada.

### 2) `test_capture.py` — Pré-visualização da captura
Mostra, em tempo real, **exatamente a região** que será capturada.

### 3) `detect_live+yolo.py` — Inferência usando YOLOv8 na ROI (region of interest)
Roda o **YOLOv8** apenas dentro da ROI definida.

### 4) `captura-video.py` — Gravação (vídeo + áudio do sistema)
Captura a ROI em **CFR** (FPS constante), grava o **áudio de loopback** do Windows e, ao finalizar, **sincroniza** A/V via FFmpeg (corrige offset/drift) gerando **MP4** com AAC. Configurações principais no topo: `OUTPUT_DIR`, `MONITOR_REGION`, `FPS`, `QUALITY_MODE` (`high|insane|lossless`) e `NVENC_MODE` (`auto|on|off`).
