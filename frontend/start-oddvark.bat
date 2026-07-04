@echo off
REM Oddvark ueber http://localhost starten.
REM WICHTIG fuer Mikrofon/Wake-Word: bei file:// vergisst Chrome die Mikro-Erlaubnis und fragt
REM staendig neu. Ueber http://localhost merkt sich Chrome die Erlaubnis dauerhaft
REM ("Beim Besuch der Website erlauben" einmal klicken -> nie wieder Nachfrage).
cd /d "%~dp0"
echo Starte lokalen Server auf http://localhost:8000 ...
start "" python -m http.server 8000
timeout /t 1 >nul
start "" http://localhost:8000/index.html
echo Server laeuft. Dieses Fenster offen lassen. Zum Beenden: Fenster schliessen.
