import streamlit as st
from pathlib import Path
import shutil
import zipfile
import subprocess
import re
from datetime import date
from jinja2 import Template

APP_DIR = Path(__file__).parent
OUTPUT_DIR = APP_DIR / "output"
UPLOAD_DIR = OUTPUT_DIR / "uploads"
TEMPLATE_PATH = APP_DIR / "templates" / "outdoor_template.tex.j2"

OUTPUT_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def latex_escape(text: str) -> str:
    """
    Escape basic LaTeX special chars.
    URLs are handled separately in the template, so avoid using this for raw links.
    """
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


def zip_output(folder: Path, zip_path: Path):
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for file in folder.rglob("*"):
            if file.is_file():
                z.write(file, file.relative_to(folder))
    return zip_path


def try_compile_pdf(tex_path: Path):
    """
    Compiles with latexmk if available, otherwise pdflatex.
    If neither exists, returns None.
    """
    cwd = tex_path.parent

    commands = [
        ["latexmk", "-pdf", "-interaction=nonstopmode", tex_path.name],
        ["pdflatex", "-interaction=nonstopmode", tex_path.name],
    ]

    for cmd in commands:
        try:
            result = subprocess.run(
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
    layout="centered"
)

st.title("🏔️ TN2G Outdoor PDF Generator")
st.caption("Compila i dati dell'uscita, carica immagini/GPX e genera il pacchetto LaTeX standardizzato.")

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
        "Uscita outdoor tranquilla con camminata panoramica, pausa foto e momento chill finale."
    )

    programma = st.text_area(
        "Programma della giornata",
        "14:30 Ritrovo\n14:45 Partenza\n16:00 Pausa panoramica\n18:30 Rientro previsto"
    )

    cosa_portare = st.text_area(
        "Cosa portare",
        "Scarpe comode\nAcqua\nSnack\nGiacca antivento\nTessera trasporti, se necessaria"
    )

    sicurezza = st.text_area(
        "Note sicurezza",
        "Percorso non tecnico. Prestare attenzione nei tratti sterrati e in caso di fondo umido."
    )

    meteo = st.text_area(
        "Note meteo",
        "Controllare il meteo il giorno stesso. In caso di peggioramento l'evento può essere modificato."
    )

    link_utili = st.text_area(
        "Link utili, uno per riga",
        "https://www.meteotrentino.it/"
    )

    st.subheader("File da caricare")

    mappa = st.file_uploader("Immagine percorso / mappa", type=["png", "jpg", "jpeg", "pdf"])
    profilo = st.file_uploader("Profilo altimetrico, opzionale", type=["png", "jpg", "jpeg", "pdf"])
    gpx = st.file_uploader("Traccia GPX", type=["gpx"])

    compile_pdf = st.checkbox(
        "Prova a compilare automaticamente il PDF, se LaTeX è installato sul computer/server",
        value=False
    )

    submitted = st.form_submit_button("Genera pacchetto LaTeX")

if submitted:
    event_slug = safe_filename(titolo)
    event_dir = OUTPUT_DIR / event_slug

    if event_dir.exists():
        shutil.rmtree(event_dir)
    event_dir.mkdir(parents=True, exist_ok=True)
    (event_dir / "uploads").mkdir(exist_ok=True)

    # Reset global upload dir for this generation
    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    mappa_path = save_upload(mappa, "mappa_percorso")
    profilo_path = save_upload(profilo, "profilo_altimetrico")
    gpx_path = save_upload(gpx, "traccia_gpx")

    # Move uploads into event dir
    for file in UPLOAD_DIR.glob("*"):
        shutil.copy(file, event_dir / "uploads" / file.name)

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
        "link_utili": [x.strip() for x in link_utili.splitlines() if x.strip()],
        "mappa_path": mappa_path,
        "profilo_path": profilo_path,
        "gpx_path": gpx_path,
    }

    tex_content = template.render(**data)
    tex_path = event_dir / f"{event_slug}.tex"
    tex_path.write_text(tex_content, encoding="utf-8")

    # Add a small compile helper
    (event_dir / "COMPILA.bat").write_text(
        f"pdflatex -interaction=nonstopmode {event_slug}.tex\npdflatex -interaction=nonstopmode {event_slug}.tex\npause\n",
        encoding="utf-8"
    )

    (event_dir / "README.txt").write_text(
        "Questo pacchetto contiene il file LaTeX generato e gli upload associati.\n"
        "Per compilare localmente: apri il file .tex in Overleaf oppure usa COMPILA.bat se hai LaTeX installato su Windows.\n",
        encoding="utf-8"
    )

    pdf_path = None
    if compile_pdf:
        pdf_path = try_compile_pdf(tex_path)

    zip_path = OUTPUT_DIR / f"{event_slug}_pacchetto_latex.zip"
    zip_output(event_dir, zip_path)

    st.success("Pacchetto generato!")

    with open(zip_path, "rb") as f:
        st.download_button(
            "Scarica pacchetto LaTeX ZIP",
            data=f,
            file_name=zip_path.name,
            mime="application/zip"
        )

    if pdf_path and pdf_path.exists():
        with open(pdf_path, "rb") as f:
            st.download_button(
                "Scarica PDF compilato",
                data=f,
                file_name=pdf_path.name,
                mime="application/pdf"
            )
    elif compile_pdf:
        st.warning("Pacchetto creato, ma la compilazione automatica non è riuscita. Apri il .tex su Overleaf oppure installa LaTeX.")