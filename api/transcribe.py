import json
import os
import urllib.request
import urllib.error
import urllib.parse
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
            key = os.environ.get("SUPADATA_API_KEY", "").strip()
            if key:
                endpoint = "https://api.supadata.ai/v1/transcript?" + urllib.parse.urlencode({
                    "url": "https://www.youtube.com/watch?v=" + vid, "text": "true", "mode": "native"
                })
                req = urllib.request.Request(endpoint, headers={"x-api-key": key, "Accept": "application/json"})
                try:
                    with urllib.request.urlopen(req, timeout=22) as response:
                        payload = json.load(response)
                except urllib.error.HTTPError as exc:
                    if exc.code in (401, 403):
                        return self.reply(502, {"error": "Clé Supadata invalide ou accès refusé."})
                    if exc.code == 429:
                        return self.reply(429, {"error": "Quota Supadata atteint. Réessayez plus tard."})
                    return self.reply(502, {"error": "Service de transcription indisponible (HTTP %s)." % exc.code})
                if payload.get("jobId"):
                    return self.reply(202, {"error": "Transcription en préparation. Réessayez dans quelques instants."})
                content = payload.get("content", "")
                result = content if isinstance(content, str) else "\n".join(
                    segment.get("text", "") for segment in content if isinstance(segment, dict)
                )
                if not result.strip():
                    return self.reply(404, {"error": "Aucun sous-titre disponible pour cette vidéo."})
                return self.reply(200, {"text": result, "language": payload.get("lang", "auto"), "videoId": vid})
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
