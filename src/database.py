from __future__ import annotations

import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from src.config import DATA_DIR

logger = logging.getLogger(__name__)


def db_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "used_cars.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                snapshot_date TEXT PRIMARY KEY,
                total_listings INTEGER NOT NULL,
                recommended_count INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                snapshot_date TEXT NOT NULL,
                model_key TEXT NOT NULL,
                rank INTEGER NOT NULL,
                listing_id TEXT NOT NULL,
                source TEXT NOT NULL,
                make TEXT NOT NULL,
                model TEXT NOT NULL,
                year INTEGER NOT NULL,
                price INTEGER NOT NULL,
                mileage_km INTEGER,
                fuel_type TEXT,
                condition_text TEXT,
                dealer_name TEXT,
                dealer_city TEXT,
                seller_type TEXT,
                listing_url TEXT NOT NULL,
                image_url TEXT,
                median_price REAL,
                price_delta REAL,
                price_delta_pct REAL,
                deal_score REAL,
                dealer_boost REAL,
                rank_score REAL,
                is_good_deal INTEGER NOT NULL,
                scraped_at TEXT,
                PRIMARY KEY (snapshot_date, model_key, rank)
            );

            CREATE INDEX IF NOT EXISTS idx_recommendations_date
                ON recommendations(snapshot_date);
            """
        )
        _ensure_schema(conn)


def _ensure_schema(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(recommendations)")}
    if "trim" not in columns:
        conn.execute("ALTER TABLE recommendations ADD COLUMN trim TEXT")
    if "dealer_province" not in columns:
        conn.execute("ALTER TABLE recommendations ADD COLUMN dealer_province TEXT")
    conn.commit()


def save_snapshot(snapshot_date: date, rows: list[dict[str, Any]]) -> None:
    init_db()
    created_at = datetime.utcnow().isoformat()
    with connect() as conn:
        conn.execute(
            "DELETE FROM recommendations WHERE snapshot_date = ?",
            (snapshot_date.isoformat(),),
        )
        conn.execute(
            "DELETE FROM snapshots WHERE snapshot_date = ?",
            (snapshot_date.isoformat(),),
        )
        conn.execute(
            """
            INSERT INTO snapshots (snapshot_date, total_listings, recommended_count, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                snapshot_date.isoformat(),
                len(rows),
                len(rows),
                created_at,
            ),
        )
        for row in rows:
            conn.execute(
                """
                INSERT INTO recommendations (
                    snapshot_date, model_key, rank, listing_id, source, make, model, trim,
                    year, price, mileage_km, fuel_type, condition_text, dealer_name,
                    dealer_city, dealer_province, seller_type, listing_url, image_url, median_price,
                    price_delta, price_delta_pct, deal_score, dealer_boost, rank_score,
                    is_good_deal, scraped_at
                ) VALUES (
                    :snapshot_date, :model_key, :rank, :listing_id, :source, :make, :model, :trim,
                    :year, :price, :mileage_km, :fuel_type, :condition_text, :dealer_name,
                    :dealer_city, :dealer_province, :seller_type, :listing_url, :image_url, :median_price,
                    :price_delta, :price_delta_pct, :deal_score, :dealer_boost, :rank_score,
                    :is_good_deal, :scraped_at
                )
                """,
                {
                    **row,
                    "snapshot_date": snapshot_date.isoformat(),
                    "is_good_deal": 1 if row.get("is_good_deal") else 0,
                    "scraped_at": row.get("scraped_at"),
                },
            )
        conn.commit()
    logger.info("Saved snapshot %s with %s recommendations", snapshot_date, len(rows))


def list_snapshot_dates(limit: int = 30) -> list[str]:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT snapshot_date FROM snapshots
            ORDER BY snapshot_date DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [row["snapshot_date"] for row in cur.fetchall()]


def get_snapshot_meta(snapshot_date: str) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM snapshots WHERE snapshot_date = ?",
            (snapshot_date,),
        ).fetchone()
        return dict(row) if row else None


def nearest_snapshot_on_or_before(target: str, available: list[str]) -> str | None:
    if not available:
        return None
    if target in available:
        return target
    earlier = [d for d in available if d <= target]
    return max(earlier) if earlier else None


def get_recommendations(snapshot_date: str) -> list[dict[str, Any]]:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            """
            SELECT * FROM recommendations
            WHERE snapshot_date = ?
            ORDER BY model_key, rank
            """,
            (snapshot_date,),
        )
        rows = []
        for row in cur.fetchall():
            item = dict(row)
            item["is_good_deal"] = bool(item["is_good_deal"])
            rows.append(item)
        return rows
