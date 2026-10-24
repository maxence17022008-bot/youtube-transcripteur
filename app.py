import re
from urllib.parse import urlparse, parse_qs

import streamlit as st
from youtube_transcript_api import YouTubeTranscriptApi

st.set_page_config(page_title="YouTube Transcripteur", page_icon="🎬", layout="centered")
st.markdown("""<style>.block-container{max-width:820px;padding-top:3rem}.stButton button[kind="primary"]{width:100%;border-radius:12px;padding:.65rem}h1{letter-spacing:-.04em}</style>""", unsafe_allow_html=True)
st.title("🎬 YouTube Transcripteur")
st.write("Transformez les sous-titres accessibles d’une vidéo YouTube en texte.")

def extract_video_id(value):
    try:
        p = urlparse(value.strip())
        host = (p.hostname or "").lower()
        if host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
            if p.path == "/watch":
                candidate = parse_qs(p.query).get("v", [""])[0]
            else:
                match = re.fullmatch(r"/(?:shorts|live|embed)/([\w-]{11})/?", p.path)
                candidate = match.group(1) if match else ""
        elif host in ("youtu.be", "www.youtu.be"):
            candidate = p.path.strip("/")
        else:
            return None
        return candidate if re.fullmatch(r"[\w-]{11}", candidate) else None
    except ValueError:
        return None

url = st.text_input("Lien de la vidéo", placeholder="https://www.youtube.com/watch?v=...")
if st.button("✨ Transcrire la vidéo", type="primary"):
    st.session_state.pop("result", None)
    vid = extract_video_id(url)
    if not vid:
        st.error("Veuillez saisir un lien YouTube valide.")
    else:
        try:
            with st.spinner("Récupération des sous-titres…"):
                available = YouTubeTranscriptApi().list(vid)
                try:
                    track = available.find_transcript(["fr", "fr-FR"])
                except Exception:
                    try:
                        track = available.find_transcript(["en"])
                    except Exception:
                        track = next(iter(available))
                segments = track.fetch()
                transcript = "\n".join(s.text for s in segments if s.text.strip())
            if not transcript:
                st.warning("Les sous-titres récupérés sont vides.")
            else:
                st.session_state["result"] = (vid, track.language, transcript)
                st.success(f"Transcription récupérée — langue : {track.language}")
        except Exception:
            st.error("Impossible de récupérer les sous-titres. Ils peuvent être désactivés, indisponibles ou bloqués par YouTube.")
            st.info("Essayez une autre vidéo disposant de sous-titres.")

if "result" in st.session_state:
    vid, language, transcript = st.session_state["result"]
    st.subheader("Votre transcription")
    st.caption(f"Langue : {language} · {len(transcript.split())} mots")
    st.text_area("Texte à copier", transcript, height=360)
    st.download_button("⬇️ Télécharger la transcription (.txt)", data=transcript.encode("utf-8"), file_name=f"transcription_{vid}.txt", mime="text/plain", use_container_width=True)

st.divider()
st.caption("L’application récupère uniquement les sous-titres disponibles. Les requêtes peuvent être bloquées par YouTube selon l’hébergeur.")
