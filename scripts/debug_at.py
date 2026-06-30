"""Debug AutoTrader parsing filters."""
import json
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.scraper.autotrader import AutoTraderScraper

url = (
    "https://www.autotrader.ca/cars/honda/cr-v/reg_on/cit_ottawa"
    "?rcp=15&rcs=0&srt=35&yrl=2022&yrh=2026&prx=75&prv=Ontario&loc=K2K2M4&hpr=Y&wcp=Y"
)
headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
r = httpx.get(url, headers=headers, timeout=30)
match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL)
data = json.loads(match.group(1))
raw = data["props"]["pageProps"]["listings"][0]
print("RAW KEYS", raw.keys())
print("vehicle", json.dumps(raw.get("vehicle"), indent=2)[:2000])
print("seller", json.dumps(raw.get("seller"), indent=2)[:1000])
print("price", raw.get("price"))
scraper = AutoTraderScraper()
model_cfg = {"key": "cr-v", "make": "Honda", "model": "CR-V", "autotrader": {"path": "honda/cr-v"}}
for i, raw in enumerate(data["props"]["pageProps"]["listings"][:15]):
    v = raw["vehicle"]
    print(
        i,
        v.get("modelYear"),
        raw["seller"].get("type"),
        raw["price"].get("priceRaw"),
        v.get("fuel"),
    )

years = [raw["vehicle"].get("modelYear") for raw in data["props"]["pageProps"]["listings"]]
print("min year", min(years), "max year", max(years), "count 2022+", sum(1 for y in years if y and y >= 2022))
