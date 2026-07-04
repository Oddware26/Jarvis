"""
Oddvark - lokaler XTTS-v2 TTS-Server (hyperrealistisch, mehrsprachig, viele Stimmen).

Laedt Coqui XTTS-v2 (coqui-tts) und stellt eine kleine HTTP-API bereit, die das
Oddvark-Frontend (file:// oder http://localhost) per fetch aufruft:

  GET  /health   -> {"ready": bool, "error": str|null, "voices": int, "languages": [...]}
  GET  /voices   -> {"voices": [Sprecher...], "languages": [{code,label}...]}
  POST /speak     -> audio/wav (binaer)
       Body: {"text": "...", "voice": "Sprechername", "language": "de", "speed": 1.0,
              "speaker_wav": "data:audio/wav;base64,..."?}   # speaker_wav = Stimmen-Klonen (optional)

Start:
  tools/start-tts.bat   (nutzt tools/tts-venv)

Voraussetzungen: coqui-tts + torch(CUDA) in tools/tts-venv (isoliert).
XTTS-v2: 17 Sprachen inkl. Deutsch, ~58 eingebaute Sprecher, Voice-Cloning aus ~6s Sample.
"""
import io
import os
import json
import base64
import wave
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault("COQUI_TOS_AGREED", "1")   # Lizenz nicht-interaktiv akzeptieren
os.environ.setdefault("COQUI_TTS_NO_MECAB", "1")

HOST = os.environ.get("TTS_HOST", "127.0.0.1")
PORT = int(os.environ.get("TTS_PORT", "7862"))
MODEL = os.environ.get("TTS_MODEL", "tts_models/multilingual/multi-dataset/xtts_v2")
DEVICE = os.environ.get("TTS_DEVICE", "cuda")  # "cuda" oder "cpu"

# Freundliche Sprachnamen fuer die im Modell unterstuetzten Codes
LANG_LABELS = {
    "de": "Deutsch", "en": "English", "es": "Espanol", "fr": "Francais", "it": "Italiano",
    "pt": "Portugues", "pl": "Polski", "tr": "Turkce", "ru": "Russkij", "nl": "Nederlands",
    "cs": "Cestina", "ar": "Arabic", "zh-cn": "Chinese", "ja": "Japanese", "hu": "Magyar",
    "ko": "Korean", "hi": "Hindi",
}

tts = None
ready = False
load_err = None
voices = []
languages = []
sample_rate = 24000
gen_lock = threading.Lock()   # GPU-gebunden -> nur eine Synthese gleichzeitig


def load_model():
    global tts, ready, load_err, voices, languages, sample_rate
    try:
        import torch
        from TTS.api import TTS as CoquiTTS
        print("[tts] lade %s auf %s ..." % (MODEL, DEVICE), flush=True)
        dev = DEVICE if (DEVICE != "cuda" or torch.cuda.is_available()) else "cpu"
        m = CoquiTTS(MODEL, progress_bar=False).to(dev)
        tts = m
        try:
            voices = list(m.synthesizer.tts_model.speaker_manager.name_to_id.keys())
        except Exception:
            voices = []
        try:
            languages = list(m.synthesizer.tts_model.config.languages)
        except Exception:
            languages = list(LANG_LABELS.keys())
        try:
            sample_rate = int(m.synthesizer.output_sample_rate)
        except Exception:
            sample_rate = 24000
        ready = True
        print("[tts] bereit. %d Stimmen, %d Sprachen, %d Hz (%s)." % (len(voices), len(languages), sample_rate, dev), flush=True)
    except Exception as e:  # noqa: BLE001
        load_err = repr(e)
        print("[tts] LADEFEHLER:", e, flush=True)


def _wav_bytes(samples):
    """float-Liste/np-Array (-1..1) -> 16-bit PCM WAV (stdlib, keine Extra-Deps)."""
    import numpy as np
    a = np.asarray(samples, dtype="float32")
    a = np.clip(a, -1.0, 1.0)
    pcm = (a * 32767.0).astype("<i2").tobytes()
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _decode_wav_to_temp(data_url):
    """data:audio/...;base64,XXXX -> temp .wav Pfad (fuer Voice-Cloning)."""
    s = data_url or ""
    if "," in s and s.strip().startswith("data:"):
        s = s.split(",", 1)[1]
    raw = base64.b64decode(s)
    fd, path = tempfile.mkstemp(suffix=".wav")
    with os.fdopen(fd, "wb") as f:
        f.write(raw)
    return path


def synth(text, voice, language, speed, speaker_wav):
    kwargs = {"text": text, "language": language or "de", "split_sentences": True}
    try:
        if speed and float(speed) != 1.0:
            kwargs["speed"] = float(speed)
    except Exception:
        pass
    tmp = None
    if speaker_wav:
        tmp = _decode_wav_to_temp(speaker_wav)
        kwargs["speaker_wav"] = tmp
    elif voice and voice in voices:
        kwargs["speaker"] = voice
    elif voices:
        kwargs["speaker"] = voices[0]
    try:
        with gen_lock:
            wav = tts.tts(**kwargs)
        return _wav_bytes(wav)
    finally:
        if tmp:
            try: os.remove(tmp)
            except Exception: pass


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _wav(self, data):
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/health"):
            self._json(200, {"ready": ready, "error": load_err, "voices": len(voices),
                             "languages": [c for c in languages]})
        elif self.path.startswith("/voices"):
            langs = [{"code": c, "label": LANG_LABELS.get(c, c)} for c in languages]
            self._json(200, {"voices": voices, "languages": langs})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/speak"):
            self._json(404, {"error": "not found"})
            return
        if not ready:
            self._json(503, {"error": load_err or "Modell laedt noch - gleich erneut versuchen."})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:  # noqa: BLE001
            self._json(400, {"error": "ungueltiger Body: " + repr(e)})
            return
        text = (data.get("text") or "").strip()
        if not text:
            self._json(400, {"error": "text fehlt"})
            return
        try:
            wav = synth(text, data.get("voice"), data.get("language"),
                        data.get("speed"), data.get("speaker_wav"))
            self._wav(wav)
        except Exception as e:  # noqa: BLE001
            self._json(500, {"error": repr(e)})

    def log_message(self, *args):
        return


if __name__ == "__main__":
    threading.Thread(target=load_model, daemon=True).start()
    srv = ThreadingHTTPServer((HOST, PORT), Handler)
    print("[tts] HTTP auf http://%s:%d  (GET /health, GET /voices, POST /speak)" % (HOST, PORT), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
