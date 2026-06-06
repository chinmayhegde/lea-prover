"""The run bridge — sync generator -> async, replayable, multi-subscriber stream.

``agent.run_events`` is a *synchronous* generator that blocks on model calls and
owns its MCP servers in a ``try/finally``. The API needs an async job clients
start and then subscribe to over SSE, with seq-numbered frames that replay on
reconnect. This module is that bridge:

  * Each run executes on a worker thread (a bounded pool caps concurrency).
  * Every event is stamped with a monotonic ``seq`` and appended to a per-run
    buffer, then pushed to any live subscriber queues.
  * SSE handlers replay the buffer from a requested seq, then tail live frames.
  * Cancel sets a flag; the worker stops at the next event boundary and closes
    the generator, so ``run_events``' own ``finally`` tears down MCP cleanly.

State is in-memory (v1): in-flight runs are lost on restart. Sessions persist
to disk via the agent independently.
"""

from __future__ import annotations

import asyncio
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

from lea.config import LeaConfig
from lea.errors import LeaError
from lea.events import Finished, SessionResumed, TurnStarted, UsageUpdated

from . import errors as api_errors
from . import wire


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class RunState:
    run_id: str
    config: LeaConfig
    task: str
    resume: str | bool
    status: str = "queued"               # queued|running|completed|failed|cancelled
    events: list[dict] = field(default_factory=list)   # seq-stamped frames
    result: dict | None = None
    transcript: dict | None = None
    error: dict | None = None
    created_at: str = field(default_factory=_now)
    finished_at: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    done: bool = False
    _next_seq: int = 0
    _subscribers: set = field(default_factory=set)     # set[asyncio.Queue]
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def model(self) -> str:
        return self.config.model_name

    def public(self) -> dict:
        """The body for GET /v1/runs/{id}."""
        return {
            "run_id": self.run_id,
            "status": self.status,
            "model": self.model,
            "result": self.result,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


class RunManager:
    """Owns the worker pool, the run registry, and the event fan-out.

    ``runner`` is injectable so tests can drive the bridge with a scripted
    generator instead of a real (paid) agent run. It must match
    ``run_events(config, task, *, resume)`` and yield ``lea.events`` events.
    """

    def __init__(self, runner=None, max_concurrent_runs: int = 4):
        if runner is None:
            from lea.agent import run_events as runner  # lazy: avoids importing litellm at module load
        self._runner = runner
        self._runs: dict[str, RunState] = {}
        self._pool = ThreadPoolExecutor(max_workers=max_concurrent_runs, thread_name_prefix="lea-run")
        self._loop: asyncio.AbstractEventLoop | None = None
        self._registry_lock = threading.Lock()

    # ---- loop wiring --------------------------------------------------------

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the app event loop so worker threads can hand frames to it."""
        self._loop = loop

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    # ---- run lifecycle ------------------------------------------------------

    def start(self, config: LeaConfig, task: str, resume: str | bool = False) -> RunState:
        run_id = "run_" + secrets.token_hex(8)
        state = RunState(run_id=run_id, config=config, task=task, resume=resume)
        with self._registry_lock:
            self._runs[run_id] = state
        self._pool.submit(self._work, state)
        return state

    def get(self, run_id: str) -> RunState | None:
        with self._registry_lock:
            return self._runs.get(run_id)

    def list(self) -> list[RunState]:
        with self._registry_lock:
            return list(self._runs.values())

    def cancel(self, state: RunState) -> None:
        state.cancel_event.set()

    # ---- the worker ---------------------------------------------------------

    def _work(self, state: RunState) -> None:
        state.status = "running"
        gen = self._runner(state.config, state.task, resume=state.resume)

        # Running totals, so a synthesized cancel/error terminal frame can carry
        # the usage seen so far (mirrors what the agent accumulates internally).
        turns = 0
        usage = {"input_tokens": 0, "output_tokens": 0}
        cost = 0.0
        session_id: str | None = None
        cancelled = False

        try:
            for ev in gen:
                if isinstance(ev, TurnStarted):
                    turns = ev.turn
                elif isinstance(ev, UsageUpdated):
                    usage["input_tokens"] += ev.input_tokens
                    usage["output_tokens"] += ev.output_tokens
                    cost += ev.cost
                elif isinstance(ev, SessionResumed):
                    session_id = ev.session_id

                if isinstance(ev, Finished):
                    state.transcript = ev.transcript
                    state.result = {
                        "reason": ev.reason, "text": ev.text, "turns": ev.turns,
                        "usage": {"input_tokens": ev.usage.input_tokens,
                                  "output_tokens": ev.usage.output_tokens},
                        "cost": ev.cost,
                    }
                    self._publish(state, wire.to_frame(ev, state.run_id))
                    state.status = "completed"
                    break

                self._publish(state, wire.to_frame(ev, state.run_id))

                if state.cancel_event.is_set():
                    cancelled = True
                    break
        except LeaError as e:
            state.error = api_errors.to_body(e)
            self._publish(state, wire.error_frame(state.error["type"], state.error["message"],
                                                  state.error.get("field")))
            state.status = "failed"
        except Exception as e:  # noqa: BLE001 — surface as a terminal error frame
            state.error = {"type": "InternalError", "message": f"{type(e).__name__}: {e}"}
            self._publish(state, wire.error_frame("InternalError", state.error["message"]))
            state.status = "failed"
        finally:
            gen.close()  # idempotent if already exhausted; runs run_events' finally (MCP teardown)
            if cancelled:
                state.status = "cancelled"
                state.result = {"reason": "cancelled", "text": "Run cancelled.",
                                "turns": turns, "usage": usage, "cost": cost}
                self._publish(state, wire.cancelled_frame(state.run_id, state.model,
                                                          session_id, turns, usage, cost))
            state.finished_at = _now()
            self._finalize(state)

    # ---- fan-out ------------------------------------------------------------

    def _publish(self, state: RunState, frame: dict) -> None:
        """Stamp seq, append to the buffer, and notify live subscribers."""
        with state._lock:
            stamped = wire.stamp(frame, state._next_seq)
            state._next_seq += 1
            state.events.append(stamped)
            subs = list(state._subscribers)
        for q in subs:
            self._enqueue(q, stamped)

    def _finalize(self, state: RunState) -> None:
        """Mark done and wake every subscriber so its stream loop can end."""
        with state._lock:
            state.done = True
            subs = list(state._subscribers)
        for q in subs:
            self._enqueue(q, None)  # sentinel

    def _enqueue(self, q, item) -> None:
        if self._loop is None:
            return  # no event loop bound (e.g. unit test without HTTP); buffer is still authoritative
        self._loop.call_soon_threadsafe(q.put_nowait, item)

    def subscribe(self, state: RunState, start_seq: int):
        """Register a live subscriber and return (queue, backlog).

        Done atomically under the run lock so no frame is both in the backlog
        and the queue: anything appended before registration is in the backlog;
        anything after is delivered via the queue.
        """
        q: asyncio.Queue = asyncio.Queue()
        with state._lock:
            backlog = [f for f in state.events if f["seq"] >= start_seq]
            already_done = state.done
            state._subscribers.add(q)
        if already_done:
            # Run already terminal: nothing more will be published; signal end.
            q.put_nowait(None)
        return q, backlog

    def unsubscribe(self, state: RunState, q) -> None:
        with state._lock:
            state._subscribers.discard(q)
