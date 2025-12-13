from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

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


def test_root_request_uses_live_endpoint(tmp_path: Path, running_server: NodeRenderServer) -> None:
    client = NodeRenderClient(running_server.base_url)  # type: ignore[arg-type]

    output_file = tmp_path / "root.png"
    image_bytes = client.fetch_image(output_path=output_file)

    assert output_file.exists()
    assert len(image_bytes) == output_file.stat().st_size

    with Image.open(output_file) as img:
        assert img.size == (800 * 2, 480 * 2)
        assert img.mode in {"RGBA", "RGB"}
