"""Run endpoints — start, observe (SSE), inspect, cancel (design §4.1).

The event stream is the primary surface. ``GET /runs/{id}/events`` replays the
seq-numbered buffer from a requested point (``Last-Event-ID`` header or
``?from_seq=``) and then tails live frames, so a dropped connection resumes
exactly where it left off.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..jobs import RunManager, RunState
from ..wire import TERMINAL_TYPES

router = APIRouter(prefix="/runs", tags=["runs"])


class RunRequest(BaseModel):
    task: str
    config: dict | None = None
    config_ref: str | None = None
    resume: bool | str = False


def _manager(request: Request) -> RunManager:
    return request.app.state.manager


def _require_run(request: Request, run_id: str) -> RunState:
    state = _manager(request).get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Unknown run: {run_id}")
    return state


def _sse(frame: dict) -> str:
    return (f"id: {frame['seq']}\n"
            f"event: {frame['type']}\n"
            f"data: {json.dumps(frame)}\n\n")


@router.post("", status_code=202)
def start_run(request: Request, req: RunRequest, response: Response) -> dict:
    if req.config_ref is not None:
        # Stored named configs are a v2 feature (config_ref resolution).
        raise HTTPException(status_code=501, detail="config_ref is not available in v1.")

    from .. import config_support
    cfg = config_support.resolve(req.config)  # ConfigError -> typed 400/422, no run created
    state = _manager(request).start(cfg, req.task, resume=req.resume)
    response.headers["Location"] = f"/v1/runs/{state.run_id}"
    return {"run_id": state.run_id, "status": state.status,
            "events_url": f"/v1/runs/{state.run_id}/events"}


@router.get("")
def list_runs(request: Request, status: str | None = None) -> dict:
    runs = _manager(request).list()
    if status:
        runs = [r for r in runs if r.status == status]
    runs.sort(key=lambda r: r.created_at, reverse=True)
    return {"runs": [r.public() for r in runs]}


@router.get("/{run_id}")
def get_run(request: Request, run_id: str) -> dict:
    return _require_run(request, run_id).public()


@router.get("/{run_id}/transcript")
def get_transcript(request: Request, run_id: str) -> dict:
    state = _require_run(request, run_id)
    if state.transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not available yet.")
    return state.transcript


@router.post("/{run_id}/cancel")
def cancel_run(request: Request, run_id: str) -> dict:
    state = _require_run(request, run_id)
    _manager(request).cancel(state)
    return {"run_id": run_id, "status": state.status}


@router.get("/{run_id}/events")
async def stream_events(
    request: Request,
    run_id: str,
    from_seq: int = Query(default=0, ge=0),
    last_event_id: str | None = Header(default=None),
) -> StreamingResponse:
    state = _require_run(request, run_id)
    manager = _manager(request)

    start_seq = from_seq
    if last_event_id is not None and last_event_id.strip().isdigit():
        start_seq = int(last_event_id) + 1  # resume *after* the last frame we saw

    q, backlog = manager.subscribe(state, start_seq)
    heartbeat = request.app.state.settings.sse_heartbeat_s

    async def gen():
        last = start_seq - 1
        try:
            for frame in backlog:
                if frame["seq"] > last:
                    yield _sse(frame)
                    last = frame["seq"]
                    if frame["type"] in TERMINAL_TYPES:
                        return
            while True:
                if await request.is_disconnected():
                    return
                try:
                    item = await asyncio.wait_for(q.get(), timeout=heartbeat)
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if item is None:  # finalize sentinel
                    return
                if item["seq"] > last:
                    yield _sse(item)
                    last = item["seq"]
                    if item["type"] in TERMINAL_TYPES:
                        return
        finally:
            manager.unsubscribe(state, q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
