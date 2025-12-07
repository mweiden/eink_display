from __future__ import annotations

from typing import Callable

from eink_display import app


def test_once_flag_triggers_immediate(monkeypatch):
    calls = {
        "immediate": None,
        "iterations": None,
        "callback_invocations": 0,
    }

    class FakeScheduler:
        def __init__(self, callback: Callable[[], None]) -> None:
            self.callback = callback

        def run(self, *, immediate: bool = False, iterations=None):
            calls["immediate"] = immediate
            calls["iterations"] = iterations
            if immediate:
                self.callback()
                calls["callback_invocations"] += 1

    def factory(callback: Callable[[], None]):
        return FakeScheduler(callback)

    app.main(["--once"], scheduler_factory=factory)

    assert calls == {
        "immediate": True,
        "iterations": 1,
        "callback_invocations": 1,
    }


def test_immediate_flag_runs_before_loop(monkeypatch):
    calls = []

    class FakeScheduler:
        def __init__(self, callback: Callable[[], None]) -> None:
            self.callback = callback

        def run(self, *, immediate: bool = False, iterations=None):
            calls.append({"immediate": immediate, "iterations": iterations})

    def factory(callback: Callable[[], None]):
        return FakeScheduler(callback)

    app.main(["--immediate"], scheduler_factory=factory)

    assert calls == [{"immediate": True, "iterations": None}]
