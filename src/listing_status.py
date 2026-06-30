from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any

from src.scraper.base import BROWSER_HEADERS, status_indicates_unavailable

logger = logging.getLogger(__name__)

_REQUEST_CACHE: dict[str, dict[str, Any]] = {}


def _autotrader_status_from_html(html: str) -> str | None:
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None

    page_props = data.get("props", {}).get("pageProps", {})
    details = page_props.get("listingDetails")
    if isinstance(details, dict):
        price = details.get("price") or {}
        if isinstance(price, dict):
            if status_indicates_unavailable(price.get("priceFormatted")):
                return "sold"
            if price.get("priceRaw") or price.get("priceFormatted"):
                return "available"

    listing = page_props.get("listing")
    if isinstance(listing, dict):
        if listing.get("availableNow") is True:
            return "available"
        if listing.get("availableNow") is False:
            return "sold"
        price = listing.get("price") or {}
        if isinstance(price, dict) and status_indicates_unavailable(price.get("priceFormatted")):
            return "sold"

    listings = page_props.get("listings")
    if isinstance(listings, list) and listings:
        item = listings[0]
        if item.get("availableNow") is True:
            return "available"
        if item.get("availableNow") is False:
            return "sold"
        price = item.get("price") or {}
        if isinstance(price, dict) and status_indicates_unavailable(price.get("priceFormatted")):
            return "sold"
        if isinstance(price, dict) and (price.get("priceRaw") or price.get("priceFormatted")):
            return "available"
    return None


def _cargurus_status_from_html(html: str) -> str | None:
    if re.search(r'"salesStatus"\s*:\s*"(SOLD|INACTIVE|REMOVED)"', html, re.I):
        return "sold"
    if re.search(r'"listingStatus"\s*:\s*"(SOLD|INACTIVE|REMOVED)"', html, re.I):
        return "sold"
    if re.search(r'"priceData"\s*:\s*\{[^}]*"current"\s*:\s*[1-9]', html):
        return "available"
    if re.search(r'"price"\s*:\s*[1-9]\d{3,}', html) and "listingTitle" in html:
        return "available"
    return None


def _html_indicates_sold(html: str, source: str) -> bool:
    if source == "autotrader":
        status = _autotrader_status_from_html(html)
        if status == "sold":
            return True
        if status == "available":
            return False
        return False

    if source == "cargurus":
        status = _cargurus_status_from_html(html)
        if status == "sold":
            return True
        if status == "available":
            return False
        return False

    return False


def reset_listing_status_cache() -> None:
    _REQUEST_CACHE.clear()


def check_listing_url(listing_id: str, url: str, source: str) -> dict[str, Any]:
    if listing_id in _REQUEST_CACHE:
        return _REQUEST_CACHE[listing_id]

    result = {"status": "unknown", "link_active": False}
    if not url:
        _REQUEST_CACHE[listing_id] = result
        return result

    try:
        req = urllib.request.Request(url, headers={**BROWSER_HEADERS, "Referer": url})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", "replace")
        if _html_indicates_sold(html, source):
            result = {"status": "sold", "link_active": False}
        elif (
            (source == "autotrader" and _autotrader_status_from_html(html) == "available")
            or (source == "cargurus" and _cargurus_status_from_html(html) == "available")
        ):
            result = {"status": "available", "link_active": True}
        else:
            result = {"status": "unknown", "link_active": True}
    except urllib.error.HTTPError as exc:
        if exc.code in {404, 410}:
            result = {"status": "sold", "link_active": False}
        else:
            logger.debug("Listing check HTTP %s for %s", exc.code, listing_id)
    except Exception:
        logger.debug("Listing check failed for %s", listing_id, exc_info=True)

    _REQUEST_CACHE[listing_id] = result
    return result


def batch_check_listings(listings: list[dict[str, str]]) -> dict[str, dict[str, Any]]:
    unique: dict[str, dict[str, str]] = {}
    for item in listings:
        unique[item["listing_id"]] = item

    results: dict[str, dict[str, Any]] = {}
    if not unique:
        return results

    workers = min(8, len(unique))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                check_listing_url,
                listing_id,
                item["listing_url"],
                item["source"],
            ): listing_id
            for listing_id, item in unique.items()
        }
        for future in as_completed(futures):
            listing_id = futures[future]
            try:
                results[listing_id] = future.result()
            except Exception:
                results[listing_id] = {"status": "unknown", "link_active": False}
    return results


def build_listing_timeline(dates: list[str], rows_by_date: dict[str, list[dict[str, Any]]]) -> dict[str, dict[str, Any]]:
    sorted_dates = sorted(dates)
    timeline: dict[str, dict[str, Any]] = {}

    for snapshot_date in sorted_dates:
        for row in rows_by_date.get(snapshot_date, []):
            listing_id = row["listing_id"]
            entry = timeline.get(listing_id)
            if entry is None:
                timeline[listing_id] = {
                    "listing_id": listing_id,
                    "listing_url": row.get("listing_url") or "",
                    "source": row.get("source") or "",
                    "first_seen": snapshot_date,
                    "last_seen": snapshot_date,
                    "seen_dates": [snapshot_date],
                }
            else:
                entry["last_seen"] = snapshot_date
                entry["seen_dates"].append(snapshot_date)

    for entry in timeline.values():
        entry["days_in_top_picks"] = len(entry["seen_dates"])
    return timeline


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def enrich_pick_status(
    pick: dict[str, Any],
    *,
    timeline: dict[str, dict[str, Any]],
    live_status: dict[str, dict[str, Any]],
    latest_snapshot_date: str | None,
) -> dict[str, Any]:
    listing_id = pick["listing_id"]
    history = timeline.get(listing_id, {})
    first_seen = history.get("first_seen", pick.get("snapshot_date"))
    last_seen = history.get("last_seen", first_seen)
    days_in_top_picks = history.get("days_in_top_picks", 1)
    live = live_status.get(listing_id, {"status": "unknown", "link_active": False})

    status = live["status"]
    link_active = bool(live.get("link_active"))

    if status == "unknown" and latest_snapshot_date and last_seen < latest_snapshot_date:
        status = "likely_sold"

    days_listed: int | None = None
    if status in {"sold", "likely_sold"}:
        days_listed = _days_between(first_seen, last_seen)
    elif status == "available":
        end = latest_snapshot_date or last_seen
        days_listed = _days_between(first_seen, end)

    status_label = {
        "available": "Available",
        "sold": "Sold",
        "likely_sold": "Likely sold",
        "unknown": "Status unknown",
    }.get(status, "Status unknown")

    return {
        **pick,
        "listing_status": status,
        "listing_status_label": status_label,
        "link_active": link_active,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "days_in_top_picks": days_in_top_picks,
        "days_listed": days_listed,
    }
