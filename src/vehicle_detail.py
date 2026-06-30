from __future__ import annotations

import re
from typing import Any

from src.drive_away import estimate_drive_away

TRIM_LADDERS: dict[str, list[str]] = {
    "cr-v": ["LX", "EX", "EX-L", "Touring"],
    "hr-v": ["LX", "Sport", "EX-L"],
    "forester": ["Convenience", "Touring", "Sport", "Limited", "Wilderness"],
    "rav4": ["LE", "XLE", "XLE Premium", "Limited"],
    "cx-5": ["GX", "GS", "GT", "GT Turbo", "Signature"],
}


def _normalize_trim_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def match_trim(model_key: str, raw_trim: str | None) -> tuple[int | None, str | None]:
    ladder = TRIM_LADDERS.get(model_key, [])
    if not ladder or not raw_trim:
        return None, None

    raw_norm = _normalize_trim_text(raw_trim)
    for name in sorted(ladder, key=len, reverse=True):
        token = _normalize_trim_text(name)
        if token and token in raw_norm:
            return ladder.index(name), name
    return None, None


def deal_score_label(price_delta_pct: float, is_good_deal: bool) -> str:
    if price_delta_pct >= 8:
        return "Excellent deal"
    if is_good_deal or price_delta_pct >= 3:
        return "Good deal"
    if price_delta_pct >= 0:
        return "Fair price"
    return "Above typical market"


def deal_score_summary(
    price_delta_pct: float,
    deal_score: float,
    is_good_deal: bool,
    model: str,
    trim_matched: str | None,
) -> str:
    label = deal_score_label(price_delta_pct, is_good_deal)
    peer = f"{model} {trim_matched}" if trim_matched else model
    if price_delta_pct > 0:
        return (
            f"{label} — about {price_delta_pct:.1f}% below similar {peer} "
            f"listings (deal score {deal_score:.1f})."
        )
    if price_delta_pct < 0:
        return (
            f"{label} — about {abs(price_delta_pct):.1f}% above similar {peer} "
            f"listings (deal score {deal_score:.1f})."
        )
    return f"{label} — in line with similar {peer} listings (deal score {deal_score:.1f})."


def recommendation_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []

    model_key = row.get("model_key") or ""
    _, trim_matched = match_trim(model_key, row.get("trim"))
    comparison = f"{row.get('model')} {trim_matched}" if trim_matched else str(row.get("model"))
    delta = float(row.get("price_delta_pct") or 0)
    if delta > 0:
        reasons.append(
            f"List price is about {delta:.1f}% below the median for similar "
            f"{comparison} listings in today's search."
        )
    elif row.get("is_good_deal"):
        reasons.append("Priced competitively against similar vehicles found today.")

    rank = row.get("rank")
    model = row.get("model")
    if rank and model:
        reasons.append(f"Ranked #{rank} among today's top {model} recommendations.")

    year = row.get("year")
    if year:
        reasons.append(f"{year} model year fits your maximum-age filter (no older than 4 years).")

    if row.get("dealer_boost", 0) > 0:
        reasons.append("Sold by a dealer on your watchlist.")

    mileage = row.get("mileage_km")
    if mileage is not None and mileage < 60000:
        reasons.append(f"Relatively low mileage at {mileage:,} km.")

    dealer_city = row.get("dealer_city") or ""
    if dealer_city:
        reasons.append(f"Ontario dealer location: {dealer_city}.")

    if row.get("fuel_type"):
        reasons.append(f"Gasoline vehicle — matches your fuel preference.")

    return reasons[:5]


def build_vehicle_detail(row: dict[str, Any]) -> dict[str, Any]:
    model_key = row.get("model_key") or ""
    trim_index, trim_matched = match_trim(model_key, row.get("trim"))
    drive_away = estimate_drive_away(int(row.get("price") or 0))
    price_delta_pct = float(row.get("price_delta_pct") or 0)
    deal_score = float(row.get("deal_score") or 0)
    is_good_deal = bool(row.get("is_good_deal"))

    return {
        "title": f"{row.get('year')} {row.get('make')} {row.get('model')}",
        "trim_raw": row.get("trim"),
        "trim_ladder": TRIM_LADDERS.get(model_key, []),
        "trim_index": trim_index,
        "trim_matched": trim_matched,
        "deal_score": round(deal_score, 1),
        "deal_label": deal_score_label(price_delta_pct, is_good_deal),
        "deal_summary": deal_score_summary(
            price_delta_pct, deal_score, is_good_deal, str(row.get("model") or ""), trim_matched
        ),
        "is_good_deal": is_good_deal,
        "price_delta_pct": round(price_delta_pct, 1),
        "median_price": row.get("median_price"),
        "drive_away": drive_away.to_dict(),
        "reasons": recommendation_reasons(row),
        "dealer_name": row.get("dealer_name"),
        "dealer_city": row.get("dealer_city"),
        "mileage_km": row.get("mileage_km"),
        "listing_url": row.get("listing_url"),
    }
