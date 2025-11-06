"""Display driver adapters for the e-ink calendar."""
from __future__ import annotations

from .base import DisplayDriver, FrameBuffer
from .waveshare import (
    DEFAULT_RESOLUTION,
    MockEPDDriver,
    WaveshareEPDDriver,
    create_display_driver,
)

__all__ = [
    "DEFAULT_RESOLUTION",
    "DisplayDriver",
    "FrameBuffer",
    "MockEPDDriver",
    "WaveshareEPDDriver",
    "create_display_driver",
]
