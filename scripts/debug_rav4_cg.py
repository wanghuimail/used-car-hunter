import json
import urllib.request

from scripts.debug_cg import extract_json_object

url = "https://www.cargurus.ca/search?zip=K2K2M4&distance=75&makeModelTrimPaths=m7/d295&sortType=DEAL_SCORE&sortDirection=ASC"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.cargurus.ca/"})
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

pos = 0
count = 0
while count < 5:
    marker = html.find('"type":"LISTING_USED', pos)
    if marker < 0:
        break
    data_start = html.find('"data":', marker) + len('"data":')
    raw = extract_json_object(html, data_start)
    pos = data_start + 1
    if not raw:
        continue
    onto = raw.get("ontologyData") or {}
    fuel = (raw.get("fuelData") or {}).get("localizedType")
    print(
        count,
        onto.get("makeName"),
        onto.get("modelName"),
        onto.get("carYear"),
        fuel,
        (raw.get("priceData") or {}).get("current"),
    )
    count += 1
