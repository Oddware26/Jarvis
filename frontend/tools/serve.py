#!/usr/bin/env python
# Jarvis Web-Server fuer die Entwicklung: liefert das frontend/-Verzeichnis MIT No-Cache-Headern,
# damit Aenderungen an app.js/.css sofort sichtbar sind (kein "harter Reload" noetig).
import http.server
import socketserver
import os

PORT = int(os.environ.get("PORT", "8000"))
HOST = os.environ.get("HOST", "127.0.0.1")
# tools/serve.py -> Elternordner ist frontend/
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

    def end_headers(self):
        # Jede Antwort explizit als nicht-cachebar markieren.
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, fmt, *args):
        pass  # ruhig halten


class Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


if __name__ == "__main__":
    with Server((HOST, PORT), Handler) as httpd:
        print("Jarvis Web (No-Cache) auf http://localhost:%d  -  Root: %s" % (PORT, ROOT), flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
