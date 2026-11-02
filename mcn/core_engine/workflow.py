"""
Scheduled jobs for MCN services.

    job daily_digest every day at "09:00"
    job sync every 15 minutes
    job weekly_report every monday at "08:30"

`mcn serve` runs jobs in a background thread (server local time). Each run is
recorded (last run, status, error) and admins can list jobs and run one now.
"""

from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def next_run(every: int, unit: str, at: str, after: datetime) -> datetime:
    """The first scheduled time strictly after `after`."""
    if unit == "minute":
        base = after.replace(second=0, microsecond=0)
        step = timedelta(minutes=every)
        minutes = base.hour * 60 + base.minute
        nxt = base + timedelta(minutes=every - (minutes % every))
        return nxt if nxt > after else nxt + step
    if unit == "hour":
        base = after.replace(minute=0, second=0, microsecond=0)
        nxt = base + timedelta(hours=every - (base.hour % every))
        return nxt if nxt > after else nxt + timedelta(hours=every)
    hh, mm = (int(x) for x in (at or "00:00").split(":"))
    candidate = after.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if unit in WEEKDAYS:
        target = WEEKDAYS.index(unit)
        candidate += timedelta(days=(target - candidate.weekday()) % 7)
        if candidate <= after:
            candidate += timedelta(days=7 * every)
        return candidate
    days = 7 * every if unit == "week" else every
    if candidate <= after:
        candidate += timedelta(days=1 if days == 1 else days)
    return candidate


def describe(every: int, unit: str, at: str) -> str:
    if unit in WEEKDAYS:
        text = f"every {unit.capitalize()}"
    elif every == 1:
        text = {"minute": "every minute", "hour": "every hour", "day": "every day",
                "week": "every week"}[unit]
    else:
        text = f"every {every} {unit}s"
    return text + (f" at {at}" if at else "")


class Job:
    def __init__(self, name: str, every: int, unit: str, at: str, fn: Callable[[], Any]):
        self.name, self.every, self.unit, self.at, self.fn = name, every, unit, at, fn
        self.next_run = next_run(every, unit, at, datetime.now())
        self.last_run: Optional[str] = None
        self.last_status: Optional[str] = None
        self.last_error: Optional[str] = None

    def run(self) -> Dict[str, Any]:
        started = datetime.now()
        try:
            self.fn()
            self.last_status, self.last_error = "ok", None
        except Exception as exc:
            self.last_status, self.last_error = "failed", str(exc)
            print(f"[mcn] job {self.name} failed: {exc}")
            traceback.print_exc()
        self.last_run = started.isoformat(timespec="seconds")
        self.next_run = next_run(self.every, self.unit, self.at, datetime.now())
        return self.info()

    def info(self) -> Dict[str, Any]:
        return {"name": self.name, "schedule": describe(self.every, self.unit, self.at),
                "next_run": self.next_run.isoformat(timespec="seconds"),
                "last_run": self.last_run, "last_status": self.last_status,
                "last_error": self.last_error}


class Scheduler:
    """Runs due jobs in one background thread; `lock` serialises with requests."""

    def __init__(self, jobs: List[Job], lock: threading.RLock):
        self.jobs = jobs
        self.lock = lock
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.jobs and self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="mcn-jobs", daemon=True)
            self._thread.start()
            for j in self.jobs:
                print(f"  job  {j.name}: {describe(j.every, j.unit, j.at)} "
                      f"(next {j.next_run:%Y-%m-%d %H:%M})")

    def stop(self) -> None:
        self._stop.set()

    def tick(self, now: Optional[datetime] = None) -> List[str]:
        """Run every job that is due; returns their names."""
        now = now or datetime.now()
        ran = []
        for job in self.jobs:
            if job.next_run <= now:
                with self.lock:
                    job.run()
                ran.append(job.name)
        return ran

    def _loop(self) -> None:
        while not self._stop.wait(timeout=5):
            self.tick()
