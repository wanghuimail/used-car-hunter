"""Temporary probe script for site structure."""
import json
import re
import urllib.request

AT_URL = (
    "https://www.autotrader.ca/cars/honda/cr-v/reg_on/cit_ottawa"
    "?rcp=15&rcs=0&srt=35&yrl=2022&yrh=2026&prx=75&prv=Ontario&loc=K2K2M4&hpr=Y&wcp=Y"
)
CG_URL = (
    "https://www.cargurus.ca/search"
    "?zip=K2K2M4&distance=75&makeModelTrimPaths=m7/d306"
    "&sortType=DEAL_SCORE&sortDirection=ASC"
)


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-CA,en;q=0.9",
            "Accept-Encoding": "identity",
            "Referer": "https://www.cargurus.ca/",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", "replace")


def probe_autotrader(html: str) -> None:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    if not m:
        print("AT: no __NEXT_DATA__")
        return
    data = json.loads(m.group(1))
    props = data.get("props", {}).get("pageProps", {})
    print("AT pageProps keys:", list(props.keys()))

    def walk(obj, depth=0):
        if depth > 10:
            return
        if isinstance(obj, dict):
            for key in ("listings", "vehicles", "results", "searchResults"):
                val = obj.get(key)
                if isinstance(val, list) and val and isinstance(val[0], dict):
                    print(f"AT FOUND {key} count={len(val)} sample={list(val[0].keys())[:20]}")
            for v in obj.values():
                walk(v, depth + 1)
        elif isinstance(obj, list) and obj:
            walk(obj[0], depth + 1)

    walk(props)


def probe_cargurus(html: str) -> None:
    print("CG len", len(html))
    patterns = (
        "__NEXT_DATA__",
        "searchResults",
        "listingTitle",
        "dealRating",
        "window.__INITIAL_STATE__",
        "preloadedState",
        "tileData",
        "listingId",
        "application/ld+json",
    )
    for pat in patterns:
        print(f"CG {pat}:", html.find(pat))

    for m in re.finditer(r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            blob = json.loads(m.group(1))
            if isinstance(blob, dict) and blob.get("@type") in ("ItemList", "Car", "Product"):
                print("LD+JSON type", blob.get("@type"), "keys", list(blob.keys())[:15])
        except json.JSONDecodeError:
            pass

    for m in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.DOTALL):
        text = m.group(1).strip()
        if "listingId" in text and len(text) > 500:
            print("script snippet with listingId, len", len(text), "start", text[:120])
            break


if __name__ == "__main__":
    print("=== AutoTrader ===")
    at_html = fetch(AT_URL)
    print("AT html len", len(at_html))
    probe_autotrader(at_html)
    print("=== CarGurus ===")
    cg_html = fetch(CG_URL)
    probe_cargurus(cg_html)
