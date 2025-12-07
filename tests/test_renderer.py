from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from eink_display.rendering import (
    CalendarEvent,
    NodeRenderClient,
    NodeRenderServer,
    ensure_node_dependencies,
)


def make_event(start_hour: int, start_minute: int, end_hour: int, end_minute: int) -> CalendarEvent:
    base = datetime(2024, 1, 1)
    return CalendarEvent(
        title="Event",
        start=base.replace(hour=start_hour, minute=start_minute),
        end=base.replace(hour=end_hour, minute=end_minute),
        location="Location",
    )


def test_calendar_event_serialization() -> None:
    event = make_event(9, 15, 10, 0)

    payload = event.to_payload()

    assert payload["start"] == 9 * 60 + 15
    assert payload["end"] == 10 * 60
    assert payload["where"] == "Location"


@pytest.fixture(scope="session")
def node_dependencies() -> None:
    ensure_node_dependencies()


@pytest.fixture(scope="session")
def running_server(node_dependencies: None):
    with NodeRenderServer(wait_timeout=60.0) as server:
        assert server.base_url is not None
        yield server


def test_render_request_writes_png(tmp_path: Path, running_server: NodeRenderServer) -> None:
    client = NodeRenderClient(running_server.base_url)  # type: ignore[arg-type]
    assert client.health()

    event = make_event(9, 0, 9, 45)
    output_file = tmp_path / "calendar.png"

    image_bytes = client.render([event], output_path=output_file)

    assert output_file.exists()
    assert len(image_bytes) == output_file.stat().st_size

    with Image.open(output_file) as img:
        assert img.size == (800 * 2, 480 * 2)
        assert img.mode in {"RGBA", "RGB"}
