"""Generazione caption TN2G Outdoor con Gemini e fallback locale.

La funzione pubblica mantiene il vecchio nome per compatibilità con app.py.
Quando è presente una chiave Gemini prova il modello configurato e, se questo
non è più disponibile, ripiega automaticamente sui modelli Flash correnti.
"""

from __future__ import annotations

import os
import re
from typing import Iterable

import requests

# Carica la compatibilità per i log TeX Live prima che app.py usi subprocess.
import sitecustomize  # noqa: F401


DEFAULT_MODEL = "gemini-3.6-flash"
MODEL_FALLBACKS = (
    "gemini-3.6-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash-lite",
)
GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent"
)
FINAL_CTA = "Chi vuole venire si prenota su @Outdoor ⛰️"


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def _secret_value(name: str) -> str:
    """Legge prima Streamlit Secrets e poi le variabili d'ambiente."""
    try:
        import streamlit as st

        value = st.secrets.get(name, "")
        if value:
            return str(value).strip()
    except Exception:
        pass

    return str(os.getenv(name.upper(), "") or "").strip()


def _notify_fallback(error: Exception) -> None:
    """Mostra un avviso utile senza interrompere la generazione del kit."""
    try:
        import streamlit as st

        st.warning(
            "Gemini non ha generato la caption; è stato usato il template "
            f"automatico. Dettaglio: {error}"
        )
    except Exception:
        pass


def _build_fallback_caption(
    *,
    title: str,
    date_text: str,
    meeting_time: str,
    meeting_place: str,
    distance: str,
    elevation: str,
    duration: str,
    difficulty: str,
    lunch: str,
    intro: str,
    route_description: str,
    bring_items: Iterable[str],
    return_time: str,
    mood: str,
) -> str:
    items = ", ".join(_clean(item) for item in bring_items if _clean(item))
    opening = _clean(intro) or _clean(route_description)
    closing = _clean(mood)

    lines = [
        f"🌲 *TN2G OUTDOOR — {_clean(title).upper()}* 🥾⛰️",
        "",
        opening,
        "",
        f"📅 *{_clean(date_text)}*",
        f"⏰ *Ritrovo:* {_clean(meeting_time)}",
        f"📍 *Dove:* {_clean(meeting_place)}",
        f"🥾 *Distanza:* {_clean(distance)}",
        f"⛰️ *Dislivello:* {_clean(elevation)}",
        f"⏱️ *Durata:* {_clean(duration)}",
        f"🟡 *Difficoltà:* {_clean(difficulty).upper()}",
    ]

    if return_time:
        lines.append(f"🏁 *Rientro previsto:* {_clean(return_time)}")
    if lunch:
        lines.append(f"🥪 *Pranzo:* {_clean(lunch)}")
    if items:
        lines.extend(["", f"🎒 *Cosa portare:* {items}."])
    if route_description:
        lines.extend(["", _clean(route_description)])
    if closing:
        lines.extend(["", closing])

    lines.extend(["", FINAL_CTA])
    return "\n".join(line for line in lines if line is not None).strip()


def _build_prompt(
    *,
    title: str,
    date_text: str,
    meeting_time: str,
    meeting_place: str,
    distance: str,
    elevation: str,
    duration: str,
    difficulty: str,
    lunch: str,
    intro: str,
    route_description: str,
    bring_items: Iterable[str],
    return_time: str,
    mood: str,
) -> str:
    items = [str(item).strip() for item in bring_items if str(item).strip()]
    bring_block = "\n".join(f"- {item}" for item in items) or "- Non specificato"

    return f"""
Scrivi la caption definitiva in italiano per un evento della community TN2G Outdoor.

DATI DISPONIBILI — usa esclusivamente questi e non inventare nulla:
Titolo: {title}
Data: {date_text}
Orario di ritrovo: {meeting_time}
Luogo di ritrovo: {meeting_place}
Distanza: {distance}
Dislivello: {elevation}
Durata: {duration}
Difficoltà: {difficulty}
Pranzo: {lunch}
Rientro previsto: {return_time}
Introduzione fornita: {intro}
Descrizione del percorso: {route_description}
Mood dell'attività: {mood}
Cosa portare:
{bring_block}

STILE TN2G:
- tono giovane, amichevole, spontaneo e concreto;
- deve sembrare scritta da un vero admin della community, non da un'AI;
- energica ma non pubblicitaria e non enfatica;
- evita frasi come “esperienza indimenticabile”, “non perdere l'occasione”,
  “avventura mozzafiato”, “lasciati trasportare” e simili;
- non ripetere la stessa informazione in più paragrafi;
- usa emoji utili senza esagerare;
- usa la formattazione WhatsApp con un solo asterisco per titolo, etichette e
  informazioni principali;
- niente hashtag;
- non aggiungere prezzi, meteo o attrezzatura non forniti;
- se un campo è vuoto, non citarlo.

STRUTTURA:
1. Titolo nella forma “🌲 *TN2G OUTDOOR — TITOLO* 🥾⛰️”.
2. Apertura naturale di 2-4 frasi che valorizzi percorso e atmosfera.
3. Blocco informazioni leggibile, una voce per riga.
4. Sezione “Cosa portare”, solo con gli elementi forniti.
5. Eventuale chiusura sul mood, senza ripetizioni.
6. Ultima riga obbligatoria, identica: “{FINAL_CTA}”.

Restituisci soltanto la caption pronta da incollare, senza introduzioni,
spiegazioni, virgolette o blocchi di codice.
""".strip()


