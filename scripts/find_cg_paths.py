"""Find CarGurus model trim paths."""
import urllib.request

BASE = "https://www.cargurus.ca/search?zip=K2K2M4&distance=75&sortType=DEAL_SCORE&sortDirection=ASC"
paths = [
    "m7/d306",
    "m6/d123",
    "m2/d123",
    "m1/d123",
    "m45/d662",
    "m25/d2479",
]
headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.cargurus.ca/"}
for path in paths:
    url = f"{BASE}&makeModelTrimPaths={path}"
    req = urllib.request.Request(url, headers=headers)
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    title_idx = html.find('"listingTitle"')
    title = html[title_idx : title_idx + 80] if title_idx >= 0 else "none"
    print(path, "->", title)
