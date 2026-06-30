import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import urllib.request
from scripts.debug_cg import extract_json_object
from src.config import get_models
from src.scraper.cargurus import CarGurusScraper

cfg = next(m for m in get_models() if m["key"] == "cx-5")
url = CarGurusScraper()._search_url(cfg, 1)
html = CarGurusScraper()._fetch_html(url)
scraper = CarGurusScraper()

pos = 0
while True:
    marker = html.find('"type":"LISTING_USED', pos)
    if marker < 0:
        break
    data_start = html.find('"data":', marker) + len('"data":')
    raw = extract_json_object(html, data_start)
    pos = data_start + 1
    if not raw:
        continue
    onto = raw.get("ontologyData") or {}
    if onto.get("modelName") != "CX-5":
        continue
    parsed = scraper._parse_tile(raw, cfg)
    print("tile year", onto.get("carYear"), "parsed", parsed is not None)
    if parsed:
        print(parsed.year, parsed.price, parsed.dealer_name)
    else:
        fuel = (raw.get("fuelData") or {}).get("localizedType")
        price = (raw.get("priceData") or {}).get("current")
        print("fuel", fuel, "price", price, "title", raw.get("listingTitle"))
