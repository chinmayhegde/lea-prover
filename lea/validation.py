"""Config schema + validator — the reusable, I/O-free half of configuration.

`validate_config(raw)` takes an already-parsed config mapping and returns a
`LeaConfig`, raising a typed `ConfigError` on the first problem. It touches no
disk and runs no agent, so the UI/API layer can call it directly on a config
payload to check it before use.

`load_config` (in config.py) is the file-I/O wrapper around this.
"""

from dataclasses import dataclass

from .errors import (
    ConfigFormatError,
    InvalidConfigValueError,
    MissingConfigKeyError,
    UnknownConfigKeyError,
)

# Recognized keys per section. Anything outside these is an UnknownConfigKeyError.
_TOP_KEYS = {"model", "agent", "mcp"}
_MODEL_KEYS = {"name", "model_kwargs", "stream"}
_AGENT_KEYS = {"prompt_variant", "max_turns", "tools", "tool_modules", "skills", "narrate_tool_steps"}
# Keys that must be present (others are optional and may be omitted/null).
_AGENT_REQUIRED = {"prompt_variant", "max_turns"}
_MCP_KEYS = {"servers"}
_MCP_STDIO_KEYS = {"command", "args", "env", "cwd"}   # subprocess transport
_MCP_HTTP_KEYS = {"url", "headers", "transport"}       # remote transport (http/sse)


@dataclass
class LeaConfig:
    """Everything the core loop needs. No defaults — values come from YAML."""

    model_name: str          # LiteLLM "provider/model", e.g. "gemini/gemini-3.1-pro-preview"
    model_kwargs: dict        # open passthrough to litellm.completion (temperature, max_tokens, ...)
    stream: bool             # True → stream tokens live; False → one blocking call
    prompt_variant: str      # name of a prompt variant (no fixed allow-list)
    max_turns: int | None    # None → run until the proof is done
    tools: list[str] | None  # tool allowlist (order = call order); None → all registered tools
    tool_modules: list[str]  # python modules to import so custom tools register
    skills: list[str]        # skill markdown files to inject into the system prompt, in order
    narrate_tool_steps: bool # True → ask the model to summarize intent before tool calls
    mcp_servers: dict        # name → server spec (stdio: command/args/env/cwd, or remote: url/headers/transport)


def _reject_unknown(section: str, got: dict, allowed: set[str]) -> None:
    unknown = set(got) - allowed
    if unknown:
        raise UnknownConfigKeyError(
            f"Unknown key(s) in '{section}': {', '.join(sorted(unknown))}. "
            f"Allowed: {', '.join(sorted(allowed))}."
        )


def _section(raw: dict, name: str) -> dict:
    value = raw.get(name) or {}
    if not isinstance(value, dict):
        raise ConfigFormatError(f"Section '{name}' must be a mapping, got {type(value).__name__}.")
    return value


def _require(section: str, data: dict, key: str) -> None:
    if key not in data:
        raise MissingConfigKeyError(f"Missing required key '{section}.{key}'.")


def _check_str(section: str, key: str, value: object) -> None:
    if not isinstance(value, str):
        raise InvalidConfigValueError(
            f"'{section}.{key}' must be a string, got {type(value).__name__}."
        )


def _check_dict(section: str, key: str, value: object) -> None:
    if not isinstance(value, dict):
        raise InvalidConfigValueError(
            f"'{section}.{key}' must be a mapping, got {type(value).__name__}."
        )


def _check_bool(section: str, key: str, value: object) -> None:
    if not isinstance(value, bool):
        raise InvalidConfigValueError(
            f"'{section}.{key}' must be a boolean, got {type(value).__name__}."
        )


def _check_opt_int(section: str, key: str, value: object) -> None:
    # bool is a subclass of int — exclude it so `true` isn't read as 1.
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        raise InvalidConfigValueError(
            f"'{section}.{key}' must be an integer or null, got {type(value).__name__}."
        )


