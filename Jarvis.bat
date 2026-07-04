@echo off
setlocal EnableExtensions
title Jarvis
cd /d "%~dp0"

echo(
echo   ============================================
echo      J A R V I S   -   startet ...
echo   ============================================
echo(

REM --- 1) Ollama sicherstellen (das einzige Muss). ---------------------------
where ollama >nul 2>nul
if errorlevel 1 (
  echo   [!] Ollama ist nicht installiert.
  echo       Bitte einmalig von https://ollama.com installieren, dann ein Modell laden:
  echo           ollama pull llama3.2
  echo(
  echo   Danach diese Datei erneut starten.
  echo(
  pause
  exit /b 1
)
curl -s -o nul --max-time 2 http://127.0.0.1:11434/api/version
if errorlevel 1 (
  echo   [*] Starte Ollama ...
  start "Ollama" /min ollama serve
)

REM --- 2) Voll-Modus mit Python (Websuche, PC-Steuerung, Stimmen) ODER --------
REM        Kern-Modus ohne alles: index.html direkt oeffnen (nur Ollama noetig). --
where python >nul 2>nul
if not errorlevel 1 (
  echo   [*] Python gefunden - starte das volle Erlebnis ^(inkl. Websuche, PC-Steuerung^).
  echo(
  python "%~dp0frontend\start.py"
  goto :eof
)

echo   [i] Python nicht gefunden - starte Jarvis im Kern-Modus.
echo       Chat, Modelle, Einstellungen und Verlauf funktionieren voll.
echo       Fuer Websuche / PC-Steuerung / eigene Stimmen spaeter einmal Python
echo       ^(https://python.org^) installieren und diese Datei erneut starten.
echo(
echo   Warte kurz auf Ollama ...
set /a _o=0
:waitollama
curl -s -o nul --max-time 2 http://127.0.0.1:11434/api/version
if not errorlevel 1 goto ollama_ok
set /a _o+=1
if %_o% geq 20 goto ollama_ok
timeout /t 2 >nul
goto waitollama
:ollama_ok

start "" "%~dp0frontend\index.html"
echo(
echo   Jarvis wurde im Browser geoeffnet. Dieses Fenster kann geschlossen werden.
timeout /t 4 >nul
