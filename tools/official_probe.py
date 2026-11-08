"""Probe: can headless Chromium on a GitHub Actions runner read the official
item-shop page past Cloudflare, and does it contain the embedded catalog
payload? Manual diagnostics only; no data is written to the repo."""

import json
import re
import sys

from playwright.sync_api import sync_playwright

URL = "https://www.fortnite.com/item-shop?lang=es-ES"

ENQUEUE_RE = re.compile(r'enqueue\("((?:[^"\\]|\\.)*)"\)')


def extract_payloads(html: str) -> list:
    payloads = []
    for match in ENQUEUE_RE.finditer(html):
        raw = match.group(1)
        try:
            decoded = json.loads(f'"{raw}"')
            payloads.append(json.loads(decoded))
        except Exception:
            continue
    return payloads


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="es-ES",
        )
        page = context.new_page()
        response = page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        status = response.status if response else None
        html = page.content()
        title = page.title()
        browser.close()
    payloads = extract_payloads(html)
    print(json.dumps({
        "http_status": status,
        "title": title,
        "html_bytes": len(html),
        "enqueue_payloads": len(payloads),
        "cloudflare_challenge": "cf_challenge" in html or "Just a moment" in title,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
