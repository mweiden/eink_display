from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from eink_display.scheduler import Scheduler, next_half_minute_boundary


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self.current = start
        self.sleeps: list[float] = []

    def now(self) -> datetime:
        return self.current

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.current += timedelta(seconds=seconds)

    def advance(self, seconds: float) -> None:
        self.current += timedelta(seconds=seconds)


@pytest.mark.parametrize(
    "moment, expected",
    [
        (datetime(2024, 1, 1, 12, 0, 5), datetime(2024, 1, 1, 12, 0, 30)),
        (datetime(2024, 1, 1, 12, 0, 30), datetime(2024, 1, 1, 12, 0, 30)),
        (datetime(2024, 1, 1, 12, 0, 45, 500000), datetime(2024, 1, 1, 12, 1, 0)),
        (datetime(2024, 1, 1, 12, 0, 59, 999999), datetime(2024, 1, 1, 12, 1, 0)),
    ],
)
def test_next_half_minute_boundary(moment: datetime, expected: datetime) -> None:
    assert next_half_minute_boundary(moment) == expected


def test_scheduler_waits_until_next_boundary() -> None:
    start = datetime(2024, 1, 1, 12, 0, 5, 500000)
    clock = FakeClock(start)
    trigger_times: list[datetime] = []

    def callback() -> None:
        trigger_times.append(clock.now())

    scheduler = Scheduler(callback, time_provider=clock.now, sleep_func=clock.sleep)
    scheduler.run(iterations=1)

    assert trigger_times == [datetime(2024, 1, 1, 12, 0, 30)]
    assert pytest.approx(clock.sleeps[0], rel=0, abs=0.001) == 24.5


def test_scheduler_resynchronizes_after_drift() -> None:
    clock = FakeClock(datetime(2024, 1, 1, 12, 0, 0))
    trigger_times: list[datetime] = []

    def callback() -> None:
        trigger_times.append(clock.now())
        # Simulate a long-running refresh that drifts past the next boundary.
        clock.advance(45)

    scheduler = Scheduler(callback, time_provider=clock.now, sleep_func=clock.sleep)
    scheduler.run(iterations=2)

    assert trigger_times == [
        datetime(2024, 1, 1, 12, 0, 0),
        datetime(2024, 1, 1, 12, 1, 0),
    ]
    # After drift we should only sleep to the next aligned boundary (15 seconds).
    assert pytest.approx(clock.sleeps[-1], rel=0, abs=0.001) == 15
