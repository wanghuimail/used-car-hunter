"""Discover CarGurus make IDs."""
import re
import urllib.request

headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.cargurus.ca/"}
for make_id in range(1, 80):
    url = (
        f"https://www.cargurus.ca/search?zip=K2K2M4&distance=75"
        f"&makeModelTrimPaths=m{make_id}&sortType=DEAL_SCORE&sortDirection=ASC"
    )
    req = urllib.request.Request(url, headers=headers)
    try:
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    except Exception:
        continue
    m = re.search(r'"make":"([^"]+)".*?"model":"([^"]+)"', html)
    if m:
        print(f"m{make_id} -> {m.group(1)} {m.group(2)}")
