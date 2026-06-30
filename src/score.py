from __future__ import annotations

import re
import statistics
from collections import defaultdict

from src.config import get_models, get_settings, get_watchlist
from src.filters import listing_is_recommendable
from src.models import Listing, ScoredListing
from src.vehicle_detail import match_trim


def _km_bucket(mileage: int | None, bucket: int) -> int:
    if mileage is None:
        return -1
    return mileage // bucket


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _trim_group(listing: Listing) -> str:
    _, matched = match_trim(listing.model_key, listing.trim)
    return matched or "other"


def _comparison_label(model: str, trim_group: str) -> str:
    if trim_group and trim_group != "other":
        return f"{model} {trim_group}"
    return model


def dealer_matches_watchlist(dealer_name: str, watchlist: list[str]) -> bool:
    dealer_norm = _normalize_name(dealer_name)
    for entry in watchlist:
        entry_norm = _normalize_name(entry)
        if entry_norm and (entry_norm in dealer_norm or dealer_norm in entry_norm):
            return True
    return False


def _model_priorities() -> dict[str, int]:
    return {model["key"]: int(model["priority"]) for model in get_models()}


def score_listings(listings: list[Listing]) -> list[ScoredListing]:
    settings = get_settings()
    scoring = settings["scoring"]
    km_bucket = int(scoring["km_bucket"])
    year_bucket = int(scoring["year_bucket"])
    threshold = float(scoring.get("below_median_pct_threshold", 0.0))
    priorities = _model_priorities()

    watchlist_cfg = get_watchlist()
    watchlist_names = [d["name"] for d in watchlist_cfg.get("dealers", []) if d.get("name")]
    watchlist_only = bool(watchlist_cfg.get("watchlist_only"))

    groups: dict[tuple[str, str, int, int], list[Listing]] = defaultdict(list)
    for listing in listings:
        year_group = listing.year // year_bucket if year_bucket else listing.year
        km_group = _km_bucket(listing.mileage_km, km_bucket)
        trim_group = _trim_group(listing)
        groups[(listing.model_key, trim_group, year_group, km_group)].append(listing)

    medians: dict[tuple[str, str, int, int], float] = {}
    for key, group in groups.items():
        prices = [item.price for item in group if item.price > 0]
        if prices:
            medians[key] = statistics.median(prices)

    trim_medians: dict[tuple[str, str], list[float]] = defaultdict(list)
    model_medians: dict[str, list[float]] = defaultdict(list)
    for (model_key, trim_group, _year_group, _km_group), median in medians.items():
        trim_medians[(model_key, trim_group)].append(median)
        model_medians[model_key].append(median)

    def resolve_median(listing: Listing, trim_group: str, year_group: int, km_group: int) -> float:
        exact = medians.get((listing.model_key, trim_group, year_group, km_group))
        if exact is not None:
            return exact

        trim_values = trim_medians.get((listing.model_key, trim_group), [])
        if trim_values:
            return statistics.median(trim_values)

        model_values = model_medians.get(listing.model_key, [])
        if model_values:
            return statistics.median(model_values)

        same_model = [x.price for x in listings if x.model_key == listing.model_key and x.price > 0]
        return statistics.median(same_model) if same_model else float(listing.price)

    scored: list[ScoredListing] = []
    for listing in listings:
        if not listing_is_recommendable(listing):
            continue
        if watchlist_only and watchlist_names:
            if not dealer_matches_watchlist(listing.dealer_name, watchlist_names):
                continue

        trim_group = _trim_group(listing)
        year_group = listing.year // year_bucket if year_bucket else listing.year
        km_group = _km_bucket(listing.mileage_km, km_bucket)
        median = resolve_median(listing, trim_group, year_group, km_group)

        price_delta = float(median) - listing.price
        price_delta_pct = (price_delta / median) * 100 if median else 0.0
        is_good_deal = price_delta_pct > threshold

        dealer_boost = 0.0
        if watchlist_names and dealer_matches_watchlist(listing.dealer_name, watchlist_names):
            dealer_boost = 5.0

        deal_score = price_delta_pct + dealer_boost
        preference_boost = max(0, 6 - priorities.get(listing.model_key, 6)) * 0.25
        rank_score = deal_score + preference_boost - (listing.mileage_km or 0) / 100_000

        scored.append(
            ScoredListing(
                listing=listing,
                median_price=float(median),
                price_delta=price_delta,
                price_delta_pct=price_delta_pct,
                deal_score=deal_score,
                dealer_boost=dealer_boost,
                rank_score=rank_score,
                is_good_deal=is_good_deal,
            )
        )

    return scored


def pick_top_per_model(scored: list[ScoredListing]) -> list[ScoredListing]:
    settings = get_settings()
    top_n = int(settings["filters"]["top_per_model"])
    by_model: dict[str, list[ScoredListing]] = defaultdict(list)
    for item in scored:
        by_model[item.listing.model_key].append(item)

    selected: list[ScoredListing] = []
    model_order = [model["key"] for model in sorted(get_models(), key=lambda m: m["priority"])]
    for model_key in model_order:
        group = by_model.get(model_key, [])
        group = sorted(
            group,
            key=lambda x: (x.rank_score, x.price_delta_pct),
            reverse=True,
        )
        picked = 0
        for item in group:
            if not listing_is_recommendable(item.listing):
                continue
            picked += 1
            item.rank = picked
            selected.append(item)
            if picked >= top_n:
                break

    return selected
