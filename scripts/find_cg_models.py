"""Discover CarGurus model IDs for target SUVs."""
import re
import urllib.request

headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.cargurus.ca/"}
targets = {
    "Honda": ["m6"],
    "Toyota": [f"m{i}" for i in range(1, 80)],
    "Mazda": [f"m{i}" for i in range(1, 80)],
}
need = {"Honda": "CR-V", "Toyota": "RAV4", "Mazda": "CX-5"}

for make, ids in targets.items():
    model = need[make]
    found = []
    for make_id in ids:
        url = (
            f"https://www.cargurus.ca/search?zip=K2K2M4&distance=75"
            f"&makeModelTrimPaths={make_id}&sortType=DEAL_SCORE&sortDirection=ASC"
        )
        req = urllib.request.Request(url, headers=headers)
        try:
            html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")
        except Exception:
            continue
        if f'"model":"{model}"' in html or f'"modelName":"{model}"' in html:
            m = re.search(rf'"make":"{make}".*?"model":"{model}"', html)
            d = re.search(rf'"modelId":"(d\d+)".*?"modelName":"{model}"', html)
            found.append((make_id, bool(m), d.group(1) if d else None))
    print(make, model, "->", found[:5])
