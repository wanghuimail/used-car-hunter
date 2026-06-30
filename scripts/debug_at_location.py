import json
import re

import httpx

url = (
    "https://www.autotrader.ca/cars/honda/cr-v/reg_on/cit_ottawa"
    "?rcp=15&rcs=0&yrl=2022&yrh=2026&prx=75&prv=Ontario&loc=K2K2M4"
)
r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
data = json.loads(
    re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.DOTALL).group(1)
)
for raw in data["props"]["pageProps"]["listings"][:15]:
    loc = raw.get("location") or {}
    addr = loc.get("address") or {}
    print(
        "city=", loc.get("city"),
        "province=", loc.get("province"),
        "display=", loc.get("displayName"),
        "addr=", {k: addr.get(k) for k in ("city", "province", "provinceCode", "zip", "country")},
    )
