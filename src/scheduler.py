from __future__ import annotations

import logging
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import get_settings
from src.pipeline import run_daily_snapshot

logger = logging.getLogger(__name__)
_scheduler: BackgroundScheduler | None = None


def _scheduled_job() -> None:
    logger.info("Running scheduled daily snapshot")
    try:
        result = run_daily_snapshot()
        logger.info("Daily snapshot complete: %s", result)
    except Exception:
        logger.exception("Scheduled snapshot failed")


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    settings = get_settings()["schedule"]
    _scheduler = BackgroundScheduler(timezone=settings["timezone"])
    _scheduler.add_job(
        _scheduled_job,
        CronTrigger(
            hour=int(settings["hour"]),
            minute=int(settings["minute"]),
            timezone=settings["timezone"],
        ),
        id="daily_snapshot",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started for %02d:%02d %s",
        settings["hour"],
        settings["minute"],
        settings["timezone"],
    )
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    _scheduler = None


def preset_dates(today: date | None = None) -> dict[str, str]:
    today = today or date.today()
    return {
        "today": today.isoformat(),
        "three_days_ago": (today - timedelta(days=3)).isoformat(),
        "one_week_ago": (today - timedelta(days=7)).isoformat(),
    }
