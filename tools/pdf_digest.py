import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from enum import Enum
from io import BytesIO

from PIL import Image
from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

try:
    from svglib.svglib import svg2rlg
except ImportError as error:
    raise SystemExit('error: svglib is required to draw stats charts (pip install svglib): ' + str(error))

TITLE = "Tienda de Fortnite: cambios del día"
SUBTITLE = "Tienda del {shop} comparada con la del {previous}"
UNCHANGED_TITLE = "Siguen en la tienda (sin cambios)"
BASELINE_TITLE = "Tienda de Fortnite: catálogo actual"
BASELINE_SUBTITLE = "Primera base de la tienda del {shop}; la comparación diaria empieza con la próxima rotación"
BASELINE_CATALOG_TITLE = "Catálogo actual"
ADDED_TITLE = "Nuevos"
REMOVED_TITLE = "Salieron"
PRICE_TITLE = "Cambios de precio"
FOOTER = (
    "Datos de fortnite-api.com. Las fechas de salida son estimadas por esa API "
    "(no garantizadas); la fecha exacta de cada objeto se ve dentro del juego, "
    "en la propia tienda."
)
PENDING_IMAGE = "Imagen pendiente"
USER_AGENT = "fortnite-shop-watch/1.0"

STATS_TITLE = "Estadisticas de la tienda"
STATS_HEADLINE = "Costo teórico del catálogo ({date}): {total} PaVos a precios publicados"
STATS_COVERAGE = "{purchases} compras cubren los {items} articulos de la tienda"
STATS_UNIQUE = ", cada uno una sola vez (hoy)"
STATS_OVERLAP = " - {overlap} articulos vienen repetidos entre las compras elegidas (cobertura verificada)"
STATS_LOTS = "La tienda tiene {catalog} lotes y la combinación mínima usa {chosen}."
STATS_SERIES_TITLE = "Serie diaria de costo teórico (PaVos)"
STATS_SERIES_SINGLE = "Primer registro de la serie"
STATS_SERIES_NOTE = "Serie diaria de costo teórico del catálogo (PaVos por fecha)."
STATS_METHOD_PRICES = (
    "Precios publicados del dia segun fortnite-api.com (terceros), sin cuenta: calculo teorico "
    "del catalogo, no una cotizacion de tu cuenta ni una recomendacion de compra."
)
STATS_METHOD_NO_PRORATE = "El precio de cada compra entra completo en una sola categoria, sin prorrateos."
STATS_CHART_TITLE = "Costo teórico del catálogo ({date}): {total} PaVos a precios publicados"
RENDER_CHART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "render_chart.js")


class StatsCategory(Enum):
    SONGS = "songs"
    BUNDLES = "bundles"
    SKINS = "skins"
    ACCESSORIES = "accessories"
    EMOTES = "emotes"
    OTHER = "other"


STATS_ORDER = [
    (StatsCategory.SONGS, "Canciones"),
    (StatsCategory.BUNDLES, "Lotes"),
    (StatsCategory.SKINS, "Skins"),
    (StatsCategory.ACCESSORIES, "Accesorios"),
    (StatsCategory.EMOTES, "Gestos"),
    (StatsCategory.OTHER, "Otros"),
]


class StatsError(Exception):
    pass

INK = HexColor("#14142b")
MUTED = HexColor("#5c5c72")
BAND = HexColor("#2b2d5e")
HEADER_BG = HexColor("#151637")
ROW_ALT = HexColor("#f1f2f8")
ROW_LINE = HexColor("#e2e3ee")
CARD_BG = HexColor("#e9eaf4")
ACCENT = HexColor("#ffd23f")

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

BODY = 13
BODY_BOLD = 13
META = 12
TITLE_SIZE = 24
SUBTITLE_SIZE = 13
SECTION_SIZE = 15
FOOTER_SIZE = 12

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
THUMB = 30 * mm
GAP = 6 * mm
ROW_PAD = 3.2 * mm
ROW_H = THUMB + ROW_PAD * 2
HEADER_H = 30 * mm

SECTION_STYLE = {
    "unchanged": (HexColor("#2f9e6e"), "sin cambios"),
    "added": (HexColor("#2f6fd0"), "nuevos"),
    "removed": (HexColor("#c0442f"), "salieron"),
    "priceChanged": (HexColor("#b07a10"), "de precio"),
}


