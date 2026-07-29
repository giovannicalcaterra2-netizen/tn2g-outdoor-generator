"""Generazione della locandina quadrata tramite Google Slides.

Il layout vive in un template Google Slides/PPTX. Python non disegna la
locandina: duplica/importa il template, sostituisce testi e riquadri immagine,
poi scarica la thumbnail nativa della slide e la porta a 1080x1080.
"""

from __future__ import annotations

import io
import subprocess
from pathlib import Path
from typing import Iterable, Mapping, Optional

import requests
from PIL import Image, ImageOps
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

from google_services import build_google_services


SLIDES_MIME = "application/vnd.google-apps.presentation"
PPTX_MIME = (
    "application/vnd.openxmlformats-officedocument.presentationml.presentation"
)
DEFAULT_TEMPLATE_PATH = (
    Path(__file__).parent / "assets" / "TN2G_Outdoor_Graphic_Template.pptx"
)
DEFAULT_CTA = "PRENOTAZIONI SU @OUTDOOR"


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def _compact_items(items: Iterable[str], max_items: int = 4) -> str:
    cleaned = [_clean(item) for item in items if _clean(item)][:max_items]
    if not cleaned:
        return "Porta acqua e abbigliamento adatto al meteo"
    return "DA PORTARE  ·  " + "  •  ".join(cleaned)


def _friendly_google_error(error: Exception) -> RuntimeError:
    message = str(error)
    if isinstance(error, HttpError):
        status = getattr(error.resp, "status", None)
        if status in (401, 403) and (
            "accessNotConfigured" in message
            or "Google Slides API" in message
            or "SERVICE_DISABLED" in message
        ):
            return RuntimeError(
                "Google Slides API non è abilitata nel progetto Google Cloud. "
                "Abilitala, attendi un minuto e riprova."
            )
        if status in (401, 403) and (
            "insufficientPermissions" in message
            or "ACCESS_TOKEN_SCOPE_INSUFFICIENT" in message
        ):
            return RuntimeError(
                "Il token OAuth non include i permessi necessari per Slides. "
                "Rigenera token.json includendo drive.file e presentations, "
                "poi aggiorna i Secrets della V2."
            )
        if status in (401, 403):
            return RuntimeError(
                "Google ha rifiutato l'accesso a Drive/Slides. Controlla il "
                "refresh token OAuth e che la cartella configurata sia "
                "accessibile allo stesso account Google."
            )
        if status == 404:
            return RuntimeError(
                "Template Google Slides non accessibile. Rimuovi "
                "slides_template_id dai Secrets per usare il template incluso "
                "nel repository, oppure autorizza quel file all'app OAuth."
            )
    return RuntimeError(message)


def _presentation_metadata(
    *,
    title: str,
    parent_folder_id: Optional[str],
) -> dict:
    metadata = {"name": title, "mimeType": SLIDES_MIME}
    if parent_folder_id:
        metadata["parents"] = [parent_folder_id]
    return metadata


def _create_working_presentation(
    drive,
    *,
    title: str,
    parent_folder_id: Optional[str],
    template_presentation_id: Optional[str],
    template_path: Path,
) -> tuple[str, bool]:
    """Copia un template nativo oppure importa il PPTX incluso nel repo.

    Il fallback PPTX rende la V2 utilizzabile anche con il solo scope
    drive.file, perché il file nativo viene creato direttamente dall'app.
    """
    if template_presentation_id:
        try:
            copied = (
                drive.files()
                .copy(
                    fileId=template_presentation_id,
                    body=_presentation_metadata(
                        title=title,
                        parent_folder_id=parent_folder_id,
                    ),
                    fields="id,webViewLink",
                )
                .execute()
            )
            return copied["id"], True
        except HttpError:
            # Un template importato manualmente può non essere visibile a un
            # token drive.file. Il template locale evita di bloccare Andrea.
            pass

    if not template_path.exists():
        raise RuntimeError(
            f"Template Slides/PPTX non trovato: {template_path.as_posix()}"
        )

    media = MediaFileUpload(
        str(template_path),
        mimetype=PPTX_MIME,
        resumable=False,
    )
    created = (
        drive.files()
        .create(
            body=_presentation_metadata(
                title=title,
                parent_folder_id=parent_folder_id,
            ),
            media_body=media,
            fields="id,webViewLink",
        )
        .execute()
    )
    return created["id"], False


