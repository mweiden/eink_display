"""Renderer for composing the day-view calendar image."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Iterable, List, Sequence

from PIL import Image, ImageDraw, ImageFont

from .layout import DEFAULT_LAYOUT, LayoutMetrics


def _font_length(font: ImageFont.ImageFont, text: str) -> float:
    try:
        return font.getlength(text)  # type: ignore[attr-defined]
    except AttributeError:  # pragma: no cover - fallback for older Pillow
        dummy_img = Image.new("L", (1, 1), color=255)
        draw = ImageDraw.Draw(dummy_img)
        return float(draw.textlength(text, font=font))


def _load_font(path_candidates: Sequence[Path], size: int) -> ImageFont.ImageFont:
    for candidate in path_candidates:
        if candidate and candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _default_font_candidates(bold: bool) -> List[Path]:
    names = [
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "Arial Bold.ttf" if bold else "Arial.ttf",
    ]
    candidates: List[Path] = []
    search_dirs = [
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts"),
        Path("/Library/Fonts"),
        Path.home() / ".fonts",
    ]
    for name in names:
        for directory in search_dirs:
            candidate = directory / name
            candidates.append(candidate)
    return candidates


@dataclass(slots=True)
class CalendarEvent:
    """Normalized calendar event information used for rendering."""

    title: str
    start: datetime
    end: datetime
    location: str | None = None
    is_all_day: bool = False


@dataclass
class RendererConfig:
    """Configuration values and font management for the renderer."""

    layout: LayoutMetrics = DEFAULT_LAYOUT
    font_regular_path: Path | None = None
    font_bold_path: Path | None = None
    preview_output_dir: Path | None = None
    background_color: int = 255
    foreground_color: int = 0
    accent_color: int = 0
    header_font_size: int = 42
    subheader_font_size: int = 24
    time_label_font_size: int = 20
    card_title_font_size: int = 24
    card_body_font_size: int = 18

    def __post_init__(self) -> None:
        if self.preview_output_dir is not None:
            self.preview_output_dir = Path(self.preview_output_dir)
            self.preview_output_dir.mkdir(parents=True, exist_ok=True)

    def _font_candidates(self, bold: bool) -> List[Path]:
        provided = self.font_bold_path if bold else self.font_regular_path
        candidates: List[Path] = []
        if provided is not None:
            candidates.append(Path(provided))
        candidates.extend(_default_font_candidates(bold))
        return candidates

    def font(self, size: int, *, bold: bool = False) -> ImageFont.ImageFont:
        return _load_font(self._font_candidates(bold), size)


class DayRenderer:
    """Compose the day view image for the e-ink display."""

    def __init__(self, config: RendererConfig | None = None) -> None:
        self.config = config or RendererConfig()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def render_day(
        self,
        events: Iterable[CalendarEvent],
        now: datetime,
        *,
        preview_name: str | None = None,
    ) -> Image.Image:
        """Render the calendar view image.

        Args:
            events: Iterable of calendar events for the day.
            now: Current timestamp used for header and current-time line.
            preview_name: Optional name for the preview PNG when preview mode
                is enabled.
        Returns:
            A Pillow image representing the day view.
        """

        cfg = self.config
        layout = cfg.layout
        image = Image.new(
            "L",
            (layout.canvas_width, layout.canvas_height),
            color=cfg.background_color,
        )
        draw = ImageDraw.Draw(image)

        self._draw_header(draw, now)
        self._draw_hour_grid(draw)
        self._draw_events(draw, list(events))
        self._draw_current_time(draw, now)

        if cfg.preview_output_dir is not None:
            name = preview_name or now.strftime("%Y%m%d-%H%M%S")
            output_path = cfg.preview_output_dir / f"{name}.png"
            image.save(output_path)

        return image

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _draw_header(self, draw: ImageDraw.ImageDraw, now: datetime) -> None:
        cfg = self.config
        layout = cfg.layout

        date_font = cfg.font(cfg.subheader_font_size)
        time_font = cfg.font(cfg.header_font_size, bold=True)
        ampm_font = cfg.font(cfg.subheader_font_size, bold=True)

        date_text = now.strftime("%A, %B %d")
        draw.text(
            (layout.timeline_left_padding, 18),
            date_text,
            font=date_font,
            fill=cfg.foreground_color,
        )

        hour_text = now.strftime("%I").lstrip("0") or "12"
        minute_text = now.strftime("%M")
        am_pm = now.strftime("%p")

        time_x = layout.card_right - _font_length(time_font, hour_text + minute_text) - 40
        time_y = 22
        draw.text((time_x, time_y), hour_text, font=time_font, fill=cfg.foreground_color)
        hour_width = _font_length(time_font, hour_text)

        dot_center_x = time_x + hour_width + 10
        dot_center_y = time_y + time_font.size // 2
        self._draw_colon_dots(draw, dot_center_x, dot_center_y, cfg.foreground_color)

        minute_x = dot_center_x + 10
        draw.text((minute_x, time_y), minute_text, font=time_font, fill=cfg.foreground_color)

        ampm_x = minute_x + _font_length(time_font, minute_text) + 6
        ampm_y = time_y + time_font.size - ampm_font.size + 6
        draw.text((ampm_x, ampm_y), am_pm, font=ampm_font, fill=cfg.foreground_color)

    def _draw_colon_dots(
        self,
        draw: ImageDraw.ImageDraw,
        center_x: float,
        center_y: float,
        color: int,
    ) -> None:
        layout = self.config.layout
        radius = layout.current_time_dot_radius
        gap = radius * 2 + 2
        top = (center_x - radius, center_y - gap - radius, center_x + radius, center_y - gap + radius)
        bottom = (center_x - radius, center_y + gap - radius, center_x + radius, center_y + gap + radius)
        draw.ellipse(top, fill=color)
        draw.ellipse(bottom, fill=color)

    def _draw_hour_grid(self, draw: ImageDraw.ImageDraw) -> None:
        cfg = self.config
        layout = cfg.layout
        grid_color = cfg.foreground_color
        label_font = cfg.font(cfg.time_label_font_size)

        for hour in range(layout.start_hour, layout.end_hour + 1):
            y = int(round(layout.y_for_time(time(hour=hour))))
            draw.line(
                (layout.card_left, y, layout.card_right, y),
                fill=grid_color,
                width=layout.grid_line_thickness,
            )
            label = self._format_hour_label(hour)
            label_x = layout.timeline_left_padding
            label_y = y - label_font.size // 2
            draw.text((label_x, label_y), label, font=label_font, fill=grid_color)

    def _format_hour_label(self, hour: int) -> str:
        suffix = "AM" if hour < 12 or hour == 24 else "PM"
        display_hour = hour % 12
        if display_hour == 0:
            display_hour = 12
        return f"{display_hour} {suffix}"

    def _draw_events(
        self,
        draw: ImageDraw.ImageDraw,
        events: List[CalendarEvent],
    ) -> None:
        cfg = self.config
        layout = cfg.layout
        title_font = cfg.font(cfg.card_title_font_size, bold=True)
        body_font = cfg.font(cfg.card_body_font_size)
        time_font = cfg.font(cfg.card_body_font_size)

        events.sort(key=lambda evt: (evt.start, evt.end))

        for event in events:
            start_y = layout.y_for_time(event.start)
            end_y = layout.y_for_time(event.end)
            if event.is_all_day:
                start_y = layout.timeline_top
                end_y = start_y + layout.hour_block_height
            height = max(end_y - start_y, cfg.card_body_font_size * 2)
            card_top = start_y + 1
            card_bottom = card_top + height - 2

            bbox = (
                layout.card_left,
                card_top,
                layout.card_right,
                card_bottom,
            )
            draw.rounded_rectangle(
                bbox,
                radius=layout.meeting_card_corner_radius,
                outline=cfg.foreground_color,
                width=2,
                fill=None,
            )

            content_left = layout.card_left + layout.meeting_card_padding_x
            content_right = layout.card_right - layout.meeting_card_padding_x
            content_top = card_top + layout.meeting_card_padding_y

            time_text = self._format_event_time(event)
            draw.text(
                (content_left, content_top),
                time_text,
                font=time_font,
                fill=cfg.foreground_color,
            )
            current_y = content_top + time_font.size + 6

            title_lines = self._wrap_text(
                event.title,
                title_font,
                max_width=content_right - content_left,
                max_lines=cfg.layout.title_max_lines,
            )
            for line in title_lines:
                draw.text((content_left, current_y), line, font=title_font, fill=cfg.foreground_color)
                current_y += title_font.size + 2

            if event.location:
                location_lines = self._wrap_text(
                    event.location,
                    body_font,
                    max_width=content_right - content_left,
                    max_lines=cfg.layout.location_max_lines,
                )
                for line in location_lines:
                    draw.text(
                        (content_left, current_y),
                        line,
                        font=body_font,
                        fill=cfg.foreground_color,
                    )
                    current_y += body_font.size + 2

    def _format_event_time(self, event: CalendarEvent) -> str:
        if event.is_all_day:
            return "All day"
        start = event.start.strftime("%I:%M").lstrip("0")
        end = event.end.strftime("%I:%M").lstrip("0")
        start_period = event.start.strftime("%p")
        end_period = event.end.strftime("%p")
        if start_period == end_period:
            return f"{start}–{end} {start_period}"
        return f"{start} {start_period} – {end} {end_period}"

    def _wrap_text(
        self,
        text: str,
        font: ImageFont.ImageFont,
        *,
        max_width: int,
        max_lines: int,
    ) -> List[str]:
        if not text:
            return []
        words = text.split()
        if not words:
            return []
        lines: List[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if _font_length(font, candidate) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)

        wrapped: List[str] = []
        for line in lines:
            if _font_length(font, line) <= max_width:
                wrapped.append(line)
            else:
                truncated = self._truncate_line(line, font, max_width)
                wrapped.append(truncated)
        if len(wrapped) <= max_lines:
            return wrapped
        truncated_lines = wrapped[:max_lines]
        last_line = truncated_lines[-1]
        ellipsis = "…"
        while last_line and _font_length(font, last_line + ellipsis) > max_width:
            last_line = last_line[:-1].rstrip()
        truncated_lines[-1] = (last_line + ellipsis) if last_line else ellipsis
        return truncated_lines

    def _truncate_line(self, line: str, font: ImageFont.ImageFont, max_width: int) -> str:
        ellipsis = "…"
        current = line
        while current and _font_length(font, current + ellipsis) > max_width:
            current = current[:-1].rstrip()
        return (current + ellipsis) if current else ellipsis

    def _draw_current_time(self, draw: ImageDraw.ImageDraw, now: datetime) -> None:
        cfg = self.config
        layout = cfg.layout

        y = layout.y_for_time(now)
        draw.line(
            (layout.card_left, y, layout.card_right, y),
            fill=cfg.accent_color or cfg.foreground_color,
            width=layout.current_time_line_thickness,
        )
        dot_x = layout.card_left - layout.column_gap
        dot_bbox = (
            dot_x - layout.current_time_dot_radius,
            y - layout.current_time_dot_radius,
            dot_x + layout.current_time_dot_radius,
            y + layout.current_time_dot_radius,
        )
        draw.ellipse(dot_bbox, fill=cfg.accent_color or cfg.foreground_color)


__all__ = ["CalendarEvent", "DayRenderer", "RendererConfig"]
