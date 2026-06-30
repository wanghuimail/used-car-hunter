"""Probe CarGurus embedded listing JSON."""
import json
import re
import urllib.request


def extract_json_object(html: str, start: int) -> dict | None:
    if start < 0 or start >= len(html) or html[start] != "{":
        return None
    depth = 0
    for i in range(start, min(start + 12000, len(html))):
        ch = html[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


url = (
    "https://www.cargurus.ca/search?zip=K2K2M4&distance=75"
    "&makeModelTrimPaths=m7/d306&sortType=DEAL_SCORE&sortDirection=ASC"
)
req = urllib.request.Request(
    url,
    headers={
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-CA,en;q=0.9",
        "Referer": "https://www.cargurus.ca/",
    },
)
html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

listing_objects = []
pos = 0
while True:
    start = html.find('{"listingId"', pos)
    if start < 0:
        break
    obj = extract_json_object(html, start)
    if obj:
        listing_objects.append(obj)
    pos = start + 1

print("listing objects", len(listing_objects))
if listing_objects:
    print(json.dumps(listing_objects[0], indent=2)[:2000])

idx = html.find('"type":"LISTING_USED')
if idx >= 0:
    data_idx = html.find('"data":', idx) + len('"data":')
    obj = extract_json_object(html, data_idx)
    if obj:
        print("sellerData", json.dumps(obj.get("sellerData", {}), indent=2))
        print(
            "ontology",
            obj.get("ontologyData", {}).get("makeName"),
            obj.get("ontologyData", {}).get("modelName"),
        )
