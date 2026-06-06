"""Config resolution shared by /v1/runs and /v1/config.

Reuses the agent's own loader pieces: ``default.yaml`` as the base, an optional
overlay merged section-by-section (``config._merge``), then the I/O-free
``validate_config``. Raising a ``ConfigError`` here is the "validate before you
spend" path — it happens before any run is created.
"""

from __future__ import annotations

import yaml

from lea.config import DEFAULT_CONFIG_PATH, _merge
from lea.validation import LeaConfig, validate_config


def default_raw() -> dict:
    """The shipped default.yaml as a plain mapping (base template)."""
    return yaml.safe_load(DEFAULT_CONFIG_PATH.read_text()) or {}


def resolve(overlay: dict | None) -> LeaConfig:
    """default.yaml + optional overlay -> validated LeaConfig (raises ConfigError)."""
    base = default_raw()
    raw = _merge(base, overlay) if overlay else base
    return validate_config(raw)


def to_public(cfg: LeaConfig) -> dict:
    """Flatten a LeaConfig to the response body shape (design §4.3)."""
    return {
        "model_name": cfg.model_name,
        "model_kwargs": cfg.model_kwargs,
        "stream": cfg.stream,
        "prompt_variant": cfg.prompt_variant,
        "max_turns": cfg.max_turns,
        "tools": cfg.tools,
        "tool_modules": cfg.tool_modules,
        "skills": cfg.skills,
        "narrate_tool_steps": cfg.narrate_tool_steps,
        "mcp_servers": cfg.mcp_servers,
    }