def _prepare_raster_image(
    path: Path,
    *,
    scratch_dir: Path,
    stem: str,
) -> Path:
    """Converte PDF/WebP in PNG quando Slides non può usarli direttamente."""
    suffix = path.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg"}:
        return path

    output = scratch_dir / f"{stem}.png"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    if suffix == ".pdf":
        output_stem = output.with_suffix("")
        try:
            subprocess.run(
                [
                    "pdftoppm",
                    "-f",
                    "1",
                    "-singlefile",
                    "-png",
                    "-r",
                    "160",
                    str(path),
                    str(output_stem),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "Per usare mappe/profili PDF manca poppler-utils sul server."
            ) from error
        except subprocess.CalledProcessError as error:
            details = error.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Impossibile convertire il PDF {path.name}: {details}"
            ) from error
        return output

    try:
        with Image.open(path) as image:
            image.convert("RGB").save(output, format="PNG")
    except Exception as error:
        raise RuntimeError(
            f"Formato immagine non supportato per la grafica: {path.name}"
        ) from error
    return output


def _upload_public_image(
    drive,
    *,
    path: Path,
    desired_name: str,
    parent_folder_id: Optional[str],
) -> tuple[str, str]:
    suffix = path.suffix.lower()
    mime_type = "image/png" if suffix == ".png" else "image/jpeg"
    metadata = {"name": desired_name}
    if parent_folder_id:
        metadata["parents"] = [parent_folder_id]

    media = MediaFileUpload(str(path), mimetype=mime_type, resumable=False)
    created = (
        drive.files()
        .create(
            body=metadata,
            media_body=media,
            fields="id",
        )
        .execute()
    )
    file_id = created["id"]
    (
        drive.permissions()
        .create(
            fileId=file_id,
            body={"type": "anyone", "role": "reader"},
            fields="id",
        )
        .execute()
    )
    return file_id, f"https://drive.google.com/uc?export=download&id={file_id}"


def _replace_text_requests(replacements: Mapping[str, str]) -> list[dict]:
    return [
        {
            "replaceAllText": {
                "containsText": {"text": marker, "matchCase": True},
                "replaceText": _clean(value),
            }
        }
        for marker, value in replacements.items()
    ]


def _replace_image_request(
    *,
    marker: str,
    url: str,
    crop: bool,
) -> dict:
    return {
        "replaceAllShapesWithImage": {
            "containsText": {"text": marker, "matchCase": True},
            "imageUrl": url,
            "replaceMethod": "CENTER_CROP" if crop else "CENTER_INSIDE",
        }
    }


