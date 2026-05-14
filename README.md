# TN2G Outdoor PDF Generator V5 - OAuth Drive

Questa versione carica il GPX sul tuo Google Drive usando OAuth utente, non service account.

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

I valori arrivano dal file locale `token.json`.
Non caricare mai `token.json` su GitHub.