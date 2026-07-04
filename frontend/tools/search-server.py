# Oddvark - lokale Websuche (DuckDuckGo, ohne API-Key), Port 7863.
# Nur Python-Standardbibliothek (wie serve.py): kein venv, keine Abhaengigkeiten.
#   GET /health           -> {"ok": true}
#   GET /search?q=..&n=8  -> {"results": [{"title","url","snippet"}, ...]}
# Quellen: html.duckduckgo.com (primaer), lite.duckduckgo.com (Fallback).
import json
import re
import datetime
import html as htmllib
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 7863
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")


def _fetch(url, data=None, extra_headers=None):
    headers = {
        "User-Agent": UA,
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.7",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.read().decode("utf-8", "replace")


def _fetch_resp(url, extra_headers=None):
    # Wie _fetch, gibt aber zusätzlich den Link-Header zurück (für HF-Cursor-Pagination).
    headers = {"User-Agent": UA, "Accept-Language": "en;q=0.9,de;q=0.7"}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", "replace"), r.headers.get("Link", "")


def _strip(s):
    return htmllib.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def _unwrap(url):
    # DDG verpackt Ziel-URLs als //duckduckgo.com/l/?uddg=<url-encoded>&rut=...
    if url.startswith("//"):
        url = "https:" + url
    m = re.search(r"[?&]uddg=([^&]+)", url)
    if m:
        url = urllib.parse.unquote(m.group(1))
    return url if url.startswith("http") else ""


def _search_html(q, n):
    body = _fetch("https://html.duckduckgo.com/html/?" +
                  urllib.parse.urlencode({"q": q, "kl": "de-de"}))
    out = []
    blocks = re.findall(
        r'<div[^>]+class="[^"]*result__body[^"]*".*?(?=<div[^>]+class="[^"]*result__body|\Z)',
        body, re.S)
    for block in blocks:
        a = re.search(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not a:
            continue
        url = _unwrap(htmllib.unescape(a.group(1)))
        if not url or "duckduckgo.com" in url:
            continue
        sn = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, re.S)
        out.append({"title": _strip(a.group(2)), "url": url,
                    "snippet": _strip(sn.group(1)) if sn else ""})
        if len(out) >= n:
            break
    return out


def _search_lite(q, n):
    body = _fetch("https://lite.duckduckgo.com/lite/",
                  data=urllib.parse.urlencode({"q": q, "kl": "de-de"}).encode())
    out = []
    # Lite: Tabellenzeilen mit <a rel="nofollow" href="...">Titel</a>, danach result-snippet-Zelle.
    rows = re.split(r"<tr", body)
    cur = None
    for row in rows:
        a = re.search(r'<a[^>]+rel="nofollow"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', row, re.S)
        if a:
            url = _unwrap(htmllib.unescape(a.group(1)))
            cur = {"title": _strip(a.group(2)), "url": url, "snippet": ""} if url else None
            continue
        sn = re.search(r'class="result-snippet"[^>]*>(.*?)</td>', row, re.S)
        if sn and cur:
            cur["snippet"] = _strip(sn.group(1))
            out.append(cur)
            cur = None
            if len(out) >= n:
                break
    return out


def search(q, n):
    try:
        res = _search_html(q, n)
        if res:
            return res
    except Exception:
        pass
    return _search_lite(q, n)


# ---- Ollama-Bibliothek (ollama.com/search) paginiert als kompaktes JSON ---------
# Holt EINE Seite (20 Modelle) der öffentlichen Ollama-Suche und parst die Modell-Karten.
# So kann die Modelle-Seite die GESAMTE Library lazy beim Scrollen nachladen, ohne alles zu bündeln.
#
# WICHTIG (durch Reverse-Engineering ermittelt): ollama.com/search paginiert per htmx.
#   - Seiten-Param ist ?page=N (NICHT ?p=N).
#   - Ohne den Header "HX-Request: true" liefert Seite >1 einen LEEREN Body.
#   - Leere Query q="" liefert nur ~236 kuratierte/aktuelle Modelle (≈ gebündelter Katalog);
#     mit echter Query q durchsucht sie die volle Community-Bibliothek (~10k) und paginiert tief.
#   - Optional: c=<vision|tools|thinking|embedding|cloud> (Fähigkeit), o=<newest|popular> (Sortierung).
def _ollama_library(q, page, cap="", order=""):
    try:
        p = max(1, int(page or 1))
    except (TypeError, ValueError):
        p = 1
    params = {"q": q or "", "page": p}
    if cap:
        params["c"] = cap
    if order:
        params["o"] = order
    url = "https://ollama.com/search?" + urllib.parse.urlencode(params)
    body = _fetch(url, extra_headers={"HX-Request": "true", "HX-Target": "searchresults"})
    out = []
    # Robust: an den x-test-model-Markern splitten (keine </li>-Abhängigkeit).
    for chunk in re.split(r"x-test-model", body)[1:]:
        nm = re.search(r'href="/library/([^"]+)"', chunk)
        if not nm:
            continue
        pulls = re.search(r"x-test-pull-count[^>]*>([^<]+)", chunk)
        upd = re.search(r"x-test-updated[^>]*>([^<]+)", chunk)
        desc = re.search(r"<p[^>]*>(.*?)</p>", chunk, re.S)
        out.append({
            "name": nm.group(1),
            "description": _strip(desc.group(1)) if desc else "",
            "capabilities": [c.strip() for c in re.findall(r"x-test-capability[^>]*>([^<]+)", chunk)],
            "sizes": [s.strip() for s in re.findall(r"x-test-size[^>]*>([^<]+)", chunk)],
            "pulls": pulls.group(1).strip() if pulls else "",
            "updated": upd.group(1).strip() if upd else "",
            "source": "ollama",
        })
    return {"models": out, "page": p, "has_more": len(out) >= 20}


# ---- HuggingFace-GGUF-Bibliothek (die eigentlichen ~zehntausend Modelle) ---------
# ollama.com/search liefert nur den kuratierten Satz. Die WIRKLICH große Bibliothek sind
# die GGUF-Repos auf HuggingFace – Ollama kann jedes davon direkt ausführen:
#     ollama run hf.co/<user>/<repo>
# Die HF-API ist paginiert (Cursor via Link-Header, unbegrenzt tief) und nach Downloads
# sortiert, sodass die Modelle-Seite sie lazy beim Scrollen streamen kann – nichts gebündelt.
# CORS der HF-API ist auf huggingface.co beschränkt -> Zugriff MUSS über diesen Proxy laufen.
_HF_SKIP_TAG = re.compile(
    r"^(i?q\d[\w.]*|f16|bf16|fp16|fp8|\d+-?bit|gguf|quantized|conversational|"
    r"text-generation-inference|autotrain_compatible|endpoints_compatible|"
    r"region:[\w-]+|license:[\w.\-]+|base_model:.*|dataset:.*|arxiv:.*|doi:.*|"
    r"safetensors|onnx|pytorch|transformers|en|imatrix)$", re.I)


def _hf_caps(tags, ptag):
    tags = [str(x).lower() for x in (tags or [])]
    ptag = (ptag or "").lower()
    caps = []
    if ptag in ("image-text-to-text", "image-to-text", "visual-question-answering") \
            or any(x in tags for x in ("multimodal", "image-text-to-text", "visual-question-answering")):
        caps.append("vision")
    if ptag in ("feature-extraction", "sentence-similarity") or "sentence-transformers" in tags:
        caps.append("embedding")
    if any(x in tags for x in ("function-calling", "tool-use", "tool-calling", "tools")):
        caps.append("tools")
    if any(x in tags for x in ("reasoning", "thinking", "chain-of-thought")):
        caps.append("thinking")
    return caps


def _hf_pulls(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    if n >= 1_000_000:
        return ("%.1fM" % (n / 1_000_000)).replace(".0M", "M")
    if n >= 1_000:
        return ("%.1fK" % (n / 1_000)).replace(".0K", "K")
    return str(n)


def _hf_next_cursor(link):
    m = re.search(r'[?&]cursor=([^&>]+)[^>]*>;\s*rel="next"', link or "")
    return urllib.parse.unquote(m.group(1)) if m else ""


def _hf_ago(iso):
    # ISO-Zeitstempel -> kompakte relative Angabe im Stil der ollama-Quelle ("3 months"),
    # die der Client dann als "{v} ago" / "vor {v}" rendert.
    if not iso:
        return ""
    try:
        dt = datetime.datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
    except (ValueError, TypeError):
        return iso[:10]
    sec = (datetime.datetime.utcnow() - dt).total_seconds()
    if sec < 0:
        sec = 0
    day = sec / 86400
    if day >= 365:
        v = int(day / 365); return "%d year%s" % (v, "" if v == 1 else "s")
    if day >= 30:
        v = int(day / 30); return "%d month%s" % (v, "" if v == 1 else "s")
    if day >= 1:
        v = int(day); return "%d day%s" % (v, "" if v == 1 else "s")
    hr = sec / 3600
    if hr >= 1:
        v = int(hr); return "%d hour%s" % (v, "" if v == 1 else "s")
    return "just now"


def _hf_library(q, cursor):
    # Basis-URL ist fest (nur huggingface.co) – der Client steuert lediglich Query + opaken
    # Cursor-Wert, nie den Host. Damit kein SSRF-Vektor.
    # expand=... hält die Antwort schlank (nur benötigte Felder) UND liefert lastModified.
    params = [
        ("filter", "gguf"), ("sort", "downloads"), ("direction", "-1"), ("limit", "24"),
        ("expand", "downloads"), ("expand", "lastModified"),
        ("expand", "pipeline_tag"), ("expand", "tags"),
    ]
    if q:
        params.append(("search", q))
    if cursor:
        params.append(("cursor", cursor))
    url = "https://huggingface.co/api/models?" + urllib.parse.urlencode(params)
    body, link = _fetch_resp(url)
    try:
        arr = json.loads(body)
    except ValueError:
        arr = []
    out = []
    for m in arr if isinstance(arr, list) else []:
        mid = m.get("id") or m.get("modelId")
        if not mid or "/" not in mid:
            continue
        tags = m.get("tags") or []
        ptag = m.get("pipeline_tag") or ""
        author = m.get("author") or mid.split("/")[0]
        label = mid.split("/")[-1]
        topics = [str(b) for b in tags if not _HF_SKIP_TAG.match(str(b))][:4]
        desc = "by " + author + (" · " + ptag if ptag else "")
        if topics:
            desc += " · " + ", ".join(topics)
        out.append({
            "name": "hf.co/" + mid,
            "label": label,
            "description": desc,
            "capabilities": _hf_caps(tags, ptag),
            "sizes": [],  # ohne Tag wählt Ollama automatisch eine Quantisierung
            "pulls": _hf_pulls(m.get("downloads")),
            "updated": _hf_ago(m.get("lastModified")),
            "source": "huggingface",
        })
    return {"models": out, "next": _hf_next_cursor(link)}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/health":
            self._send(200, {"ok": True})
            return
        if u.path == "/search":
            qs = urllib.parse.parse_qs(u.query)
            q = (qs.get("q") or [""])[0].strip()
            try:
                n = max(1, min(10, int((qs.get("n") or ["8"])[0])))
            except ValueError:
                n = 8
            if not q:
                self._send(400, {"error": "q fehlt"})
                return
            try:
                self._send(200, {"results": search(q, n)})
            except Exception as e:
                self._send(502, {"error": str(e)})
            return
        if u.path == "/ollama_library":
            qs = urllib.parse.parse_qs(u.query)
            q = (qs.get("q") or [""])[0].strip()
            page = (qs.get("page") or ["1"])[0]
            cap = (qs.get("c") or [""])[0].strip()
            order = (qs.get("o") or [""])[0].strip()
            try:
                self._send(200, _ollama_library(q, page, cap, order))
            except Exception as e:
                self._send(502, {"error": str(e)})
            return
        if u.path == "/hf_library":
            qs = urllib.parse.parse_qs(u.query)
            q = (qs.get("q") or [""])[0].strip()
            cursor = (qs.get("cursor") or [""])[0]
            try:
                self._send(200, _hf_library(q, cursor))
            except Exception as e:
                self._send(502, {"error": str(e)})
            return
        self._send(404, {"error": "nicht gefunden"})

    def log_message(self, fmt, *args):  # kompaktes Log
        print("[Suche] " + (fmt % args))


if __name__ == "__main__":
    print("Oddvark Websuche-Server auf http://127.0.0.1:%d (Beenden: Strg+C)" % PORT)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
