"""Shared fixtures + scripted fake runners for the API tests.

The fake runners let us drive the whole run bridge — replay, fan-out,
reconnect, cancel — with zero model spend and no Lean toolchain. A runner just
needs the ``run_events(config, task, *, resume)`` shape and to yield
``lea.events`` events.
"""

import time

import pytest
from fastapi.testclient import TestClient

from lea.events import (
    AssistantTextDelta,
    Finished,
    ToolCalled,
    ToolResulted,
    TurnStarted,
    UsageUpdated,
)
from lea.providers import Usage

from lea_api import config_support
from lea_api.app import create_app
from lea_api.jobs import RunManager
from lea_api.settings import Settings


def default_config():
    return config_support.resolve(None)


def make_finished(transcript=None):
    return Finished(
        reason="completed", text="Proof complete.", turns=2,
        session_id="sess-1", model="gemini/gemini-3.1-pro-preview",
        usage=Usage(100, 20), cost=0.01,
        transcript=transcript or {"session_id": "sess-1", "model": "gemini/x",
                                  "turns": 2, "usage": {"input_tokens": 100, "output_tokens": 20},
                                  "messages": [{"role": "user", "content": "prove"}]},
    )


def sample_events():
    return [
        TurnStarted(1),
        AssistantTextDelta("We proceed by induction"),
        ToolCalled("lean_check", {"path": "Proof.lean"}),
        UsageUpdated(100, 20, 0.01),
        ToolResulted("lean_check", "no goals", "no goals"),
        make_finished(),
    ]


def scripted_runner(events):
    def runner(config, task, *, resume=False):
        for ev in events:
            yield ev
    return runner


def looping_runner():
    """Yields forever until the generator is closed — for cancel tests."""
    def runner(config, task, *, resume=False):
        i = 0
        try:
            while True:
                i += 1
                yield TurnStarted(i)
                yield AssistantTextDelta(f"chunk {i}")
                time.sleep(0.01)
        except GeneratorExit:
            return
    return runner


def wait_done(state, timeout=5.0):
    end = time.time() + timeout
    while time.time() < end:
        if state.done:
            return
        time.sleep(0.005)
    raise AssertionError(f"run {state.run_id} did not finish in {timeout}s (status={state.status})")


@pytest.fixture
def build_app():
    """Returns a builder: (runner, settings?) -> (app, manager)."""
    def _build(runner, settings=None):
        s = settings or Settings(api_keys="")
        mgr = RunManager(runner=runner, max_concurrent_runs=2)
        return create_app(settings=s, manager=mgr), mgr
    return _build


@pytest.fixture
def client(build_app):
    """Sync TestClient over an app with an empty scripted runner (lifespan runs)."""
    app, _ = build_app(scripted_runner([]))
    with TestClient(app) as c:
        yield c