def _download_thumbnail(
    slides,
    *,
    presentation_id: str,
    output_path: Path,
) -> str:
    presentation = (
        slides.presentations()
        .get(
            presentationId=presentation_id,
            fields="slides(objectId)",
        )
        .execute()
    )
    slide_ids = [
        slide["objectId"]
        for slide in presentation.get("slides", [])
        if slide.get("objectId")
    ]
    if not slide_ids:
        raise RuntimeError("Il template Google Slides non contiene slide.")

    thumb = (
        slides.presentations()
        .pages()
        .getThumbnail(
            presentationId=presentation_id,
            pageObjectId=slide_ids[0],
            thumbnailProperties_thumbnailSize="LARGE",
            thumbnailProperties_mimeType="PNG",
        )
        .execute()
    )
    response = requests.get(thumb["contentUrl"], timeout=60)
    response.raise_for_status()

    with Image.open(io.BytesIO(response.content)) as image:
        square = ImageOps.fit(
            image.convert("RGB"),
            (1080, 1080),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        square.save(output_path, format="PNG", optimize=True)
    return slide_ids[0]


def generate_slides_graphic(
    output_path: Path,
    *,
    secrets,
    title: str,
    subtitle: str,
    date_text: str,
    meeting_time: str,
    meeting_place: str,
    distance: str,
    elevation: str,
    duration: str,
    difficulty: str,
    route_type: str,
    lunch: str,
    weather: str,
    bring_items: Iterable[str],
    cover_path: Optional[Path] = None,
    map_path: Optional[Path] = None,
    profile_path: Optional[Path] = None,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
) -> dict:
    """Genera PNG e copia Google Slides modificabile.

    Ritorna path PNG, ID/URL della presentazione e se è stato usato il
    template nativo configurato oppure il fallback incluso nel repository.
    """
    temp_ids: list[str] = []
    presentation_id = ""
    try:
        _, drive, slides = build_google_services(secrets)
        preferred_folder_id = secrets.get("slides_output_folder_id") or None
        drive_folder_id = secrets.get("drive_folder_id") or None
        template_id = secrets.get("slides_template_id") or None

        presentation_title = f"TN2G — {_clean(title)}"
        folder_candidates = []
        for folder_id in [preferred_folder_id, drive_folder_id, None]:
            if folder_id not in folder_candidates:
                folder_candidates.append(folder_id)

        create_error = None
        parent_folder_id = None
        used_native_template = False
        for candidate_folder_id in folder_candidates:
            try:
                (
                    presentation_id,
                    used_native_template,
                ) = _create_working_presentation(
                    drive,
                    title=presentation_title,
                    parent_folder_id=candidate_folder_id,
                    template_presentation_id=template_id,
                    template_path=template_path,
                )
                parent_folder_id = candidate_folder_id
                create_error = None
                break
            except HttpError as error:
                create_error = error

        if create_error is not None or not presentation_id:
            raise create_error or RuntimeError(
                "Impossibile creare la copia Google Slides."
            )

        text_replacements = {
            "{{TITLE}}": _clean(title).upper(),
            "{{SUBTITLE}}": _clean(subtitle).upper(),
            "{{DATE}}": date_text,
            "{{MEETING_TIME}}": meeting_time,
            "{{MEETING_POINT}}": meeting_place,
            "{{DISTANCE}}": distance,
            "{{DURATION}}": duration,
            "{{ELEVATION}}": elevation,
            "{{DIFFICULTY}}": _clean(difficulty).upper(),
            "{{ROUTE_TYPE}}": _clean(route_type).upper(),
            "{{LUNCH}}": lunch,
            "{{BRING_LINE}}": _compact_items(bring_items),
            "{{WEATHER}}": weather,
            "{{CTA}}": DEFAULT_CTA,
        }
        requests_body = _replace_text_requests(text_replacements)

        scratch_dir = output_path.parent / ".slides-assets"
        image_specs = [
            ("{{HERO_IMAGE}}", cover_path or map_path, "hero", True),
            ("{{MAP_IMAGE}}", map_path, "mappa", False),
            ("{{PROFILE_IMAGE}}", profile_path, "profilo", False),
        ]

        for marker, source_path, stem, crop in image_specs:
            if source_path and source_path.exists():
                raster = _prepare_raster_image(
                    source_path,
                    scratch_dir=scratch_dir,
                    stem=stem,
                )
                file_id, image_url = _upload_public_image(
                    drive,
                    path=raster,
                    desired_name=f"{presentation_title} — {stem}{raster.suffix}",
                    parent_folder_id=parent_folder_id,
                )
                temp_ids.append(file_id)
                requests_body.append(
                    _replace_image_request(
                        marker=marker,
                        url=image_url,
                        crop=crop,
                    )
                )
            else:
                fallback = {
                    "{{HERO_IMAGE}}": "",
                    "{{MAP_IMAGE}}": "Mappa non caricata",
                    "{{PROFILE_IMAGE}}": "Profilo non caricato",
                }[marker]
                requests_body.extend(
                    _replace_text_requests({marker: fallback})
                )

        (
            slides.presentations()
            .batchUpdate(
                presentationId=presentation_id,
                body={"requests": requests_body},
            )
            .execute()
        )
        slide_id = _download_thumbnail(
            slides,
            presentation_id=presentation_id,
            output_path=output_path,
        )

        return {
            "png_path": output_path,
            "presentation_id": presentation_id,
            "presentation_url": (
                f"https://docs.google.com/presentation/d/"
                f"{presentation_id}/edit"
            ),
            "slide_id": slide_id,
            "used_native_template": used_native_template,
        }
    except Exception as error:
        raise _friendly_google_error(error) from error
    finally:
        # Le immagini sono già incorporate nella presentazione; eliminiamo
        # soltanto gli upload tecnici temporanei, mai la presentazione finale.
        if temp_ids:
            try:
                _, cleanup_drive, _ = build_google_services(secrets)
                for file_id in temp_ids:
                    try:
                        cleanup_drive.files().delete(fileId=file_id).execute()
                    except Exception:
                        pass
            except Exception:
                pass
