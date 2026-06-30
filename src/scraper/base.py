from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod

from src.models import Listing

logger = logging.getLogger(__name__)

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-CA,en;q=0.9",
}


class BaseScraper(ABC):
    source: str

    @abstractmethod
    def fetch_model(self, model_cfg: dict) -> list[Listing]:
        raise NotImplementedError


def normalize_fuel(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip().lower())


def is_gasoline(fuel: str, allowed: list[str]) -> bool:
    fuel_l = normalize_fuel(fuel)
    if not fuel_l:
        return True
    if any(bad in fuel_l for bad in ("diesel", "electric", "hybrid", "plug-in", "phev")):
        return False
    return any(token in fuel_l for token in allowed) or "gas" in fuel_l


def parse_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def clean_trim(value: str | None) -> str | None:
    if not value:
        return None
    trim = value.split("|")[0].strip()
    trim = re.sub(r"\s+", " ", trim)
    if not trim or trim.lower() in {"used", "new", "n/a", "na"}:
        return None
    return trim[:80] if len(trim) > 80 else trim


def trim_from_title(title: str, make: str, model: str) -> str | None:
    if not title:
        return None
    pattern = re.compile(
        rf"{re.escape(str(make))}\s+{re.escape(model.replace('-', '[- ]?'))}\s+(.+)",
        re.IGNORECASE,
    )
    match = pattern.search(title)
    if match:
        return clean_trim(match.group(1))
    return None


_ACTIVE_STATUS_TOKENS = frozenset({"paying", "available", "active"})


def normalize_listing_status(value: object) -> str:
    return re.sub(r"[\s_]+", " ", str(value or "").strip().lower())


def status_indicates_unavailable(*values: object) -> bool:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            if value:
                return True
            continue
        status = normalize_listing_status(value)
        if not status:
            continue
        if status in _ACTIVE_STATUS_TOKENS:
            continue
        if any(token in status for token in ("sold", "pending", "inactive", "removed", "unavail")):
            return True
    return False


def autotrader_listing_unavailable(raw: dict) -> bool:
    if raw.get("availableNow") is False:
        return True
    if status_indicates_unavailable(
        raw.get("status"),
        raw.get("listingStatus"),
        raw.get("isSalePending"),
        raw.get("salePending"),
    ):
        return True

    price = raw.get("price")
    if isinstance(price, dict):
        return status_indicates_unavailable(price.get("priceFormatted"))
    return False


def cargurus_listing_unavailable(raw: dict, seller: dict | None = None) -> bool:
    seller = seller or raw.get("sellerData") or {}
    if status_indicates_unavailable(raw.get("salePending"), raw.get("isSold")):
        return True
    for obj in (raw, seller):
        if status_indicates_unavailable(
            obj.get("salesStatus"),
            obj.get("listingStatus"),
        ):
            return True
    return False
