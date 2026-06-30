from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass
class Listing:
    listing_id: str
    source: str
    make: str
    model: str
    model_key: str
    year: int
    price: int
    mileage_km: int | None
    fuel_type: str
    condition_text: str
    dealer_name: str
    dealer_city: str
    seller_type: str
    listing_url: str
    trim: str | None = None
    dealer_province: str | None = None
    image_url: str | None = None
    scraped_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["scraped_at"] = self.scraped_at.isoformat()
        return data


@dataclass
class ScoredListing:
    listing: Listing
    median_price: float
    price_delta: float
    price_delta_pct: float
    deal_score: float
    dealer_boost: float
    rank_score: float
    is_good_deal: bool
    rank: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.listing.to_dict(),
            "median_price": self.median_price,
            "price_delta": self.price_delta,
            "price_delta_pct": self.price_delta_pct,
            "deal_score": self.deal_score,
            "dealer_boost": self.dealer_boost,
            "rank_score": self.rank_score,
            "is_good_deal": self.is_good_deal,
            "rank": self.rank,
        }


@dataclass
class SnapshotSummary:
    snapshot_date: date
    total_listings: int
    recommended_count: int
    created_at: datetime
