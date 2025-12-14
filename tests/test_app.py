from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PIL import Image

from eink_display import app


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def fetch_png(self, *, now=None, **_: Any):
        self.calls += 1
        return Image.new("L", (800, 480), 255)


class FakeScheduler:
    def __init__(self, callback: Callable[[], None], runs: list[dict[str, Any]]):
        self.callback = callback
        self.runs = runs

    def run(self, *, immediate: bool = False, iterations=None):
        self.runs.append({"immediate": immediate, "iterations": iterations})
        if immediate:
            self.callback()


def test_once_flag_triggers_single_refresh(monkeypatch):
    scheduler_runs: list[dict[str, Any]] = []
    fake_client = FakeClient()

    def scheduler_factory(callback: Callable[[], None]):
        return FakeScheduler(callback, scheduler_runs)

    def client_factory(base_url: str, *, timeout: float):
        assert base_url == app.DEFAULT_NODE_URL
        assert timeout == 30.0
        return fake_client

    app.main(
        ["--once", "--display-driver", "mock"],
        scheduler_factory=scheduler_factory,
        node_client_factory=client_factory,
    )

    assert scheduler_runs == [{"immediate": True, "iterations": 1}]
    assert fake_client.calls == 1


def test_immediate_flag_runs_before_loop():
    scheduler_runs: list[dict[str, Any]] = []
    fake_client = FakeClient()

    def scheduler_factory(callback: Callable[[], None]):
        return FakeScheduler(callback, scheduler_runs)

    def client_factory(base_url: str, *, timeout: float):
        return fake_client

    app.main(
        ["--immediate", "--display-driver", "mock"],
        scheduler_factory=scheduler_factory,
        node_client_factory=client_factory,
    )

    assert scheduler_runs == [{"immediate": True, "iterations": None}]
    assert fake_client.calls == 1


def test_start_node_server_flag_launches_server():
    scheduler_runs: list[dict[str, Any]] = []
    fake_client = FakeClient()
    started = {"start": 0, "stop": 0}

    class FakeServer:
        def __init__(self, *, wait_timeout: float):
            self.wait_timeout = wait_timeout
            self.base_url = "http://127.0.0.1:4567"
            started["init"] = wait_timeout

        def start(self):
            started["start"] += 1

        def stop(self):
            started["stop"] += 1

    def scheduler_factory(callback: Callable[[], None]):
        return FakeScheduler(callback, scheduler_runs)

    def client_factory(base_url: str, *, timeout: float):
        assert base_url == "http://127.0.0.1:4567"
        return fake_client

    app.main(
        ["--once", "--display-driver", "mock", "--start-node-server"],
        scheduler_factory=scheduler_factory,
        node_client_factory=client_factory,
        node_server_factory=lambda **kwargs: FakeServer(**kwargs),
    )

    assert started["start"] == 1
    assert started["stop"] == 1
    assert scheduler_runs == [{"immediate": True, "iterations": 1}]
    assert fake_client.calls == 1
    assert started["init"] == 30.0
