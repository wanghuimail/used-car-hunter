from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))


def load_yaml(name: str) -> dict[str, Any]:
    with open(CONFIG_DIR / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_json(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(name: str, data: dict[str, Any]) -> None:
    path = CONFIG_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def current_model_year() -> int:
    return datetime.now().year


def min_allowed_year() -> int:
    settings = load_yaml("settings.yaml")
    offset = int(settings["filters"]["min_model_year_offset"])
    return current_model_year() - offset


def get_settings() -> dict[str, Any]:
    return load_yaml("settings.yaml")


def get_models() -> list[dict[str, Any]]:
    return load_yaml("models.yaml")["models"]


def get_watchlist() -> dict[str, Any]:
    data = load_json("dealers_watchlist.json")
    if "dealers" not in data:
        data["dealers"] = []
    if "watchlist_only" not in data:
        data["watchlist_only"] = False
    return data


def get_suggested_dealers() -> list[dict[str, Any]]:
    return load_json("dealers_suggested.json").get("dealers", [])
