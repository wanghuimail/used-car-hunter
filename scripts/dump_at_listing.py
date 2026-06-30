"""Dump one AutoTrader listing for schema reference."""
import json
import re
import urllib.request

URL = (
    "https://www.autotrader.ca/cars/honda/cr-v/reg_on/cit_ottawa"
    "?rcp=15&rcs=0&srt=35&yrl=2022&yrh=2026&prx=75&prv=Ontario&loc=K2K2M4&hpr=Y&wcp=Y"
)
req = urllib.request.Request(
    URL,
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    },
)
html = urllib.request.urlopen(req, timeout=30).read().decode()
match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
data = json.loads(match.group(1))
listing = data["props"]["pageProps"]["listings"][0]
print(json.dumps(listing, indent=2)[:8000])
