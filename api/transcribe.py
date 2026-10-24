import json
import re
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from youtube_transcript_api import YouTubeTranscriptApi

def video_id(url):
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
        if p.path == "/watch":
            v = parse_qs(p.query).get("v", [""])[0]
        else:
            m = re.fullmatch(r"/(?:shorts|live|embed)/([A-Za-z0-9_-]{11})/?", p.path)
            v = m.group(1) if m else ""
    elif host in ("youtu.be", "www.youtu.be"):
        v = p.path.strip("/")
    else:
        return None
    return v if re.fullmatch(r"[A-Za-z0-9_-]{11}", v) else None

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size < 1 or size > 4096:
                return self.reply(400, {"error": "Requête invalide."})
            data = json.loads(self.rfile.read(size))
            vid = video_id(data.get("url", ""))
            if not vid:
                return self.reply(400, {"error": "Lien YouTube invalide."})
            transcripts = YouTubeTranscriptApi().list(vid)
            try:
                track = transcripts.find_transcript(["fr", "fr-FR", "en"])
            except Exception:
                track = next(iter(transcripts))
            lines = track.fetch()
            text = "\n".join(x.text for x in lines if x.text.strip())
            if not text:
                return self.reply(404, {"error": "Sous-titres vides."})
            return self.reply(200, {"text": text, "language": track.language, "videoId": vid})
        except Exception:
            return self.reply(422, {"error": "Sous-titres indisponibles ou accès bloqué par YouTube."})

    def reply(self, status, body):
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
