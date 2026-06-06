"""API settings — environment-driven configuration for the service.

All knobs are read from ``LEA_API_*`` environment variables. Defaults are
chosen so the service runs out of the box for local development (auth off,
modest concurrency).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LEA_API_", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8000

    # Worker pool size = max concurrently *running* jobs. Extra runs stay queued.
    max_concurrent_runs: int = 4

    # Comma-separated bearer keys. Empty string => auth disabled (local dev).
    api_keys: str = ""

    # Where per-run scratch dirs live (proof artifacts, v2).
    runs_dir: Path = Path.home() / ".lea" / "runs"

    # Verify (single-file compile) timeout, seconds.
    verify_timeout: int = 900

    # SSE heartbeat interval, seconds (keeps proxies from idling the connection).
    sse_heartbeat_s: float = 15.0

    @property
    def auth_enabled(self) -> bool:
        return bool(self.api_keys.strip())

    @property
    def key_set(self) -> set[str]:
        return {k.strip() for k in self.api_keys.split(",") if k.strip()}


def get_settings() -> Settings:
    return Settings()