def _extract_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        feedback = payload.get("promptFeedback") or {}
        raise RuntimeError(f"Nessuna risposta testuale da Gemini: {feedback}")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(str(part.get("text", "")) for part in parts).strip()
    text = re.sub(r"^```(?:text|markdown)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text).strip()

    if len(text) < 80:
        raise RuntimeError("La risposta di Gemini è vuota o troppo breve.")

    if FINAL_CTA not in text:
        text = f"{text.rstrip()}\n\n{FINAL_CTA}"

    return text


def _normalise_model(model: str) -> str:
    model = str(model or "").strip()
    if model.startswith("models/"):
        model = model.removeprefix("models/")
    return model or DEFAULT_MODEL


def _model_candidates(configured_model: str) -> list[str]:
    """Restituisce modelli unici, dal configurato ai fallback correnti."""
    candidates: list[str] = []
    for model in (_normalise_model(configured_model), *MODEL_FALLBACKS):
        if model and model not in candidates:
            candidates.append(model)
    return candidates


def _generate_with_gemini(*, api_key: str, model: str, prompt: str) -> str:
    response = requests.post(
        GEMINI_ENDPOINT.format(model=_normalise_model(model)),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        },
        json={
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Sei il copywriter della community universitaria TN2G. "
                            "Scrivi in italiano naturale e non inventare mai dati."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 1400,
            },
        },
        timeout=60,
    )

    if not response.ok:
        try:
            details = response.json().get("error", {}).get("message", response.text)
        except Exception:
            details = response.text
        raise RuntimeError(f"Gemini API {response.status_code}: {details}")

    return _extract_text(response.json())


def _generate_with_model_retry(
    *,
    api_key: str,
    configured_model: str,
    prompt: str,
) -> str:
    errors: list[str] = []

    for model in _model_candidates(configured_model):
        try:
            return _generate_with_gemini(
                api_key=api_key,
                model=model,
                prompt=prompt,
            )
        except Exception as error:
            errors.append(f"{model}: {error}")

    raise RuntimeError(" | ".join(errors))


def generate_fallback_caption(
    *,
    title: str,
    date_text: str,
    meeting_time: str,
    meeting_place: str,
    distance: str,
    elevation: str,
    duration: str,
    difficulty: str,
    lunch: str,
    intro: str,
    route_description: str,
    bring_items: Iterable[str],
    return_time: str,
    mood: str,
) -> str:
    """Genera prima con Gemini e usa il template locale come fallback sicuro."""
    items = list(bring_items)
    fallback = _build_fallback_caption(
        title=title,
        date_text=date_text,
        meeting_time=meeting_time,
        meeting_place=meeting_place,
        distance=distance,
        elevation=elevation,
        duration=duration,
        difficulty=difficulty,
        lunch=lunch,
        intro=intro,
        route_description=route_description,
        bring_items=items,
        return_time=return_time,
        mood=mood,
    )

    api_key = _secret_value("gemini_api_key") or _secret_value("google_api_key")
    if not api_key:
        return fallback

    configured_model = _secret_value("gemini_model") or DEFAULT_MODEL
    prompt = _build_prompt(
        title=title,
        date_text=date_text,
        meeting_time=meeting_time,
        meeting_place=meeting_place,
        distance=distance,
        elevation=elevation,
        duration=duration,
        difficulty=difficulty,
        lunch=lunch,
        intro=intro,
        route_description=route_description,
        bring_items=items,
        return_time=return_time,
        mood=mood,
    )

    try:
        return _generate_with_model_retry(
            api_key=api_key,
            configured_model=configured_model,
            prompt=prompt,
        )
    except Exception as error:
        _notify_fallback(error)
        return fallback
