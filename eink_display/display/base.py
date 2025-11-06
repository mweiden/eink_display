"""Abstract display driver interfaces used by the application."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Sequence

from PIL import Image

FrameBuffer = bytes | bytearray | memoryview | Sequence[int]


class DisplayDriver(ABC):
    """Defines the behaviour required from any e-ink display driver."""

    @property
    @abstractmethod
    def resolution(self) -> tuple[int, int]:
        """Return the (width, height) of the display in pixels."""

    @abstractmethod
    def initialize(self) -> None:
        """Power on and prepare the display for updates."""

    @abstractmethod
    def clear(self) -> None:
        """Clear the display to a blank white frame."""

    @abstractmethod
    def display_frame(self, frame_buffer: FrameBuffer) -> None:
        """Push a raw frame buffer to the display."""

    @abstractmethod
    def display_image(self, image: Image.Image) -> None:
        """Push a rendered PIL image to the display."""

    @abstractmethod
    def sleep(self) -> None:
        """Put the display into low power sleep mode."""
