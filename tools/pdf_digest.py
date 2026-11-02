import json
import sys
import urllib.request
from io import BytesIO
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth

SECTION_TITLES = {"added": "Nuevos", "removed": "Salieron", "priceChanged": "Cambios de precio"}
INK = HexColor("#1a1a2e")
MUTED = HexColor("#6b6b7b")
LINE = HexColor("#d8d8e0")
PLACEHOLDER = HexColor("#e8e8ef")

def load_thumb(url, box):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "shop-digest/1.0"})
        raw = Image.open(BytesIO(urllib.request.urlopen(req, timeout=20).read()))
        if raw.mode in ("RGBA", "LA") or (raw.mode == "P" and "transparency" in raw.info):
            bg = Image.new("RGB", raw.size, (255, 255, 255))
            bg.paste(raw.convert("RGBA"), mask=raw.convert("RGBA").split()[-1])
            img = bg
        else:
            img = raw.convert("RGB")
        img.thumbnail((box, box), Image.LANCZOS)
        return img
    except Exception:
        return None

def wrap(text, font, size, width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if stringWidth(trial, font, size) <= width:
            cur = trial
        else:
            lines.append(cur or w)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:2]

def main():
    src, out_path = sys.argv[1], sys.argv[2]
    data = json.load(open(src))
    changes = data.get("changes", [])
    by_kind = {k: [c for c in changes if c["kind"] == k] for k in ("added", "removed", "priceChanged")}
    page_w, page_h = A4
    margin = 14 * mm
    thumb = 15 * mm
    row_h = 19 * mm
    c = Canvas(out_path, pagesize=A4)
    c.setTitle(f"Cambios tienda Fortnite {data['shopDate']}")
    y = page_h - margin
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 17)
    c.drawString(margin, y - 6 * mm, "Tienda de Fortnite: cambios del d\u00eda")
    c.setFont("Helvetica", 10.5)
    c.setFillColor(MUTED)
    c.drawString(margin, y - 12 * mm, f"Tienda del {data['shopDate']} comparada con la del {data.get('previousDate') or 'dia anterior'}")
    y -= 20 * mm
    def new_page():
        nonlocal y
        c.showPage()
        y = page_h - margin
    def section_header(title, count):
        nonlocal y
        if y < margin + row_h * 1.5:
            new_page()
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 12.5)
        c.drawString(margin, y - 4 * mm, f"{title} ({count})")
        y -= 8 * mm
        c.setStrokeColor(LINE)
        c.setLineWidth(0.6)
        c.line(margin, y, page_w - margin, y)
        y -= 2 * mm
    def item_row(change):
        nonlocal y
        if y < margin + row_h:
            new_page()
        offer = change["offer"]
        img = load_thumb(offer.get("imageUrl"), 128) if offer.get("imageUrl") else None
        top = y - 3 * mm
        if img:
            c.drawImage(ImageReader(img), margin, top - thumb, thumb, thumb, preserveAspectRatio=True, anchor="c", mask="auto")
        else:
            c.setFillColor(PLACEHOLDER)
            c.roundRect(margin, top - thumb, thumb, thumb, 2 * mm, stroke=0, fill=1)
        tx = margin + thumb + 5 * mm
        tw = page_w - margin - tx
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 10.5)
        for i, line in enumerate(wrap(offer.get("name") or "Sin nombre", "Helvetica-Bold", 10.5, tw)):
            c.drawString(tx, top - 4 * mm - i * 4.4 * mm, line)
        meta = []
        if offer.get("section"):
            meta.append(offer["section"])
        if change["kind"] == "priceChanged":
            meta.append(f"{change['oldPrice']} -> {change['newPrice']} PaVos")
        elif offer.get("finalPrice") is not None:
            meta.append(f"{offer['finalPrice']} PaVos")
        if offer.get("outDate"):
            meta.append(f"sale aprox. {offer['outDate'][8:10]}/{offer['outDate'][5:7]}")
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 9.5)
        c.drawString(tx, top - thumb + 3.5 * mm, "  |  ".join(meta))
        y -= row_h
        c.setStrokeColor(LINE)
        c.setLineWidth(0.4)
        c.line(margin, y + 2 * mm, page_w - margin, y + 2 * mm)
    for kind in ("added", "removed", "priceChanged"):
        if by_kind[kind]:
            section_header(SECTION_TITLES[kind], len(by_kind[kind]))
            for change in by_kind[kind]:
                item_row(change)
            y -= 3 * mm
    if not changes:
        c.setFont("Helvetica", 11)
        c.setFillColor(MUTED)
        c.drawString(margin, y, "Sin cambios respecto del chequeo anterior.")
    if y < margin + 14 * mm:
        new_page()
    c.setFillColor(MUTED)
    c.setFont("Helvetica", 8.5)
    c.drawString(margin, margin + 4 * mm, "Datos de fortnite-api.com. Las fechas de salida son estimadas por esa API (no garantizadas);")
    c.drawString(margin, margin, "la fecha exacta de cada objeto se ve dentro del juego, en la propia tienda.")
    c.save()
    print(f"PDF written: {out_path} ({len(changes)} changes)")

main()
