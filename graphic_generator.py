from pathlib import Path
from typing import Iterable, Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps


CANVAS_SIZE = 1080
BG = "#F2EBDD"
DARK = "#0B4A35"
DARK_2 = "#176045"
ACCENT = "#E2AF2E"
TEXT = "#16241C"
MUTED = "#5E6A62"
WHITE = "#FFFFFF"
LIGHT = "#FBF7EE"
BORDER = "#D6CCB9"


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def _rounded(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    fill: str,
    outline: Optional[str] = None,
    radius: int = 22,
    width: int = 2,
):
    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=fill,
        outline=outline,
        width=width,
    )


def _text_width(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _line_height(draw: ImageDraw.ImageDraw, font) -> int:
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    return bbox[3] - bbox[1]


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
    max_lines: int,
) -> list[str]:
    words = _clean(text).split()
    if not words:
        return [""]

    lines: list[str] = []
    current = ""
    consumed = 0

    for index, word in enumerate(words):
        trial = word if not current else f"{current} {word}"
        if _text_width(draw, trial, font) <= max_width:
            current = trial
            consumed = index + 1
            continue

        if current:
            lines.append(current)
        current = word
        consumed = index + 1

        if len(lines) >= max_lines - 1:
            break

    if current and len(lines) < max_lines:
        lines.append(current)

    if consumed < len(words) and lines:
        suffix = "…"
        last = lines[-1]
        while last and _text_width(draw, last + suffix, font) > max_width:
            last = last[:-1].rstrip()
        lines[-1] = (last or "…") + suffix

    return lines


def _fit_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    max_width: int,
    max_height: int,
    max_size: int,
    min_size: int,
    max_lines: int,
    bold: bool = False,
    line_gap: int = 5,
):
    clean = _clean(text)
    for size in range(max_size, min_size - 1, -1):
        font = _font(size, bold)
        lines = _wrap(draw, clean, font, max_width, max_lines)
        height = len(lines) * _line_height(draw, font)
        height += max(0, len(lines) - 1) * line_gap
        if height <= max_height and all(
            _text_width(draw, line, font) <= max_width for line in lines
        ):
            return font, lines

    font = _font(min_size, bold)
    return font, _wrap(draw, clean, font, max_width, max_lines)


def _draw_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    *,
    x: int,
    y: int,
    font,
    fill: str,
    line_gap: int = 5,
    align: str = "left",
    width: Optional[int] = None,
    stroke_width: int = 0,
    stroke_fill: Optional[str] = None,
) -> int:
    line_h = _line_height(draw, font)
    for line in lines:
        draw_x = x
        if width is not None and align == "center":
            draw_x = x + (width - _text_width(draw, line, font)) / 2
        draw.text(
            (draw_x, y),
            line,
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )
        y += line_h + line_gap
    return y


