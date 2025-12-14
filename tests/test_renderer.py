from __future__ import annotations

from pathlib import Path

import pytest

from eink_display.rendering import (
    NodeRenderClient,
    NodeRenderServer,
    ensure_node_dependencies,
)
@pytest.fixture(scope="session")
def node_dependencies() -> None:
    ensure_node_dependencies()


@pytest.fixture(scope="session")
def running_server(node_dependencies: None):
    with NodeRenderServer(wait_timeout=60.0) as server:
        assert server.base_url is not None
        yield server


def test_root_request_returns_html(tmp_path: Path, running_server: NodeRenderServer) -> None:
    client = NodeRenderClient(running_server.base_url)  # type: ignore[arg-type]

    output_file = tmp_path / "root.html"
    html_text = client.fetch_html(output_path=output_file)

    assert output_file.exists()
    assert output_file.read_text(encoding="utf-8") == html_text
    assert "<!doctype html>" in html_text.lower()


def test_png_endpoint_returns_image(running_server: NodeRenderServer) -> None:
    client = NodeRenderClient(running_server.base_url)  # type: ignore[arg-type]

    image = client.fetch_png()

    assert image.size == (800, 480)
    assert image.mode == "L"
