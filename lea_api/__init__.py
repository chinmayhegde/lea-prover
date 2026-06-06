"""Lea API — an HTTP + streaming service over the config-driven, event-out agent.

The API is the *third consumer* of the agent core (after the CLI and eval): it
serializes the same `events.py` contract over the network. Nothing in `lea/`
changes; this package wraps it.

See ``lea-api-design.md`` for the spec and ``IMPLEMENTATION_PLAN.md`` for the
build plan this implements (v1).
"""

from .app import create_app

__all__ = ["create_app"]

SCHEMA_VERSION = "1"
"""Version of the event wire format (see wire.py). Additive changes only within
a version; a breaking change bumps this."""
