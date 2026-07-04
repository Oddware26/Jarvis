"""
Oddvark - lokaler Spracherkennungs-Server (Speech-to-Text) mit faster-whisper.

Offline, lokal, genau und mehrsprachig - damit Oddvark nicht mehr von der
Cloud-Web-Speech-API abhaengt. Nimmt Audio (webm/ogg/wav/mp3) entgegen und
gibt den erkannten Text zurueck. Das Frontend (file:// oder http://localhost)
ruft die API per fetch auf:

  GET  /health        -> {"ok": true, "available": bool, "model": str|null, "loaded": bool}
  GET  /capabilities  -> {"available": bool, "model_size": str, "device": str, "note": str}
  POST /transcribe    -> {"text": str, "language": str, "duration": float}
       Eingabe 1: Content-Type: application/json  {"audio_base64": "...", "mime"?, "language"?}
       Eingabe 2: Content-Type: audio/*  oder  multipart/form-data  (rohe Bytes)
  POST /warmup        -> {"ok": bool, ...}   (Modell vorab laden)

faster-whisper ist eine OPTIONALE Abhaengigkeit: fehlt sie, startet der Server
trotzdem und meldet ueber /health + /capabilities available:false mit klarem
Installationshinweis. Er stuerzt NIE ab, sondern degradiert sauber.

Start:
  tools/start-stt.bat

Voraussetzungen (optional):  pip install faster-whisper
Fuer webm/ogg wird zusaetzlich ffmpeg im PATH benoetigt (WAV geht auch ohne).
Das Modell wird von faster-whisper beim ersten /transcribe automatisch
heruntergeladen und gecacht.
"""
import os
import json
import base64
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from faster_whisper import WhisperModel
except Exception:  # noqa: BLE001 - Lib optional, Server soll trotzdem starten
    WhisperModel = None

HOST = os.environ.get("STT_HOST", "127.0.0.1")
PORT = int(os.environ.get("STT_PORT", "7865"))

_HERE = os.path.dirname(os.path.abspath(__file__))
_FRONTEND = os.path.dirname(_HERE)
CONFIG_PATH = os.path.join(_FRONTEND, "config.json")

PIP_HINT = "pip install faster-whisper"

# Defaults (per config.json ueberschreibbar, Key "whisper")
DEFAULTS = {
    "model_size": "base",     # tiny | base | small | medium | large-v3 ...
    "device": "auto",         # auto -> cuda falls verfuegbar sonst cpu
    "compute_type": "auto",   # auto | int8 | float16 | float32 ...
    "language": None,         # None = automatische Spracherkennung
}

# mime -> Dateiendung fuer die Temp-Datei (faster-whisper liest via ffmpeg)
MIME_EXT = {
    "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/wav": ".wav",
    "audio/x-wav": ".wav", "audio/wave": ".wav", "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
    "audio/flac": ".flac", "audio/webm;codecs=opus": ".webm",
}

model = None          # geladenes WhisperModel (lazy)
loaded = False
device_used = "cpu"
load_err = None
gpu_lock = threading.Lock()   # nur EINE Transkription gleichzeitig


def load_config():
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user = json.load(f) or {}
        w = user.get("whisper") or {}
        for k in DEFAULTS:
            if k in w:
                cfg[k] = w[k]
        print("[STT] config.json geladen: %s" % CONFIG_PATH)
    except FileNotFoundError:
        print("[STT] keine config.json - nutze Defaults (siehe config.example.json)")
    except Exception as e:  # noqa: BLE001
        print("[STT] config.json fehlerhaft (%r) - nutze Defaults" % e)
    return cfg


CONFIG = load_config()


def _resolve_device():
    """'auto' -> 'cuda' falls eine CUDA-GPU verfuegbar ist, sonst 'cpu'."""
    dev = (CONFIG.get("device") or "auto").lower()
    if dev != "auto":
        return dev
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


def load_model():
    """Modell lazy laden (thread-safe). Rueckgabe True bei Erfolg."""
    global model, loaded, device_used, load_err
    if loaded:
        return True
    if WhisperModel is None:
        return False
    with gpu_lock:
        if loaded:
            return True
        try:
            dev = _resolve_device()
            ct = CONFIG.get("compute_type") or "auto"
            size = CONFIG.get("model_size") or "base"
            print("[STT] lade Whisper '%s' auf %s (compute=%s) ..." % (size, dev, ct), flush=True)
            model = WhisperModel(size, device=dev, compute_type=ct)
            device_used = dev
            loaded = True
            load_err = None
            print("[STT] bereit.", flush=True)
            return True
        except Exception as e:  # noqa: BLE001
            load_err = repr(e)
            print("[STT] LADEFEHLER:", e, flush=True)
            return False


def _ext_for(mime):
    m = (mime or "").split(";")[0].strip().lower()
    if mime and mime.lower() in MIME_EXT:
        return MIME_EXT[mime.lower()]
    return MIME_EXT.get(m, ".webm")


