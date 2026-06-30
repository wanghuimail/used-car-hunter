from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from urllib.parse import urljoin

import httpx

from src.config import get_settings, min_allowed_year
from src.filters import format_location, is_ontario_listing, normalize_province
from src.models import Listing
from src.scraper.base import (
    BROWSER_HEADERS,
    BaseScraper,
    autotrader_listing_unavailable,
    clean_trim,
    is_gasoline,
    parse_int,
    trim_from_title,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://www.autotrader.ca"


class AutoTraderScraper(BaseScraper):
    source = "autotrader"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.allowed_fuels = [f.lower() for f in self.settings["filters"]["fuel_types"]]
        self.min_year = min_allowed_year()
        loc = self.settings["location"]
        self.postal = loc["postal_code"].replace(" ", "")
        self.radius = int(loc["radius_km"])
        self.province = loc["province"]

    def _search_url(self, path: str, page: int = 1) -> str:
        offset = (page - 1) * 15
        return (
            f"{BASE_URL}/cars/{path}/reg_on/cit_ottawa"
            f"?rcp=15&rcs={offset}&srt=35"
            f"&yrl={self.min_year}&yrh={datetime.now().year}"
            f"&prx={self.radius}&prv={self.province}&loc={self.postal}"
            f"&hpr=Y&wcp=Y&inMarket=advancedSearch"
        )

    def fetch_model(self, model_cfg: dict) -> list[Listing]:
        listings: list[Listing] = []
        seen: set[str] = set()
        path = model_cfg["autotrader"]["path"]

        with httpx.Client(headers=BROWSER_HEADERS, timeout=30.0, follow_redirects=True) as client:
            for page in range(1, 6):
                url = self._search_url(path, page)
                try:
                    response = client.get(url)
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    logger.warning("AutoTrader fetch failed %s: %s", url, exc)
                    break

                page_listings = self._parse_page(response.text, model_cfg)
                if not page_listings:
                    break

                for item in page_listings:
                    if item.listing_id in seen:
                        continue
                    seen.add(item.listing_id)
                    listings.append(item)

                if len(page_listings) < 15:
                    break

        logger.info("AutoTrader %s: %s listings", model_cfg["key"], len(listings))
        return listings

    def _parse_page(self, html: str, model_cfg: dict) -> list[Listing]:
        match = re.search(
            r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            html,
            re.DOTALL,
        )
        if not match:
            return []

        data = json.loads(match.group(1))
        raw_listings = data.get("props", {}).get("pageProps", {}).get("listings", [])
        results: list[Listing] = []

        for raw in raw_listings:
            if autotrader_listing_unavailable(raw):
                continue
            parsed = self._parse_listing(raw, model_cfg)
            if parsed:
                results.append(parsed)
        return results

    def _parse_listing(self, raw: dict, model_cfg: dict) -> Listing | None:
        vehicle = raw.get("vehicle") or {}
        seller = raw.get("seller") or {}
        location = raw.get("location") or {}

        seller_type = (seller.get("type") or seller.get("sellerType") or "").lower()
        if seller_type and "dealer" not in seller_type:
            return None
        if seller.get("isPrivateSeller") is True:
            return None

        year = parse_int(vehicle.get("modelYear") or vehicle.get("year"))
        if year is None or year < self.min_year:
            return None

        fuel = vehicle.get("fuel") or vehicle.get("fuelType") or ""
        if not is_gasoline(str(fuel), self.allowed_fuels):
            return None

        price_block = raw.get("price") or {}
        if isinstance(price_block, dict):
            price = parse_int(price_block.get("priceRaw") or price_block.get("price"))
        else:
            price = parse_int(price_block)
        if price is None or price <= 0:
            return None

        mileage = parse_int(
            vehicle.get("mileageInKm")
            or vehicle.get("mileage")
            or vehicle.get("odometer")
            or vehicle.get("distance")
        )

        images = raw.get("images") or []
        image_url = None
        if images:
            first = images[0]
            if isinstance(first, dict):
                image_url = first.get("url") or first.get("href")
                if isinstance(image_url, dict):
                    image_url = image_url.get("href")
            else:
                image_url = str(first)

        listing_url = raw.get("url") or ""
        if listing_url and not listing_url.startswith("http"):
            listing_url = urljoin(BASE_URL, listing_url)

        dealer_name = (
            seller.get("companyName")
            or seller.get("name")
            or seller.get("dealerName")
            or location.get("sellerName")
            or "Unknown dealer"
        )
        address = location.get("address") or {}
        dealer_province = normalize_province(
            location.get("province")
            or location.get("provinceCode")
            or address.get("province")
            or address.get("provinceCode")
        )
        city_raw = (
            location.get("city")
            or location.get("displayName")
            or address.get("city")
            or seller.get("city")
            or ""
        )
        dealer_city = format_location(str(city_raw).strip(), dealer_province)

        if not is_ontario_listing(dealer_city, dealer_province, dealer_name=str(dealer_name)):
            return None

        condition = vehicle.get("condition") or vehicle.get("inventoryType") or "Used"
        listing_id = str(raw.get("id") or raw.get("identifier") or listing_url)
        trim = clean_trim(vehicle.get("modelVersionInput") or vehicle.get("variant"))

        return Listing(
            listing_id=f"at-{listing_id}",
            source=self.source,
            make=model_cfg["make"],
            model=model_cfg["model"],
            model_key=model_cfg["key"],
            year=year,
            trim=trim,
            price=price,
            mileage_km=mileage,
            fuel_type=str(fuel or "Gasoline"),
            condition_text=str(condition),
            dealer_name=str(dealer_name).strip(),
            dealer_city=dealer_city,
            dealer_province=dealer_province or "ON",
            seller_type="dealer",
            listing_url=listing_url,
            image_url=image_url,
        )
