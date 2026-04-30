# TN2G Outdoor PDF Generator V3 - Google Drive GPX

Questa versione carica automaticamente il GPX su una cartella Google Drive e inserisce nel LaTeX un link cliccabile "Scarica traccia GPX".

## Secrets richiesti su Streamlit Cloud

Nelle impostazioni dell'app Streamlit Cloud, sezione Secrets, incolla:

```toml
drive_folder_id = "ID_DELLA_CARTELLA_DRIVE"

[gcp_service_account]
type = "service_account"
project_id = "..."
private_key_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "nome-service-account@progetto.iam.gserviceaccount.com"
client_id = "..."
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "..."
universe_domain = "googleapis.com"
```

Importante:
- non caricare mai il file JSON delle credenziali su GitHub;
- condividi la cartella Drive con l'email `client_email` del service account;
- l'app rende ogni GPX accessibile a chi ha il link.