@echo off
REM Jarvis - lokaler XTTS-v2 TTS-Server starten (isoliertes venv tts-venv).
REM Erster Start laedt das XTTS-v2 Modell herunter (~1.8 GB) und dann beim Start auf die GPU.
REM CPU erzwingen:        set TTS_DEVICE=cpu
REM Anderer Port:         set TTS_PORT=7862
echo Starte TTS-Server ... (erster Start laedt das XTTS-v2 Modell, dauert etwas)
"%~dp0tts-venv\Scripts\python.exe" "%~dp0tts-server.py"
pause
