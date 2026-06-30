from __future__ import annotations

from datetime import date
from typing import Any

from src.config import get_models
from src.database import get_recommendations, list_snapshot_dates
from src.drive_away import estimate_drive_away
from src.filters import row_is_recommendable
from src.listing_status import (
    batch_check_listings,
    build_listing_timeline,
    enrich_pick_status,
    reset_listing_status_cache,
)

MODEL_LABELS = {
    "cr-v": "Honda CR-V",
    "hr-v": "Honda HR-V",
    "forester": "Subaru Forester",
    "cx-5": "Mazda CX-5",
    "rav4": "Toyota RAV4",
}


def _model_order() -> list[dict[str, Any]]:
    return sorted(get_models(), key=lambda item: item["priority"])


def _enrich_pick(row: dict[str, Any]) -> dict[str, Any]:
    drive_away = estimate_drive_away(int(row["price"]))
    return {
        **row,
        "drive_away": drive_away.drive_away,
        "vehicle_label": _vehicle_label(row),
    }


def _vehicle_label(row: dict[str, Any]) -> str:
    parts = [str(row.get("year") or "")]
    if row.get("trim"):
        parts.append(str(row["trim"]))
    return " ".join(part for part in parts if part).strip()


def _avg_median(picks: list[dict[str, Any]]) -> float | None:
    values = [float(p["median_price"]) for p in picks if p.get("median_price")]
    if not values:
        return None
    return round(sum(values) / len(values))


def _enrich_picks(
    picks: list[dict[str, Any]],
    *,
    timeline: dict[str, dict[str, Any]],
    live_status: dict[str, dict[str, Any]],
    latest_snapshot_date: str | None,
) -> list[dict[str, Any]]:
    return [
        enrich_pick_status(
            pick,
            timeline=timeline,
            live_status=live_status,
            latest_snapshot_date=latest_snapshot_date,
        )
        for pick in picks
    ]


