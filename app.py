import re
import shutil
import subprocess
import zipfile
from datetime import date
from pathlib import Path

import streamlit as st
from jinja2 import Template

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


APP_DIR = Path(__file__).parent
OUTPUT_DIR = APP_DIR / "output"
UPLOAD_DIR = OUTPUT_DIR / "uploads"
TEMPLATE_PATH = APP_DIR / "templates" / "outdoor_template.tex.j2"

OUTPUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def latex_escape(text: str) -> str:
    if text is None:
        return ""
    text = str(text)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(c, c) for c in text)


def safe_filename(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_\-]+", "_", name)
    return name.strip("_") or "evento_outdoor"


def save_upload(uploaded_file, target_name: str):
    if uploaded_file is None:
        return ""
    suffix = Path(uploaded_file.name).suffix.lower()
    filename = f"{target_name}{suffix}"
    target = UPLOAD_DIR / filename
    with open(target, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return f"uploads/{filename}"


def parse_links(raw: str):
    links = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        if "|" in line:
            label, url = line.split("|", 1)
            label, url = label.strip(), url.strip()
        else:
            label, url = "", line

        if url.startswith(("http://", "https://", "mailto:")):
            links.append({"label": latex_escape(label), "url": url})
        else:
            links.append({"label": latex_escape(line), "url": ""})

    return links


def get_drive_service():
    if "oauth_token" not in st.secrets:
        raise RuntimeError("Secrets mancanti: sezione [oauth_token].")

    token = dict(st.secrets["oauth_token"])
    required = ["token", "refresh_token", "token_uri", "client_id", "client_secret", "scopes"]
    missing = [k for k in required if k not in token]

    if missing:
        raise RuntimeError(f"Secrets OAuth incompleti. Mancano: {', '.join(missing)}")

    creds = Credentials(
        token=token["token"],
        refresh_token=token["refresh_token"],
        token_uri=token["token_uri"],
        client_id=token["client_id"],
        client_secret=token["client_secret"],
        scopes=list(token["scopes"]),
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

    return build("drive", "v3", credentials=creds)


def upload_gpx_to_drive_oauth(local_file: Path, desired_name: str) -> str:
    if "drive_folder_id" not in st.secrets:
        raise RuntimeError("Secret mancante: drive_folder_id.")

    folder_id = st.secrets["drive_folder_id"]
    service = get_drive_service()

    file_metadata = {
        "name": desired_name,
        "parents": [folder_id],
        "mimeType": "application/gpx+xml",
    }

    media = MediaFileUpload(
        str(local_file),
        mimetype="application/gpx+xml",
        resumable=False,
    )

    created = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink, webContentLink",
    ).execute()

    file_id = created["id"]

    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        fields="id",
    ).execute()

    return f"https://drive.google.com/uc?export=download&id={file_id}"


def zip_output(folder: Path, zip_path: Path):
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for file in folder.rglob("*"):
            if file.is_file():
                z.write(file, file.relative_to(folder))
    return zip_path


def try_compile_pdf(tex_path: Path):
    cwd = tex_path.parent
    commands = [
        ["latexmk", "-pdf", "-interaction=nonstopmode", tex_path.name],
        ["pdflatex", "-interaction=nonstopmode", tex_path.name],
    ]

    for cmd in commands:
        try:
            subprocess.run(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60,
            )
            pdf_path = tex_path.with_suffix(".pdf")
            if pdf_path.exists():
                return pdf_path
        except Exception:
            continue

    return None


st.set_page_config(
    page_title="TN2G Outdoor PDF Generator",
    page_icon="🏔️",
    layout="centered",
)

st.title("🏔️ TN2G Outdoor PDF Generator")
st.caption("Genera schede Outdoor standardizzate. V5: upload GPX su Google Drive con OAuth utente.")

with st.form("event_form"):
    st.subheader("Info principali")

    col1, col2 = st.columns(2)
    with col1:
        titolo = st.text_input("Titolo evento", "Sentiero dei Castagni")
        data_evento = st.date_input("Data", value=date.today())
        luogo = st.text_input("Luogo", "Sardagna / Trento")
        ritrovo = st.text_input("Punto di ritrovo", "Funivia Sardagna")

    with col2:
        ora_ritrovo = st.text_input("Ora ritrovo", "14:30")
        ora_rientro = st.text_input("Rientro previsto", "18:30")
        difficolta = st.selectbox("Difficoltà", ["Facile", "Media", "Impegnativa"])
        categoria = st.text_input("Categoria", "Outdoor")

    st.subheader("Dati percorso")

    col3, col4, col5 = st.columns(3)
    with col3:
        km = st.text_input("Lunghezza", "7 km")
    with col4:
        dislivello = st.text_input("Dislivello positivo", "+300 m")
    with col5:
        durata = st.text_input("Durata cammino", "2h 30min")

    descrizione = st.text_area(
        "Descrizione breve",
        "Uscita outdoor tranquilla con camminata panoramica, pausa foto e momento chill finale.",
    )

    programma = st.text_area(
        "Programma della giornata",
        "14:30 Ritrovo\n14:45 Partenza\n16:00 Pausa panoramica\n18:30 Rientro previsto",
    )

    cosa_portare = st.text_area(
        "Cosa portare",
        "Scarpe comode\nAcqua\nSnack\nGiacca antivento\nTessera trasporti, se necessaria",
    )

    sicurezza = st.text_area(
        "Note sicurezza",
        "Percorso non tecnico. Prestare attenzione nei tratti sterrati e in caso di fondo umido.",
    )

    meteo = st.text_area(
        "Note meteo",
        "Controllare il meteo il giorno stesso.\nIn caso di peggioramento l'evento può essere modificato.",
    )

    st.subheader("Link utili")
    st.caption("Formato consigliato: Etichetta | https://link")
    link_utili = st.text_area(
        "Link utili, uno per riga",
        "MeteoTrentino | https://www.meteotrentino.it/",
    )

    st.subheader("File da caricare")

    mappa = st.file_uploader("Immagine percorso / mappa", type=["png", "jpg", "jpeg", "pdf"])
    profilo = st.file_uploader("Profilo altimetrico, opzionale", type=["png", "jpg", "jpeg", "pdf"])
    gpx = st.file_uploader("Traccia GPX", type=["gpx"])

    upload_drive = st.checkbox(
        "Carica automaticamente il GPX sul mio Google Drive e inserisci link cliccabile",
        value=True,
    )

    compile_pdf = st.checkbox(
        "Prova a compilare automaticamente il PDF, se LaTeX è installato",
        value=False,
    )

    submitted = st.form_submit_button("Genera pacchetto LaTeX")

