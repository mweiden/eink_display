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
    {"title": "Design Review", "where": "PA–Waverly", "start": (9, 0), "end": (9, 45)},
    {"title": "John / Matt", "where": "PA–University", "start": (11, 0), "end": (11, 30)},
    {"title": "Team Lunch", "where": "Cafeteria", "start": (13, 0), "end": (14, 0)},
    {"title": "Pickup visitor", "where": "PA-FrontDesk", "start": (13, 0), "end": (13, 15)},
    {"title": "Recruiting Sync", "where": "PA–Cowper", "start": (13, 45), "end": (14, 30)},
    {"title": "Dave / Matt", "where": "PA–Alma", "start": (16, 0), "end": (16, 30)},
    {"title": "Jennifer / Matt", "where": "PA–Middlefield", "start": (16, 30), "end": (17, 0)},
]


def _parse_time(value: str) -> time:
    cleaned = value.strip().upper().replace(" ", "")
    fmts = ["%I:%M:%S%p", "%I:%M%p", "%H:%M:%S", "%H:%M"]
    for fmt in fmts:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.time()
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(f"Invalid time '{value}'. Use formats like 11:30:45AM or 23:30.")


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
    parser.add_argument(
        "--time",
        type=_parse_time,
        default=_parse_time("11:15:15AM"),
        help="Wall-clock time for rendering (default: 11:30:45AM)",
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
    current_minutes = args.time.hour * 60 + args.time.minute

    with NodeRenderServer() as server:
        if server.base_url is None:
            raise RuntimeError("Render server failed to report a base URL")
        client = NodeRenderClient(server.base_url)
        client.render(
            events,
            output_path=output_path,
            current_minutes=current_minutes,
            current_seconds=args.time.second,
        )

    print(f"Wrote sample preview to {output_path}")


if __name__ == "__main__":
    main()
