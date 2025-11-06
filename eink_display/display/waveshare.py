"""Waveshare 7.5"" display adapter with optional mock implementation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Optional

from PIL import Image

from .base import DisplayDriver, FrameBuffer

try:  # pragma: no cover - import guard depends on environment
    from waveshare_epd import epd7in5_V2
except ImportError:  # pragma: no cover - handled via fallback
    epd7in5_V2 = None  # type: ignore[assignment]


DEFAULT_RESOLUTION: tuple[int, int] = (800, 480)


class WaveshareEPDDriver(DisplayDriver):
    """Concrete driver that talks to the physical Waveshare EPD module."""

    def __init__(self, *, epd: Any | None = None, logger: logging.Logger | None = None) -> None:
        if epd is None:
            if epd7in5_V2 is None:
                raise RuntimeError(
                    "waveshare_epd.epd7in5_V2 is not available – use MockEPDDriver instead."
                )
            epd = epd7in5_V2.EPD()
        self._epd = epd
        self._logger = logger or logging.getLogger(__name__)
        self._initialized = False

    @classmethod
    def is_supported(cls) -> bool:
        """Return True when the vendor library can be imported."""

        return epd7in5_V2 is not None

    @property
    def resolution(self) -> tuple[int, int]:
        return int(self._epd.width), int(self._epd.height)

    def initialize(self) -> None:
        if not self._initialized:
            self._logger.debug("Initializing Waveshare EPD")
            self._epd.init()
            self._initialized = True

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("Display has not been initialized. Call initialize() first.")

    def clear(self) -> None:
        self._require_initialized()
        self._logger.debug("Clearing display")
        self._epd.Clear()

    def display_frame(self, frame_buffer: FrameBuffer) -> None:
        self._require_initialized()
        size = len(frame_buffer) if hasattr(frame_buffer, "__len__") else None
        if size is not None:
            self._logger.debug("Pushing frame buffer of %d bytes", size)
        else:
            self._logger.debug("Pushing frame buffer to display")
        self._epd.display(frame_buffer)

    def display_image(self, image: Image.Image) -> None:
        self._require_initialized()
        processed = self._prepare_image(image)
        frame = self._epd.getbuffer(processed)
        self.display_frame(frame)

    def sleep(self) -> None:
        if self._initialized:
            self._logger.debug("Putting display to sleep")
            self._epd.sleep()
            self._initialized = False

    def _prepare_image(self, image: Image.Image) -> Image.Image:
        width, height = self.resolution
        if image.size != (width, height):
            raise ValueError(
                f"Image has resolution {image.size}, expected {(width, height)} for this display."
            )
        return image.convert("1")


@dataclass
class MockEPDDriver(DisplayDriver):
    """Mock implementation for development environments without hardware."""

    resolution: tuple[int, int] = DEFAULT_RESOLUTION
    output_dir: Optional[Path] = None
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))
    keep_history: bool = True

    def __post_init__(self) -> None:
        self._initialized = False
        self._history: list[Image.Image] = []
        self._last_frame: Optional[bytes] = None
        if self.output_dir is not None:
            self.output_dir = Path(self.output_dir)
            self.output_dir.mkdir(parents=True, exist_ok=True)

    def initialize(self) -> None:
        if not self._initialized:
            self.logger.debug("Mock display initialized")
            self._initialized = True

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("Mock display has not been initialized. Call initialize() first.")

    def clear(self) -> None:
        self._require_initialized()
        self.logger.debug("Mock display cleared")
        if self.keep_history:
            blank = Image.new("1", self.resolution, 255)
            self._history.append(blank)

    def display_frame(self, frame_buffer: FrameBuffer) -> None:
        self._require_initialized()
        size = len(frame_buffer) if hasattr(frame_buffer, "__len__") else None
        if size is not None:
            self.logger.debug("Received frame buffer of %d bytes", size)
        else:
            self.logger.debug("Received frame buffer")
        self._last_frame = bytes(frame_buffer)

    def display_image(self, image: Image.Image) -> None:
        self._require_initialized()
        if image.size != self.resolution:
            raise ValueError(
                f"Image has resolution {image.size}, expected {self.resolution} for the mock display."
            )
        processed = image.convert("1")
        if self.keep_history:
            self._history.append(processed.copy())
        if self.output_dir is not None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%fZ")
            output_path = self.output_dir / f"mock-frame-{timestamp}.png"
            processed.save(output_path)
            self.logger.debug("Saved mock frame to %s", output_path)
        self._last_frame = processed.tobytes()

    def sleep(self) -> None:
        if self._initialized:
            self.logger.debug("Mock display sleeping")
            self._initialized = False

    @property
    def history(self) -> list[Image.Image]:
        """Return copies of the frames pushed to the display (if enabled)."""

        return [frame.copy() for frame in self._history]

    @property
    def last_frame(self) -> Optional[bytes]:
        """Return the raw bytes of the last frame buffer that was displayed."""

        return self._last_frame


def create_display_driver(
    *,
    prefer_mock: bool = False,
    mock_output_dir: Optional[Path] = None,
    logger: Optional[logging.Logger] = None,
) -> DisplayDriver:
    """Create a display driver instance using the hardware driver when available."""

    if prefer_mock or not WaveshareEPDDriver.is_supported():
        return MockEPDDriver(output_dir=mock_output_dir, logger=logger or logging.getLogger(__name__))
    return WaveshareEPDDriver(logger=logger)
