@echo off
REM Oddvark - Z-Image-Turbo Bild-Server starten (isoliertes venv, nutzt globale CUDA-torch).
REM Standard: sequential Offload (~50s/Bild, laeuft auf 12 GB). Mehr VRAM/Tempo: set ZIMAGE_OFFLOAD=model
REM Modellordner ueberschreiben:                set ZIMAGE_MODEL=D:\...\Z-Image-Turbo
echo Starte Z-Image-Server ... (erster Start laedt das Modell, dauert ~1 Min)
"%~dp0zimage-venv\Scripts\python.exe" "%~dp0zimage-server.py"
pause
