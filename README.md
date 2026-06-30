# Used Car Hunter

Daily web digest of used **Honda CR-V**, **Toyota RAV4**, and **Mazda CX-5** listings near Ottawa/Kanata.

## What it does

- Scrapes **AutoTrader.ca** and **CarGurus.ca** (dealers only)
- Filters to gasoline vehicles no older than 4 years within **75 km** of Kanata
- Scores listings against the **median price** for similar model/year/mileage buckets
- Saves a daily snapshot and shows the **top 5 per model** (up to 15 total)
- Lets you maintain a **dealer watchlist** with optional watchlist-only filtering
- Refreshes automatically at **6:00 AM Eastern**

## Quick start (local)

```powershell
cd "C:\AI learning projects\2026-07 Used Car Hunter"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\run_daily.py
python -m uvicorn web.app:app --host 0.0.0.0 --port 8000
```

Open http://localhost:8000

## Configuration

| File | Purpose |
|------|---------|
| `config/settings.yaml` | Location, radius, schedule, scoring |
| `config/models.yaml` | Target makes/models and source paths |
| `config/dealers_watchlist.json` | Your dealer watchlist |
| `config/dealers_suggested.json` | Starter Ottawa/Kanata dealers |

## Dealer watchlist

Use **Dealer Watchlist** in the web UI to add/remove dealers. Watchlist dealers receive a scoring boost. Enable **Only show listings from watchlist dealers** to restrict results.

Suggested starter dealers include Kanata Honda, Tony Graham Toyota, Kanata Toyota, Barrhaven Honda, Bank Street Honda, Kanata Mazda, Barrhaven Mazda, Bank Street Mazda, Carling Motors, and Hunt Club Honda.

## Deployment (AI Builders)

This repo includes a `Dockerfile` compatible with [ai-builders.space](https://ai-builders.space):

1. Push to a **public** GitHub repository
2. Ensure secrets are not committed (`.env` is gitignored)
3. Deploy with your AI Builders token

The platform injects `AI_BUILDER_TOKEN` and `PORT` at runtime.

## Notes

- Listing sites change frequently; if a source stops parsing, check logs and update the scraper.
- Verify price and availability on the dealer site before visiting.
- Historical snapshots are stored in `data/used_cars.db`.
