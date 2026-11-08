"""Security tests for thumbnail fetching (pure fixtures, no network)."""

from __future__ import annotations

import struct
import zlib
from io import BytesIO

from shopwatch import pdf


def _boom(*args, **kwargs):
    raise AssertionError("urlopen must not be called for rejected URLs")


def _tiny_png_bytes():
    def chunk(tag, data):
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * 2 for _ in range(2))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, _limit=-1):
        return self._payload


def test_rejects_non_https_without_fetching(monkeypatch):
    monkeypatch.setattr(pdf.urllib.request, "urlopen", _boom)
    assert pdf.fetch_thumb("http://cdn.fortnite-api.com/x.png") is None


def test_rejects_unknown_host_without_fetching(monkeypatch):
    monkeypatch.setattr(pdf.urllib.request, "urlopen", _boom)
    assert pdf.fetch_thumb("https://evil.example.com/x.png") is None
    assert pdf.fetch_thumb("https://cdn.fortnite-api.com.evil.example.com/x.png") is None


def test_rejects_file_and_data_schemes_without_fetching(monkeypatch):
    monkeypatch.setattr(pdf.urllib.request, "urlopen", _boom)
    assert pdf.fetch_thumb("file:///etc/passwd") is None
    assert pdf.fetch_thumb("data:image/png;base64,AAAA") is None


def test_rejects_oversized_payload(monkeypatch):
    big = b"\x00" * (pdf.MAX_IMAGE_BYTES + 1)
    monkeypatch.setattr(
        pdf.urllib.request, "urlopen", lambda *a, **k: _FakeResponse(big)
    )
    assert pdf.fetch_thumb("https://cdn.fortnite-api.com/x.png") is None


def test_accepts_allowlisted_https_image(monkeypatch):
    payload = _tiny_png_bytes()
    monkeypatch.setattr(
        pdf.urllib.request, "urlopen", lambda *a, **k: _FakeResponse(payload)
    )
    # isolate the fetch/validation path from thumbnail heuristics
    monkeypatch.setattr(pdf, "is_visible", lambda *a, **k: True)
    monkeypatch.setattr(pdf, "shrink_thumbnail", lambda img: img)
    thumb = pdf.fetch_thumb("https://cdn.fortnite-api.com/x.png")
    assert thumb is not None


def test_empty_url_returns_none(monkeypatch):
    monkeypatch.setattr(pdf.urllib.request, "urlopen", _boom)
    assert pdf.fetch_thumb(None) is None
    assert pdf.fetch_thumb("") is None
