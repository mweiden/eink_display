"""Bindings for the Node-based Tufte day-view renderer."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Mapping

from PIL import Image

RENDERER_DIR = Path(__file__).resolve().parent / "node_renderer"
SERVER_SCRIPT = RENDERER_DIR / "render_server.js"
DEFAULT_NODE_EXECUTABLE = os.environ.get("NODE", "node")
DEFAULT_RENDER_WIDTH = 800
DEFAULT_RENDER_HEIGHT = 480


def _format_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat()
    return value.astimezone().isoformat()


class NodeRenderClient:
    """HTTP client for talking to the Node rendering service."""

    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def health(self) -> bool:
        try:
            with urllib.request.urlopen(
                f"{self.base_url}/health", timeout=self.timeout
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return bool(payload.get("ok"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            return False

    def _build_url(
        self,
        path: str,
        extra_params: Mapping[str, str | None] | None = None,
    ) -> str:
        clean_path, _, raw_query = path.partition("?")
        if not clean_path.startswith("/"):
            clean_path = f"/{clean_path}"

        params: dict[str, str] = dict(
            urllib.parse.parse_qsl(raw_query, keep_blank_values=True)
        )
        if extra_params:
            for key, value in extra_params.items():
                if value is None:
                    continue
                params[key] = value

        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}{clean_path}"
        if query:
            url = f"{url}?{query}"
        return url

    def fetch_html(
        self,
        *,
        output_path: Path | None = None,
        path: str = "/",
        now: datetime | None = None,
    ) -> str:
        """Fetch the rendered HTML document from the server."""

        params = {"now": _format_datetime(now)}
        url = self._build_url(path, params)
        with urllib.request.urlopen(url, timeout=self.timeout) as response:
            html_text = response.read().decode("utf-8")

        if output_path:
            Path(output_path).write_text(html_text, encoding="utf-8")

        return html_text

    def fetch_png(
        self,
        *,
        path: str = "/png",
        now: datetime | None = None,
        width: int | None = None,
        height: int | None = None,
        dpr: float | None = None,
    ) -> Image.Image:
        """Fetch a PNG capture of the rendered calendar."""

        width_value = int(width) if width is not None else None
        height_value = int(height) if height is not None else None

        params: dict[str, str | None] = {
            "now": _format_datetime(now),
            "width": str(width_value) if width_value is not None else None,
            "height": str(height_value) if height_value is not None else None,
            "dpr": str(dpr) if dpr is not None else None,
        }

        url = self._build_url(path, params)
        with urllib.request.urlopen(url, timeout=self.timeout) as response:
            payload = response.read()

        buffer = BytesIO(payload)
        with Image.open(buffer) as image:
            target_size = (
                width_value or DEFAULT_RENDER_WIDTH,
                height_value or DEFAULT_RENDER_HEIGHT,
            )
            processed = image
            if processed.size != target_size:
                processed = processed.resize(
                    target_size,
                    Image.Resampling.LANCZOS,
                )
            return processed.convert("L")


class NodeRenderServer:
    """Lifecycle manager for the Node rendering HTTP service."""

    def __init__(
        self,
        *,
        script: Path | None = None,
        project_dir: Path | None = None,
        node_executable: str = DEFAULT_NODE_EXECUTABLE,
        port: int | None = None,
        env: dict[str, str] | None = None,
        wait_timeout: float = 30.0,
    ) -> None:
        self.script = script or SERVER_SCRIPT
        self.project_dir = project_dir or RENDERER_DIR
        self.node_executable = node_executable
        self.port = port
        self.env = env or os.environ.copy()
        self.wait_timeout = wait_timeout
        self._process: subprocess.Popen[bytes] | None = None
        self.base_url: str | None = None

    def __enter__(self) -> "NodeRenderServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()

    def start(self) -> None:
        if self._process is not None:
            raise RuntimeError("Render server already running")
        if not self.script.exists():
            raise FileNotFoundError(self.script)
        ensure_node_dependencies(self.project_dir)

        port = self.port or _find_open_port()
        env = self.env.copy()
        env["PORT"] = str(port)
        if "PUPPETEER_SKIP_DOWNLOAD" not in env and sys.platform.startswith("linux"):
            env["PUPPETEER_SKIP_DOWNLOAD"] = "1"

        command = [self.node_executable, str(self.script)]
        self._process = subprocess.Popen(
            command,
            cwd=str(self.project_dir),
            env=env,
        )
        self.port = port
        self.base_url = f"http://127.0.0.1:{port}"

        client = NodeRenderClient(self.base_url, timeout=self.wait_timeout)
        deadline = time.monotonic() + self.wait_timeout
        while time.monotonic() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError("Render server terminated during startup")
            if client.health():
                return
            time.sleep(0.2)

        raise TimeoutError("Timed out waiting for render server readiness")

    def stop(self) -> None:
        if self._process is None:
            return
        self._process.terminate()
        try:
            self._process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=5)
        finally:
            self._process = None


def ensure_node_dependencies(project_dir: Path | None = None) -> None:
    project_dir = project_dir or RENDERER_DIR
    package_lock = project_dir / "package-lock.json"
    node_modules = project_dir / "node_modules"
    dist_bundle = project_dir / "dist" / "TufteDayCalendar.cjs"

    npm = os.environ.get("NPM", "npm")
    if shutil.which(npm) is None:
        raise RuntimeError("npm executable not found in PATH")

    env = os.environ.copy()
    env.setdefault("PUPPETEER_SKIP_DOWNLOAD", "1")

    if not node_modules.exists():
        if not package_lock.exists():
            raise FileNotFoundError("package-lock.json not found; cannot install dependencies")

        subprocess.run([npm, "install"], cwd=str(project_dir), check=True, env=env)

    if not dist_bundle.exists():
        subprocess.run([npm, "run", "build"], cwd=str(project_dir), check=True, env=env)


def _find_open_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
