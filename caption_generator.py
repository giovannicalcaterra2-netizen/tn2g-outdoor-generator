from typing import Iterable


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


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
    items = ", ".join(_clean(item) for item in bring_items if _clean(item))
    opening = _clean(intro) or _clean(route_description)
    closing = _clean(mood)

    lines = [
        f"🌲 TN2G OUTDOOR — {_clean(title).upper()} 🥾⛰️",
        "",
        opening,
        "",
        f"📅 {_clean(date_text)}",
        f"⏰ Ritrovo: {_clean(meeting_time)}",
        f"📍 {_clean(meeting_place)}",
        f"🥾 Distanza: {_clean(distance)}",
        f"⛰️ Dislivello: {_clean(elevation)}",
        f"⏱️ Durata: {_clean(duration)}",
        f"🟡 Difficoltà: {_clean(difficulty).upper()}",
    ]

    if return_time:
        lines.append(f"🏁 Rientro previsto: {_clean(return_time)}")
    if lunch:
        lines.append(f"🥪 Pranzo: {_clean(lunch)}")

    if items:
        lines.extend(["", f"🎒 Da portare: {items}."])

    if route_description:
        lines.extend(["", _clean(route_description)])
    if closing:
        lines.extend(["", closing])

    lines.extend(["", "Chi vuole venire si prenota su @Outdoor ⛰️"])
    return "\n".join(line for line in lines if line is not None).strip()
