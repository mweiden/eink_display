from __future__ import annotations

from datetime import datetime

from eink_display.rendering import (
    CalendarEvent,
    RendererConfig,
    TufteDayRenderer,
    assign_label_columns_top,
    assign_overlap_columns,
    compute_density_buckets,
)


def _event(start_hour: int, start_minute: int, end_hour: int, end_minute: int) -> CalendarEvent:
    base = datetime(2024, 1, 1)
    return CalendarEvent(
        title="Event",
        start=base.replace(hour=start_hour, minute=start_minute),
        end=base.replace(hour=end_hour, minute=end_minute),
    )


def test_assign_overlap_columns_handles_overlapping_events() -> None:
    events = [
        _event(9, 0, 10, 0),
        _event(9, 30, 10, 30),
        _event(11, 0, 12, 0),
    ]

    columns = assign_overlap_columns(events)

    assert columns[0] == 0
    assert columns[1] == 1
    assert columns[2] == 0


def test_assign_label_columns_top_clusters_overlapping_labels() -> None:
    desired = [(0, 0), (1, 5), (2, 40)]

    result = assign_label_columns_top(desired_tops=desired, box_height=20, min_gap=4)

    assert result[0] == 1
    assert result[1] == 0
    assert result[2] == 0


def test_compute_density_buckets_counts_overlap_minutes() -> None:
    events = [
        _event(9, 0, 10, 0),
        _event(9, 30, 10, 0),
    ]

    buckets, max_bucket = compute_density_buckets(events, day_start=9 * 60, day_end=11 * 60, bucket_minutes=30)

    assert buckets == [30, 60, 0, 0]
    assert max_bucket == 60


def test_render_preview_writes_png(tmp_path) -> None:
    config = RendererConfig(preview_output_dir=tmp_path)
    renderer = TufteDayRenderer(config)
    event = _event(9, 0, 9, 45)

    image = renderer.render_day([event], now=event.start, preview_name="sample")

    assert image.size == (config.canvas_width, config.canvas_height)
    assert (tmp_path / "sample.png").exists()
