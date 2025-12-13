#!/usr/bin/env python3
"""Generate a sample calendar preview using the Node-based renderer."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eink_display.rendering import NodeRenderClient, NodeRenderServer


DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "previews" / "tufte_day_sample.png"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Where to write the preview PNG (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--path",
        type=str,
        default="/",
        help="Server path to capture (default: root, which renders live calendar/sample events)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path: Path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with NodeRenderServer() as server:
        if server.base_url is None:
            raise RuntimeError("Render server failed to report a base URL")
        client = NodeRenderClient(server.base_url)
        client.fetch_image(path=args.path, output_path=output_path)

    print(f"Wrote preview to {output_path}")


if __name__ == "__main__":
    main()
