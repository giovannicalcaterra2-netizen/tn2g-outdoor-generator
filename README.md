# TN2G Outdoor Generator 2.0 — DEV

La branch `v2-dev` genera da un solo form:

- PDF LaTeX;
- traccia GPX con link Drive;
- grafica quadrata 1080 × 1080 costruita da Google Slides;
- caption TN2G;
- ZIP completo.

La branch `main`, usata dalla V1 di Andrea, non viene modificata.

## Grafica Google Slides

Il layout non viene più disegnato con coordinate Pillow. La V2:

1. copia il template Google Slides configurato, oppure importa il template
   PPTX incluso nel repository;
2. sostituisce testi, foto principale, mappa e profilo;
3. conserva una copia modificabile nel Drive dell'utente;
4. esporta la prima slide come PNG quadrato 1080 × 1080.

Template nativo creato per la V2:

```text
https://docs.google.com/presentation/d/1cZRdNfcMxnpBj6PRDDXFTp2EVpAfDfWcBWN3Kr9jk6Y/edit
```

Il file di fallback è:

```text
assets/TN2G_Outdoor_Graphic_Template.pptx
```

Questo fallback rende la generazione utilizzabile anche quando il token
`drive.file` non può leggere un template creato manualmente.

## Google Cloud

Nel progetto OAuth devono essere abilitate:

- Google Drive API;
- Google Slides API.

## Secrets Streamlit

Configurazione minima già compatibile con il caricamento GPX:

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

Configurazione consigliata per la grafica:

```toml
slides_template_id = "1cZRdNfcMxnpBj6PRDDXFTp2EVpAfDfWcBWN3Kr9jk6Y"
slides_output_folder_id = "1ebAfO2eBlpX7T8Z0t7VaIUhooSuJCGsd"
```

Entrambi sono opzionali:

- senza `slides_template_id`, la webapp importa il template PPTX incluso;
- senza `slides_output_folder_id`, usa `drive_folder_id`.

## Personalizzare il design

Puoi modificare colori, font, spazi e posizioni direttamente nel template
Google Slides. Non rinominare o rimuovere questi segnaposto:

```text
{{HERO_IMAGE}}
{{MAP_IMAGE}}
{{PROFILE_IMAGE}}
{{TITLE}}
{{SUBTITLE}}
{{DATE}}
{{MEETING_TIME}}
{{MEETING_POINT}}
{{DISTANCE}}
{{DURATION}}
{{ELEVATION}}
{{DIFFICULTY}}
{{ROUTE_TYPE}}
{{LUNCH}}
{{BRING_LINE}}
{{WEATHER}}
{{CTA}}
```

Se la copia del template nativo non è consentita dal token OAuth, la webapp
passa automaticamente al template incluso nel repository anziché bloccare il
kit.

## Streamlit Cloud

Dopo un aggiornamento della branch `v2-dev`:

```text
Manage app → Reboot app
```

`packages.txt` installa LaTeX e `poppler-utils`; quest'ultimo converte
mappe/profili PDF in PNG prima di inserirli nella grafica Slides.
