# lea_api — HTTP + streaming API over the Lea agent

The API is the third consumer of the agent core (after the CLI and eval): it
serializes the same `lea/events.py` contract over the network. Nothing in `lea/`
changes. Spec: [`../lea-api-design.md`](../lea-api-design.md). Build plan:
[`../IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md).

## Install & run

```bash
uv sync --extra api          # or: pip install -e ".[api]"
lea-api                      # or: python -m lea_api
# serves on 0.0.0.0:8000 by default
```

Model-provider keys (`GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, …) are read from the
server environment exactly as the CLI reads them; they are never accepted over
the API.

## Configuration (env, `LEA_API_*`)

| Var | Default | Meaning |
| --- | --- | --- |
| `LEA_API_HOST` / `LEA_API_PORT` | `0.0.0.0` / `8000` | bind address |
| `LEA_API_MAX_CONCURRENT_RUNS` | `4` | worker pool size; extra runs queue |
| `LEA_API_KEYS` | *(empty)* | comma-separated bearer keys. Empty ⇒ **auth disabled** |
| `LEA_API_VERIFY_TIMEOUT` | `900` | `/verify` compile timeout (s) |
| `LEA_API_SSE_HEARTBEAT_S` | `15` | SSE keep-alive interval |

## v1 endpoints

| Method & path | Purpose |
| --- | --- |
| `POST /v1/runs` | start a run (`202` + `run_id`); config validated synchronously first |
| `GET  /v1/runs/{id}/events` | SSE event stream; `Last-Event-ID` / `?from_seq=` replay |
| `GET  /v1/runs/{id}` | run status + result |
| `GET  /v1/runs/{id}/transcript` | clean transcript (once finished) |
| `POST /v1/runs/{id}/cancel` | cooperative cancel (closes the generator → MCP teardown) |
| `GET  /v1/runs` | list/filter runs |
| `POST /v1/config/validate` | validate a config payload; no run, no disk |
| `GET  /v1/config/default` | the shipped `default.yaml` |
| `GET  /v1/tools`, `/v1/tools/{name}` | registered tool schemas |
| `POST /v1/verify` | single-file compile + `#print axioms` |
| `GET  /v1/healthz`, `/v1/version`, `/v1/capabilities` | meta |

Interactive docs at `/docs` (FastAPI/OpenAPI).

## Architecture (one paragraph)

`agent.run_events` is a **synchronous generator**. `jobs.RunManager` runs each
job on a worker thread, stamps every event with a monotonic `seq`, appends it to
a per-run buffer, and fans it out to live SSE subscribers. SSE handlers replay
the buffer from a requested `seq` then tail live frames, so a dropped connection
resumes exactly where it left off. Cancel sets a flag; the worker closes the
generator at the next event boundary, reusing `run_events`' own `finally` for
clean MCP teardown. `wire.py` is the single mapping from event dataclasses to the
versioned JSON frames (the `Finished` frame links the transcript rather than
inlining it). Run state is in-memory in v1.

## Tests

```bash
pytest tests/api/
```

The whole bridge — replay, multi-subscriber fan-out, `Last-Event-ID` resume,
cancel/teardown — is tested against a **fake runner** (scripted events), so the
suite needs no API keys and no Lean toolchain. The single `/verify` happy-path
test is skipped automatically when `lean`/`lake` is absent.
