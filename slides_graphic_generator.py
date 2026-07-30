"""Generazione della locandina quadrata tramite Google Slides.

La V2 usa esclusivamente il template Google Slides configurato nei Secrets.
Non esiste più alcun fallback al vecchio PPTX incluso nel repository: se il
template non è accessibile, l'app mostra l'errore reale invece di produrre una
grafica con il layout precedente.
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
DEFAULT_CTA = "PRENOTAZIONI SU @OUTDOOR"


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def _secret_value(secrets, key: str) -> str:
    value = secrets.get(key, "")
    return str(value).strip() if value is not None else ""


def _compact_items(items: Iterable[str], max_items: int = 5) -> str:
    cleaned = [_clean(item) for item in items if _clean(item)][:max_items]
    if not cleaned:
        return "• Acqua\n• Scarpe adatte\n• Abbigliamento per il meteo"
    return "\n".join(f"• {item}" for item in cleaned)


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
            or "insufficient authentication scopes" in message.lower()
        ):
            return RuntimeError(
                "Il token OAuth non permette di copiare il template Slides. "
                "Rigenera token.json con gli scope "
                "https://www.googleapis.com/auth/drive e "
                "https://www.googleapis.com/auth/presentations, quindi aggiorna "
                "refresh_token e scopes nei Secrets della V2."
            )

        if status == 404:
            return RuntimeError(
                "Il template indicato da slides_template_id non è accessibile "
                "all'app OAuth. Con il solo scope drive.file Google può nascondere "
                "i file creati fuori dall'app. Rigenera token.json usando lo scope "
                "https://www.googleapis.com/auth/drive insieme a "
                "https://www.googleapis.com/auth/presentations."
            )

        if status in (401, 403):
            return RuntimeError(
                "Google ha rifiutato l'accesso a Drive/Slides. Controlla il "
                "refresh token, gli scope OAuth e che template e cartella output "
                "appartengano allo stesso account Google."
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


def _copy_configured_template(
    drive,
    *,
    template_presentation_id: str,
    title: str,
    parent_folder_id: Optional[str],
) -> str:
    """Duplica soltanto il template configurato nei Secrets."""
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
    return copied["id"]


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
                    "180",
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
                "Per usare mappe o profili PDF manca poppler-utils sul server."
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
                "replaceText": str(value or ""),
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
            "imageReplaceMethod": "CENTER_CROP" if crop else "CENTER_INSIDE",
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
    template_path: Optional[Path] = None,
) -> dict:
    """Genera il PNG usando obbligatoriamente slides_template_id."""
    del template_path  # Compatibilità con eventuali chiamate precedenti.

    temp_ids: list[str] = []
    drive = None
    presentation_id = ""

    try:
        template_id = _secret_value(secrets, "slides_template_id")
        if not template_id:
            raise RuntimeError(
                "Secret mancante: slides_template_id. La V2 non usa più il "
                "vecchio template PPTX del repository."
            )

        _, drive, slides = build_google_services(secrets)
        preferred_folder_id = _secret_value(
            secrets, "slides_output_folder_id"
        ) or None
        drive_folder_id = _secret_value(secrets, "drive_folder_id") or None

        presentation_title = f"TN2G — {_clean(title)}"
        folder_candidates: list[Optional[str]] = []
        for folder_id in [preferred_folder_id, drive_folder_id, None]:
            if folder_id not in folder_candidates:
                folder_candidates.append(folder_id)

        copy_error: Optional[Exception] = None
        parent_folder_id: Optional[str] = None
        for candidate_folder_id in folder_candidates:
            try:
                presentation_id = _copy_configured_template(
                    drive,
                    template_presentation_id=template_id,
                    title=presentation_title,
                    parent_folder_id=candidate_folder_id,
                )
                parent_folder_id = candidate_folder_id
                copy_error = None
                break
            except HttpError as error:
                copy_error = error

        if not presentation_id:
            raise copy_error or RuntimeError(
                "Impossibile duplicare il template Google Slides configurato."
            )

        text_replacements = {
            "{{TITLE}}": _clean(title).upper(),
            "{{SUBTITLE}}": _clean(subtitle).upper(),
            "{{DATE}}": _clean(date_text),
            "{{MEETING_TIME}}": _clean(meeting_time),
            "{{MEETING_POINT}}": _clean(meeting_place),
            "{{DISTANCE}}": _clean(distance),
            "{{DURATION}}": _clean(duration),
            "{{ELEVATION}}": _clean(elevation),
            "{{DIFFICULTY}}": _clean(difficulty).upper(),
            "{{ROUTE_TYPE}}": _clean(route_type).upper(),
            "{{LUNCH}}": _clean(lunch),
            "{{BRING_LINE}}": _compact_items(bring_items),
            "{{WEATHER}}": _clean(weather),
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
                    desired_name=(
                        f"{presentation_title} — {stem}{raster.suffix}"
                    ),
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
            "used_native_template": True,
            "template_id_used": template_id,
        }
    except Exception as error:
        raise _friendly_google_error(error) from error
    finally:
        if drive is not None and temp_ids:
            for file_id in temp_ids:
                try:
                    drive.files().delete(fileId=file_id).execute()
                except Exception:
                    pass
