import urllib.request

headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.cargurus.ca/"}
for make_id in range(1, 80):
    url = f"https://www.cargurus.ca/search?zip=K2K2M4&distance=75&makeModelTrimPaths=m{make_id}&sortType=DEAL_SCORE&sortDirection=ASC"
    html = urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=15).read().decode("utf-8", "replace")
    if '"makeName":"Mazda"' in html or '"make":"Mazda"' in html:
        print("mazda make id candidate", make_id, "CX-5", "CX-5" in html)
