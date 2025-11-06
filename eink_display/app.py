"""Command line entry point for the e-ink display scheduler."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from typing import Callable, Iterable, Optional

from .scheduler import Scheduler

LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="E-Ink display refresh scheduler")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single refresh immediately and exit.",
    )
    parser.add_argument(
        "--immediate",
        action="store_true",
        help="Perform an immediate refresh before entering the timed loop.",
    )
    return parser


def default_refresh_callback() -> None:
    LOGGER.info("Refreshing display at %s", datetime.now().isoformat())


def main(
    argv: Optional[Iterable[str]] = None,
    *,
    scheduler_factory: Callable[[Callable[[], None]], Scheduler] = Scheduler,
) -> None:
    logging.basicConfig(level=logging.INFO)
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.once and args.immediate:
        parser.error("--once and --immediate are mutually exclusive")

    scheduler = scheduler_factory(default_refresh_callback)

    if args.once:
        scheduler.run(immediate=True, iterations=1)
        return

    scheduler.run(immediate=args.immediate)


if __name__ == "__main__":
    main()
