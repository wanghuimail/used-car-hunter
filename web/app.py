from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config import get_models, get_settings, get_suggested_dealers, get_watchlist, save_json
from src.filters import max_drive_away_cap, row_is_recommendable
from src.database import (
    get_recommendations,
    get_snapshot_meta,
    init_db,
    list_snapshot_dates,
    nearest_snapshot_on_or_before,
)
from src.drive_away import estimate_drive_away
from src.vehicle_detail import build_vehicle_detail
from src.pipeline import run_daily_snapshot
from src.scheduler import preset_dates, start_scheduler, stop_scheduler
from src.trends import build_trend_view

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
templates.env.filters["drive_away"] = lambda price: estimate_drive_away(int(price))
templates.env.filters["vehicle_detail"] = build_vehicle_detail

MODEL_LABELS = {
    "cr-v": "Honda CR-V",
    "hr-v": "Honda HR-V",
    "forester": "Subaru Forester",
    "cx-5": "Mazda CX-5",
    "rav4": "Toyota RAV4",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    from src.database import list_snapshot_dates
    from src.pipeline import run_daily_snapshot

    if not list_snapshot_dates():
        try:
            run_daily_snapshot()
        except Exception:
            logger.exception("Initial snapshot on startup failed")
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Used Car Hunter", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(WEB_DIR / "static")), name="static")


def _build_model_nav() -> list[dict[str, str]]:
    return [
        {
            "key": model["key"],
            "label": MODEL_LABELS.get(model["key"], model["model"]),
        }
        for model in sorted(get_models(), key=lambda item: item["priority"])
    ]


def _filter_display_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row_is_recommendable(row)]


def _build_sections(rows: list[dict]) -> list[dict]:
    by_key: dict[str, list[dict]] = {}
    for row in rows:
        by_key.setdefault(row["model_key"], []).append(row)

    sections: list[dict] = []
    for model in sorted(get_models(), key=lambda item: item["priority"]):
        items = sorted(by_key.get(model["key"], []), key=lambda item: item["rank"])
        if not items:
            continue
        sections.append(
            {
                "key": model["key"],
                "label": MODEL_LABELS.get(model["key"], model["model"]),
                "listings": items,
            }
        )
    return sections


def _nearest_snapshot(target: str, available: list[str]) -> str | None:
    return nearest_snapshot_on_or_before(target, available)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, selected: str | None = None, snapshot_date: str | None = None):
    today = date.today().isoformat()
    requested_date = snapshot_date or selected or today
    available = list_snapshot_dates()
    has_snapshot = requested_date in available
    nearest_date = _nearest_snapshot(requested_date, available) if not has_snapshot else None

    presets = preset_dates()
    quick_dates = {
        "Today": presets["today"],
        "3 days ago": presets["three_days_ago"],
        "1 week ago": presets["one_week_ago"],
    }

    rows = _filter_display_rows(get_recommendations(requested_date) if has_snapshot else [])
    meta = get_snapshot_meta(requested_date) if has_snapshot else None
    max_drive_away = max_drive_away_cap()

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "requested_date": requested_date,
            "selected_date": requested_date,
            "available_dates": available,
            "has_snapshot": has_snapshot,
            "nearest_date": nearest_date,
            "quick_dates": quick_dates,
            "snapshot_meta": meta,
            "sections": _build_sections(rows),
            "model_nav": _build_model_nav(),
            "is_today": requested_date == today,
            "max_drive_away": max_drive_away,
        },
    )


@app.get("/trends", response_class=HTMLResponse)
async def trends_page(request: Request, model: str | None = None, days: int = 14):
    days = max(1, min(days, 30))
    trend_data = build_trend_view(model_key=model, days=days)
    return templates.TemplateResponse(
        request,
        "trends.html",
        {
            "request": request,
            **trend_data,
        },
    )


@app.get("/dealers", response_class=HTMLResponse)
async def dealers_page(request: Request):
    return templates.TemplateResponse(
        request,
        "dealers.html",
        {
            "watchlist": get_watchlist(),
            "suggested": get_suggested_dealers(),
        },
    )


@app.post("/dealers/add")
async def add_dealer(name: str = Form(...), city: str = Form("")):
    watchlist = get_watchlist()
    names = {_normalize(name) for item in watchlist["dealers"] for name in [item["name"]]}
    if _normalize(name) not in names:
        watchlist["dealers"].append({"name": name.strip(), "city": city.strip()})
        save_json("dealers_watchlist.json", watchlist)
    return RedirectResponse("/dealers", status_code=303)


@app.post("/dealers/remove")
async def remove_dealer(name: str = Form(...)):
    watchlist = get_watchlist()
    watchlist["dealers"] = [
        dealer for dealer in watchlist["dealers"] if dealer["name"] != name
    ]
    save_json("dealers_watchlist.json", watchlist)
    return RedirectResponse("/dealers", status_code=303)


@app.post("/dealers/toggle-filter")
async def toggle_filter(watchlist_only: str | None = Form(None)):
    watchlist = get_watchlist()
    watchlist["watchlist_only"] = watchlist_only == "1"
    save_json("dealers_watchlist.json", watchlist)
    return RedirectResponse("/dealers", status_code=303)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/snapshots")
async def snapshots() -> JSONResponse:
    return JSONResponse({"dates": list_snapshot_dates()})


@app.post("/api/run-now")
async def run_now():
    result = run_daily_snapshot()
    return RedirectResponse("/", status_code=303)


@app.post("/api/run")
async def run_api() -> JSONResponse:
    result = run_daily_snapshot()
    return JSONResponse(result)


def _normalize(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("web.app:app", host="0.0.0.0", port=port, reload=False)
