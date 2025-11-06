"""Tufte-inspired day view renderer for the e-ink calendar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from typing import Iterable, List, Sequence

from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
            candidates.append(directory / name)
    return candidates


def _wrap_text(
    text: str,
    font: ImageFont.ImageFont,
    *,
    max_width: int,
    max_lines: int,
) -> List[str]:
    if not text:
        return []

    words = text.split()
    lines: List[str] = []
    current: List[str] = []

    def flush_line(force: bool = False) -> None:
        nonlocal current
        if current or force:
            line = " ".join(current)
            if not line and force:
                line = ""
            if line:
                lines.append(line)
            current = []

    while words:
        word = words.pop(0)
        candidate = " ".join(current + [word])
        if not current and _font_length(font, word) > max_width:
            # hard-break the long word
            trimmed = word
            while trimmed and _font_length(font, trimmed + "…") > max_width:
                trimmed = trimmed[:-1]
            if trimmed:
                lines.append(trimmed + "…")
            else:
                lines.append(word)
            if len(lines) >= max_lines:
                return lines[:max_lines]
            continue

        if _font_length(font, candidate) <= max_width:
            current.append(word)
        else:
            flush_line()
            words.insert(0, word)
            if len(lines) == max_lines - 1:
                break

    flush_line(force=True)

    if len(lines) > max_lines:
        lines = lines[:max_lines]

    if words and lines:
        last = lines[-1]
        while last and _font_length(font, last + "…") > max_width:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CalendarEvent:
    """Normalized calendar event information."""

    title: str
    start: datetime
    end: datetime
    location: str | None = None

    def minutes_since_midnight(self) -> tuple[int, int]:
        return (_minutes_of_day(self.start), _minutes_of_day(self.end))


@dataclass
class RendererConfig:
    """Configuration and font management for the Tufte renderer."""

    canvas_width: int = 480
    canvas_height: int = 800
    padding_y: int = 24
    hour_column_width: int = 72
    column_gap: int = 16
    axis_inset: int = 0
    label_offset_left: int = 28
    label_col_gap: int = 10
    label_col_width: int = 160
    text_offset: int = -3
    tick_width: int = 4
    tick_shift: int = 8
    label_box_line_height: int = 11
    label_box_lines: int = 2
    label_box_extra: int = 4
    leader_color: int = 210
    axis_color: int = 189
    half_hour_color: int = 230
    text_color: int = 17
    secondary_text_color: int = 90
    background_color: int = 255
    density_color: int = 30
    density_axis_color: int = 230
    font_regular_path: Path | None = None
    font_bold_path: Path | None = None
    preview_output_dir: Path | None = None

    hour_font_size: int = 13
    title_font_size: int = 15
    detail_font_size: int = 12
    clock_font_size: int = 20
    clock_ampm_font_size: int = 20
    clock_dot_font_size: int = 12

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


# ---------------------------------------------------------------------------
# Core algorithms (ported from the React reference implementation)
# ---------------------------------------------------------------------------


def compute_density_buckets(
    events: Sequence[CalendarEvent],
    *,
    day_start: int,
    day_end: int,
    bucket_minutes: int = 10,
) -> tuple[List[int], int]:
    total = day_end - day_start
    n = max(1, (total + bucket_minutes - 1) // bucket_minutes)
    buckets = [0 for _ in range(n)]

    for event in events:
        start, end = event.minutes_since_midnight()
        s = max(0, start - day_start)
        e = min(total, end - day_start)
        if e <= s:
            continue

        start_idx = s // bucket_minutes
        end_idx = (e + bucket_minutes - 1) // bucket_minutes
        for idx in range(start_idx, end_idx):
            b_start = idx * bucket_minutes
            b_end = (idx + 1) * bucket_minutes
            overlap = max(0, min(e, b_end) - max(s, b_start))
            buckets[idx] += overlap

    max_bucket = max(1, *buckets)
    return buckets, max_bucket


def assign_overlap_columns(events: Sequence[CalendarEvent]) -> dict[int, int]:
    evts = [(_minutes_of_day(e.start), _minutes_of_day(e.end), idx) for idx, e in enumerate(events)]
    evts.sort()
    active: List[tuple[int, int]] = []  # (end, col)
    out: dict[int, int] = {}

    for start, end, idx in evts:
        active = [(e_end, col) for e_end, col in active if e_end > start]
        used = {col for _, col in active}
        col = 0
        while col in used:
            col += 1
        active.append((end, col))
        out[idx] = col

    return out


def assign_label_columns_top(
    *,
    desired_tops: Sequence[tuple[int, int]],
    box_height: int,
    min_gap: int = 4,
) -> dict[int, int]:
    sorted_items = sorted(desired_tops, key=lambda item: item[1])
    clusters: List[List[tuple[int, int]]] = []
    current: List[tuple[int, int]] = []
    cur_bottom = -10**9

    for item in sorted_items:
        idx, top = item
        if not current:
            current = [item]
            cur_bottom = top + box_height
            continue
        if top < cur_bottom + min_gap:
            current.append(item)
            cur_bottom = max(cur_bottom, top + box_height)
        else:
            clusters.append(current)
            current = [item]
            cur_bottom = top + box_height
    if current:
        clusters.append(current)

    out: dict[int, int] = {}
    for cluster in clusters:
        k = len(cluster)
        for pos, item in enumerate(cluster):
            idx, _ = item
            out[idx] = k - 1 - pos
    return out


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _minutes_of_day(dt: datetime) -> int:
    return dt.hour * 60 + dt.minute


class TufteDayRenderer:
    """Render a Tufte-inspired single-day calendar."""

    def __init__(self, config: RendererConfig | None = None) -> None:
        self.config = config or RendererConfig()

    def render_day(
        self,
        events: Iterable[CalendarEvent],
        *,
        now: datetime | None = None,
        day_start: time | None = None,
        day_end: time | None = None,
        show_density: bool = False,
        preview_name: str | None = None,
    ) -> Image.Image:
        cfg = self.config
        now = now or datetime.now()
        events_list = list(events)

        start_time = day_start or time(8, 0)
        end_time = day_end or time(21, 0)
        start_minutes = start_time.hour * 60 + start_time.minute
        end_minutes = end_time.hour * 60 + end_time.minute
        if end_minutes <= start_minutes:
            raise ValueError("day_end must be after day_start")

        filtered_events: List[CalendarEvent] = []
        for event in events_list:
            s, e = event.minutes_since_midnight()
            if e <= start_minutes or s >= end_minutes:
                continue
            filtered_events.append(event)

        filtered_events.sort(key=lambda evt: (evt.start, evt.end))

        canvas = Image.new("L", (cfg.canvas_width, cfg.canvas_height), color=cfg.background_color)
        draw = ImageDraw.Draw(canvas)

        padding = cfg.padding_y
        content_height = cfg.canvas_height - padding * 2
        total_minutes = end_minutes - start_minutes
        px_per_min = content_height / total_minutes

        def minute_to_y(minute: int) -> int:
            return int(round((minute - start_minutes) * px_per_min))

        # Build hour ticks
        hour_start = (start_minutes + 59) // 60 * 60
        hours = list(range(hour_start, end_minutes + 1, 60))

        # Pre-compute y ranges for events
        y_ranges: List[tuple[int, int]] = []
        for event in filtered_events:
            s, e = event.minutes_since_midnight()
            clamped_start = max(start_minutes, s)
            clamped_end = min(end_minutes, e)
            y1 = minute_to_y(clamped_start)
            y2 = minute_to_y(clamped_end)
            y_ranges.append((y1, y2))

        gap_px = 2
        for i in range(1, len(y_ranges)):
            prev_y1, prev_y2 = y_ranges[i - 1]
            cur_y1, cur_y2 = y_ranges[i]
            if abs(cur_y1 - prev_y2) <= 1:
                prev_y2 -= gap_px // 2
                cur_y1 += gap_px // 2
                y_ranges[i - 1] = (prev_y1, prev_y2)
                y_ranges[i] = (cur_y1, cur_y2)

        label_line_h = cfg.label_box_line_height
        label_box_h = label_line_h * cfg.label_box_lines + cfg.label_box_extra
        desired_tops = [(idx, y1) for idx, (y1, _) in enumerate(y_ranges)]
        label_cols = assign_label_columns_top(
            desired_tops=desired_tops, box_height=label_box_h, min_gap=4
        )

        label_map: dict[int, int] = {}
        by_col: dict[int, List[int]] = {}
        for idx, top in desired_tops:
            col = label_cols.get(idx, 0)
            by_col.setdefault(col, []).append(idx)
            label_map[idx] = top

        for col, indices in by_col.items():
            indices.sort(key=lambda i: label_map[i])
            last_bottom = -10**9
            for idx in indices:
                desired = label_map[idx]
                top = max(desired, last_bottom + 2)
                top = min(top, content_height - label_box_h)
                label_map[idx] = top
                last_bottom = top + label_box_h

        columns = assign_overlap_columns(filtered_events)

        self._draw_hour_labels(draw, hours, minute_to_y, padding)
        self._draw_spine(draw, hours, minute_to_y, padding, content_height, start_minutes, end_minutes)
        self._draw_now_indicator(draw, now, start_minutes, end_minutes, minute_to_y, padding)
        self._draw_events(
            draw,
            filtered_events,
            y_ranges,
            columns,
            label_cols,
            label_map,
            padding,
        )
        self._draw_labels(draw, filtered_events, y_ranges, label_cols, label_map, padding)
        self._draw_clock(draw, now)

        if show_density and filtered_events:
            self._draw_density(draw, filtered_events, start_minutes, end_minutes)

        if cfg.preview_output_dir is not None and preview_name is not None:
            output_path = cfg.preview_output_dir / f"{preview_name}.png"
            canvas.save(output_path)

        return canvas

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------

    def _draw_hour_labels(
        self,
        draw: ImageDraw.ImageDraw,
        hours: Sequence[int],
        minute_to_y,
        padding: int,
    ) -> None:
        cfg = self.config
        font = cfg.font(cfg.hour_font_size)
        for minute in hours:
            y = padding + minute_to_y(minute) - 6
            label_hour = (minute // 60) % 12 or 12
            suffix = "PM" if minute // 60 >= 12 else "AM"
            text = f"{label_hour} {suffix}"
            width = _font_length(font, text)
            x = cfg.hour_column_width - 4 - width
            draw.text((x, y), text, font=font, fill=cfg.secondary_text_color)

    def _draw_spine(
        self,
        draw,
        hours,
        minute_to_y,
        padding: int,
        content_height: int,
        start_minutes: int,
        end_minutes: int,
    ) -> None:
        cfg = self.config
        axis_x = cfg.hour_column_width + cfg.column_gap + cfg.axis_inset
        draw.line(
            (axis_x, padding, axis_x, padding + content_height),
            fill=cfg.axis_color,
            width=1,
        )
        for minute in hours:
            y = padding + minute_to_y(minute)
            draw.line((axis_x, y, axis_x + 5, y), fill=cfg.axis_color, width=1)
            half_minute = minute + 30
            if half_minute < end_minutes:
                half_y = padding + minute_to_y(half_minute)
                if half_y < padding + content_height:
                    draw.line((axis_x, half_y, axis_x + 3, half_y), fill=cfg.half_hour_color, width=1)

    def _draw_now_indicator(
        self,
        draw,
        now: datetime,
        start_minutes: int,
        end_minutes: int,
        minute_to_y,
        padding: int,
    ) -> None:
        cfg = self.config
        current = _minutes_of_day(now)
        if not (start_minutes <= current <= end_minutes):
            return
        axis_x = cfg.hour_column_width + cfg.column_gap + cfg.axis_inset
        y = padding + minute_to_y(current)
        r = 5
        draw.ellipse((axis_x - r, y - r, axis_x + r, y + r), fill=cfg.text_color)

    def _draw_events(
        self,
        draw,
        events: Sequence[CalendarEvent],
        y_ranges: Sequence[tuple[int, int]],
        columns: dict[int, int],
        label_cols: dict[int, int],
        label_map: dict[int, int],
        padding: int,
    ) -> None:
        cfg = self.config
        axis_x = cfg.hour_column_width + cfg.column_gap + cfg.axis_inset

        for idx, event in enumerate(events):
            y1, y2 = y_ranges[idx]
            col = columns.get(idx, 0)
            tick_x = axis_x + col * cfg.tick_shift
            draw.line(
                (tick_x, padding + y1, tick_x, padding + y2),
                fill=cfg.text_color,
                width=cfg.tick_width,
            )
            label_col = label_cols.get(idx, 0)
            label_left = (
                axis_x
                + cfg.label_offset_left
                + label_col * (cfg.label_col_width + cfg.label_col_gap)
            )
            draw.line(
                (tick_x, padding + y1, label_left, padding + y1),
                fill=cfg.leader_color,
                width=1,
            )

    def _draw_labels(
        self,
        draw,
        events: Sequence[CalendarEvent],
        y_ranges: Sequence[tuple[int, int]],
        label_cols: dict[int, int],
        label_map: dict[int, int],
        padding: int,
    ) -> None:
        cfg = self.config
        title_font = cfg.font(cfg.title_font_size, bold=True)
        detail_font = cfg.font(cfg.detail_font_size)
        axis_x = cfg.hour_column_width + cfg.column_gap + cfg.axis_inset

        for idx, event in enumerate(events):
            label_col = label_cols.get(idx, 0)
            left = (
                axis_x
                + cfg.label_offset_left
                + label_col * (cfg.label_col_width + cfg.label_col_gap)
            )
            top = padding + label_map.get(idx, y_ranges[idx][0]) + cfg.text_offset

            title_lines = _wrap_text(
                event.title,
                title_font,
                max_width=cfg.label_col_width,
                max_lines=2,
            )
            if not title_lines:
                title_lines = [""]

            start_minute, end_minute = event.minutes_since_midnight()
            details = (
                f"{_format_minutes(start_minute)}–{_format_minutes(end_minute)}"
                + (f" · {event.location}" if event.location else "")
            )
            detail_lines = _wrap_text(
                details,
                detail_font,
                max_width=cfg.label_col_width,
                max_lines=2,
            )

            y_cursor = top
            for line in title_lines:
                draw.text((left, y_cursor), line, font=title_font, fill=cfg.text_color)
                y_cursor += cfg.label_box_line_height
            for line in detail_lines:
                draw.text((left, y_cursor), line, font=detail_font, fill=cfg.secondary_text_color)
                y_cursor += cfg.label_box_line_height

    def _draw_clock(self, draw: ImageDraw.ImageDraw, now: datetime) -> None:
        cfg = self.config
        clock_font = cfg.font(cfg.clock_font_size)
        ampm_font = cfg.font(cfg.clock_ampm_font_size)
        dot_font = cfg.font(cfg.clock_dot_font_size)

        h = now.hour % 12 or 12
        m = f"{now.minute:02d}"
        time_text = f"{h}:{m}"
        ampm_text = "PM" if now.hour >= 12 else "AM"
        dot = "•"

        width = cfg.canvas_width - 3
        x = width
        y = 6

        ampm_width = _font_length(ampm_font, ampm_text)
        dot_width = _font_length(dot_font, dot)
        time_width = _font_length(clock_font, time_text)

        ampm_x = x - ampm_width
        dot_x = ampm_x - dot_width - 3
        time_x = dot_x - time_width - 2

        show_dot_high = now.second >= 30
        dot_y = y + (-5 if show_dot_high else 5)

        draw.text((time_x, y), time_text, font=clock_font, fill=cfg.text_color)
        draw.text((dot_x, dot_y), dot, font=dot_font, fill=cfg.secondary_text_color)
        draw.text((ampm_x, y), ampm_text, font=ampm_font, fill=cfg.text_color)

    def _draw_density(
        self,
        draw: ImageDraw.ImageDraw,
        events: Sequence[CalendarEvent],
        day_start: int,
        day_end: int,
    ) -> None:
        cfg = self.config
        buckets, max_bucket = compute_density_buckets(
            events, day_start=day_start, day_end=day_end, bucket_minutes=10
        )
        chart_height = 24
        base_y = cfg.canvas_height - chart_height - 12
        axis_x = cfg.hour_column_width + cfg.column_gap + cfg.axis_inset
        chart_width = len(buckets)
        if chart_width <= 1:
            return

        draw.line(
            (axis_x, base_y + chart_height, axis_x + chart_width - 1, base_y + chart_height),
            fill=cfg.density_axis_color,
            width=1,
        )
        points: List[tuple[int, int]] = []
        for i, value in enumerate(buckets):
            norm = value / max_bucket if max_bucket else 0
            y = base_y + chart_height - int(round(norm * (chart_height - 4)))
            points.append((axis_x + i, y))

        if len(points) >= 2:
            draw.line(points, fill=cfg.density_color, width=1)


def _format_minutes(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    display = h % 12 or 12
    suffix = "PM" if h >= 12 else "AM"
    return f"{display}:{m:02d} {suffix}"
