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


def get_model_catalog() -> list[dict[str, Any]]:
    return load_yaml("model_catalog.yaml")["brands"]


def get_model_selection() -> list[dict[str, str]]:
    data = load_json("models_selection.json")
    selections = data.get("selections") or []
    return [
        {"make": str(item["make"]).strip(), "model": str(item["model"]).strip()}
        for item in selections
        if item.get("make") and item.get("model")
    ]


def save_model_selection(selections: list[dict[str, str]]) -> None:
    save_json("models_selection.json", {"selections": selections})


def validate_model_selection(selections: list[dict[str, str]]) -> list[dict[str, str]]:
    lookup = _catalog_lookup()
    valid: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in selections[:5]:
        make = item.get("make", "").strip()
        model = item.get("model", "").strip()
        key = (make, model)
        if not make or not model or key in seen or key not in lookup:
            continue
        seen.add(key)
        valid.append({"make": make, "model": model})
    return valid


def _catalog_lookup() -> dict[tuple[str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    for brand in get_model_catalog():
        make = brand["make"]
        for model in brand["models"]:
            lookup[(make, model["name"])] = {
                "make": make,
                "model": model["name"],
                "key": model["key"],
                "autotrader": model["autotrader"],
                "cargurus": model.get("cargurus") or brand["cargurus_brand"],
            }
    return lookup


def format_model_label(model: dict[str, Any]) -> str:
    return f"{model['make']} {model['model']}"


def model_labels_map() -> dict[str, str]:
    return {model["key"]: format_model_label(model) for model in get_models()}


def get_models() -> list[dict[str, Any]]:
    lookup = _catalog_lookup()
    models: list[dict[str, Any]] = []
    for priority, selection in enumerate(get_model_selection(), start=1):
        entry = lookup.get((selection["make"], selection["model"]))
        if not entry:
            continue
        models.append(
            {
                "key": entry["key"],
                "make": entry["make"],
                "model": entry["model"],
                "priority": priority,
                "autotrader": {"path": entry["autotrader"]},
                "cargurus": {"make_model_trim": entry["cargurus"]},
            }
        )
    return models


def get_watchlist() -> dict[str, Any]:
    data = load_json("dealers_watchlist.json")
    if "dealers" not in data:
        data["dealers"] = []
    if "watchlist_only" not in data:
        data["watchlist_only"] = False
    return data


def get_suggested_dealers() -> list[dict[str, Any]]:
    return load_json("dealers_suggested.json").get("dealers", [])
