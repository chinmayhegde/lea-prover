"""The run bridge — driven directly (no HTTP) for deterministic core coverage."""

import time

from lea_api.jobs import RunManager

from .conftest import default_config, looping_runner, sample_events, scripted_runner, wait_done


def test_run_completes_with_monotonic_seqs():
    mgr = RunManager(runner=scripted_runner(sample_events()))
    try:
        state = mgr.start(default_config(), "prove something")
        wait_done(state)

        assert state.status == "completed"
        seqs = [f["seq"] for f in state.events]
        assert seqs == list(range(len(seqs)))           # 0..N, monotonic, no gaps
        assert all(f["schema_version"] == "1" for f in state.events)

        terminal = state.events[-1]
        assert terminal["type"] == "finished"
        assert terminal["reason"] == "completed"
        assert terminal["transcript_url"] == f"/v1/runs/{state.run_id}/transcript"
        assert "transcript" not in terminal             # linked, not inlined

        assert state.transcript is not None             # captured for GET /transcript
        assert state.result["reason"] == "completed"
        assert state.result["usage"] == {"input_tokens": 100, "output_tokens": 20}
    finally:
        mgr.shutdown()


def test_exactly_one_terminal_frame():
    mgr = RunManager(runner=scripted_runner(sample_events()))
    try:
        state = mgr.start(default_config(), "x")
        wait_done(state)
        terminals = [f for f in state.events if f["type"] in {"finished", "error"}]
        assert len(terminals) == 1
    finally:
        mgr.shutdown()


def test_cancel_synthesizes_terminal_frame():
    mgr = RunManager(runner=looping_runner())
    try:
        state = mgr.start(default_config(), "x")
        # let it produce a few events so it's genuinely mid-run
        deadline = time.time() + 2
        while len(state.events) < 2 and time.time() < deadline:
            time.sleep(0.005)
        mgr.cancel(state)
        wait_done(state)

        assert state.status == "cancelled"
        terminal = state.events[-1]
        assert terminal["type"] == "finished"
        assert terminal["reason"] == "cancelled"
        assert state.result["reason"] == "cancelled"
    finally:
        mgr.shutdown()


def test_failing_runner_emits_error_frame():
    from lea.errors import ToolError

    def boom(config, task, *, resume=False):
        yield from ()  # make it a generator
        raise ToolError("unknown tool 'frobnicate'")

    mgr = RunManager(runner=boom)
    try:
        state = mgr.start(default_config(), "x")
        wait_done(state)
        assert state.status == "failed"
        assert state.events[-1]["type"] == "error"
        assert state.events[-1]["error"]["type"] == "ToolError"
        assert state.error["type"] == "ToolError"
    finally:
        mgr.shutdown()
