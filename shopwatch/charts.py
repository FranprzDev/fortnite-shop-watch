"""Barras nativas de reportlab para la página de estadísticas."""

from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth

INK = HexColor("#14142b")
ACCENT = HexColor("#ffd23f")
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
BODY = 13

CATEGORY_ORDER = ("songs", "bundles", "skins", "accessories", "emotes", "other")
CATEGORY_LABELS = {
    "songs": "Canciones",
    "bundles": "Lotes",
    "skins": "Skins",
    "accessories": "Accesorios",
    "emotes": "Gestos",
    "other": "Otros",
}


def _count(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0
    return int(round(value))


def _format_count(value):
    return f"{_count(value):,}".replace(",", ".")


def _label(key):
    text = getattr(key, "value", key)
    text = str(text)
    return CATEGORY_LABELS.get(text, text.replace("_", " ").capitalize())


def _values(entry):
    if isinstance(entry, dict):
        value = entry.get("paVos")
        if value is None:
            value = entry.get("value")
        if value is None:
            value = entry.get("count")
        purchases = entry.get("purchases")
        if purchases is None:
            purchases = entry.get("compras")
        return _count(value), None if purchases is None else _count(purchases)
    return _count(entry), None


def normalize_categories(stats):
    data = stats.get("categories", stats) if isinstance(stats, dict) else stats
    rows = []
    if isinstance(data, dict):
        keys = list(data.keys())
        ordered = [key for key in CATEGORY_ORDER if key in data]
        ordered += [key for key in keys if key not in CATEGORY_ORDER]
        for key in ordered:
            value, purchases = _values(data[key])
            rows.append((_label(key), value, purchases))
    elif isinstance(data, (list, tuple)):
        for entry in data:
            if isinstance(entry, dict):
                key = entry.get("label")
                if key is None:
                    key = entry.get("name")
                if key is None:
                    key = entry.get("category")
                value, purchases = _values(entry)
                rows.append((_label(key), value, purchases))
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                value, purchases = _values(entry[1])
                if purchases is None and len(entry) > 2:
                    purchases = _count(entry[2])
                rows.append((_label(entry[0]), value, purchases))
    return rows


def _caption(value, purchases):
    text = f"{_format_count(value)} PaVos"
    if purchases is not None:
        text += f" · {_format_count(purchases)} compras"
    return text


def draw_stats_bars(
    canvas,
    stats,
    x,
    y,
    width,
    *,
    label_width=34 * mm,
    bar_height=8 * mm,
    gap=4.5 * mm,
    font_size=BODY,
    max_value=None,
    bar_color=ACCENT,
    text_color=INK,
):
    rows = normalize_categories(stats)
    if not rows:
        return y
    captions = [_caption(value, purchases) for _, value, purchases in rows]
    peak = max(value for _, value, _ in rows)
    if max_value is not None and max_value > 0:
        peak = max(peak, max_value)
    peak = peak or 1
    max_text = max(stringWidth(text, FONT, font_size) for text in captions)
    scale = (width - label_width - max_text - 6 * mm) / peak
    if scale < 0:
        scale = 0.0
    for (label, value, _), caption in zip(rows, captions):
        canvas.setFillColor(text_color)
        canvas.setFont(FONT_BOLD, font_size)
        canvas.drawRightString(x + label_width - 3 * mm, y - bar_height + 2.6 * mm, label)
        bar_width = max(value * scale, 1.2 * mm)
        canvas.setFillColor(bar_color)
        canvas.rect(x + label_width, y - bar_height, bar_width, bar_height, fill=1, stroke=0)
        canvas.setFillColor(text_color)
        canvas.setFont(FONT, font_size)
        canvas.drawString(x + label_width + bar_width + 2.5 * mm, y - bar_height + 2.6 * mm, caption)
        y -= bar_height + gap
    return y


draw_category_bars = draw_stats_bars
draw_stats = draw_stats_bars