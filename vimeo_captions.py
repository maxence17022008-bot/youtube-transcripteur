"""Read caption tracks exposed by the Vimeo player."""
import html
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import Request, urlopen


class VimeoError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def parse_vimeo_url(value):
    try:
        url = urlsplit(value.strip())
        if url.scheme not in ("http", "https") or url.username or url.password:
            return None
        if url.hostname == "player.vimeo.com":
            pattern = r"/video/([0-9]+)"
        elif url.hostname in ("vimeo.com", "www.vimeo.com"):
            pattern = (r"/(?:channels/[\w-]+/|groups/[\w-]+/videos/|"
                       r"(?:showcase|album)/[0-9]+/video/)?([0-9]+)(?:/([a-zA-Z0-9]+))?")
        else:
            return None
        match = re.fullmatch(pattern, url.path.rstrip("/"))
        if not match:
            return None
        video, *suffix = match.groups()
        token = (suffix and suffix[0]) or parse_qs(url.query).get("h", [""])[0]
        if token and not re.fullmatch(r"[a-zA-Z0-9]+", token):
            return None
        return video, token
    except (ValueError, AttributeError):
        return None


def read_player_resource(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"})
    try:
        with urlopen(request, timeout=9) as response:
            data = response.read(8 * 1024 * 1024 + 1)
    except HTTPError as exc:
        if exc.code in (401, 403, 404):
            raise VimeoError(422, "Vidéo ou sous-titres inaccessibles. Pour une vidéo non répertoriée, collez son lien de partage complet.") from exc
        if exc.code == 429:
            raise VimeoError(429, "Vimeo reçoit trop de requêtes. Réessayez plus tard.") from exc
        raise VimeoError(502, "Vimeo est temporairement indisponible.") from exc
    except (URLError, TimeoutError) as exc:
        raise VimeoError(502, "Impossible de joindre Vimeo. Réessayez plus tard.") from exc
    if len(data) > 8 * 1024 * 1024:
        raise VimeoError(422, "La piste de sous-titres est trop volumineuse.")
    return data.decode("utf-8-sig")


def parse_cues(vtt):
    if not vtt.startswith("WEBVTT"):
        raise VimeoError(422, "Le format des sous-titres Vimeo est illisible.")
    segments = []
    for block in re.split(r"\n[ \t]*\n", vtt.replace("\r\n", "\n").replace("\r", "\n")):
        lines = block.strip().splitlines()
        if not lines or re.match(r"^(WEBVTT|NOTE|STYLE|REGION)(?:\s|$)", lines[0]):
            continue
        timing = 0 if "-->" in lines[0] else 1
        if len(lines) <= timing + 1:
            continue
        match = re.match(r"^(?:(\d{2,}):)?(\d{2}):(\d{2})\.(\d{3})\s+-->\s+", lines[timing])
        if match:
            hours, minutes, seconds, millis = map(int, match.groups(default="0"))
            offset = ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis
            words = html.unescape(re.sub(r"<[^>]+>", "", " ".join(lines[timing + 1:]))).strip()
            if words:
                segments.append({"offset": offset, "text": words})
    return segments


def vimeo_transcript(video, token):
    base = f"https://player.vimeo.com/video/{video}/config"
    config = json.loads(read_player_resource(base + ("?h=" + token if token else "")))
    tracks = [t for t in config.get("request", {}).get("text_tracks", [])
              if t.get("url") and t.get("kind", "subtitles") in ("captions", "subtitles")]
    if not tracks:
        raise VimeoError(404, "Aucun sous-titre accessible pour cette vidéo Vimeo.")

    def preference(track):
        language = track.get("lang", "").lower().split("-")[0]
        return {"fr": 0, "en": 1}.get(language, 2)

    track = min(tracks, key=preference)
    url = urljoin(base, track["url"])
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or not (host == "vimeo.com" or host.endswith((".vimeo.com", ".vimeocdn.com"))):
        raise VimeoError(502, "Adresse de sous-titres Vimeo inattendue.")
    segments = parse_cues(read_player_resource(url))
    if not segments:
        raise VimeoError(404, "La piste de sous-titres Vimeo est vide.")
    return track.get("label") or track.get("lang") or "auto", segments
