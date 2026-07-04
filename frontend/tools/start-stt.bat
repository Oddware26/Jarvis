@echo off
REM Jarvis - lokaler Spracherkennungs-Server (faster-whisper) starten, Port 7865.
REM Optionale Abhaengigkeit:   pip install faster-whisper
REM Fuer webm/ogg zusaetzlich ffmpeg im PATH (WAV geht auch ohne).
REM Erster /transcribe laedt das Whisper-Modell automatisch herunter (~140 MB bei "base").
REM CPU erzwingen:        set STT_DEVICE=cpu   (bzw. config.json -> whisper.device)
REM Anderer Port:         set STT_PORT=7865
echo Starte STT-Server ... (erster /transcribe laedt das Whisper-Modell herunter)
python "%~dp0stt-server.py"
pause
