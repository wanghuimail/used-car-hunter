from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from urllib.parse import urljoin

from src.config import get_settings, min_allowed_year
from src.filters import format_location, is_ontario_listing, normalize_province, province_from_city_text, text_indicates_sold_marker
from src.models import Listing
from src.scraper.base import (
    BROWSER_HEADERS,
    BaseScraper,
    cargurus_listing_unavailable,
    clean_trim,
    is_gasoline,
    parse_int,
    trim_from_title,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://www.cargurus.ca"


def _extract_json_object(html: str, start: int) -> dict | None:
    if start < 0 or start >= len(html) or html[start] != "{":
        return None
    depth = 0
    for i in range(start, min(start + 15000, len(html))):
        ch = html[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(html[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


class CarGurusScraper(BaseScraper):
    source = "cargurus"

    def __init__(self) -> None:
        self.settings = get_settings()
        self.allowed_fuels = [f.lower() for f in self.settings["filters"]["fuel_types"]]
        self.min_year = min_allowed_year()
        loc = self.settings["location"]
        self.postal = loc["postal_code"].replace(" ", "")
        self.radius = int(loc["radius_km"])

    def _search_url(self, model_cfg: dict, page: int = 1) -> str:
        trim = model_cfg["cargurus"]["make_model_trim"]
        return (
            f"{BASE_URL}/search?zip={self.postal}&distance={self.radius}"
            f"&makeModelTrimPaths={trim}&sortType=DEAL_SCORE&sortDirection=ASC"
            f"&page={page}"
        )

    def _fetch_html(self, url: str) -> str:
        headers = {
            **BROWSER_HEADERS,
            "Referer": BASE_URL + "/",
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8", "replace")

    def fetch_model(self, model_cfg: dict) -> list[Listing]:
        listings: list[Listing] = []
        seen: set[str] = set()

        for page in range(1, 6):
            url = self._search_url(model_cfg, page)
            try:
                html = self._fetch_html(url)
            except urllib.error.URLError as exc:
                logger.warning("CarGurus fetch failed %s: %s", url, exc)
                break

            page_listings = self._parse_page(html, model_cfg)
            if not page_listings:
                break

            for item in page_listings:
                if item.listing_id in seen:
                    continue
                seen.add(item.listing_id)
                listings.append(item)

            if len(page_listings) < 10:
                break

        logger.info("CarGurus %s: %s listings", model_cfg["key"], len(listings))
        return listings

    def _parse_page(self, html: str, model_cfg: dict) -> list[Listing]:
        results: list[Listing] = []
        seen_ids: set[str] = set()

        pos = 0
        while True:
            marker = html.find('"type":"LISTING_USED', pos)
            if marker < 0:
                break
            data_start = html.find('"data":', marker)
            if data_start < 0:
                break
            data_start += len('"data":')
            raw = _extract_json_object(html, data_start)
            pos = data_start + 1
            if not raw:
                continue
            parsed = self._parse_tile(raw, model_cfg)
            if parsed and parsed.listing_id not in seen_ids:
                seen_ids.add(parsed.listing_id)
                results.append(parsed)

        if results:
            return results

        pos = 0
        while True:
            start = html.find('{"listingId"', pos)
            if start < 0:
                break
            raw = _extract_json_object(html, start)
            pos = start + 1
            if not raw:
                continue
            parsed = self._parse_compact(raw, model_cfg)
            if parsed and parsed.listing_id not in seen_ids:
                seen_ids.add(parsed.listing_id)
                results.append(parsed)

        return results

    def _model_matches(self, make: str, model: str, model_cfg: dict) -> bool:
        target_make = model_cfg["make"].lower()
        target_model = model_cfg["model"].lower().replace("-", "")
        if make.lower() != target_make:
            return False

        model_norm = model.lower().replace("-", "").replace(" ", "")
        if target_model == "rav4":
            return model_norm.startswith("rav4") and "hybrid" not in model.lower()
        if target_model == "cx5":
            return model_norm == "cx5" or (
                model_norm.startswith("cx5") and not model_norm.startswith("cx50")
            )
        if target_model == "hrv":
            return model_norm.startswith("hrv")
        if target_model == "forester":
            return model_norm.startswith("forester")
        return model_norm == target_model or model_norm.startswith(target_model)

    def _parse_tile(self, raw: dict, model_cfg: dict) -> Listing | None:
        seller = raw.get("sellerData") or {}
        if cargurus_listing_unavailable(raw, seller):
            return None
        if seller.get("salesStatus") == "PRIVATE":
            return None

        ontology = raw.get("ontologyData") or {}
        make = ontology.get("makeName") or ""
        model = ontology.get("modelName") or ""
        if not self._model_matches(make, model, model_cfg):
            title = raw.get("listingTitle") or ""
            if model_cfg["model"].lower() not in title.lower():
                return None
            make = model_cfg["make"]
            model = model_cfg["model"]

        year = parse_int(ontology.get("carYear") or raw.get("year"))
        if year is None or year < self.min_year:
            return None

        fuel_data = raw.get("fuelData") or {}
        fuel = fuel_data.get("localizedType") or ""
        title = raw.get("listingTitle") or ""
        if fuel:
            if not is_gasoline(str(fuel), self.allowed_fuels):
                return None
        elif any(
            bad in title.lower()
            for bad in ("hybrid", "diesel", "electric", "plug-in", "phev")
        ):
            return None

        price_data = raw.get("priceData") or {}
        price = parse_int(price_data.get("current") or price_data.get("basePrice"))
        if price is None or price <= 0:
            return None

        mileage_data = raw.get("mileageData") or {}
        mileage = parse_int(mileage_data.get("value") or raw.get("localizedMileage"))

        listing_id = str(raw.get("id") or raw.get("listingId"))
        listing_url = f"{BASE_URL}/Cars/inventorylisting/viewDetailsFilterViewInventoryListing.action?listingId={listing_id}"

        picture = raw.get("pictureData") or {}
        image_url = picture.get("url")

        dealer_name = seller.get("serviceProviderName") or seller.get("name") or "Unknown dealer"
        display_location = seller.get("displayLocation") or ""
        dealer_province = normalize_province(seller.get("region")) or province_from_city_text(
            display_location
        )
        city_raw = seller.get("city") or display_location or ""
        if "," in str(city_raw):
            city_raw = str(city_raw).split(",")[0].strip()
        dealer_city = format_location(str(city_raw).strip(), dealer_province)

        if not is_ontario_listing(dealer_city, dealer_province, dealer_name=str(dealer_name)):
            return None

        trim = clean_trim(ontology.get("trimName")) or trim_from_title(
            title, model_cfg["make"], model_cfg["model"]
        )
        if text_indicates_sold_marker(trim, title, raw.get("listingTitle")):
            return None

        return Listing(
            listing_id=f"cg-{listing_id}",
            source=self.source,
            make=model_cfg["make"],
            model=model_cfg["model"],
            model_key=model_cfg["key"],
            year=year,
            trim=trim,
            price=price,
            mileage_km=mileage,
            fuel_type=str(fuel or "Gasoline"),
            condition_text=str(raw.get("dealRating") or "Used"),
            dealer_name=str(dealer_name).strip(),
            dealer_city=dealer_city,
            dealer_province=dealer_province or "ON",
            seller_type="dealer",
            listing_url=listing_url,
            image_url=image_url,
        )

    def _parse_compact(self, raw: dict, model_cfg: dict) -> Listing | None:
        if cargurus_listing_unavailable(raw):
            return None

        make = str(raw.get("make") or model_cfg["make"])
        model = str(raw.get("model") or model_cfg["model"])
        if not self._model_matches(make, model, model_cfg):
            return None

        seller_type = str(raw.get("sellerType") or "DEALER").upper()
        if "PRIVATE" in seller_type:
            return None

        year = parse_int(raw.get("year"))
        if year is None or year < self.min_year:
            return None

        title = raw.get("listingTitle") or ""
        if any(
            bad in title.lower()
            for bad in ("hybrid", "diesel", "electric", "plug-in", "phev")
        ):
            return None

        price = parse_int(raw.get("price"))
        if price is None or price <= 0:
            return None

        listing_id = str(raw.get("listingId"))
        listing_url = f"{BASE_URL}/Cars/inventorylisting/viewDetailsFilterViewInventoryListing.action?listingId={listing_id}"
        city_region = str(raw.get("cityRegion") or "")
        dealer_province = province_from_city_text(city_region)
        dealer_city = city_region if city_region else ""
        if dealer_city and dealer_province:
            city_name = dealer_city.split(",")[0].strip()
            dealer_city = format_location(city_name, dealer_province)
        trim = clean_trim(raw.get("trim")) or trim_from_title(
            title, model_cfg["make"], model_cfg["model"]
        )
        if text_indicates_sold_marker(trim, title):
            return None

        if not is_ontario_listing(dealer_city, dealer_province, dealer_name=""):
            return None

        return Listing(
            listing_id=f"cg-{listing_id}",
            source=self.source,
            make=model_cfg["make"],
            model=model_cfg["model"],
            model_key=model_cfg["key"],
            year=year,
            trim=trim,
            price=price,
            mileage_km=parse_int(raw.get("mileage")),
            fuel_type="Gasoline",
            condition_text=str(raw.get("dealFinderRating") or "Used"),
            dealer_name="Unknown dealer",
            dealer_city=dealer_city,
            dealer_province=dealer_province,
            seller_type="dealer",
            listing_url=listing_url,
            image_url=raw.get("imageUrl"),
        )
