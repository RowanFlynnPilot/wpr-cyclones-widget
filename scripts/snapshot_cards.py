#!/usr/bin/env python3
"""
Daily snapshot script — renders the ?mini=tickets card as a static PNG
that can be embedded in email newsletters (where iframes are stripped).

Serves docs/ locally, opens the card in headless Chromium, and writes the
cropped card to docs/snapshots/cyclones-today.png. Unlike the baseball
widget, the hockey card renders fully synchronously from static JSON, so
there are no async fetches to wait on.

Run by .github/workflows/snapshot.yml once a day, then committed back to
the repo. GitHub Pages serves it at
  https://rowanflynnpilot.github.io/wpr-cyclones-widget/snapshots/cyclones-today.png

Usage:
    pip install -r scripts/requirements.txt
    playwright install --with-deps chromium
    python scripts/snapshot_cards.py
"""

import functools
import http.server
import socketserver
import sys
import threading
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip install -r scripts/requirements.txt")
    sys.exit(1)

PORT = 8765
ROOT = Path(__file__).parent.parent
DOCS_DIR = ROOT / "docs"
SNAPSHOTS_DIR = DOCS_DIR / "snapshots"
TEAM = "cyclones"
# Retina-quality PNG so the 380px-wide embed looks crisp on high-DPI screens.
DEVICE_SCALE = 2


def start_server():
    """Serve docs/ on PORT in a background daemon thread."""
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(DOCS_DIR)
    )
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f"Local server running on http://127.0.0.1:{PORT}")
    return httpd


def snapshot(page):
    url = f"http://127.0.0.1:{PORT}/?team={TEAM}&mini=tickets"
    print(f"\n[{TEAM}] Loading {url}")
    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_selector(".mt", timeout=10000)
    card = page.locator(".mt")
    out = SNAPSHOTS_DIR / f"{TEAM}-today.png"
    card.screenshot(path=str(out))
    print(f"[{TEAM}] Wrote {out} ({out.stat().st_size:,} bytes)")


def main():
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    httpd = start_server()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": 380, "height": 700},
            device_scale_factor=DEVICE_SCALE,
        )
        snapshot(page)
        browser.close()
    httpd.shutdown()
    print("\n✓ Done!")


if __name__ == "__main__":
    main()