def _open_image(path: Optional[Path]) -> Optional[Image.Image]:
    if not path or not path.exists():
        return None
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def _paste_cover(
    canvas: Image.Image,
    path: Optional[Path],
    box: tuple[int, int, int, int],
) -> bool:
    image = _open_image(path)
    if image is None:
        return False

    x0, y0, x1, y1 = box
    fitted = ImageOps.fit(
        image,
        (x1 - x0, y1 - y0),
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
    canvas.paste(fitted, (x0, y0))
    return True


def _paste_contain(
    canvas: Image.Image,
    path: Optional[Path],
    box: tuple[int, int, int, int],
    *,
    background: str = WHITE,
) -> bool:
    image = _open_image(path)
    if image is None:
        return False

    x0, y0, x1, y1 = box
    width = x1 - x0
    height = y1 - y0
    canvas.paste(background, box)

    contained = ImageOps.contain(
        image,
        (width, height),
        method=Image.Resampling.LANCZOS,
    )
    x = x0 + (width - contained.width) // 2
    y = y0 + (height - contained.height) // 2
    canvas.paste(contained, (x, y))
    return True


def _draw_stat(
    draw: ImageDraw.ImageDraw,
    *,
    x0: int,
    y0: int,
    width: int,
    label: str,
    value: str,
    value_fill: str,
):
    label_font, label_lines = _fit_wrapped(
        draw,
        label.upper(),
        max_width=width - 20,
        max_height=28,
        max_size=20,
        min_size=15,
        max_lines=1,
        bold=False,
    )
    _draw_lines(
        draw,
        label_lines,
        x=x0,
        y=y0 + 17,
        font=label_font,
        fill="#DCECE5",
        align="center",
        width=width,
    )

    value_font, value_lines = _fit_wrapped(
        draw,
        value,
        max_width=width - 24,
        max_height=60,
        max_size=28,
        min_size=16,
        max_lines=2,
        bold=True,
        line_gap=1,
    )
    value_h = len(value_lines) * _line_height(draw, value_font)
    value_h += max(0, len(value_lines) - 1)
    value_y = y0 + 66 + max(0, (48 - value_h) // 2)
    _draw_lines(
        draw,
        value_lines,
        x=x0,
        y=value_y,
        font=value_font,
        fill=value_fill,
        align="center",
        width=width,
        line_gap=1,
    )


def _draw_info_row(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    width: int,
    label: str,
    value: str,
    max_lines: int,
    row_height: int,
):
    label_font = _font(21, True)
    draw.text((x, y), label.upper(), font=label_font, fill=DARK)

    value_font, value_lines = _fit_wrapped(
        draw,
        value,
        max_width=width,
        max_height=row_height - 34,
        max_size=25,
        min_size=17,
        max_lines=max_lines,
        bold=True,
        line_gap=2,
    )
    _draw_lines(
        draw,
        value_lines,
        x=x,
        y=y + 31,
        font=value_font,
        fill=TEXT,
        line_gap=2,
    )


def generate_square_graphic(
    output_path: Path,
    *,
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
    logo_path: Optional[Path] = None,
) -> Path:
    canvas = Image.new("RGB", (CANVAS_SIZE, CANVAS_SIZE), BG)
    draw = ImageDraw.Draw(canvas)

    hero_bottom = 360
    stats_bottom = 480
    footer_top = 1020

    if not _paste_cover(canvas, cover_path, (0, 0, CANVAS_SIZE, hero_bottom)):
        if not _paste_cover(canvas, map_path, (0, 0, CANVAS_SIZE, hero_bottom)):
            draw.rectangle((0, 0, CANVAS_SIZE, hero_bottom), fill="#A8CAD6")
            draw.polygon(
                [(0, 360), (0, 245), (220, 155), (420, 270), (650, 130), (850, 250), (1080, 155), (1080, 360)],
                fill="#48705A",
            )
            draw.polygon(
                [(0, 360), (0, 285), (235, 220), (480, 325), (705, 210), (915, 300), (1080, 250), (1080, 360)],
                fill="#254E3B",
            )

    overlay = Image.new("RGBA", (CANVAS_SIZE, hero_bottom), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle((0, 0, CANVAS_SIZE, 95), fill=(0, 0, 0, 85))
    overlay_draw.rectangle((0, 80, CANVAS_SIZE, hero_bottom), fill=(0, 0, 0, 38))
    overlay_draw.rectangle((0, 250, CANVAS_SIZE, hero_bottom), fill=(0, 0, 0, 95))
    canvas.paste(overlay, (0, 0), overlay)

    header_font = _font(35, True)
    draw.text((38, 25), "TN2G OUTDOOR", font=header_font, fill=WHITE)

    if logo_path and logo_path.exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((118, 90), Image.Resampling.LANCZOS)
            canvas.paste(
                logo,
                (CANVAS_SIZE - logo.width - 34, 13),
                logo,
            )
        except Exception:
            pass

    title_font, title_lines = _fit_wrapped(
        draw,
        title.upper(),
        max_width=950,
        max_height=190,
        max_size=82,
        min_size=42,
        max_lines=3,
        bold=True,
        line_gap=2,
    )
    _draw_lines(
        draw,
        title_lines,
        x=40,
        y=94,
        font=title_font,
        fill=WHITE,
        line_gap=2,
        stroke_width=2,
        stroke_fill="#1A1A1A",
    )

    subtitle_text = _clean(subtitle or route_type).upper()
    if subtitle_text:
        subtitle_font, subtitle_lines = _fit_wrapped(
            draw,
            subtitle_text,
            max_width=880,
            max_height=44,
            max_size=31,
            min_size=19,
            max_lines=1,
            bold=True,
        )
        subtitle_value = subtitle_lines[0]
        pill_width = min(
            950,
            _text_width(draw, subtitle_value, subtitle_font) + 52,
        )
        _rounded(
            draw,
            (40, hero_bottom - 61, 40 + pill_width, hero_bottom - 18),
            DARK,
            radius=16,
        )
        draw.text(
            (66, hero_bottom - 55),
            subtitle_value,
            font=subtitle_font,
            fill=WHITE,
        )

    draw.rectangle((0, hero_bottom, CANVAS_SIZE, stats_bottom), fill=DARK)
    stats = [
        ("Distanza", _clean(distance)),
        ("Durata", _clean(duration)),
        ("Dislivello", _clean(elevation)),
        ("Difficoltà", _clean(difficulty).upper()),
        ("Percorso", _clean(route_type).upper()),
    ]
    col_width = CANVAS_SIZE // 5
    for index, (label, value) in enumerate(stats):
        x0 = index * col_width
        if index:
            draw.line(
                (x0, hero_bottom + 19, x0, stats_bottom - 19),
                fill="#9DBDAD",
                width=2,
            )
        _draw_stat(
            draw,
            x0=x0,
            y0=hero_bottom,
            width=col_width,
            label=label,
            value=value,
            value_fill=ACCENT if label == "Difficoltà" else WHITE,
        )

    left_box = (28, 502, 330, 1002)
    map_box = (350, 502, 1052, 770)
    profile_box = (350, 788, 745, 1002)
    utility_box = (763, 788, 1052, 1002)

    _rounded(draw, left_box, LIGHT, BORDER)
    _rounded(draw, map_box, LIGHT, BORDER)
    _rounded(draw, profile_box, LIGHT, BORDER)
    _rounded(draw, utility_box, LIGHT, BORDER)

    info_x = 52
    info_width = 250
    info_rows = [
        ("Data", date_text, 2, 102),
        ("Ritrovo", meeting_time, 2, 102),
        ("Luogo", meeting_place, 3, 144),
        ("Pranzo", lunch, 2, 92),
    ]
    current_y = 526
    for index, (label, value, max_lines, row_height) in enumerate(info_rows):
        _draw_info_row(
            draw,
            x=info_x,
            y=current_y,
            width=info_width,
            label=label,
            value=value,
            max_lines=max_lines,
            row_height=row_height,
        )
        current_y += row_height
        if index < len(info_rows) - 1:
            draw.line(
                (info_x, current_y - 7, left_box[2] - 26, current_y - 7),
                fill=BORDER,
                width=2,
            )

    map_header_h = 44
    _rounded(
        draw,
        (map_box[0] + 1, map_box[1] + 1, map_box[2] - 1, map_box[1] + map_header_h),
        DARK,
        radius=20,
    )
    draw.rectangle(
        (map_box[0] + 1, map_box[1] + 23, map_box[2] - 1, map_box[1] + map_header_h),
        fill=DARK,
    )
    draw.text(
        (map_box[0] + 22, map_box[1] + 9),
        "MAPPA DEL PERCORSO",
        font=_font(24, True),
        fill=WHITE,
    )
    map_inner = (
        map_box[0] + 16,
        map_box[1] + map_header_h + 10,
        map_box[2] - 16,
        map_box[3] - 14,
    )
    if not _paste_contain(canvas, map_path, map_inner, background=WHITE):
        fallback_font, fallback_lines = _fit_wrapped(
            draw,
            "Mappa non caricata",
            max_width=map_inner[2] - map_inner[0] - 30,
            max_height=80,
            max_size=30,
            min_size=20,
            max_lines=2,
            bold=True,
        )
        _draw_lines(
            draw,
            fallback_lines,
            x=map_inner[0],
            y=map_inner[1] + 70,
            font=fallback_font,
            fill=MUTED,
            align="center",
            width=map_inner[2] - map_inner[0],
        )

    profile_header_h = 40
    _rounded(
        draw,
        (
            profile_box[0] + 1,
            profile_box[1] + 1,
            profile_box[2] - 1,
            profile_box[1] + profile_header_h,
        ),
        DARK,
        radius=20,
    )
    draw.rectangle(
        (
            profile_box[0] + 1,
            profile_box[1] + 21,
            profile_box[2] - 1,
            profile_box[1] + profile_header_h,
        ),
        fill=DARK,
    )
    draw.text(
        (profile_box[0] + 19, profile_box[1] + 8),
        "PROFILO ALTIMETRICO",
        font=_font(20, True),
        fill=WHITE,
    )
    profile_inner = (
        profile_box[0] + 14,
        profile_box[1] + profile_header_h + 10,
        profile_box[2] - 14,
        profile_box[3] - 14,
    )
    if not _paste_contain(
        canvas,
        profile_path,
        profile_inner,
        background=WHITE,
    ):
        draw.text(
            (profile_inner[0] + 57, profile_inner[1] + 54),
            "Profilo non caricato",
            font=_font(20, True),
            fill=MUTED,
        )

    utility_header_h = 40
    _rounded(
        draw,
        (
            utility_box[0] + 1,
            utility_box[1] + 1,
            utility_box[2] - 1,
            utility_box[1] + utility_header_h,
        ),
        DARK,
        radius=20,
    )
    draw.rectangle(
        (
            utility_box[0] + 1,
            utility_box[1] + 21,
            utility_box[2] - 1,
            utility_box[1] + utility_header_h,
        ),
        fill=DARK,
    )
    draw.text(
        (utility_box[0] + 18, utility_box[1] + 8),
        "COSA PORTARE",
        font=_font(20, True),
        fill=WHITE,
    )

    items = [_clean(item) for item in bring_items if _clean(item)][:4]
    item_font = _font(16, False)
    item_y = utility_box[1] + 50
    item_max_width = utility_box[2] - utility_box[0] - 42
    for item in items:
        wrapped = _wrap(draw, item, item_font, item_max_width - 16, 1)
        draw.text(
            (utility_box[0] + 18, item_y),
            "•",
            font=_font(19, True),
            fill=DARK,
        )
        draw.text(
            (utility_box[0] + 37, item_y + 1),
            wrapped[0],
            font=item_font,
            fill=TEXT,
        )
        item_y += 22

    separator_y = utility_box[1] + 140
    draw.line(
        (
            utility_box[0] + 16,
            separator_y,
            utility_box[2] - 16,
            separator_y,
        ),
        fill=BORDER,
        width=2,
    )
    draw.text(
        (utility_box[0] + 18, separator_y + 7),
        "METEO / CONSIGLIO",
        font=_font(16, True),
        fill=DARK,
    )
    weather_font, weather_lines = _fit_wrapped(
        draw,
        weather,
        max_width=utility_box[2] - utility_box[0] - 36,
        max_height=43,
        max_size=15,
        min_size=12,
        max_lines=2,
        bold=False,
        line_gap=1,
    )
    _draw_lines(
        draw,
        weather_lines,
        x=utility_box[0] + 18,
        y=separator_y + 28,
        font=weather_font,
        fill=TEXT,
        line_gap=1,
    )

    draw.rectangle((0, footer_top, CANVAS_SIZE, CANVAS_SIZE), fill=DARK)
    footer = "PRENOTAZIONI SU @OUTDOOR"
    footer_font = _font(30, True)
    footer_width = _text_width(draw, footer, footer_font)
    draw.text(
        ((CANVAS_SIZE - footer_width) / 2, footer_top + 15),
        footer,
        font=footer_font,
        fill=WHITE,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    return output_path