def clean_text(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"\s+", " ", value).strip()


def currency_status(offer):
    currency = offer.get("currency")
    if currency == "MtxCurrency":
        return "verified"
    if currency is None or currency == "unknown":
        return "unverified"
    return "non_vbucks"


def resolve_name(offer):
    name = clean_text(offer.get("name"))
    if name:
        return name
    dev = clean_text(offer.get("devName"))
    if dev:
        dev = re.sub(r"^(?:[A-Za-z]+:?/)+", "", dev)
        dev = re.sub(r"[_\-/]+", " ", dev)
        dev = clean_text(dev)
        if dev:
            return dev
    items = offer.get("itemNames")
    if isinstance(items, list):
        for item in items:
            text = clean_text(item)
            if text:
                return text
    return ""


def short_date(value):
    text = clean_text(value)
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return f"{match.group(3)}/{match.group(2)}"
    match = re.match(r"^(\d{2})/(\d{2})", text)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return None


def format_price(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if float(value).is_integer():
        value = int(value)
    text = f"{value:,}".replace(",", ".")
    return f"{text} PaVos"


def format_count(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "0"
    return f"{int(value):,}".replace(",", ".")


def display_date(value):
    text = clean_text(value)
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return f"{match.group(3)}/{match.group(2)}/{match.group(1)}"
    return text


def load_totals(path):
    with open(path, "r", encoding="utf-8") as handle:
        totals = json.load(handle)
    if not isinstance(totals, dict) or not isinstance(totals.get("days"), dict):
        raise StatsError("totals file has unexpected schema")
    dates = sorted(key for key in totals["days"] if re.match(r"^\d{4}-\d{2}-\d{2}$", key))
    if not dates:
        raise StatsError("totals file has no daily entries")
    current_key = dates[-1]
    current = totals["days"][current_key]
    if not isinstance(current, dict):
        raise StatsError("totals day entry has unexpected schema")
    for field in ("totalMinPaVos", "purchases", "itemsCovered", "overlapItems", "chosenNamedBundles", "namedBundlesInCatalog"):
        if not isinstance(current.get(field), (int, float)) or isinstance(current.get(field), bool):
            raise StatsError(f"totals day entry is missing {field}")
    if not isinstance(current.get("categories"), dict) or not isinstance(current.get("itemsObtained"), dict):
        raise StatsError("totals day entry is missing category breakdowns")
    series = []
    for key in dates:
        entry = totals["days"][key]
        if isinstance(entry, dict) and isinstance(entry.get("totalMinPaVos"), (int, float)) and not isinstance(entry.get("totalMinPaVos"), bool):
            series.append((key, int(entry["totalMinPaVos"])))
    return current_key, current, series


def stats_rows(day):
    rows = []
    for category, label in STATS_ORDER:
        data = day["categories"].get(category.value)
        if not isinstance(data, dict):
            continue
        purchases = int(data.get("purchases") or 0)
        if purchases <= 0:
            continue
        rows.append((category, label, int(data.get("paVos") or 0), purchases))
    if not rows:
        raise StatsError("totals day entry has no category purchases")
    return rows


def chart_max(values):
    peak = max(values) if values else 0
    if peak <= 0:
        return 1
    magnitude = 10 ** (len(str(int(peak))) - 1)
    step = magnitude
    for candidate in (magnitude, 2 * magnitude, 5 * magnitude, 10 * magnitude):
        step = candidate
        if peak % step == 0 and peak // step <= 6:
            return peak
    return ((peak // step) + 1) * step


def quoted(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_chart(source, workdir, name):
    source_path = os.path.join(workdir, f"{name}.mmd")
    svg_path = os.path.join(workdir, f"{name}.svg")
    with open(source_path, "w", encoding="utf-8") as handle:
        handle.write(source + "\n")
    try:
        result = subprocess.run(
            ["node", RENDER_CHART, source_path, svg_path],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as error:
        raise StatsError(f"node is required to render stats charts: {error}")
    if result.returncode != 0:
        detail = clean_text(result.stderr) or clean_text(result.stdout) or f"exit {result.returncode}"
        raise StatsError(f"render_chart failed for {name}: {detail}")
    try:
        drawing = svg2rlg(svg_path)
    except Exception as error:
        raise StatsError(f"svglib could not parse {name} chart: {error}")
    if drawing is None:
        raise StatsError(f"svglib returned no drawing for {name} chart")
    return drawing


def wrap_lines(text, font, size, width, max_lines):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if stringWidth(trial, font, size) <= width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        while last and stringWidth(last + "…", font, size) > width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "…"
    return lines


THUMB_MAX_PX = 160
THUMB_QUALITY = 70
DARK_TILE = (26, 26, 46)
VISIBILITY_SIZE = 48
VISIBILITY_MIN_STDDEV = 6.0


def shrink_thumbnail(image):
    longest = max(image.size)
    if longest > THUMB_MAX_PX:
        scale = THUMB_MAX_PX / longest
        size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
        image = image.resize(size, Image.LANCZOS)
    if image.mode != "RGB":
        image = image.convert("RGB")
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=THUMB_QUALITY, optimize=True)
    buffer.seek(0)
    return buffer


def is_visible(image, bbox=None):
    sample = image.convert("L")
    if bbox is None:
        bbox = sample.getbbox()
    if bbox is not None and bbox != (0, 0, sample.width, sample.height):
        sample = sample.crop(bbox)
    sample = sample.resize((VISIBILITY_SIZE, VISIBILITY_SIZE), Image.LANCZOS)
    pixels = list(sample.getdata())
    if not pixels:
        return False
    mean = sum(pixels) / len(pixels)
    variance = sum((value - mean) ** 2 for value in pixels) / len(pixels)
    return variance ** 0.5 >= VISIBILITY_MIN_STDDEV


def composite_rgba(rgba, background):
    tile = Image.new("RGB", rgba.size, background)
    tile.paste(rgba, mask=rgba.split()[-1])
    return tile


def fetch_thumb(url):
    if not url:
        return None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = Image.open(BytesIO(response.read()))
                raw.load()
            if raw.mode in ("RGBA", "LA") or (raw.mode == "P" and "transparency" in raw.info):
                rgba = raw.convert("RGBA")
                composed = composite_rgba(rgba, DARK_TILE)
                if not is_visible(composed, rgba.split()[-1].getbbox()):
                    if attempt < 2:
                        time.sleep(0.5 * (attempt + 1))
                        continue
                    return None
                return shrink_thumbnail(composed)
            composed = raw.convert("RGB")
            if not is_visible(composed):
                if attempt < 2:
                    time.sleep(0.5 * (attempt + 1))
                    continue
                return None
            return shrink_thumbnail(composed)
        except Exception:
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    return None


def load_thumbnail(offer):
    return fetch_thumb(offer.get("imageUrl"))


def draw_rounded_image(canvas, image, x, y, size, radius):
    path = canvas.beginPath()
    path.moveTo(x + radius, y)
    path.lineTo(x + size - radius, y)
    path.arcTo(x + size - radius * 2, y, x + size, y + radius * 2, startAng=270, extent=90)
    path.lineTo(x + size, y + size - radius)
    path.arcTo(x + size - radius * 2, y + size - radius * 2, x + size, y + size, startAng=0, extent=90)
    path.lineTo(x + radius, y + size)
    path.arcTo(x, y + size - radius * 2, x + radius * 2, y + size, startAng=90, extent=90)
    path.lineTo(x, y + radius)
    path.arcTo(x, y, x + radius * 2, y + radius * 2, startAng=180, extent=90)
    path.close()
    canvas.saveState()
    canvas.clipPath(path, stroke=0, fill=0)
    canvas.setFillColor(HexColor("#1a1a2e"))
    canvas.rect(x, y, size, size, stroke=0, fill=1)
    canvas.drawImage(ImageReader(image), x, y, size, size, preserveAspectRatio=True, anchor="c", mask="auto")
    canvas.restoreState()
    canvas.saveState()
    canvas.setStrokeColor(ROW_LINE)
    canvas.setLineWidth(0.6)
    canvas.roundRect(x, y, size, size, radius, stroke=1, fill=0)
    canvas.restoreState()


def draw_pending_image(canvas, x, y, size, radius):
    canvas.saveState()
    canvas.setFillColor(CARD_BG)
    canvas.roundRect(x, y, size, size, radius, stroke=0, fill=1)
    canvas.setStrokeColor(ROW_LINE)
    canvas.setLineWidth(0.6)
    canvas.roundRect(x, y, size, size, radius, stroke=1, fill=0)
    canvas.setFillColor(MUTED)
    canvas.setFont(FONT_BOLD, META)
    lines = wrap_lines(PENDING_IMAGE, FONT_BOLD, META, size - 6 * mm, 2)
    total = len(lines) * META * 1.25
    start = y + size / 2 + total / 2 - META
    for index, line in enumerate(lines):
        width = stringWidth(line, FONT_BOLD, META)
        canvas.drawString(x + (size - width) / 2, start - index * META * 1.25, line)
    canvas.restoreState()


class Digest:
    def __init__(self, path, changes_data):
        self.canvas = Canvas(path, pagesize=A4)
        self.margin = MARGIN
        self.content_w = PAGE_W - MARGIN * 2
        self.y = PAGE_H - HEADER_H - 8 * mm
        self.row_index = 0
        self.images_total = 0
        self.images_ok = 0
        self.images_pending = 0
        self.shop_date = changes_data.get("shopDate")
        self.previous_date = changes_data.get("previousDate")
        self.baseline = not (changes_data.get("changes") or []) and not clean_text(self.previous_date)
        self.canvas.setTitle(BASELINE_TITLE if self.baseline else TITLE)
        self._draw_header()

    def _draw_header(self):
        canvas = self.canvas
        canvas.saveState()
        canvas.setFillColor(HEADER_BG)
        canvas.rect(0, PAGE_H - HEADER_H, PAGE_W, HEADER_H, stroke=0, fill=1)
        canvas.setFillColor(ACCENT)
        canvas.rect(0, PAGE_H - HEADER_H, PAGE_W, 1.8 * mm, stroke=0, fill=1)
        canvas.setFillColor(white)
        canvas.setFont(FONT_BOLD, TITLE_SIZE)
        if self.baseline:
            canvas.drawString(self.margin, PAGE_H - HEADER_H + 15 * mm, BASELINE_TITLE)
            canvas.setFillColor(HexColor("#c9cbe6"))
            canvas.setFont(FONT, SUBTITLE_SIZE)
            subtitle = BASELINE_SUBTITLE.format(shop=self.shop_date or "hoy")
            for index, line in enumerate(wrap_lines(subtitle, FONT, SUBTITLE_SIZE, self.content_w, 2)):
                canvas.drawString(self.margin, PAGE_H - HEADER_H + (9 * mm) - index * SUBTITLE_SIZE * 1.2, line)
            canvas.restoreState()
            return
        canvas.drawString(self.margin, PAGE_H - HEADER_H + 15 * mm, TITLE)
        canvas.setFillColor(HexColor("#c9cbe6"))
        canvas.setFont(FONT, SUBTITLE_SIZE)
        subtitle = SUBTITLE.format(
            shop=self.shop_date or "hoy",
            previous=self.previous_date or "el día anterior",
        )
        canvas.drawString(self.margin, PAGE_H - HEADER_H + 8 * mm, subtitle)
        canvas.restoreState()

    def new_page(self):
        self.canvas.showPage()
        self.y = PAGE_H - MARGIN

    def ensure_space(self, height):
        if self.y - height < MARGIN + 18 * mm:
            self.new_page()

    def start_section(self, key, title, count):
        self.ensure_space(14 * mm + ROW_H)
        canvas = self.canvas
        color, label = SECTION_STYLE.get(key, (BAND, ""))
        band_h = 11 * mm
        top = self.y
        canvas.saveState()
        canvas.setFillColor(color)
        canvas.roundRect(MARGIN, top - band_h, self.content_w, band_h, 2.5 * mm, stroke=0, fill=1)
        canvas.setFillColor(white)
        canvas.setFont(FONT_BOLD, SECTION_SIZE)
        heading = f"{title} ({count})"
        canvas.drawString(MARGIN + 5 * mm, top - band_h + 3.6 * mm, heading)
        canvas.restoreState()
        self.y = top - band_h - 3 * mm
        self.row_index = 0

    def empty_note(self, text):
        self.ensure_space(10 * mm)
        self.canvas.setFillColor(MUTED)
        self.canvas.setFont(FONT, BODY)
        self.canvas.drawString(MARGIN + 2 * mm, self.y - 5 * mm, text)
        self.y -= 10 * mm

    def wrapped_note(self, text, max_lines=3):
        size = BODY
        lines = wrap_lines(text, FONT, size, self.content_w, max_lines)
        height = len(lines) * size * 1.22 + 4 * mm
        self.ensure_space(height)
        self.canvas.setFillColor(MUTED)
        self.canvas.setFont(FONT, size)
        base = self.y - 5 * mm
        for index, line in enumerate(lines):
            self.canvas.drawString(MARGIN + 2 * mm, base - index * size * 1.22, line)
        self.y -= height

    def meta_line(self, offer, entry):
        parts = []
        section = clean_text(offer.get("section"))
        if section:
            parts.append(section)
        kind = entry.get("kind")
        if kind == "priceChanged":
            old = format_price(entry.get("oldPrice"))
            if old is None:
                old = format_price(offer.get("finalPrice"))
            new = format_price(entry.get("newPrice"))
            if new is None:
                new = format_price(offer.get("finalPrice"))
            if old and new:
                parts.append(f"{old} -> {new}")
            elif new:
                parts.append(new)
        else:
            price = format_price(offer.get("finalPrice"))
            if price:
                parts.append(price)
        out_date = short_date(offer.get("outDate"))
        if out_date:
            parts.append(f"Se retira aprox. {out_date}")
        return "  |  ".join(parts)

    def draw_row(self, offer, entry, name):
        self.ensure_space(ROW_H + 2 * mm)
        canvas = self.canvas
        color, _ = SECTION_STYLE.get(entry.get("kind") or "unchanged", (BAND, ""))
        top = self.y
        self.images_total += 1
        image = load_thumbnail(offer)
        if image is not None:
            self.images_ok += 1
        else:
            self.images_pending += 1
        if self.row_index % 2 == 1:
            canvas.saveState()
            canvas.setFillColor(ROW_ALT)
            canvas.roundRect(MARGIN, top - ROW_H, self.content_w, ROW_H, 2.5 * mm, stroke=0, fill=1)
            canvas.restoreState()
        else:
            canvas.saveState()
            canvas.setFillColor(white)
            canvas.roundRect(MARGIN, top - ROW_H, self.content_w, ROW_H, 2.5 * mm, stroke=0, fill=1)
            canvas.restoreState()
        canvas.saveState()
        canvas.setFillColor(color)
        canvas.roundRect(MARGIN + 1.5 * mm, top - ROW_H + 2 * mm, 1.6 * mm, ROW_H - 4 * mm, 0.8 * mm, stroke=0, fill=1)
        canvas.restoreState()
        thumb_x = MARGIN + 5 * mm
        thumb_y = top - ROW_PAD - THUMB
        if image is not None:
            draw_rounded_image(canvas, image, thumb_x, thumb_y, THUMB, 3 * mm)
        else:
            draw_pending_image(canvas, thumb_x, thumb_y, THUMB, 3 * mm)
        text_x = thumb_x + THUMB + GAP
        text_w = MARGIN + self.content_w - 4 * mm - text_x
        name_lines = wrap_lines(name, FONT_BOLD, BODY_BOLD, text_w, 2)
        name_top = top - ROW_PAD - BODY_BOLD - 1 * mm
        for index, line in enumerate(name_lines):
            canvas.setFillColor(INK)
            canvas.setFont(FONT_BOLD, BODY_BOLD)
            canvas.drawString(text_x, name_top - index * BODY_BOLD * 1.25, line)
        meta = self.meta_line(offer, entry)
        meta_y = thumb_y + 3 * mm
        if meta:
            canvas.setFillColor(MUTED)
            canvas.setFont(FONT, META)
            meta_lines = wrap_lines(meta, FONT, META, text_w, 2)
            for index, line in enumerate(meta_lines):
                canvas.drawString(text_x, meta_y + (len(meta_lines) - 1 - index) * META * 1.2, line)
        self.y = top - ROW_H - 1.6 * mm
        self.row_index += 1

    def stats_heading(self, title):
        self.ensure_space(16 * mm)
        canvas = self.canvas
        if self.y > PAGE_H - MARGIN:
            self.new_page()
        band_h = 11 * mm
        top = self.y
        canvas.saveState()
        canvas.setFillColor(BAND)
        canvas.roundRect(MARGIN, top - band_h, self.content_w, band_h, 2.5 * mm, stroke=0, fill=1)
        canvas.setFillColor(white)
        canvas.setFont(FONT_BOLD, SECTION_SIZE)
        canvas.drawString(MARGIN + 5 * mm, top - band_h + 3.6 * mm, title)
        canvas.restoreState()
        self.y = top - band_h - 4 * mm

    def stats_paragraph(self, text, size=BODY, bold=False):
        font = FONT_BOLD if bold else FONT
        lines = wrap_lines(text, font, size, self.content_w - 4 * mm, 12)
        height = len(lines) * size * 1.24 + 3 * mm
        self.ensure_space(height)
        self.canvas.setFillColor(INK if bold else MUTED)
        self.canvas.setFont(font, size)
        base = self.y - size
        for index, line in enumerate(lines):
            self.canvas.drawString(MARGIN, base - index * size * 1.24, line)
        self.y -= height

    def stats_table_row(self, cells, widths, bold=False):
        size = BODY
        font = FONT_BOLD if bold else FONT
        height = size * 1.5
        self.ensure_space(height)
        x = MARGIN
        self.canvas.setFont(font, size)
        for index, cell in enumerate(cells):
            width = widths[index]
            if index == len(cells) - 1:
                self.canvas.setFillColor(INK if bold else MUTED)
                self.canvas.drawRightString(x + width, self.y - size, cell)
            else:
                self.canvas.setFillColor(INK if bold else MUTED)
                self.canvas.drawString(x, self.y - size, cell)
            x += width
        self.y -= height

    def stats_chart(self, drawing, caption):
        size = META
        if drawing.width <= 0 or drawing.height <= 0:
            raise StatsError("chart has no size")
        scale = self.content_w / drawing.width
        height = drawing.height * scale
        self.ensure_space(height + size * 1.4 + 4 * mm)
        drawing.scale(scale, scale)
        drawing.width *= scale
        drawing.height *= scale
        drawing.drawOn(self.canvas, MARGIN, self.y - height)
        self.y -= height + 2 * mm
        self.canvas.setFillColor(MUTED)
        self.canvas.setFont(FONT, size)
        lines = wrap_lines(caption, FONT, size, self.content_w, 2)
        for index, line in enumerate(lines):
            self.canvas.drawString(MARGIN, self.y - size - index * size * 1.22, line)
        self.y -= len(lines) * size * 1.22 + 4 * mm

    def draw_stats(self, totals):
        date_key, day, series = load_totals(totals)
        rows = stats_rows(day)
        total = int(day["totalMinPaVos"])
        date_label = display_date(date_key)
        self.stats_heading(STATS_TITLE)
        self.stats_paragraph(STATS_HEADLINE.format(date=date_label, total=format_count(total)), bold=True)
        obtained = day["itemsObtained"]
        breakdown = (
            f"{format_count(obtained.get('songs', 0))} canciones, "
            f"{format_count(obtained.get('accessories', 0))} accesorios, "
            f"{format_count(obtained.get('skins', 0))} skins, "
            f"{format_count(obtained.get('emotes', 0))} gestos y "
            f"{format_count(obtained.get('other', 0))} vehiculos e instrumentos"
        )
        coverage = STATS_COVERAGE.format(
            purchases=format_count(day["purchases"]),
            items=format_count(day["itemsCovered"]),
        )
        coverage += f" ({breakdown})"
        overlap = int(day["overlapItems"])
        if overlap == 0:
            coverage += STATS_UNIQUE
        else:
            coverage += STATS_OVERLAP.format(overlap=format_count(overlap))
        self.stats_paragraph(coverage)
        self.stats_paragraph(STATS_LOTS.format(
            catalog=format_count(day["namedBundlesInCatalog"]),
            chosen=format_count(day["chosenNamedBundles"]),
        ))
        row_widths = [self.content_w * 0.4, self.content_w * 0.3, self.content_w * 0.3]
        self.stats_table_row(["Categoria", "PaVos", "Compras"], row_widths, bold=True)
        for category, label, pa_vos, purchases in rows:
            if category == StatsCategory.SKINS:
                label_text = f"Skins ({self.skins_label(day, purchases)})"
            else:
                label_text = label
            self.stats_table_row([label_text, format_count(pa_vos), format_count(purchases)], row_widths)

        workdir = tempfile.mkdtemp(prefix="fortnite-stats-")
        chart_title = STATS_CHART_TITLE.format(date=date_label, total=format_count(total))
        x_labels = [f"{label} ({format_count(purchases)})" for _, label, _, purchases in rows]
        bar_values = [pa_vos for _, _, pa_vos, _ in rows]
        bar_source = "\n".join([
            "xychart-beta",
            f"    title {quoted(chart_title)}",
            f"    x-axis [{', '.join(quoted(label) for label in x_labels)}]",
            f"    y-axis {quoted('Costo teórico en PaVos')} 0 --> {chart_max(bar_values)}",
            f"    bar [{', '.join(str(value) for value in bar_values)}]",
        ])
        bar_chart = render_chart(bar_source, workdir, f"categories-{date_key}")
        self.stats_chart(bar_chart, chart_title)

        if len(series) <= 1:
            self.stats_paragraph(STATS_SERIES_SINGLE, bold=True)
        else:
            line_labels = [display_date(key)[:5] for key, _ in series]
            line_values = [value for _, value in series]
            line_source = "\n".join([
                "xychart-beta",
                f"    title {quoted(STATS_SERIES_TITLE)}",
                f"    x-axis [{', '.join(quoted(label) for label in line_labels)}]",
                f"    y-axis {quoted('Costo teórico en PaVos')} 0 --> {chart_max(line_values)}",
                f"    line [{', '.join(str(value) for value in line_values)}]",
            ])
            line_chart = render_chart(line_source, workdir, f"series-{date_key}")
            self.stats_chart(line_chart, STATS_SERIES_NOTE)

        self.stats_paragraph(STATS_METHOD_PRICES, size=META)
        self.stats_paragraph(STATS_METHOD_NO_PRORATE, size=META)
        return total, overlap, 2 if len(series) > 1 else 1

    def skins_label(self, day, skin_purchases):
        singles = int(day.get("chosenSingles") or 0)
        combos = int(day.get("chosenComboOffers") or 0)
        combo_skins = max(skin_purchases - singles, 0)
        if combos <= 0 or combo_skins <= 0:
            return f"{format_count(skin_purchases)} sueltas"
        return f"{format_count(singles)} sueltas + {format_count(combo_skins)} ofertas de skin con extras"

    def draw_footer(self):
        if self.y < MARGIN + 22 * mm:
            self.new_page()
        canvas = self.canvas
        canvas.saveState()
        canvas.setStrokeColor(ROW_LINE)
        canvas.setLineWidth(0.8)
        canvas.line(MARGIN, MARGIN + 16 * mm, PAGE_W - MARGIN, MARGIN + 16 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont(FONT, FOOTER_SIZE)
        lines = wrap_lines(FOOTER, FONT, FOOTER_SIZE, self.content_w, 6)
        base = MARGIN + 11 * mm
        for index, line in enumerate(lines):
            canvas.drawString(MARGIN, base - index * FOOTER_SIZE * 1.22, line)
        canvas.restoreState()

    def save(self):
        self.canvas.save()


def unique_by_id(items):
    seen = set()
    result = []
    for item in items:
        offer = item.get("offer") or {}
        offer_id = offer.get("offerId")
        if offer_id in seen:
            continue
        seen.add(offer_id)
        result.append(item)
    return result


def main():
    if len(sys.argv) not in (4, 5):
        print("usage: python3 tools/pdf_digest.py <changes.json> <snapshot.json> <out.pdf> [totals.json]", file=sys.stderr)
        sys.exit(1)
    changes_path, snapshot_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    totals_path = sys.argv[4] if len(sys.argv) == 5 else None
    with open(changes_path, "r", encoding="utf-8") as handle:
        changes_data = json.load(handle)
    with open(snapshot_path, "r", encoding="utf-8") as handle:
        snapshot = json.load(handle)
    changes = changes_data.get("changes") or []
    offers = snapshot.get("offers") or []

    non_vbucks_ids = set()
    unverified_ids = set()
    verified_offers = []
    for offer in offers:
        status = currency_status(offer)
        if status == "verified":
            verified_offers.append(offer)
        elif status == "unverified":
            unverified_ids.add(offer.get("offerId"))
        else:
            non_vbucks_ids.add(offer.get("offerId"))
    offers = verified_offers
    verified_changes = []
    for entry in changes:
        offer = entry.get("offer") or {}
        status = currency_status(offer)
        if status == "verified":
            verified_changes.append(entry)
        elif status == "unverified":
            unverified_ids.add(offer.get("offerId"))
        else:
            non_vbucks_ids.add(offer.get("offerId"))
    changes = verified_changes
    for entry in changes_data.get("excludedNonVbucks") or []:
        non_vbucks_ids.add(entry.get("offerId"))
    for entry in changes_data.get("excludedUnverified") or []:
        unverified_ids.add(entry.get("offerId"))
    unverified_ids -= non_vbucks_ids
    excluded_ids = non_vbucks_ids | unverified_ids

    by_kind = {"added": [], "removed": [], "priceChanged": []}
    for entry in changes:
        kind = entry.get("kind")
        if kind in by_kind:
            by_kind[kind].append(entry)

    changed_ids = {entry["offer"]["offerId"] for entry in by_kind["added"] + by_kind["priceChanged"] if (entry.get("offer") or {}).get("offerId")}
    unchanged = [offer for offer in offers if offer.get("offerId") not in changed_ids]

    unresolved = []
    all_offers = list(offers) + [entry.get("offer") or {} for entry in changes]
    seen_ids = set()
    for offer in all_offers:
        offer_id = offer.get("offerId")
        if offer_id in seen_ids:
            continue
        seen_ids.add(offer_id)
        if offer_id in excluded_ids:
            continue
        if not resolve_name(offer):
            unresolved.append(offer_id)
    if unresolved:
        print("unresolved offers: " + ", ".join(str(value) for value in unresolved), file=sys.stderr)
        sys.exit(2)

    digest = Digest(out_path, changes_data)

    unchanged_rows = [{"kind": "unchanged", "offer": item["offer"]} for item in unique_by_id([{"offer": offer} for offer in unchanged])]
    section_title = BASELINE_CATALOG_TITLE if digest.baseline else UNCHANGED_TITLE
    digest.start_section("unchanged", section_title, len(unchanged_rows))
    if unchanged_rows:
        for entry in unchanged_rows:
            digest.draw_row(entry["offer"], entry, resolve_name(entry["offer"]))
    else:
        digest.empty_note("Ninguna oferta se mantuvo exactamente igual.")

    sections = [] if digest.baseline else [
        ("added", ADDED_TITLE, by_kind["added"], "No hubo ofertas nuevas."),
        ("removed", REMOVED_TITLE, by_kind["removed"], "No salió ninguna oferta."),
        ("priceChanged", PRICE_TITLE, by_kind["priceChanged"], "No hubo cambios de precio."),
    ]
    for key, title, entries, empty_text in sections:
        rows = unique_by_id(entries)
        digest.start_section(key, title, len(rows))
        if rows:
            for entry in rows:
                digest.draw_row(entry["offer"], entry, resolve_name(entry["offer"]))
        else:
            digest.empty_note(empty_text)

    if non_vbucks_ids:
        digest.wrapped_note(f"Se excluyeron {len(non_vbucks_ids)} ofertas que no se compran con PaVos, según el marcador de moneda de fortnite-api.com.")
    if unverified_ids:
        digest.wrapped_note(f"Se excluyeron {len(unverified_ids)} ofertas cuya moneda no pudo verificarse en fortnite-api.com.")

    try:
        stats_result = digest.draw_stats(totals_path) if totals_path else None
    except StatsError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)

    digest.draw_footer()
    digest.save()

    if stats_result is not None:
        total, overlap, charts = stats_result
        print(f"stats section: totalMin={total} overlap={overlap} charts={charts}")
    print(f"PDF written: {out_path} ({len(changes)} changes, {len(unchanged)} unchanged)")
    print(f"images: {digest.images_ok}/{digest.images_total} visible, {digest.images_pending} pendientes")
    print(f"excluded non-V-Bucks: {len(non_vbucks_ids)}")
    print(f"excluded unverified: {len(unverified_ids)}")


if __name__ == "__main__":
    main()
