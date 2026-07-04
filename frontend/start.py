#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jarvis – plattformübergreifender Starter (Windows / macOS / Linux).

Startet alle lokalen Dienste und öffnet Jarvis im Browser. Nichts ist auf einen
bestimmten Rechner hartkodiert – einfach das Repo klonen und `python start.py` ausführen.

    python start.py

Dienste (jeder in einem eigenen Prozess; fehlende werden übersprungen):
    Ollama        11434  LLM-Backend            (muss installiert sein: https://ollama.com)
    Websuche      7863   tools/search-server.py (stdlib – läuft immer)
    Aktionen      7864   tools/action-server.py (PC-/Datei-/Browser-/Vision-Zugriff)
    STT (Whisper) 7865   tools/stt-server.py    (lokal; braucht `pip install faster-whisper`)
    TTS (XTTS)    7862   tools/tts-server.py    (nur falls tools/tts-venv vorhanden)
    Z-Image       7861   tools/zimage-server.py (nur falls tools/zimage-venv vorhanden)
    Web           8000   tools/serve.py         (Frontend)

Beenden: dieses Fenster schließen (Strg+C) – die Dienste laufen als Kindprozesse und
werden mitbeendet.
"""
import os
import sys
import time
import shutil
import socket
import subprocess
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable or "python"
CHILDREN = []


def port_open(port, host="127.0.0.1", timeout=0.4):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def spawn(title, args, cwd=None):
    """Startet einen Kindprozess in einem eigenen Fenster (Windows) bzw. normal (POSIX)."""
    try:
        if os.name == "nt":
            flags = subprocess.CREATE_NEW_CONSOLE  # eigenes Fenster je Dienst
            p = subprocess.Popen(args, cwd=cwd or HERE, creationflags=flags)
        else:
            p = subprocess.Popen(args, cwd=cwd or HERE)
        CHILDREN.append(p)
        print("  [start] %s" % title)
        return p
    except Exception as e:
        print("  [übersprungen] %s (%r)" % (title, e))
        return None


def start_service(title, port, args, needed=True, cwd=None):
    if port and port_open(port):
        print("  [läuft]  %s (Port %d)" % (title, port))
        return
    if not needed:
        print("  [fehlt]  %s – übersprungen" % title)
        return
    spawn(title, args, cwd=cwd)


def has_venv_python(venv_dir):
    """Pfad zum python im venv oder None."""
    cand = [os.path.join(venv_dir, "Scripts", "python.exe"),
            os.path.join(venv_dir, "bin", "python")]
    for c in cand:
        if os.path.isfile(c):
            return c
    return None


def main():
    tools = os.path.join(HERE, "tools")
    print("=" * 54)
    print("   J A R V I S   –   Dienste starten")
    print("=" * 54)

    # 1) Ollama (nur starten, wenn installiert und nicht schon aktiv)
    if port_open(11434):
        print("  [läuft]  Ollama (11434)")
    elif shutil.which("ollama"):
        spawn("Ollama 11434", ["ollama", "serve"])
    else:
        print("  [fehlt]  Ollama nicht gefunden – bitte installieren: https://ollama.com")

    # 2) Kern-Server (reine stdlib – laufen immer)
    start_service("Websuche 7863", 7863, [PY, os.path.join(tools, "search-server.py")])
    start_service("Aktionen 7864", 7864, [PY, os.path.join(tools, "action-server.py")])
    start_service("STT/Whisper 7865", 7865, [PY, os.path.join(tools, "stt-server.py")])

    # 3) Optionale Modell-Server (nur wenn ihr venv existiert)
    tts_py = has_venv_python(os.path.join(tools, "tts-venv"))
    if tts_py and not port_open(7862):
        spawn("TTS/XTTS 7862", [tts_py, os.path.join(tools, "tts-server.py")])
    elif port_open(7862):
        print("  [läuft]  TTS (7862)")
    else:
        print("  [fehlt]  TTS (tools/tts-venv) – Browser-Stimme wird genutzt")

    zi_py = has_venv_python(os.path.join(tools, "zimage-venv"))
    if zi_py and not port_open(7861):
        spawn("Z-Image 7861", [zi_py, os.path.join(tools, "zimage-server.py")])
    elif port_open(7861):
        print("  [läuft]  Z-Image (7861)")
    else:
        print("  [fehlt]  Z-Image (tools/zimage-venv) – Bildgenerierung deaktiviert")

    # 4) Web-Server (Frontend)
    start_service("Web 8000", 8000, [PY, os.path.join(tools, "serve.py")])

    # 5) Auf Web-Server warten, dann Browser öffnen
    print("-" * 54)
    print("  Warte auf Web-Server (http://localhost:8000) …")
    for _ in range(40):
        if port_open(8000):
            break
        time.sleep(0.5)
    url = "http://localhost:8000/index.html"
    print("  Öffne Jarvis: %s" % url)
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print("=" * 54)
    print("  Fertig. Dienste laufen. Zum Beenden: Strg+C bzw. Fenster schließen.")
    print("  Tipp: Mikrofon-Knopf im Chat = sprechen; 'Hey Jarvis' als Wake-Word.")
    print("=" * 54)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n  Beende Dienste …")
        for p in CHILDREN:
            try:
                p.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()
