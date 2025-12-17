"""Command line entry point for the e-ink display scheduler."""

from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Optional

from .config import load_env_file
from .display import DisplayDriver, MockEPDDriver, WaveshareEPDDriver, create_display_driver
from .rendering import NodeRenderClient, NodeRenderServer
from .scheduler import Scheduler

LOGGER = logging.getLogger(__name__)
DEFAULT_NODE_URL = "http://127.0.0.1:3000"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="E-Ink display refresh scheduler")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional path to a .env file loaded before the app starts.",
    )
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
    parser.add_argument(
        "--start-node-server",
        action="store_true",
        help="Launch the bundled Node renderer instead of connecting to an external instance.",
    )
    parser.add_argument(
        "--node-url",
        type=str,
        default=None,
        help="Base URL for the Node renderer (ignored when --start-node-server is set).",
    )
    parser.add_argument(
        "--node-timeout",
        type=float,
        default=10.0,
        help="Timeout (seconds) for renderer startup and requests.",
    )

    display_group = parser.add_argument_group("Display options")
    display_group.add_argument(
        "--display-driver",
        choices=("auto", "waveshare", "mock"),
        default="auto",
        help="Select the display driver backend. 'auto' picks hardware when available.",
    )
    display_group.add_argument(
        "--mock-output-dir",
        type=Path,
        default=None,
        help="Directory where the mock display driver writes captured frames.",
    )

    return parser


@dataclass
class AppSettings:
    once: bool
    immediate: bool
    start_node_server: bool
    node_url: str | None
    node_timeout: float
    display_driver: str
    mock_output_dir: Path | None


class AppRuntime:
    """Owns the lifecycle of the renderer client, display, and scheduler."""

    def __init__(
        self,
        *,
        settings: AppSettings,
        scheduler_factory: Callable[[Callable[[], None]], Scheduler] = Scheduler,
        node_client_factory: Callable[..., NodeRenderClient] = NodeRenderClient,
        node_server_factory: Callable[..., NodeRenderServer] = NodeRenderServer,
        display_factory: Callable[..., DisplayDriver] = create_display_driver,
        now_provider: Callable[[], datetime] = datetime.now,
        logger: logging.Logger | None = None,
    ) -> None:
        self.settings = settings
        self.scheduler_factory = scheduler_factory
        self.node_client_factory = node_client_factory
        self.node_server_factory = node_server_factory
        self.display_factory = display_factory
        self.now_provider = now_provider
        self.logger = logger or LOGGER

        self._display: DisplayDriver | None = None
        self._client: NodeRenderClient | None = None
        self._server: NodeRenderServer | None = None
        self._scheduler: Scheduler | None = None
        self._started = False

    def start(self) -> None:
        """Instantiate dependencies and prepare the refresh loop."""

        if self._started:
            return

        try:
            self._display = self._create_display_driver()
            self._display.initialize()
            self._client = self._create_render_client()
            self._scheduler = self.scheduler_factory(self.refresh_once)
            self._started = True
        except Exception:
            self.close()
            raise

    def run(self, *, immediate: bool = False, iterations: Optional[int] = None) -> None:
        if not self._scheduler:
            raise RuntimeError("Scheduler has not been started")
        self._scheduler.run(immediate=immediate, iterations=iterations)

    def refresh_once(self) -> None:
        if not self._display or not self._client:
            raise RuntimeError("Runtime has not been fully started")

        now = self.now_provider()
        self.logger.info("Refreshing display at %s", now.isoformat())

        self._display.initialize()

        try:
            image = self._client.fetch_png(now=now)
        except Exception:
            self.logger.exception("Failed to fetch PNG from Node renderer")
            self._sleep_display_safely()
            return

        try:
            self._display.display_image(image)
        except Exception:
            self.logger.exception("Failed to push frame to display")
        finally:
            self._sleep_display_safely()

    def close(self) -> None:
        if self._display:
            try:
                self._display.sleep()
            except Exception:
                self.logger.exception("Error while putting display to sleep")
            finally:
                self._display = None

        if self._server:
            try:
                self._server.stop()
            except Exception:
                self.logger.exception("Error while stopping Node renderer")
            finally:
                self._server = None

        self._client = None
        self._scheduler = None
        self._started = False

    def _sleep_display_safely(self) -> None:
        if not self._display:
            return
        try:
            self._display.sleep()
        except Exception:
            self.logger.exception("Failed to put display into sleep mode")

    # Internal helpers -------------------------------------------------
    def _create_display_driver(self) -> DisplayDriver:
        mode = self.settings.display_driver
        if mode == "waveshare":
            if not WaveshareEPDDriver.is_supported():
                raise RuntimeError("waveshare driver not available in this environment")
            return WaveshareEPDDriver(logger=self.logger)
        if mode == "mock":
            return MockEPDDriver(output_dir=self.settings.mock_output_dir, logger=self.logger)
        return self.display_factory(
            prefer_mock=False,
            mock_output_dir=self.settings.mock_output_dir,
            logger=self.logger,
        )

    def _create_render_client(self) -> NodeRenderClient:
        if self.settings.start_node_server:
            self._server = self.node_server_factory(wait_timeout=self.settings.node_timeout)
            self._server.start()
            base_url = self._server.base_url
        else:
            base_url = self.settings.node_url

        if not base_url:
            raise RuntimeError("Renderer base URL is not configured")

        return self.node_client_factory(base_url, timeout=self.settings.node_timeout)


def resolve_settings(args: argparse.Namespace) -> AppSettings:
    load_env_file(args.env_file)
    node_url = args.node_url or os.environ.get("NODE_RENDER_URL") or DEFAULT_NODE_URL
    if args.start_node_server:
        node_url = None

    return AppSettings(
        once=args.once,
        immediate=args.immediate,
        start_node_server=args.start_node_server,
        node_url=node_url,
        node_timeout=args.node_timeout,
        display_driver=args.display_driver,
        mock_output_dir=args.mock_output_dir,
    )


def main(
    argv: Optional[Iterable[str]] = None,
    *,
    scheduler_factory: Callable[[Callable[[], None]], Scheduler] = Scheduler,
    node_client_factory: Callable[..., NodeRenderClient] = NodeRenderClient,
    node_server_factory: Callable[..., NodeRenderServer] = NodeRenderServer,
) -> None:
    logging.basicConfig(level=logging.INFO)
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.once and args.immediate:
        parser.error("--once and --immediate are mutually exclusive")

    settings = resolve_settings(args)

    runtime = AppRuntime(
        settings=settings,
        scheduler_factory=scheduler_factory,
        node_client_factory=node_client_factory,
        node_server_factory=node_server_factory,
    )

    try:
        runtime.start()
        if settings.once:
            runtime.run(immediate=True, iterations=1)
        else:
            runtime.run(immediate=settings.immediate)
    except KeyboardInterrupt:
        LOGGER.info("Interrupted, shutting down")
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
