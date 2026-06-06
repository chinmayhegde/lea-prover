"""End-to-end run flow over HTTP, including SSE replay and Last-Event-ID resume.

Uses an in-process ASGI transport with a scripted runner, so the full
POST -> stream -> reconnect path is exercised with no model spend.
"""

import asyncio

import httpx
import pytest

from .conftest import sample_events, scripted_runner


def _frames(sse_text: str) -> list[tuple[str, str]]:
    """Parse an SSE body into (id, event) pairs."""
    out = []
    cur = {}
    for line in sse_text.splitlines():
        if line.startswith("id: "):
            cur["id"] = line[4:]
        elif line.startswith("event: "):
            cur["event"] = line[7:]
        elif line == "" and cur:
            out.append((cur.get("id"), cur.get("event")))
            cur = {}
    return out


async def _wait_completed(client, run_id, tries=300):
    for _ in range(tries):
        s = (await client.get(f"/v1/runs/{run_id}")).json()
        if s["status"] in {"completed", "failed", "cancelled"}:
            return s
        await asyncio.sleep(0.01)
    raise AssertionError("run did not complete")


@pytest.mark.asyncio
async def test_post_then_stream_replay(build_app):
    app, mgr = build_app(scripted_runner(sample_events()))
    mgr.bind_loop(asyncio.get_running_loop())
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/v1/runs", json={"task": "prove evens"})
        assert r.status_code == 202
        run_id = r.json()["run_id"]
        assert r.json()["events_url"] == f"/v1/runs/{run_id}/events"

        s = await _wait_completed(client, run_id)
        assert s["status"] == "completed"
        assert s["result"]["reason"] == "completed"

        # Replay the whole buffer over SSE.
        async with client.stream("GET", f"/v1/runs/{run_id}/events") as resp:
            assert resp.status_code == 200
            assert resp.headers["content-type"].startswith("text/event-stream")
            body = ""
            async for chunk in resp.aiter_text():
                body += chunk
                if "event: finished" in body:
                    break

    frames = _frames(body)
    events = [e for _, e in frames]
    assert events[0] == "turn_started"
    assert "tool_called" in events
    assert events[-1] == "finished"
    # ids are the monotonic seqs
    ids = [int(i) for i, _ in frames]
    assert ids == sorted(ids)


@pytest.mark.asyncio
async def test_last_event_id_resumes_after_seq(build_app):
    app, mgr = build_app(scripted_runner(sample_events()))
    mgr.bind_loop(asyncio.get_running_loop())
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        run_id = (await client.post("/v1/runs", json={"task": "x"})).json()["run_id"]
        await _wait_completed(client, run_id)

        # Reconnect as if we'd already seen up to seq 2.
        async with client.stream("GET", f"/v1/runs/{run_id}/events",
                                 headers={"Last-Event-ID": "2"}) as resp:
            body = ""
            async for chunk in resp.aiter_text():
                body += chunk
                if "event: finished" in body:
                    break

    ids = [int(i) for i, _ in _frames(body)]
    assert min(ids) == 3              # resumed strictly after seq 2
    assert ids == sorted(ids)


@pytest.mark.asyncio
async def test_config_ref_not_implemented(build_app):
    app, mgr = build_app(scripted_runner([]))
    mgr.bind_loop(asyncio.get_running_loop())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/v1/runs", json={"task": "x", "config_ref": "saved"})
        assert r.status_code == 501


@pytest.mark.asyncio
async def test_bad_config_returns_422_no_run(build_app):
    app, mgr = build_app(scripted_runner([]))
    mgr.bind_loop(asyncio.get_running_loop())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        r = await client.post("/v1/runs", json={"task": "x", "config": {"model": {"stream": 3}}})
        assert r.status_code == 422
        assert r.json()["error"]["field"] == "model.stream"
        assert (await client.get("/v1/runs")).json()["runs"] == []   # nothing created


@pytest.mark.asyncio
async def test_unknown_run_404(build_app):
    app, mgr = build_app(scripted_runner([]))
    mgr.bind_loop(asyncio.get_running_loop())
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        assert (await client.get("/v1/runs/run_nope")).status_code == 404
        assert (await client.get("/v1/runs/run_nope/transcript")).status_code == 404
