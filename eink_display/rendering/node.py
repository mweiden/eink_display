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
import urllib.request
from pathlib import Path

RENDERER_DIR = Path(__file__).resolve().parent / "node_renderer"
SERVER_SCRIPT = RENDERER_DIR / "render_server.js"
DEFAULT_NODE_EXECUTABLE = os.environ.get("NODE", "node")
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

    def fetch_image(
        self, *, output_path: Path | None = None, path: str = "/"
    ) -> bytes:
        """Fetch a rendered image from the server without supplying payload data.

        The root path (``/``) returns the live Google Calendar rendering. Additional
        paths may be exposed by the Node server for debugging.
        """

        with urllib.request.urlopen(
            f"{self.base_url}{path}", timeout=self.timeout
        ) as response:
            image_bytes = response.read()

        if output_path:
            Path(output_path).write_bytes(image_bytes)

        return image_bytes

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
    if shutil.which(npm) is None:  # type: ignore[name-defined]
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
