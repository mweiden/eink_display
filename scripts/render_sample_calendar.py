#!/usr/bin/env python3
"""Generate a sample calendar preview using the Node-based renderer."""

from __future__ import annotations

import argparse
from datetime import date, datetime, time
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eink_display.rendering import CalendarEvent, NodeRenderClient, NodeRenderServer


DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "previews" / "tufte_day_sample.png"

SAMPLE_EVENTS = [
    {"title": "Design Review", "where": "MTV–Aristotle", "start": (9, 0), "end": (9, 45)},
    {"title": "Rachel / Matt", "where": "MTV–Descartes", "start": (11, 0), "end": (11, 30)},
    {"title": "Team Lunch", "where": "Cafeteria", "start": (13, 0), "end": (14, 0)},
    {"title": "Recruiting Sync", "where": "MTV–DaVinci", "start": (13, 45), "end": (14, 30)},
    {"title": "Luke / Matt", "where": "MTV–Descartes", "start": (16, 0), "end": (16, 35)},
    {"title": "Kevin / Matt", "where": "MTV–Descartes", "start": (16, 30), "end": (17, 0)},
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Where to write the preview PNG (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--date",
        type=date.fromisoformat,
        default=date.today(),
        help="ISO-8601 date for the sample events (default: today)",
    )
    return parser.parse_args()


def _as_datetime(day: date, hm: tuple[int, int]) -> datetime:
    hours, minutes = hm
    return datetime.combine(day, time(hour=hours, minute=minutes))


def build_sample_events(day: date) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    for spec in SAMPLE_EVENTS:
        events.append(
            CalendarEvent(
                title=spec["title"],
                start=_as_datetime(day, spec["start"]),
                end=_as_datetime(day, spec["end"]),
                location=spec["where"],
            )
        )
    return events


def main() -> None:
    args = parse_args()
    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    events = build_sample_events(args.date)

    with NodeRenderServer() as server:
        if server.base_url is None:
            raise RuntimeError("Render server failed to report a base URL")
        client = NodeRenderClient(server.base_url)
        client.render(events, output_path=output_path)

    print(f"Wrote sample preview to {output_path}")


if __name__ == "__main__":
    main()
