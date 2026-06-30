#!/usr/bin/env python3
"""Run one daily snapshot from the command line."""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.pipeline import run_daily_snapshot

logging.basicConfig(level=logging.INFO)


def main() -> None:
    result = run_daily_snapshot()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
