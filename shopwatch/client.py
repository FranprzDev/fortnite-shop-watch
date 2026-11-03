from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Optional

from .models import Snapshot
from .normalize import normalize_entry

SHOP_URL = "https://fortnite-api.com/v2/shop?language=es"
USER_AGENT = "fortnite-shop-watch/1.0"
REQUEST_TIMEOUT_MS = 20000
MAX_ATTEMPTS = 3
RETRY_DELAY_MS = 3000


def request_shop() -> dict:
    request = urllib.request.Request(SHOP_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_MS / 1000) as response:
        status = response.status if hasattr(response, "status") else response.getcode()
        if status != 200:
            raise ValueError(f"shop request failed with HTTP {status}")
        raw = response.read().decode("utf-8")
    return json.loads(raw)


def fetch_shop_snapshot() -> Snapshot:
    last_error: Optional[Exception] = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            body = request_shop()
            data = body.get("data")
            if (
                body.get("status") != 200
                or not data
                or not isinstance(data.get("entries"), list)
                or not isinstance(data.get("date"), str)
                or not isinstance(data.get("hash"), str)
            ):
                raise ValueError("shop response failed validation")
            offers = []
            for entry in data["entries"]:
                offer = normalize_entry(entry)
                if offer is not None:
                    offers.append(offer)
            if len(offers) == 0:
                raise ValueError("shop response contained no valid offers")
            return Snapshot(date=data["date"], hash=data["hash"], offers=offers)
        except Exception as error:  # noqa: BLE001 - mirror TS catch-all
            last_error = error
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_DELAY_MS / 1000)
    raise last_error if last_error is not None else RuntimeError("shop request failed")
