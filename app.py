import re
import shutil
import subprocess
import zipfile
from pathlib import Path

import streamlit as st
from jinja2 import Template

from googleapiclient.http import MediaFileUpload

from caption_generator import generate_fallback_caption
from google_services import build_drive_service
from slides_graphic_generator import generate_slides_graphic


APP_DIR = Path(__file__).parent
OUTPUT_DIR = APP_DIR / "output"
UPLOAD_DIR = OUTPUT_DIR / "uploads"
TEMPLATE_PATH = APP_DIR / "templates" / "outdoor_template.tex.j2"
DEFAULT_LOGO_PATH = APP_DIR / "assets" / "logo_outdoor.png"

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


def latex_paragraphs(text: str) -> str:
    escaped = latex_escape(text or "")
    lines = [line.strip() for line in escaped.splitlines()]
    paragraphs = []
    current = []
    for line in lines:
        if not line:
            if current:
                paragraphs.append(" ".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(" ".join(current))
    return "\n\n".join(paragraphs)


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


def parse_list(raw: str):
    return [latex_escape(line.strip()) for line in raw.splitlines() if line.strip()]


def raw_list(raw: str):
    return [line.strip() for line in raw.splitlines() if line.strip()]


def parse_geocaches(raw: str):
    geocaches = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        if "|" in line:
            label, url = line.split("|", 1)
            label, url = label.strip(), url.strip()
        else:
            label = line.strip()
            code = label.split()[0].strip()
            url = f"https://www.geocaching.com/geocache/{code}" if code.upper().startswith("GC") else ""

        geocaches.append({
            "label": latex_escape(label),
            "url": url,
        })

    return geocaches


def get_drive_service():
    return build_drive_service(st.secrets)


def upload_gpx_to_drive_oauth(local_file: Path, desired_name: str) -> str:
    if "drive_folder_id" not in st.secrets:
        raise RuntimeError("Secret mancante: drive_folder_id.")

    service = get_drive_service()

    file_metadata = {
        "name": desired_name,
        "parents": [st.secrets["drive_folder_id"]],
        "mimeType": "application/gpx+xml",
    }

    media = MediaFileUpload(str(local_file), mimetype="application/gpx+xml", resumable=False)

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
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in folder.rglob("*"):
            if file.is_file():
                archive.write(file, file.relative_to(folder))
    return zip_path


def compile_pdf_on_server(tex_path: Path):
    cwd = tex_path.parent
    commands = [
        ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_path.name],
    ]

    logs = []

    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
            logs.append(
                f"$ {' '.join(cmd)}\n\nSTDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            )
            pdf_path = tex_path.with_suffix(".pdf")
            if result.returncode == 0 and pdf_path.exists():
                return pdf_path, "\n\n---\n\n".join(logs)
        except FileNotFoundError as error:
            logs.append(f"Comando non trovato: {cmd[0]}\n{error}")
        except subprocess.TimeoutExpired as error:
            logs.append(f"Timeout durante la compilazione con {cmd[0]}.\n{error}")
        except Exception as error:
            logs.append(f"Errore durante la compilazione con {cmd[0]}:\n{error}")

    return None, "\n\n---\n\n".join(logs)


st.set_page_config(
    page_title="TN2G Outdoor Generator 2.0",
    page_icon="🏔️",
    layout="centered",
)

st.title("🏔️ TN2G Outdoor Generator 2.0")
st.caption("PDF, grafica quadrata Google Slides e caption da un unico form.")
st.info("Versione DEV collegata alla branch `v2-dev`. La V1 usata da Andrea non viene modificata.")

with st.form("event_form"):
    st.subheader("Info principali")

    col1, col2 = st.columns(2)
    with col1:
        titolo = st.text_input("Titolo evento", "Monte Calisio – Anello via Campèl")
        data_evento = st.text_input("Data / quando", "Domenica pomeriggio")
        luogo = st.text_input("Luogo", "Monte Calisio / Trento")
        ritrovo = st.text_input("Punto di ritrovo", "Parcheggio del Rifugio Campèl")
    with col2:
        ora_ritrovo = st.text_input("Ora ritrovo", "15:00")
        ora_rientro = st.text_input("Rientro previsto", "18:30")
        difficolta = st.selectbox("Difficoltà", ["Facile", "Media", "Impegnativa"])
        categoria = st.text_input("Tipologia", "Outdoor chill + social walk + viewpoint")

    st.subheader("Dati per la grafica 2.0")
    g1, g2, g3 = st.columns(3)
    with g1:
        tipo_percorso = st.selectbox(
            "Tipo di percorso",
            ["Anello", "Andata e ritorno", "Traversata", "Altro"],
        )
    with g2:
        pranzo = st.text_input("Pranzo", "Al sacco")
    with g3:
        meteo_breve = st.text_input(
            "Meteo / consiglio breve",
            "Controllare il meteo prima di partire",
        )

    st.subheader("Intro e mood")
    sottotitolo = st.text_input("Sottotitolo header", "Attività community Trentogether")
    highlight_title = st.text_input("Titolo box highlight iniziale", "Nuova attività outdoor TN2G")
    highlight = st.text_area(
        "Testo box highlight iniziale",
        "Una camminata outdoor chill sopra Trento, tra bosco, social talk, viewpoint e mood TN2G.",
    )

    st.subheader("Dati percorso")
    col3, col4, col5 = st.columns(3)
    with col3:
        km = st.text_input("Lunghezza", "6,6 km")
    with col4:
        dislivello = st.text_input("Dislivello positivo", "+350 m")
    with col5:
        durata = st.text_input("Durata prevista", "2,5–3 ore")

    come_arrivare = st.text_area(
        "Come arrivare / partenza effettiva",
        "Inizieremo direttamente dal punto di ritrovo imboccando il percorso ad anello.\nCon i mezzi: indicare qui eventuali bus, fermate o tratto a piedi.",
    )

    descrizione = st.text_area(
        "Il percorso",
        "Si tratta di una breve escursione quasi urbana, con vista sulla città di Trento e su un contesto tranquillo e rilassante.\n\nÈ una proposta perfetta per un’uscita TN2G: scenica, sociale, accessibile e senza stress.",
    )

    st.subheader("Programma e cose utili")
    programma = st.text_area(
        "Programma della giornata",
        "15:00 Ritrovo\n15:15 Partenza\n16:30 Pausa panoramica\n18:30 Rientro previsto",
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
        "Nota meteo",
        "Prima di partire controlliamo sempre il radar meteo.\nImportante: per leggere correttamente il radar, ricordate che l’orario può essere in UTC.",
    )

    st.subheader("Mappa e note")
    note_mappa = st.text_area(
        "Come leggere l'immagine, una voce per riga",
        "La linea colorata mostra il percorso previsto.\nIl grafico rappresenta il profilo altimetrico del giro.\nEventuali stelline o marker indicano punti di interesse lungo il percorso.",
    )

    st.subheader("Link utili")
    st.caption("Formato consigliato: Etichetta | https://link")
    link_utili = st.text_area(
        "Link utili, uno per riga",
        "MeteoTrentino | https://www.meteotrentino.it/",
    )

    st.subheader("Geocaching / Explorer mode")
    geocaching_intro = st.text_area(
        "Testo introduttivo geocaching, opzionale",
        "Durante la passeggiata potremo anche cercare alcuni geocache nascosti lungo la zona. Per chi non lo conoscesse, il geocaching è una sorta di caccia al tesoro GPS.",
    )
    geocaches = st.text_area("Codici geocache, uno per riga, opzionale", "")
    explorer_mission = st.text_area(
        "Mini-missione TN2G, opzionale",
        "Se riusciamo a trovarli durante il giro, potremo considerarli come una piccola missione explorer della community. Perfetto mix tra outdoor, esplorazione e nerd mode.",
    )

    st.subheader("Mood finale")
    mood_attivita = st.text_area(
        "Mood dell'attività",
        "Questa uscita è pensata come un outdoor social leggero, adatto a chi ha voglia di camminare in compagnia, vedere un angolo bello sopra Trento e fare due chiacchiere senza stress.",
    )

    st.subheader("File da caricare")
    foto_copertina = st.file_uploader(
        "Foto principale per la grafica quadrata",
        type=["png", "jpg", "jpeg", "webp"],
    )
    mappa = st.file_uploader(
        "Immagine percorso / mappa",
        type=["png", "jpg", "jpeg", "pdf"],
    )
    profilo = st.file_uploader(
        "Profilo altimetrico, opzionale",
        type=["png", "jpg", "jpeg", "pdf"],
    )
    gpx = st.file_uploader("Traccia GPX", type=["gpx"])

    upload_drive = st.checkbox(
        "Carica automaticamente il GPX sul mio Google Drive e inserisci link cliccabile",
        value=True,
    )
    generate_pdf = st.checkbox("Genera direttamente il PDF nella webapp", value=True)
    generate_graphic = st.checkbox(
        "Genera la grafica quadrata 1080 × 1080 con Google Slides",
        value=True,
    )
    generate_caption = st.checkbox("Genera la caption TN2G", value=True)

    submitted = st.form_submit_button("Genera kit TN2G 2.0")

if submitted:
    event_slug = safe_filename(titolo)
    event_dir = OUTPUT_DIR / event_slug

    if event_dir.exists():
        shutil.rmtree(event_dir)

    event_dir.mkdir(parents=True, exist_ok=True)
    (event_dir / "uploads").mkdir(exist_ok=True)
    (event_dir / "assets").mkdir(exist_ok=True)

    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    cover_path = save_upload(foto_copertina, "foto_copertina")
    mappa_path = save_upload(mappa, "mappa_percorso")
    profilo_path = save_upload(profilo, "profilo_altimetrico")
    gpx_path = save_upload(gpx, "traccia")

    for file in UPLOAD_DIR.glob("*"):
        shutil.copy(file, event_dir / "uploads" / file.name)

    logo_path = ""
    if DEFAULT_LOGO_PATH.exists():
        shutil.copy(DEFAULT_LOGO_PATH, event_dir / "assets" / "logo_outdoor.png")
        logo_path = "assets/logo_outdoor.png"

    gpx_download_link = ""
    drive_warning = ""

    if gpx_path and upload_drive:
        try:
            local_gpx = event_dir / gpx_path
            drive_name = f"{event_slug}.gpx"
            gpx_download_link = upload_gpx_to_drive_oauth(local_gpx, drive_name)
            st.success("GPX caricato sul tuo Google Drive e link generato.")
        except Exception as error:
            drive_warning = str(error)
            st.warning(f"Pacchetto creato, ma upload GPX su Drive non riuscito: {error}")

    template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))

    data = {
        "titolo": latex_escape(titolo),
        "data_evento": latex_escape(data_evento),
        "luogo": latex_escape(luogo),
        "sottotitolo": latex_escape(sottotitolo),
        "highlight_title": latex_escape(highlight_title),
        "highlight": latex_paragraphs(highlight),
        "ritrovo": latex_escape(ritrovo),
        "ora_ritrovo": latex_escape(ora_ritrovo),
        "ora_rientro": latex_escape(ora_rientro),
        "difficolta": latex_escape(difficolta),
        "categoria": latex_escape(categoria),
        "km": latex_escape(km),
        "dislivello": latex_escape(dislivello),
        "durata": latex_escape(durata),
        "come_arrivare": latex_paragraphs(come_arrivare),
        "descrizione": latex_paragraphs(descrizione),
        "programma": parse_list(programma),
        "cosa_portare": parse_list(cosa_portare),
        "sicurezza": latex_paragraphs(sicurezza),
        "meteo": latex_paragraphs(meteo),
        "note_mappa": parse_list(note_mappa),
        "links": parse_links(link_utili),
        "geocaching_intro": latex_paragraphs(geocaching_intro),
        "geocaches": parse_geocaches(geocaches),
        "explorer_mission": latex_paragraphs(explorer_mission),
        "mood_attivita": latex_paragraphs(mood_attivita),
        "mappa_path": mappa_path,
        "profilo_path": profilo_path,
        "gpx_path": gpx_path,
        "gpx_download_link": gpx_download_link,
        "logo_path": logo_path,
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
        "Kit TN2G Outdoor 2.0 generato automaticamente.\n"
        "Contiene il materiale prodotto dalla webapp e gli allegati caricati.\n",
        encoding="utf-8",
    )

    pdf_path = None
    compile_log = ""
    if generate_pdf:
        with st.spinner("Compilo il PDF su Streamlit Cloud..."):
            pdf_path, compile_log = compile_pdf_on_server(tex_path)

    graphic_path = None
    graphic_error = ""
    slides_presentation_url = ""
    if generate_graphic:
        try:
            graphic_path = event_dir / f"{event_slug}_grafica_quadrata.png"
            slides_result = generate_slides_graphic(
                graphic_path,
                secrets=st.secrets,
                title=titolo,
                subtitle=f"TN2G Outdoor · {tipo_percorso}",
                date_text=data_evento,
                meeting_time=ora_ritrovo,
                meeting_place=ritrovo,
                distance=km,
                elevation=dislivello,
                duration=durata,
                difficulty=difficolta,
                route_type=tipo_percorso,
                lunch=pranzo,
                weather=meteo_breve,
                bring_items=raw_list(cosa_portare),
                cover_path=(event_dir / cover_path) if cover_path else None,
                map_path=(event_dir / mappa_path) if mappa_path else None,
                profile_path=(event_dir / profilo_path) if profilo_path else None,
            )
            slides_presentation_url = slides_result["presentation_url"]
            st.success(
                "Grafica generata con Google Slides. "
                "Resta anche una copia modificabile nel tuo Drive."
            )
        except Exception as error:
            graphic_error = str(error)
            st.warning(f"PDF elaborato, ma grafica Slides non generata: {error}")

    caption_text = ""
    caption_path = None
    if generate_caption:
        caption_text = generate_fallback_caption(
            title=titolo,
            date_text=data_evento,
            meeting_time=ora_ritrovo,
            meeting_place=ritrovo,
            distance=km,
            elevation=dislivello,
            duration=durata,
            difficulty=difficolta,
            lunch=pranzo,
            intro=highlight,
            route_description=descrizione,
            bring_items=raw_list(cosa_portare),
            return_time=ora_rientro,
            mood=mood_attivita,
        )
        caption_path = event_dir / f"{event_slug}_caption.txt"
        caption_path.write_text(caption_text, encoding="utf-8")

    kit_zip_path = OUTPUT_DIR / f"{event_slug}_kit_tn2g_v2.zip"
    zip_output(event_dir, kit_zip_path)

    st.session_state["v2_results"] = {
        "event_slug": event_slug,
        "pdf_path": str(pdf_path) if pdf_path else "",
        "compile_log": compile_log,
        "graphic_path": str(graphic_path) if graphic_path and graphic_path.exists() else "",
        "graphic_error": graphic_error,
        "slides_presentation_url": slides_presentation_url,
        "caption_text": caption_text,
        "caption_path": str(caption_path) if caption_path else "",
        "kit_zip_path": str(kit_zip_path),
        "tex_path": str(tex_path),
        "gpx_download_link": gpx_download_link,
        "drive_warning": drive_warning,
    }

    st.success("Kit TN2G 2.0 generato.")