if submitted:
    event_slug = safe_filename(titolo)
    event_dir = OUTPUT_DIR / event_slug

    if event_dir.exists():
        shutil.rmtree(event_dir)

    event_dir.mkdir(parents=True, exist_ok=True)
    (event_dir / "uploads").mkdir(exist_ok=True)

    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    mappa_path = save_upload(mappa, "mappa_percorso")
    profilo_path = save_upload(profilo, "profilo_altimetrico")
    gpx_path = save_upload(gpx, "traccia_gpx")

    for file in UPLOAD_DIR.glob("*"):
        shutil.copy(file, event_dir / "uploads" / file.name)

    gpx_download_link = ""

    if gpx_path and upload_drive:
        try:
            local_gpx = event_dir / gpx_path
            drive_name = f"{event_slug}_{data_evento.strftime('%Y%m%d')}.gpx"
            gpx_download_link = upload_gpx_to_drive_oauth(local_gpx, drive_name)
            st.success("GPX caricato sul tuo Google Drive e link generato.")
        except Exception as e:
            st.warning(f"Pacchetto creato, ma upload GPX su Drive non riuscito: {e}")

    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))

    data = {
        "titolo": latex_escape(titolo),
        "data_evento": latex_escape(data_evento.strftime("%d/%m/%Y")),
        "luogo": latex_escape(luogo),
        "ritrovo": latex_escape(ritrovo),
        "ora_ritrovo": latex_escape(ora_ritrovo),
        "ora_rientro": latex_escape(ora_rientro),
        "difficolta": latex_escape(difficolta),
        "categoria": latex_escape(categoria),
        "km": latex_escape(km),
        "dislivello": latex_escape(dislivello),
        "durata": latex_escape(durata),
        "descrizione": latex_escape(descrizione).replace("\n", r"\\ " + "\n"),
        "programma": [latex_escape(x) for x in programma.splitlines() if x.strip()],
        "cosa_portare": [latex_escape(x) for x in cosa_portare.splitlines() if x.strip()],
        "sicurezza": latex_escape(sicurezza).replace("\n", r"\\ " + "\n"),
        "meteo": latex_escape(meteo).replace("\n", r"\\ " + "\n"),
        "links": parse_links(link_utili),
        "mappa_path": mappa_path,
        "profilo_path": profilo_path,
        "gpx_path": gpx_path,
        "gpx_download_link": gpx_download_link,
    }

    tex_content = template.render(**data)
    tex_path = event_dir / f"{event_slug}.tex"
    tex_path.write_text(tex_content, encoding="utf-8")

    (event_dir / "COMPILA.bat").write_text(
        f"pdflatex -interaction=nonstopmode {event_slug}.tex\n"
        f"pdflatex -interaction=nonstopmode {event_slug}.tex\n"
        "pause\n",
        encoding="utf-8",
    )

    (event_dir / "README.txt").write_text(
        "Pacchetto LaTeX generato automaticamente.\n"
        "Il GPX resta anche nella cartella uploads. Se l'upload OAuth funziona, il PDF include anche il link Drive cliccabile.\n",
        encoding="utf-8",
    )

    pdf_path = None
    if compile_pdf:
        pdf_path = try_compile_pdf(tex_path)

    zip_path = OUTPUT_DIR / f"{event_slug}_pacchetto_latex.zip"
    zip_output(event_dir, zip_path)

    st.success("Pacchetto generato!")

    if gpx_download_link:
        st.info(f"Link GPX generato: {gpx_download_link}")

    with open(zip_path, "rb") as f:
        st.download_button(
            "Scarica pacchetto LaTeX ZIP",
            data=f,
            file_name=zip_path.name,
            mime="application/zip",
        )

    if pdf_path and pdf_path.exists():
        with open(pdf_path, "rb") as f:
            st.download_button(
                "Scarica PDF compilato",
                data=f,
                file_name=pdf_path.name,
                mime="application/pdf",
            )
    elif compile_pdf:
        st.warning("Pacchetto creato, ma la compilazione automatica non è riuscita.")