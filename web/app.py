from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from src.config import (
    format_model_label,
    get_model_catalog,
    get_model_selection,
    get_models,
    get_settings,
    get_suggested_dealers,
    get_watchlist,
    model_labels_map,
    save_json,
    save_model_selection,
    validate_model_selection,
)
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

_search_running = False


def _run_snapshot_job() -> None:
    global _search_running
    if _search_running:
        logger.info("Search already running; skipping duplicate request")
        return
    _search_running = True
    try:
        result = run_daily_snapshot()
        logger.info("Search finished: %s", result)
    except Exception:
        logger.exception("Search failed")
    finally:
        _search_running = False


WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))
templates.env.filters["drive_away"] = lambda price: estimate_drive_away(int(price))
templates.env.filters["vehicle_detail"] = build_vehicle_detail


def _model_summary_text() -> str:
    labels = [format_model_label(model) for model in sorted(get_models(), key=lambda item: item["priority"])]
    return " · ".join(labels) if labels else "No models selected"


def _catalog_for_picker() -> list[dict]:
    return [
        {
            "make": brand["make"],
            "models": [{"name": model["name"]} for model in brand["models"]],
        }
        for brand in get_model_catalog()
    ]


def _model_picker_slots() -> list[dict]:
    selection = get_model_selection()
    slots: list[dict] = []
    for index in range(5):
        if index < len(selection):
            slots.append(
                {
                    "index": index + 1,
                    "make": selection[index]["make"],
                    "model": selection[index]["model"],
                }
            )
        else:
            slots.append({"index": index + 1, "make": "", "model": ""})
    return slots


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
    labels = model_labels_map()
    return [
        {
            "key": model["key"],
            "label": labels.get(model["key"], model["model"]),
        }
        for model in sorted(get_models(), key=lambda item: item["priority"])
    ]


def _filter_display_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row_is_recommendable(row)]


def _build_sections(rows: list[dict]) -> list[dict]:
    labels = model_labels_map()
    by_key: dict[str, list[dict]] = {}
    for row in rows:
        by_key.setdefault(row["model_key"], []).append(row)

    sections: list[dict] = []
    for model in sorted(get_models(), key=lambda item: item["priority"]):
        items = sorted(by_key.get(model["key"], []), key=lambda item: item["rank"])
        sections.append(
            {
                "key": model["key"],
                "label": labels.get(model["key"], model["model"]),
                "listings": items,
            }
        )
    return sections


def _snapshot_missing_models(rows: list[dict]) -> list[dict[str, str]]:
    labels = model_labels_map()
    snapshot_keys = {row["model_key"] for row in rows}
    missing: list[dict[str, str]] = []
    for model in sorted(get_models(), key=lambda item: item["priority"]):
        if model["key"] not in snapshot_keys:
            missing.append(
                {
                    "key": model["key"],
                    "label": labels.get(model["key"], model["model"]),
                }
            )
    return missing


def _nearest_snapshot(target: str, available: list[str]) -> str | None:
    return nearest_snapshot_on_or_before(target, available)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, selected: str | None = None, snapshot_date: str | None = None):
    today = date.today().isoformat()
    requested_date = snapshot_date or selected or today
    search_started = request.query_params.get("search_started") == "1"
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
    sections = _build_sections(rows) if has_snapshot else []
    missing_models = _snapshot_missing_models(rows) if has_snapshot else []

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
            "sections": sections,
            "missing_models": missing_models,
            "snapshot_stale": bool(missing_models),
            "search_started": search_started,
            "search_running": _search_running,
            "model_nav": _build_model_nav(),
            "is_today": requested_date == today,
            "max_drive_away": max_drive_away,
            "model_summary": _model_summary_text(),
        },
    )


@app.get("/models", response_class=HTMLResponse)
async def models_page(request: Request):
    active_models = [
        {
            "key": model["key"],
            "label": format_model_label(model),
        }
        for model in sorted(get_models(), key=lambda item: item["priority"])
    ]
    return templates.TemplateResponse(
        request,
        "models.html",
        {
            "catalog": get_model_catalog(),
            "catalog_json": json.dumps(_catalog_for_picker()),
            "slots": _model_picker_slots(),
            "active_models": active_models,
        },
    )


@app.post("/models/save")
async def save_models(request: Request):
    form = await request.form()
    submitted: list[dict[str, str]] = []
    for index in range(5):
        make = str(form.get(f"make_{index}") or "").strip()
        model = str(form.get(f"model_{index}") or "").strip()
        if make and model:
            submitted.append({"make": make, "model": model})

    validated = validate_model_selection(submitted)
    if validated:
        save_model_selection(validated)
        return RedirectResponse("/api/run-now", status_code=303)
    return RedirectResponse("/models", status_code=303)


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
async def run_now(background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_snapshot_job)
    return RedirectResponse("/?search_started=1", status_code=303)


@app.post("/api/run")
async def run_api(background_tasks: BackgroundTasks) -> JSONResponse:
    background_tasks.add_task(_run_snapshot_job)
    return JSONResponse({"status": "started"})


def _normalize(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("web.app:app", host="0.0.0.0", port=port, reload=False)
