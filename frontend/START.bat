@echo off
setlocal EnableExtensions
title Oddvark - ALLES starten
cd /d "%~dp0"

echo(
echo ==================================================
echo    O D D V A R K   -   startet alle Dienste
echo ==================================================
echo(
echo  Dienste:  Ollama 11434 . TTS 7862 . Z-Image 7861 . Suche 7863 . STT 7865 . Aktionen 7864 . Web 8000
echo  Plattformuebergreifend geht auch:  python start.py
echo  Jeder Dienst laeuft in einem EIGENEN Fenster.
echo  Nicht gewuenschtes einfach unten mit REM auskommentieren.
echo(

REM =====================================================================
REM  1) Ollama  (LLM-Backend, http://localhost:11434)
REM =====================================================================
curl -s -o nul --max-time 2 http://127.0.0.1:11434/api/version
if errorlevel 1 (
  echo [1/6] Ollama wird gestartet ...
  start "Oddvark - Ollama" ollama serve
) else (
  echo [1/6] Ollama laeuft bereits.
)

REM =====================================================================
REM  2) TTS / XTTS-v2  (hyperrealistische Stimmen, http://localhost:7862)
REM     Erster Start laedt das Modell (~1.8 GB) - dauert etwas.
REM =====================================================================
curl -s -o nul --max-time 2 http://127.0.0.1:7862/health
if errorlevel 1 (
  if exist "%~dp0tools\tts-venv\Scripts\python.exe" (
    echo [2/6] TTS-Server wird gestartet ... erster Start laedt das Modell
    start "Oddvark - TTS (XTTS)" "%~dp0tools\start-tts.bat"
  ) else (
    echo [2/6] TTS uebersprungen ^(tools\tts-venv fehlt^).
  )
) else (
  echo [2/6] TTS-Server laeuft bereits.
)

REM =====================================================================
REM  3) Z-Image  (Bildgenerierung, http://localhost:7861)
REM =====================================================================
curl -s -o nul --max-time 2 http://127.0.0.1:7861/health
if errorlevel 1 (
  if exist "%~dp0tools\zimage-venv\Scripts\python.exe" (
    echo [3/6] Z-Image-Server wird gestartet ... erster Start laedt das Modell
    start "Oddvark - Z-Image" "%~dp0tools\start-zimage.bat"
  ) else (
    echo [3/6] Z-Image uebersprungen ^(tools\zimage-venv fehlt^).
  )
) else (
  echo [3/6] Z-Image-Server laeuft bereits.
)

REM =====================================================================
REM  4) Websuche  (lokale DuckDuckGo-Suche fuer /web + web_search-Tool, Port 7863)
REM =====================================================================
curl -s -o nul --max-time 2 http://127.0.0.1:7863/health
if errorlevel 1 (
  echo [4/6] Websuche-Server wird gestartet auf http://127.0.0.1:7863 ...
  start "Oddvark - Websuche" cmd /k python "%~dp0tools\search-server.py"
) else (
  echo [4/6] Websuche-Server laeuft bereits.
)

REM =====================================================================
REM  Whisper-STT  (lokale Offline-Spracherkennung, Port 7865; braucht faster-whisper)
REM =====================================================================
curl -s -o nul --max-time 2 http://127.0.0.1:7865/health
if errorlevel 1 (
  echo [STT] Whisper-Server wird gestartet auf http://127.0.0.1:7865 ...
  start "Oddvark - STT" cmd /k python "%~dp0tools\stt-server.py"
) else (
  echo [STT] Whisper-Server laeuft bereits.
)

REM =====================================================================
REM  5) Aktionen  (PC-/Datei-/Browser-/Vision-Zugriff fuer den Chat, Port 7864)
REM     Voller Zugriff mit Bestaetigung bei riskanten Aktionen. Nur 127.0.0.1.
REM =====================================================================
curl -s -o nul --max-time 2 http://127.0.0.1:7864/health
if errorlevel 1 (
  echo [5/6] Aktions-Server wird gestartet auf http://127.0.0.1:7864 ...
  start "Oddvark - Aktionen" cmd /k python "%~dp0tools\action-server.py"
) else (
  echo [5/6] Aktions-Server laeuft bereits.
)

REM =====================================================================
REM  6) Web-Server (Frontend) + Browser  (http://localhost:8000)
REM     Ueber localhost statt file:// merkt sich Chrome die Mikro-Erlaubnis.
REM =====================================================================
curl -s -o nul --max-time 2 http://127.0.0.1:8000/index.html
if errorlevel 1 (
  echo [6/6] Web-Server wird gestartet auf http://localhost:8000 ^(No-Cache^) ...
  start "Oddvark - Web" /d "%~dp0" cmd /k python "%~dp0tools\serve.py"
) else (
  echo [6/6] Web-Server laeuft bereits.
)

REM =====================================================================
REM  Erst auf Bereitschaft warten, DANN Browser oeffnen (sonst laedt die
REM  Seite bevor Ollama antwortet -> "Failed to fetch" / Connection refused).
REM =====================================================================
echo(
echo  Warte auf Ollama (max. ~60s, erster Start dauert) ...
set /a _o=0
:waitollama
curl -s -o nul --max-time 2 http://127.0.0.1:11434/api/version
if not errorlevel 1 goto ollama_ok
set /a _o+=1
if %_o% geq 30 ( echo  Ollama antwortet noch nicht - oeffne trotzdem ^(spaeter Seite neu laden^). & goto ollama_ok )
timeout /t 2 >nul
goto waitollama
:ollama_ok

echo  Warte auf Web-Server ...
set /a _w=0
:waitweb
curl -s -o nul --max-time 2 http://127.0.0.1:8000/index.html
if not errorlevel 1 goto web_ok
set /a _w+=1
if %_w% geq 20 goto web_ok
timeout /t 1 >nul
goto waitweb
:web_ok

echo  Alles bereit - oeffne Oddvark im Browser ...
start "" http://localhost:8000/index.html

echo(
echo ==================================================
echo  Fertig. Alle Dienste laufen in eigenen Fenstern.
echo  Beenden: die jeweiligen Fenster schliessen.
echo ==================================================
echo(
echo  Dieses Fenster kann geschlossen werden.
pause >nul
