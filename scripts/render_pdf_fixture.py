"""Render a PDF preview with a local fixture thumbnail (zero network).

Used by CI to validate the PDF pipeline on the exact pinned dependency
set: pdf.fetch_thumb is replaced by a deterministic local image, so no
external CDN is contacted. Defaults to the newest reports/*.json changes
file and data/shop-latest.json.

usage: python scripts/render_pdf_fixture.py [changes.json] [snapshot.json] [out.pdf]
"""

from __future__ import annotations

import glob
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image  # noqa: E402

from shopwatch import pdf  # noqa: E402


def fixture_image():
    random.seed(7)
    data = bytes(random.getrandbits(8) for _ in range(64 * 64 * 3))
    return Image.frombytes("RGB", (64, 64), data)


def main():
    changes = sorted(glob.glob("reports/2*.json"))[-1]
    snapshot = "data/shop-latest.json"
    out = "pdf-preview.pdf"
    if len(sys.argv) >= 2:
        changes = sys.argv[1]
    if len(sys.argv) >= 3:
        snapshot = sys.argv[2]
    if len(sys.argv) >= 4:
        out = sys.argv[3]
    pdf.fetch_thumb = lambda url: fixture_image()
    pdf.generate_pdf(changes, snapshot, out)


if __name__ == "__main__":
    main()
