"""Waveshare 7.5"" display adapter with optional mock implementation."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import Any, Optional

from PIL import Image, ImageChops

from .base import DisplayDriver, FrameBuffer

try:  # pragma: no cover - exercised indirectly when hardware is available
    from .waveshare_epd import epd7in5_V2
except Exception:  # pragma: no cover - import fails on non-hardware hosts
    epd7in5_V2 = None


DEFAULT_RESOLUTION: tuple[int, int] = (800, 480)
FULL_REFRESH_INTERVAL = 6
MAX_PARTIAL_REGIONS = 8
REGION_PADDING = 2
REGION_MERGE_GAP = 6


class WaveshareEPDDriver(DisplayDriver):
    """Concrete driver that talks to the physical Waveshare EPD module."""

    def __init__(self, *, epd: Any | None = None, logger: logging.Logger | None = None) -> None:
        if epd is None:
            if epd7in5_V2 is None:
                raise RuntimeError("Waveshare vendor driver is unavailable on this host")
            epd = epd7in5_V2.EPD()
        self._epd = epd
        self._logger = logger or logging.getLogger(__name__)
        self._initialized = False
        self._last_frame: Image.Image | None = None
        width, height = self.resolution
        self._blank_image = Image.new("1", (width, height), 255)
        self._partial_updates = 0

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
        self._last_frame = self._blank_image.copy()
        self._partial_updates = FULL_REFRESH_INTERVAL

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

        diff_regions: list[tuple[int, int, int, int]] | None = None
        if self._last_frame is not None:
            diff_regions = self._find_changed_regions(self._last_frame, processed)
            if not diff_regions:
                self._logger.debug("Frame unchanged; skipping update")
                return
            self._logger.debug("Detected %d diff region(s)", len(diff_regions))
        else:
            self._logger.debug("Performing initial refresh from blank panel state")

        require_full_refresh = self._last_frame is None or self._partial_updates >= FULL_REFRESH_INTERVAL
        if require_full_refresh:
            reason = "initial" if self._last_frame is None else "periodic"
            self._logger.debug("Performing %s full refresh", reason)
            buffer = bytes(self._epd.getbuffer(processed))
            self._display_full_buffer(buffer)
            self._partial_updates = 0
        else:
            assert diff_regions is not None
            self._logger.debug("Performing partial refresh across %d region(s)", len(diff_regions))
            for bbox in diff_regions:
                self._display_partial_region(processed, bbox)
            self._partial_updates += 1

        self._last_frame = processed.copy()

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
        grayscale = image.convert("L")
        return grayscale.convert("1", dither=Image.FLOYDSTEINBERG)

    def _display_full_buffer(self, buffer: bytes) -> None:
        self._epd.display(buffer)

    def _align_bbox(self, bbox: tuple[int, int, int, int] | None) -> tuple[int, int, int, int] | None:
        if bbox is None:
            return None
        width, height = self.resolution
        left, top, right, bottom = bbox
        left = max(0, left - (left % 8))
        right = min(width, ((right + 7) // 8) * 8)
        top = max(0, top)
        bottom = min(height, bottom)
        if left >= right or top >= bottom:
            return None
        return left, top, right, bottom

    def _display_partial_region(self, frame: Image.Image, bbox: tuple[int, int, int, int]) -> None:
        left, top, right, bottom = bbox
        region = frame.crop((left, top, right, bottom)).convert("1")
        buffer = bytearray(region.tobytes())
        for idx in range(len(buffer)):
            buffer[idx] ^= 0xFF
        self._logger.debug(
            "Performing partial refresh: x=%d-%d, y=%d-%d", left, right, top, bottom
        )
        self._epd.display_Partial(buffer, left, top, right, bottom)

    def _find_changed_regions(
        self, previous: Image.Image, current: Image.Image
    ) -> list[tuple[int, int, int, int]]:
        """Return bounding boxes for distinct changed regions."""

        diff_image = ImageChops.difference(previous, current)
        diff_bbox = diff_image.getbbox()
        if diff_bbox is None:
            return []

        diff_l = diff_image.convert("L")
        width, height = diff_l.size
        data = diff_l.tobytes()
        visited = bytearray(width * height)
        raw_regions: list[tuple[int, int, int, int]] = []
        queue: deque[int] = deque()

        for pixel_index in range(width * height):
            if data[pixel_index] == 0 or visited[pixel_index]:
                continue

            queue.append(pixel_index)
            visited[pixel_index] = 1
            min_x = width
            min_y = height
            max_x = -1
            max_y = -1

            while queue:
                current_index = queue.popleft()
                y, x = divmod(current_index, width)

                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)

                for ny in range(max(0, y - 1), min(height - 1, y + 1) + 1):
                    for nx in range(max(0, x - 1), min(width - 1, x + 1) + 1):
                        neighbor_index = ny * width + nx
                        if visited[neighbor_index] or data[neighbor_index] == 0:
                            continue
                        visited[neighbor_index] = 1
                        queue.append(neighbor_index)

            padded_bbox = (
                max(0, min_x - REGION_PADDING),
                max(0, min_y - REGION_PADDING),
                min(width, max_x + 1 + REGION_PADDING),
                min(height, max_y + 1 + REGION_PADDING),
            )
            aligned = self._align_bbox(padded_bbox)
            if aligned is not None:
                raw_regions.append(aligned)

        merged_regions = self._merge_regions(raw_regions)
        if MAX_PARTIAL_REGIONS and len(merged_regions) > MAX_PARTIAL_REGIONS:
            fallback = self._align_bbox(diff_bbox)
            if fallback is None:
                return []
            self._logger.debug(
                "Detected %d diff regions but limiting to %d; falling back to single bbox",
                len(merged_regions),
                MAX_PARTIAL_REGIONS,
            )
            return [fallback]
        return merged_regions

    def _merge_regions(self, regions: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
        """Merge overlapping or near-by bounding boxes to avoid excessive updates."""

        merged: list[tuple[int, int, int, int]] = []
        for region in regions:
            merged_region = region
            index = 0
            while index < len(merged):
                candidate = merged[index]
                if self._regions_should_merge(merged_region, candidate):
                    merged_region = (
                        min(merged_region[0], candidate[0]),
                        min(merged_region[1], candidate[1]),
                        max(merged_region[2], candidate[2]),
                        max(merged_region[3], candidate[3]),
                    )
                    merged.pop(index)
                    index = 0
                    continue
                index += 1
            aligned = self._align_bbox(merged_region)
            if aligned is not None:
                merged.append(aligned)
        return merged

    def _regions_should_merge(
        self, first: tuple[int, int, int, int], second: tuple[int, int, int, int]
    ) -> bool:
        """Return True when regions overlap or are within the merge gap."""

        gap_x = 0
        if first[2] < second[0]:
            gap_x = second[0] - first[2]
        elif second[2] < first[0]:
            gap_x = first[0] - second[2]

        gap_y = 0
        if first[3] < second[1]:
            gap_y = second[1] - first[3]
        elif second[3] < first[1]:
            gap_y = first[1] - second[3]

        return gap_x <= REGION_MERGE_GAP and gap_y <= REGION_MERGE_GAP


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
