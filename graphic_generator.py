from pathlib import Path
from typing import Iterable, Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps


CANVAS_SIZE = 1080
BG = "#F3EBDD"
DARK = "#0B3D2B"
DARK_2 = "#14543C"
ACCENT = "#D9A52A"
TEXT = "#152219"
MUTED = "#5C665F"
WHITE = "#FFFFFF"
LIGHT = "#F8F4EA"
BORDER = "#D7CDBB"


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def _fit_cover(path: Optional[Path], size: tuple[int, int]) -> Optional[Image.Image]:
    if not path or not path.exists():
        return None
    try:
        img = Image.open(path).convert("RGB")
        return ImageOps.fit(img, size, method=Image.Resampling.LANCZOS)
    except Exception:
        return None


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_width: int, max_lines: int = 4) -> list[str]:
    words = _clean(text).split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
            if len(lines) >= max_lines - 1:
                break
    if current and len(lines) < max_lines:
        lines.append(current)
    used = " ".join(lines)
    original = " ".join(words)
    if used != original and lines:
        while draw.textbbox((0, 0), lines[-1] + "...", font=font)[2] > max_width and len(lines[-1]) > 3:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "..."
    return lines


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font,
    fill: str,
    max_width: int,
    line_gap: int = 8,
    max_lines: int = 4,
):
    x, y = xy
    lines = _wrap(draw, text, font, max_width, max_lines)
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    line_height = bbox[3] - bbox[1]
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height + line_gap
    return y