def _check_opt_str_list(section: str, key: str, value: object) -> None:
    if value is None:
        return
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        raise InvalidConfigValueError(
            f"'{section}.{key}' must be a list of strings or null, got {type(value).__name__}."
        )


def _validate_mcp(raw: dict) -> dict:
    """Validate the optional `mcp` section and return its server map (or {})."""
    mcp = _section(raw, "mcp")
    if not mcp:
        return {}
    _reject_unknown("mcp", mcp, _MCP_KEYS)
    servers = mcp.get("servers") or {}
    if not isinstance(servers, dict):
        raise ConfigFormatError(f"'mcp.servers' must be a mapping, got {type(servers).__name__}.")

    for name, spec in servers.items():
        where = f"mcp.servers.{name}"
        if not isinstance(spec, dict):
            raise ConfigFormatError(f"'{where}' must be a mapping, got {type(spec).__name__}.")
        has_cmd, has_url = "command" in spec, "url" in spec
        if has_cmd == has_url:  # neither, or both
            raise InvalidConfigValueError(
                f"'{where}' must have exactly one of 'command' (stdio) or 'url' (remote)."
            )
        if has_cmd:
            _reject_unknown(where, spec, _MCP_STDIO_KEYS)
            _check_str(where, "command", spec["command"])
            _check_opt_str_list(where, "args", spec.get("args"))
            if spec.get("env") is not None:
                _check_dict(where, "env", spec["env"])
            if spec.get("cwd") is not None:
                _check_str(where, "cwd", spec["cwd"])
        else:
            _reject_unknown(where, spec, _MCP_HTTP_KEYS)
            _check_str(where, "url", spec["url"])
            if spec.get("headers") is not None:
                _check_dict(where, "headers", spec["headers"])
            transport = spec.get("transport")
            if transport is not None and transport not in ("http", "sse"):
                raise InvalidConfigValueError(
                    f"'{where}.transport' must be 'http' or 'sse', got {transport!r}."
                )
    return servers


def validate_config(raw: dict) -> LeaConfig:
    """Validate a parsed config mapping and return a LeaConfig (raises on first error)."""
    if not isinstance(raw, dict):
        raise ConfigFormatError(f"Config must be a mapping, got {type(raw).__name__}.")
    _reject_unknown("(top level)", raw, _TOP_KEYS)

    model = _section(raw, "model")
    agent = _section(raw, "agent")
    _reject_unknown("model", model, _MODEL_KEYS)
    _reject_unknown("agent", agent, _AGENT_KEYS)
    mcp_servers = _validate_mcp(raw)

    for key in _MODEL_KEYS:
        _require("model", model, key)
    for key in _AGENT_REQUIRED:
        _require("agent", agent, key)

    _check_str("model", "name", model["name"])
    _check_dict("model", "model_kwargs", model["model_kwargs"])
    _check_bool("model", "stream", model["stream"])
    _check_str("agent", "prompt_variant", agent["prompt_variant"])
    _check_opt_int("agent", "max_turns", agent["max_turns"])
    narrate_tool_steps = agent.get("narrate_tool_steps", False)
    _check_bool("agent", "narrate_tool_steps", narrate_tool_steps)

    # Optional tool keys: omitted/null tools → all registered tools; omitted
    # tool_modules → no custom modules.
    tools = agent.get("tools")
    tool_modules = agent.get("tool_modules")
    skills = agent.get("skills")
    _check_opt_str_list("agent", "tools", tools)
    _check_opt_str_list("agent", "tool_modules", tool_modules)
    _check_opt_str_list("agent", "skills", skills)

    return LeaConfig(
        model_name=model["name"],
        model_kwargs=model["model_kwargs"],
        stream=model["stream"],
        prompt_variant=agent["prompt_variant"],
        max_turns=agent["max_turns"],
        tools=tools,
        tool_modules=tool_modules or [],
        skills=skills or [],
        narrate_tool_steps=narrate_tool_steps,
        mcp_servers=mcp_servers,
    )
