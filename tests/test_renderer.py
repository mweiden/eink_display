from __future__ import annotations

from datetime import datetime, time

from eink_display.rendering import DayRenderer, LayoutMetrics, RendererConfig


def test_layout_metrics_basic_properties() -> None:
    layout = LayoutMetrics()
    assert layout.canvas_width == 480
    assert layout.canvas_height == 800
    assert layout.timeline_top == layout.header_height
    assert layout.timeline_bottom == layout.canvas_height - layout.footer_height
    assert layout.card_right - layout.card_left == layout.card_width

    start_y = layout.y_for_time(time(hour=layout.start_hour))
    end_y = layout.y_for_time(time(hour=layout.end_hour))
    assert start_y == layout.timeline_top
    assert end_y == layout.timeline_bottom


def test_text_wrapping_truncates_lines() -> None:
    renderer = DayRenderer()
    font = renderer.config.font(renderer.config.card_title_font_size, bold=True)
    bbox = font.getbbox("MMMM")
    max_width = bbox[2] - bbox[0]

    lines = renderer._wrap_text(
        "This is an intentionally verbose meeting title to test wrapping",
        font,
        max_width=max_width,
        max_lines=2,
    )
    assert len(lines) == 2
    assert lines[-1].endswith("…")


def test_preview_mode_writes_png(tmp_path) -> None:
    config = RendererConfig(preview_output_dir=tmp_path)
    renderer = DayRenderer(config)
    now = datetime(2024, 1, 1, 9, 30)

    image = renderer.render_day([], now, preview_name="preview")

    assert image.size == (config.layout.canvas_width, config.layout.canvas_height)
    assert (tmp_path / "preview.png").exists()
