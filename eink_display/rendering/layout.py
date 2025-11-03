"""Layout constants and helpers for the e-ink calendar display."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Final


@dataclass(frozen=True)
class LayoutMetrics:
    """Collection of reusable layout constants derived from the design."""

    canvas_width: int = 480
    canvas_height: int = 800
    header_height: int = 120
    footer_height: int = 40
    hour_label_width: int = 72
    timeline_left_padding: int = 16
    timeline_right_padding: int = 24
    column_gap: int = 6
    start_hour: int = 6
    end_hour: int = 22
    current_time_line_thickness: int = 3
    current_time_dot_radius: int = 5
    grid_line_thickness: int = 1
    meeting_card_corner_radius: int = 10
    meeting_card_padding_x: int = 14
    meeting_card_padding_y: int = 10
    title_max_lines: int = 3
    location_max_lines: int = 2

    @property
    def hours_displayed(self) -> int:
        return self.end_hour - self.start_hour

    @property
    def timeline_top(self) -> int:
        return self.header_height

    @property
    def timeline_bottom(self) -> int:
        return self.canvas_height - self.footer_height

    @property
    def timeline_height(self) -> int:
        return self.timeline_bottom - self.timeline_top

    @property
    def hour_block_height(self) -> float:
        return self.timeline_height / self.hours_displayed

    @property
    def hour_label_area(self) -> int:
        return self.hour_label_width + self.timeline_left_padding

    @property
    def timeline_x(self) -> int:
        return self.timeline_left_padding + self.hour_label_width // 2

    @property
    def card_left(self) -> int:
        return self.timeline_left_padding + self.hour_label_width + self.column_gap

    @property
    def card_right(self) -> int:
        return self.canvas_width - self.timeline_right_padding

    @property
    def card_width(self) -> int:
        return self.card_right - self.card_left

    def y_for_time(self, value: datetime | time) -> float:
        """Return the vertical offset for a datetime within the visible window."""

        if isinstance(value, datetime):
            hour = value.hour + value.minute / 60 + value.second / 3600
        else:
            hour = value.hour + value.minute / 60 + value.second / 3600

        relative = max(self.start_hour, min(hour, self.end_hour)) - self.start_hour
        return self.timeline_top + relative * self.hour_block_height


DEFAULT_LAYOUT: Final[LayoutMetrics] = LayoutMetrics()

__all__ = ["DEFAULT_LAYOUT", "LayoutMetrics"]