def build_trend_view(
    *,
    model_key: str | None = None,
    days: int = 14,
) -> dict[str, Any]:
    today = date.today().isoformat()
    all_dates = list_snapshot_dates(limit=max(days, 30))
    dates = all_dates[:days]
    model_defs = _model_order()
    valid_keys = {model["key"] for model in model_defs}

    if model_key and model_key not in valid_keys:
        model_key = None

    # Load picks grouped by date -> model -> rank
    by_date_model: dict[str, dict[str, list[dict[str, Any]]]] = {}
    rows_by_date: dict[str, list[dict[str, Any]]] = {}
    top_price_by_date_model: dict[str, dict[str, int | None]] = {}

    for snapshot_date in dates:
        rows = [
            _enrich_pick(row)
            for row in get_recommendations(snapshot_date)
            if row_is_recommendable(row)
        ]
        rows_by_date[snapshot_date] = rows
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["model_key"], []).append(row)
        for key, picks in grouped.items():
            picks.sort(key=lambda item: item["rank"])

        by_date_model[snapshot_date] = grouped
        top_price_by_date_model[snapshot_date] = {
            key: picks[0]["price"] if picks else None for key, picks in grouped.items()
        }

    latest_snapshot_date = dates[0] if dates else None
    timeline = build_listing_timeline(dates, rows_by_date)
    reset_listing_status_cache()
    listing_refs = [
        {
            "listing_id": entry["listing_id"],
            "listing_url": entry["listing_url"],
            "source": entry["source"],
        }
        for entry in timeline.values()
        if entry.get("listing_url")
    ]
    live_status = batch_check_listings(listing_refs)

    for snapshot_date, grouped in by_date_model.items():
        for key, picks in grouped.items():
            grouped[key] = _enrich_picks(
                picks,
                timeline=timeline,
                live_status=live_status,
                latest_snapshot_date=latest_snapshot_date,
            )

    # Day-over-day top-pick price change (dates are newest-first)
    price_delta_by_date_model: dict[str, dict[str, int | None]] = {}
    for index, snapshot_date in enumerate(dates):
        deltas: dict[str, int | None] = {}
        for model in model_defs:
            key = model["key"]
            current = top_price_by_date_model.get(snapshot_date, {}).get(key)
            previous = None
            if index + 1 < len(dates):
                previous = top_price_by_date_model.get(dates[index + 1], {}).get(key)
            if current is not None and previous is not None:
                deltas[key] = current - previous
            else:
                deltas[key] = None
        price_delta_by_date_model[snapshot_date] = deltas

    day_sections: list[dict[str, Any]] = []
    for snapshot_date in dates:
        grouped = by_date_model.get(snapshot_date, {})
        model_rows: list[dict[str, Any]] = []
        for model in model_defs:
            key = model["key"]
            if model_key and key != model_key:
                continue
            picks = grouped.get(key, [])
            if not picks and model_key:
                continue
            model_rows.append(
                {
                    "key": key,
                    "label": MODEL_LABELS.get(key, model["model"]),
                    "picks": picks,
                    "pick_count": len(picks),
                    "top_price": picks[0]["price"] if picks else None,
                    "top_drive_away": picks[0]["drive_away"] if picks else None,
                    "avg_median": _avg_median(picks),
                    "top_price_delta": price_delta_by_date_model.get(snapshot_date, {}).get(key),
                }
            )
        if model_rows or not model_key:
            day_sections.append(
                {
                    "date": snapshot_date,
                    "is_today": snapshot_date == today,
                    "total_picks": sum(row["pick_count"] for row in model_rows),
                    "models": model_rows,
                }
            )

    # Price ladder: daily #1 list price per model (newest first)
    ladder_models = [model for model in model_defs if not model_key or model["key"] == model_key]
    price_ladder: list[dict[str, Any]] = []
    for snapshot_date in dates:
        cells: list[dict[str, Any]] = []
        for model in ladder_models:
            key = model["key"]
            price = top_price_by_date_model.get(snapshot_date, {}).get(key)
            cells.append(
                {
                    "key": key,
                    "label": MODEL_LABELS.get(key, model["model"]),
                    "price": price,
                    "delta": price_delta_by_date_model.get(snapshot_date, {}).get(key),
                }
            )
        price_ladder.append({"date": snapshot_date, "is_today": snapshot_date == today, "cells": cells})

    # Rolling summary per model across available days
    model_summaries: list[dict[str, Any]] = []
    for model in model_defs:
        key = model["key"]
        if model_key and key != model_key:
            continue
        top_prices: list[int] = []
        medians: list[float] = []
        for snapshot_date in dates:
            grouped = by_date_model.get(snapshot_date, {})
            picks = grouped.get(key, [])
            if picks:
                top_prices.append(picks[0]["price"])
                avg = _avg_median(picks)
                if avg is not None:
                    medians.append(avg)
        if not top_prices:
            continue
        earliest = top_prices[-1]
        latest = top_prices[0]
        model_summaries.append(
            {
                "key": key,
                "label": MODEL_LABELS.get(key, model["model"]),
                "days_seen": len(top_prices),
                "latest_top_price": latest,
                "avg_top_price": round(sum(top_prices) / len(top_prices)),
                "avg_median": round(sum(medians) / len(medians)) if medians else None,
                "window_change": latest - earliest if len(top_prices) > 1 else None,
            }
        )

    return {
        "dates": dates,
        "days": days,
        "days_tracked": len(dates),
        "selected_model": model_key,
        "selected_model_label": MODEL_LABELS.get(model_key, "All models") if model_key else "All models",
        "model_nav": [
            {"key": model["key"], "label": MODEL_LABELS.get(model["key"], model["model"])}
            for model in model_defs
        ],
        "day_sections": day_sections,
        "price_ladder": price_ladder,
        "model_summaries": model_summaries,
        "has_data": bool(dates),
    }
