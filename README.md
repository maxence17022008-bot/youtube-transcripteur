# 🎬 YouTube Transcripteur

Application web Streamlit en français : collez un lien YouTube, récupérez les sous-titres accessibles, copiez-les ou téléchargez-les en .txt.

## Déploiement Streamlit Community Cloud
1. Connectez-vous à https://share.streamlit.io/ via GitHub.
2. Sélectionnez le dépôt `maxence17022008-bot/youtube-transcripteur`.
3. Branche : `main` ; fichier principal : `app.py`.
4. Cliquez sur **Deploy** et récupérez l'URL publique.

## En local
```sh
pip install -r requirements.txt
streamlit run app.py
```

**Limites :** il faut des sous-titres accessibles (automatiques ou manuels). Cette application ne transcrit pas directement l'audio. YouTube peut bloquer les requêtes des hébergeurs cloud.
