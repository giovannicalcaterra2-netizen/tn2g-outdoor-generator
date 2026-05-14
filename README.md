# TN2G Outdoor PDF Generator V6 - Editoriale

Versione con template più vicino ai PDF TN2G Outdoor già prodotti:
- header editoriale;
- logo TN2G Outdoor se presente in `assets/logo_outdoor.png`;
- box highlight iniziale;
- info evento in tabella;
- mappa grande;
- note mappa;
- link GPX con bottone cliccabile;
- geocaching opzionale;
- mood finale.

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

## Logo

Aggiungi nel repository:

```text
assets/logo_outdoor.png
```

Se il file non esiste, il PDF viene generato senza logo.
