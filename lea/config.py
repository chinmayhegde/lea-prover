"""Config loading — the file-I/O layer over the validator.

`configs/default.yaml` (shipped, repo root) is the single source of truth for
default behavior and is always read as the base. A user `--config` file is
overlaid section-by-section on top, so user configs can be partial. The merged
mapping is handed to `validate_config` (in validation.py), which is where all
validation lives.
"""

from pathlib import Path

import yaml

from .errors import ConfigFormatError
from .validation import LeaConfig, validate_config  # re-exported for callers

# Repo-root configs/ dir (sibling of the lea/ package), same pattern as WORKSPACE.
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "default.yaml"


def _read_yaml(path: Path) -> dict:
    raw = yaml.safe_load(path.read_text()) or {}
    if not isinstance(raw, dict):
        raise ConfigFormatError(f"Config {path} must be a YAML mapping, got {type(raw).__name__}.")
    return raw


def _merge(base: dict, user: dict) -> dict:
    """Overlay `user` on `base`: shallow at top level, one level deep for sections."""
    merged = {**base, **user}
    for section in ("model", "agent", "mcp"):
        if isinstance(base.get(section), dict) and isinstance(user.get(section), dict):
            merged[section] = {**base[section], **user[section]}
    return merged


def load_config(path: str | None) -> LeaConfig:
    """Build a LeaConfig: default.yaml as base, optional user file overlaid on top."""
    base = _read_yaml(DEFAULT_CONFIG_PATH)
    if path is not None:
        base = _merge(base, _read_yaml(Path(path)))
    return validate_config(base)
