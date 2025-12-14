#!/usr/bin/env python3
"""Generate sample calendar previews (HTML or PNG) using the Node-based renderer."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eink_display.rendering import NodeRenderClient, NodeRenderServer


PREVIEWS_DIR = Path(__file__).resolve().parents[1] / "previews"
DEFAULT_HTML_OUTPUT = PREVIEWS_DIR / "tufte_day_sample.html"
DEFAULT_PNG_OUTPUT = PREVIEWS_DIR / "tufte_day_sample.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Where to write the preview file (defaults to previews/tufte_day_sample.<ext>).",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Server path to capture (defaults to '/' for HTML and '/png' for PNG captures).",
    )
    parser.add_argument(
        "--format",
        choices=("html", "png"),
        default="png",
        help="Capture format. PNG hits the /png endpoint and writes a bitmap.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    format_choice: str = args.format
    output_path = args.output or (
        DEFAULT_PNG_OUTPUT if format_choice == "png" else DEFAULT_HTML_OUTPUT
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    path = args.path
    if path is None:
        path = "/png" if format_choice == "png" else "/"

    with NodeRenderServer() as server:
        if server.base_url is None:
            raise RuntimeError("Render server failed to report a base URL")
        client = NodeRenderClient(server.base_url)
        if format_choice == "png":
            image = client.fetch_png(path=path)
            image.save(output_path)
        else:
            client.fetch_html(path=path, output_path=output_path)

    print(f"Wrote preview to {output_path}")


if __name__ == "__main__":
    main()
