# TN2G Outdoor PDF Generator V7 - Autocompile

Questa versione compila direttamente il PDF su Streamlit Cloud.

## File nuovi/importanti

- app.py
- requirements.txt
- packages.txt
- templates/outdoor_template.tex.j2
- assets/logo_outdoor.png opzionale

## Streamlit Cloud

Il file `packages.txt` installa LaTeX sul server Streamlit Cloud. Dopo il commit, fai Reboot app.

## Logo

Carica nel repository:

```text
assets/logo_outdoor.png
```

Se il file non esiste, il PDF viene generato senza logo.

## Secrets Streamlit richiesti

```toml
drive_folder_id = "ID_CARTELLA_DRIVE"

[oauth_token]
token = "..."
refresh_token = "..."
token_uri = "https://oauth2.googleapis.com/token"
client_id = "..."
client_secret = "..."
scopes = ["https://www.googleapis.com/auth/drive.file"]
```
