from __future__ import annotations

import re
import unicodedata

from src.config import get_settings
from src.drive_away import estimate_drive_away
from src.models import Listing

# Major Quebec cities sometimes returned inside a 75 km Ottawa search radius.
QUEBEC_CITIES = frozenset(
    {
        "montreal",
        "montréal",
        "gatineau",
        "laval",
        "quebec",
        "québec",
        "longueuil",
        "brossard",
        "saint-eustache",
        "st-eustache",
        "terrebonne",
        "blainville",
        "salaberry-de-valleyfield",
        "sherbrooke",
        "trois-rivieres",
        "trois-rivières",
        "drummondville",
        "granby",
        "saguenay",
        "levis",
        "lévis",
        "repentigny",
        "mirabel",
        "chateauguay",
        "châteauguay",
        "mascouche",
        "shawinigan",
        "joliette",
        "rimouski",
        "victoriaville",
        "saint-jean-sur-richelieu",
        "val-dor",
        "val-d'or",
        "rouyn-noranda",
        "saint-jerome",
        "saint-jérôme",
        "boisbriand",
        "saint-hyacinthe",
        "magog",
        "candiac",
        "saint-georges",
        "rimouski",
        "hull",
    }
)

# Ontario cities commonly seen within ~75 km of Kanata/Ottawa.
OTTAWA_REGION_ON_CITIES = frozenset(
    {
        "ottawa",
        "kanata",
        "nepean",
        "orleans",
        "orléans",
        "gloucester",
        "barrhaven",
        "stittsville",
        "manotick",
        "carp",
        "richmond",
        "metcalfe",
        "winchester",
        "embrun",
        "russell",
        "casselman",
        "rockland",
        "arnprior",
        "carleton place",
        "almonte",
        "perth",
        "smiths falls",
        "kemptville",
        "north gower",
        "greely",
        "osgoode",
        "navan",
        "cumberland",
        "vanier",
        "gloucester",
        "hunt club",
        "westboro",
        "bell's corners",
        "bells corners",
        "constance bay",
        "cobden",
        "renfrew",
        "pembroke",
        "hawkesbury",
        "cornwall",
        "alexandria",
        "limoges",
        "verner",
        "plantagenet",
    }
)


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_city_key(city: str) -> str:
    city = _strip_accents(city.strip().lower())
    return re.sub(r"\s+", " ", city)


def normalize_province(value: str | None) -> str | None:
    if not value:
        return None
    token = _strip_accents(value.strip().lower())
    if token in {"on", "ontario"}:
        return "ON"
    if token in {"qc", "quebec", "québec"}:
        return "QC"
    if len(token) == 2 and token.isalpha():
        return token.upper()
    return None


def province_from_city_text(city: str) -> str | None:
    if "," not in city:
        return None
    return normalize_province(city.split(",")[-1].strip())


def format_location(city: str, province: str | None) -> str:
    city = city.strip()
    if not city:
        return province or ""
    prov = normalize_province(province)
    if "," in city:
        return city
    if prov:
        label = "ON" if prov == "ON" else prov
        return f"{city}, {label}"
    return city


def is_ontario_listing(
    dealer_city: str,
    dealer_province: str | None = None,
    *,
    dealer_name: str = "",
) -> bool:
    city = (dealer_city or "").strip()
    combined = f"{city} {dealer_province or ''} {dealer_name}".lower()

    if re.search(r"\b(qc|quebec|québec)\b", _strip_accents(combined)):
        return False
    if ", qc" in combined or combined.endswith(" qc"):
        return False

    province = normalize_province(dealer_province) or province_from_city_text(city)
    if province == "QC":
        return False
    if province == "ON":
        return True

    city_name = city.split(",")[0].strip() if city else ""
    city_key = normalize_city_key(city_name)

    if city_key in QUEBEC_CITIES:
        return False
    if city_key in OTTAWA_REGION_ON_CITIES:
        return True

    # Dealer names sometimes include Quebec locations.
    if any(qc in combined for qc in ("gatineau", "montreal", "montréal", "brossard")):
        return False

    return False


def max_drive_away_cap() -> int | None:
    value = get_settings().get("filters", {}).get("max_drive_away")
    return int(value) if value is not None else None


def price_within_drive_away_budget(price: int) -> bool:
    cap = max_drive_away_cap()
    if cap is None:
        return True
    return estimate_drive_away(price).drive_away <= cap


def listing_within_budget(listing: Listing) -> bool:
    return price_within_drive_away_budget(listing.price)


def text_indicates_sold_marker(*values: object) -> bool:
    text = " ".join(str(value or "") for value in values).lower()
    if not text.strip():
        return False
    sold_phrases = (
        "just sold",
        ">>sold<<",
        "sold pending",
        "sale pending",
        "no longer available",
    )
    return any(phrase in text for phrase in sold_phrases)


def listing_is_recommendable(listing: Listing) -> bool:
    if not listing_within_budget(listing):
        return False
    if text_indicates_sold_marker(
        listing.trim,
        listing.condition_text,
        listing.model,
        listing.dealer_name,
    ):
        return False
    return True


def row_within_budget(row: dict) -> bool:
    price = row.get("price")
    if price is None:
        return False
    return price_within_drive_away_budget(int(price))


def row_is_recommendable(row: dict) -> bool:
    if not row_within_budget(row):
        return False
    if text_indicates_sold_marker(
        row.get("trim"),
        row.get("condition_text"),
        row.get("model"),
        row.get("dealer_name"),
    ):
        return False
    return True
