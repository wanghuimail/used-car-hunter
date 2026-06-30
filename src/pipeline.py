from __future__ import annotations

import logging
from datetime import date

from src.config import get_models, get_settings
from src.filters import is_ontario_listing, listing_is_recommendable
from src.database import save_snapshot
from src.models import Listing
from src.score import pick_top_per_model, score_listings
from src.scraper.autotrader import AutoTraderScraper
from src.scraper.cargurus import CarGurusScraper

logger = logging.getLogger(__name__)


def dedupe_listings(listings: list[Listing]) -> list[Listing]:
    seen_urls: set[str] = set()
    seen_keys: set[tuple[str, int, int, str]] = set()
    unique: list[Listing] = []

    for listing in listings:
        url_key = listing.listing_url.split("?")[0].rstrip("/").lower()
        fuzzy_key = (
            listing.model_key,
            listing.year,
            listing.price,
            _normalize_name(listing.dealer_name),
        )
        if url_key in seen_urls or fuzzy_key in seen_keys:
            continue
        seen_urls.add(url_key)
        seen_keys.add(fuzzy_key)
        unique.append(listing)
    return unique


def _normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def filter_listings(listings: list[Listing]) -> list[Listing]:
    settings = get_settings()
    ontario_only = settings.get("filters", {}).get("ontario_only", True)

    kept: list[Listing] = []
    for listing in listings:
        if ontario_only and not is_ontario_listing(
            listing.dealer_city, listing.dealer_province, dealer_name=listing.dealer_name
        ):
            logger.info(
                "Excluded non-Ontario listing: %s %s (%s)",
                listing.dealer_name,
                listing.dealer_city,
                listing.source,
            )
            continue
        if not listing_is_recommendable(listing):
            logger.info(
                "Excluded ineligible listing: %s %s $%s (%s)",
                listing.year,
                listing.model,
                listing.price,
                listing.source,
            )
            continue
        kept.append(listing)
    return kept


def fetch_all_listings() -> list[Listing]:
    scrapers = [AutoTraderScraper(), CarGurusScraper()]
    models = get_models()
    all_listings: list[Listing] = []

    for model_cfg in models:
        for scraper in scrapers:
            try:
                all_listings.extend(scraper.fetch_model(model_cfg))
            except Exception:
                logger.exception(
                    "Scraper %s failed for %s",
                    scraper.source,
                    model_cfg["key"],
                )

    return filter_listings(dedupe_listings(all_listings))


def run_daily_snapshot(snapshot_date: date | None = None) -> dict:
    snapshot_date = snapshot_date or date.today()
    listings = fetch_all_listings()
    scored = score_listings(listings)
    top = pick_top_per_model(scored)

    rows = []
    for item in top:
        row = item.to_dict()
        row["model_key"] = item.listing.model_key
        rows.append(row)

    save_snapshot(snapshot_date, rows)

    return {
        "snapshot_date": snapshot_date.isoformat(),
        "total_listings_scraped": len(listings),
        "scored_listings": len(scored),
        "recommended_count": len(rows),
    }