def _rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: Optional[str] = None, radius: int = 24, width: int = 2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


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

    hero_h = 410
    cover = _fit_cover(cover_path, (CANVAS_SIZE, hero_h))
    if cover is None:
        cover = _fit_cover(map_path, (CANVAS_SIZE, hero_h))

    if cover:
        canvas.paste(cover, (0, 0))
    else:
        draw.rectangle((0, 0, CANVAS_SIZE, hero_h), fill="#9EC6D6")
        for i, color in enumerate(("#557C5C", "#37634C", "#234B3A")):
            y = 260 + i * 45
            draw.polygon([(0, hero_h), (0, y), (230, y - 110), (430, y - 20), (650, y - 150), (850, y - 40), (1080, y - 120), (1080, hero_h)], fill=color)

    overlay = Image.new("RGBA", (CANVAS_SIZE, hero_h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, CANVAS_SIZE, hero_h), fill=(0, 0, 0, 65))
    od.rectangle((0, 235, CANVAS_SIZE, hero_h), fill=(0, 0, 0, 90))
    canvas.paste(overlay, (0, 0), overlay)

    header_font = _font(38, True)
    title_font = _font(78, True)
    subtitle_font = _font(34, True)
    small_font = _font(24, False)
    small_bold = _font(25, True)

    draw.text((40, 30), "TN2G OUTDOOR", font=header_font, fill=WHITE)

    if logo_path and logo_path.exists():
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((155, 110), Image.Resampling.LANCZOS)
            canvas.paste(logo, (CANVAS_SIZE - logo.width - 35, 22), logo)
        except Exception:
            pass

    title_y = 105
    title_lines = _wrap(draw, title.upper(), title_font, 960, max_lines=3)
    if len(title_lines) >= 3:
        title_font = _font(62, True)
        title_lines = _wrap(draw, title.upper(), title_font, 960, max_lines=3)
    for line in title_lines:
        draw.text((40, title_y), line, font=title_font, fill=WHITE, stroke_width=2, stroke_fill="#1B1B1B")
        title_y += 78 if title_font.size >= 70 else 64

    subtitle_clean = _clean(subtitle or route_type).upper()
    if subtitle_clean:
        bbox = draw.textbbox((0, 0), subtitle_clean, font=subtitle_font)
        pill_w = min(960, bbox[2] - bbox[0] + 54)
        _rounded(draw, (40, hero_h - 70, 40 + pill_w, hero_h - 20), DARK, radius=18)
        draw.text((67, hero_h - 62), subtitle_clean, font=subtitle_font, fill=WHITE)

    stats_y0, stats_y1 = hero_h, 545
    draw.rectangle((0, stats_y0, CANVAS_SIZE, stats_y1), fill=DARK)
    stats = [
        ("DISTANZA", distance),
        ("DURATA", duration),
        ("DISLIVELLO", elevation),
        ("DIFFICOLTÀ", difficulty.upper()),
        ("PERCORSO", route_type.upper()),
    ]
    col_w = CANVAS_SIZE // len(stats)
    for idx, (label, value) in enumerate(stats):
        x0 = idx * col_w
        if idx:
            draw.line((x0, stats_y0 + 24, x0, stats_y1 - 24), fill="#A8C5B5", width=2)
        label_box = draw.textbbox((0, 0), label, font=small_font)
        value_box = draw.textbbox((0, 0), value, font=small_bold)
        draw.text((x0 + (col_w - (label_box[2] - label_box[0])) / 2, stats_y0 + 22), label, font=small_font, fill="#E7F1EC")
        value_fill = ACCENT if label == "DIFFICOLTÀ" else WHITE
        draw.text((x0 + (col_w - (value_box[2] - value_box[0])) / 2, stats_y0 + 67), value, font=small_bold, fill=value_fill)

    left = (28, 568, 364, 1002)
    right = (382, 568, 1052, 1002)
    _rounded(draw, left, LIGHT, BORDER, radius=24)
    _rounded(draw, right, LIGHT, BORDER, radius=24)

    section_font = _font(29, True)
    value_font = _font(25, True)
    body_font = _font(22, False)

    x = 55
    y = 592
    info_rows = [
        ("DATA", date_text),
        ("RITROVO", meeting_time),
        ("LUOGO", meeting_place),
        ("PRANZO", lunch),
    ]
    for label, value in info_rows:
        draw.text((x, y), label, font=small_bold, fill=DARK)
        y += 31
        row_font = _font(23, True) if label == "LUOGO" else value_font
        row_lines = 3 if label == "LUOGO" else 2
        y = _draw_wrapped(draw, (x, y), value, row_font, TEXT, 270, line_gap=3, max_lines=row_lines) + 13
        draw.line((x, y, 335, y), fill=BORDER, width=2)
        y += 13

    map_img = _fit_cover(map_path, (622, 258))
    if map_img:
        canvas.paste(map_img, (406, 608))
        draw.rectangle((406, 576, 690, 620), fill=DARK)
        draw.text((426, 584), "MAPPA DEL PERCORSO", font=small_bold, fill=WHITE)
    else:
        draw.text((412, 592), "INFO UTILI", font=section_font, fill=DARK)
        _draw_wrapped(draw, (412, 640), meeting_place, _font(30, True), TEXT, 590, max_lines=4)

    profile_img = _fit_cover(profile_path, (360, 92))
    if profile_img:
        canvas.paste(profile_img, (406, 898))
        draw.rectangle((406, 870, 696, 906), fill=DARK)
        draw.text((423, 874), "PROFILO ALTIMETRICO", font=_font(20, True), fill=WHITE)

    weather_x = 785 if profile_img else 412
    weather_y = 884 if profile_img else 770
    weather_w = 235 if profile_img else 590
    draw.text((weather_x, weather_y), "METEO / CONSIGLI", font=_font(23, True), fill=DARK)
    _draw_wrapped(draw, (weather_x, weather_y + 38), weather, body_font, TEXT, weather_w, line_gap=4, max_lines=3)

    bring_text = " · ".join(_clean(item) for item in list(bring_items)[:5])
    draw.text((412, 950), "COSA PORTARE", font=_font(21, True), fill=DARK)
    _draw_wrapped(draw, (600, 950), bring_text, _font(18, False), TEXT, 420, line_gap=2, max_lines=2)

    draw.rectangle((0, 1020, CANVAS_SIZE, CANVAS_SIZE), fill=DARK)
    footer = "PRENOTAZIONI SU @OUTDOOR"
    fb = draw.textbbox((0, 0), footer, font=_font(29, True))
    draw.text(((CANVAS_SIZE - (fb[2] - fb[0])) / 2, 1034), footer, font=_font(29, True), fill=WHITE)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, format="PNG", optimize=True)
    return output_path
