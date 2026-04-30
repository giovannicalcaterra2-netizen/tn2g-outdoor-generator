# TN2G Outdoor PDF Generator

Questo è uno strumento semplice per generare un pacchetto LaTeX standardizzato per le uscite TN2G Outdoor.

## Cosa fa

Andrea compila un form, carica:
- immagine del percorso / mappa
- profilo altimetrico opzionale
- traccia GPX opzionale

Lo strumento genera:
- file `.tex` già impaginato
- cartella `uploads`
- pacchetto ZIP pronto da caricare su Overleaf
- PDF diretto solo se sul computer/server è installato LaTeX

## Installazione

Apri il terminale nella cartella del progetto e lancia:

```bash
pip install -r requirements.txt
streamlit run app.py
```

Poi apri il link che Streamlit mostra nel browser.

## Uso consigliato

Per la V1:
1. Andrea compila i dati.
2. Carica una mappa già pronta come PNG/JPG.
3. Carica eventuale profilo altimetrico.
4. Scarica lo ZIP.
5. Tu apri lo ZIP su Overleaf e compili.

## Per compilare automaticamente il PDF

Serve installare una distribuzione LaTeX, ad esempio:
- MiKTeX su Windows
- TeX Live su Linux/Mac

Dopo l'installazione, puoi spuntare "Prova a compilare automaticamente il PDF".