results = st.session_state.get("v2_results")
if results:
    st.divider()
    pdf_tab, graphic_tab, caption_tab, kit_tab = st.tabs(
        ["📄 PDF", "🎨 Grafica", "✍️ Caption", "📦 Kit completo"]
    )

    with pdf_tab:
        pdf_path = Path(results["pdf_path"]) if results["pdf_path"] else None
        if pdf_path and pdf_path.exists():
            st.download_button(
                "Scarica PDF finale",
                data=pdf_path.read_bytes(),
                file_name=pdf_path.name,
                mime="application/pdf",
            )
        else:
            st.error("Il PDF non è stato generato.")
            if results["compile_log"]:
                with st.expander("Mostra log compilazione LaTeX"):
                    st.code(results["compile_log"])

        if results["gpx_download_link"]:
            st.success("Nel PDF è presente il link GPX scaricabile.")
            st.code(results["gpx_download_link"])
        elif results["drive_warning"]:
            st.warning(f"Link GPX non inserito: {results['drive_warning']}")

    with graphic_tab:
        graphic_path = Path(results["graphic_path"]) if results["graphic_path"] else None
        if graphic_path and graphic_path.exists():
            st.image(
                str(graphic_path),
                caption="Anteprima grafica quadrata Google Slides 1080 × 1080",
            )
            st.download_button(
                "Scarica grafica quadrata",
                data=graphic_path.read_bytes(),
                file_name=graphic_path.name,
                mime="image/png",
            )
            if results.get("slides_presentation_url"):
                st.link_button(
                    "Apri e modifica in Google Slides",
                    results["slides_presentation_url"],
                )
        else:
            st.error("La grafica non è stata generata.")
            if results["graphic_error"]:
                st.code(results["graphic_error"])

    with caption_tab:
        caption_key = f"caption_editor_{results['event_slug']}"
        if caption_key not in st.session_state:
            st.session_state[caption_key] = results["caption_text"]

        st.text_area(
            "Caption pronta da copiare e modificare",
            key=caption_key,
            height=430,
        )
        st.download_button(
            "Scarica caption TXT",
            data=st.session_state[caption_key].encode("utf-8"),
            file_name=f"{results['event_slug']}_caption.txt",
            mime="text/plain",
        )
        st.caption("Questa prima versione usa un template automatico. Il collegamento Gemini arriverà nello step successivo.")

    with kit_tab:
        kit_path = Path(results["kit_zip_path"])
        if kit_path.exists():
            st.download_button(
                "Scarica kit TN2G completo",
                data=kit_path.read_bytes(),
                file_name=kit_path.name,
                mime="application/zip",
            )
        st.caption("Il kit include PDF se compilato, grafica, caption, LaTeX, immagini e GPX.")
