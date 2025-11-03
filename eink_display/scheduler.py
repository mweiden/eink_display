"""Scheduling utilities for aligning refresh cycles to half-minute boundaries."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

LOGGER = logging.getLogger(__name__)


def next_half_minute_boundary(moment: datetime) -> datetime:
    """Return the next :00 or :30 second boundary at or after ``moment``.

    The returned value is aligned to the system represented by ``moment``
    (timezone-aware datetimes stay aware). If ``moment`` already falls exactly on
    a boundary, the same timestamp is returned.
    """

    # Normalize to second granularity, rounding up if there are remaining
    # microseconds so that we never schedule a trigger in the past.
    if moment.microsecond:
        moment = moment.replace(microsecond=0) + timedelta(seconds=1)
    else:
        moment = moment.replace(microsecond=0)

    if moment.second % 30 == 0:
        return moment

    delta = 30 - (moment.second % 30)
    return moment + timedelta(seconds=delta)


@dataclass
class Scheduler:
    """Run a callback on half-minute boundaries."""

    callback: Callable[[], None]
    time_provider: Callable[[], datetime] = datetime.now
    sleep_func: Callable[[float], None] = time.sleep

    def run(
        self,
        *,
        immediate: bool = False,
        iterations: Optional[int] = None,
    ) -> None:
        """Run the scheduler loop.

        Args:
            immediate: If ``True`` the callback is triggered immediately before
                waiting for the next boundary.
            iterations: Optional number of iterations to execute. ``None`` runs
                indefinitely.
        """

        remaining = iterations

        if immediate:
            LOGGER.debug("Executing immediate refresh override before schedule")
            self.callback()
            if remaining is not None:
                remaining -= 1
                if remaining <= 0:
                    return

        while remaining is None or remaining > 0:
            target = self.wait_until_next_boundary()
            LOGGER.debug("Reached scheduled refresh time at %s", target.isoformat())
            self.callback()
            if remaining is not None:
                remaining -= 1

    def wait_until_next_boundary(self) -> datetime:
        """Block until the next :00 or :30 second boundary.

        Returns the timestamp of the boundary that was reached.
        """

        target = next_half_minute_boundary(self.time_provider())
        while True:
            now = self.time_provider()
            remaining = (target - now).total_seconds()
            if remaining <= 0:
                return target
            LOGGER.debug(
                "Sleeping %.3f seconds until next boundary at %s",
                remaining,
                target.isoformat(),
            )
            self.sleep_func(remaining)