def transcribe_bytes(audio, mime, language):
    """Rohe Audio-Bytes -> {text, language, duration}. Wirft bei echtem Fehler."""
    if not load_model():
        raise RuntimeError(load_err or "Modell nicht geladen")
    lang = language or CONFIG.get("language") or None
    fd, path = tempfile.mkstemp(suffix=_ext_for(mime))
    with os.fdopen(fd, "wb") as f:
        f.write(audio)
    try:
        with gpu_lock:
            segments, info = model.transcribe(path, language=lang, vad_filter=True)
            text = "".join(seg.text for seg in segments).strip()
        return {
            "text": text,
            "language": getattr(info, "language", None) or lang or "",
            "duration": round(float(getattr(info, "duration", 0.0) or 0.0), 3),
        }
    finally:
        try:
            os.remove(path)
        except Exception:  # noqa: BLE001
            pass


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Cache-Control", "no-store")

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, {
                "ok": True,
                "available": WhisperModel is not None,
                "model": (CONFIG.get("model_size") if WhisperModel is not None else None),
                "loaded": loaded,
            })
        elif self.path.startswith("/capabilities"):
            avail = WhisperModel is not None
            note = ("bereit" if avail else
                    "faster-whisper nicht installiert - " + PIP_HINT)
            self._send(200, {
                "available": avail,
                "model_size": CONFIG.get("model_size"),
                "device": _resolve_device() if avail else CONFIG.get("device"),
                "note": note,
            })
        else:
            self._send(404, {"error": "not found"})

    def _read_audio(self):
        """Liest Audio-Bytes + mime + language aus dem Request.
        Rueckgabe (audio_bytes|None, mime, language)."""
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b""
        ctype = (self.headers.get("Content-Type") or "").lower()
        if ctype.startswith("application/json"):
            data = json.loads(raw or b"{}")
            b64 = data.get("audio_base64") or ""
            if "," in b64 and b64.strip().startswith("data:"):
                b64 = b64.split(",", 1)[1]
            audio = base64.b64decode(b64) if b64 else b""
            return (audio or None), data.get("mime"), data.get("language")
        # audio/* oder multipart/form-data oder sonstige rohe Bytes
        if ctype.startswith("multipart/form-data"):
            audio, mime = _extract_multipart(raw, ctype)
        else:
            audio, mime = (raw or None), (ctype or None)
        lang = self.headers.get("X-Language") or None
        return audio, mime, lang

    def do_POST(self):
        if self.path.startswith("/warmup"):
            if WhisperModel is None:
                self._send(200, {"ok": False, "available": False,
                                 "error": "faster-whisper nicht installiert",
                                 "hint": PIP_HINT})
                return
            ok = load_model()
            self._send(200, {"ok": ok, "loaded": loaded, "device": device_used,
                             "error": load_err})
            return
        if not self.path.startswith("/transcribe"):
            self._send(404, {"error": "not found"})
            return
        if WhisperModel is None:
            self._send(200, {"error": "faster-whisper nicht installiert",
                             "hint": PIP_HINT})
            return
        try:
            audio, mime, language = self._read_audio()
        except Exception as e:  # noqa: BLE001
            self._send(400, {"error": "ungueltiger Body: " + repr(e)})
            return
        if not audio:
            self._send(400, {"error": "kein Audio empfangen",
                             "hint": "audio_base64 (JSON) oder rohe Bytes mit Content-Type audio/*"})
            return
        try:
            self._send(200, transcribe_bytes(audio, mime, language))
        except Exception as e:  # noqa: BLE001
            msg = repr(e)
            low = msg.lower()
            if "ffmpeg" in low or "winerror 2" in low or "no such file" in low or "failed to load audio" in low:
                self._send(200, {"error": "Audio konnte nicht gelesen werden: " + msg,
                                 "hint": "ffmpeg noetig fuer webm/ogg; oder WAV senden"})
            else:
                self._send(500, {"error": msg})

    def log_message(self, fmt, *args):  # kompaktes Log
        print("[STT] " + (fmt % args))


def _extract_multipart(raw, ctype):
    """Sehr einfacher multipart/form-data-Parser: erster Datei-Part -> (bytes, mime)."""
    m = None
    for part in ctype.split(";"):
        part = part.strip()
        if part.startswith("boundary="):
            m = part[len("boundary="):].strip('"')
    if not m:
        return (raw or None), None
    sep = ("--" + m).encode()
    for chunk in raw.split(sep):
        if b"\r\n\r\n" not in chunk:
            continue
        head, body = chunk.split(b"\r\n\r\n", 1)
        head_l = head.lower()
        if b"filename=" not in head_l and b"application/octet-stream" not in head_l and b"audio/" not in head_l:
            continue
        body = body.rstrip(b"\r\n").rstrip(b"-").rstrip(b"\r\n")
        mime = None
        for line in head.split(b"\r\n"):
            if line.lower().startswith(b"content-type:"):
                mime = line.split(b":", 1)[1].strip().decode("ascii", "replace")
        if body:
            return body, mime
    return (raw or None), None


if __name__ == "__main__":
    avail = "verfuegbar" if WhisperModel is not None else ("NICHT installiert (%s)" % PIP_HINT)
    print("[STT] faster-whisper: %s" % avail, flush=True)
    print("[STT] HTTP auf http://%s:%d  (GET /health, GET /capabilities, POST /transcribe, POST /warmup)"
          % (HOST, PORT), flush=True)
    try:
        ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
