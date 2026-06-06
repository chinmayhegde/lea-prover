"""Unit tests for the config layer (config.py + validation.py + errors.py).

Run:  uv run python -m tests.config.test_config
Exits 0 if every check passes, 1 otherwise.
"""

import sys
import tempfile
from pathlib import Path

from lea.config import load_config
from lea.validation import validate_config, LeaConfig
from lea.errors import (
    ConfigFormatError,
    UnknownConfigKeyError,
    MissingConfigKeyError,
    InvalidConfigValueError,
)

_FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        _FAILURES.append(name)


def expect_raises(name: str, err_type: type, fn) -> None:
    try:
        fn()
    except err_type:
        print(f"  ok   {name}")
    except Exception as e:  # wrong exception type
        print(f"  FAIL {name} (raised {type(e).__name__}, expected {err_type.__name__})")
        _FAILURES.append(name)
    else:
        print(f"  FAIL {name} (no error raised, expected {err_type.__name__})")
        _FAILURES.append(name)


def valid_raw() -> dict:
    """A complete, valid config mapping."""
    return {
        "model": {"name": "test-model", "stream": True, "model_kwargs": {"temperature": 0.0}},
        "agent": {"prompt_variant": "default", "max_turns": None},
    }


def test_defaults_match_today():
    cfg = load_config(None)
    check("defaults: model_name", cfg.model_name == "gemini/gemini-3.1-pro-preview")
    check("defaults: model_kwargs", cfg.model_kwargs == {"max_tokens": 16384})
    check("defaults: stream is True", cfg.stream is True)
    check("defaults: prompt_variant", cfg.prompt_variant == "default")
    check("defaults: max_turns is None", cfg.max_turns is None)
    check("defaults: tools is None (all)", cfg.tools is None)
    check("defaults: tool_modules is []", cfg.tool_modules == [])
    check("defaults: skills is []", cfg.skills == [])
    check("defaults: narrate_tool_steps is False", cfg.narrate_tool_steps is False)
    check("defaults: mcp_servers is {}", cfg.mcp_servers == {})


def test_valid_passes():
    cfg = validate_config(valid_raw())
    check("valid config returns LeaConfig", isinstance(cfg, LeaConfig))
    check("valid config: name mapped", cfg.model_name == "test-model")
    check("valid config: model_kwargs mapped", cfg.model_kwargs == {"temperature": 0.0})
    check("valid config: narrate default", cfg.narrate_tool_steps is False)


def test_null_and_empty_allowed():
    cfg = validate_config(valid_raw())
    check("null max_turns allowed", cfg.max_turns is None)
    empty = valid_raw()
    empty["model"]["model_kwargs"] = {}
    check("empty model_kwargs allowed", validate_config(empty).model_kwargs == {})


def test_typed_errors():
    bad_top = valid_raw(); bad_top["extra"] = 1
    expect_raises("unknown top key", UnknownConfigKeyError, lambda: validate_config(bad_top))

    # temperature belongs inside model_kwargs, not at the model level
    bad_model = valid_raw(); bad_model["model"]["temperature"] = 0.5
    expect_raises("unknown model key", UnknownConfigKeyError, lambda: validate_config(bad_model))

    missing = valid_raw(); del missing["model"]["name"]
    expect_raises("missing model.name", MissingConfigKeyError, lambda: validate_config(missing))

    missing_kwargs = valid_raw(); del missing_kwargs["model"]["model_kwargs"]
    expect_raises("missing model.model_kwargs", MissingConfigKeyError, lambda: validate_config(missing_kwargs))

    bad_kwargs = valid_raw(); bad_kwargs["model"]["model_kwargs"] = "lots"
    expect_raises("model_kwargs not a mapping", InvalidConfigValueError, lambda: validate_config(bad_kwargs))

    missing_stream = valid_raw(); del missing_stream["model"]["stream"]
    expect_raises("missing model.stream", MissingConfigKeyError, lambda: validate_config(missing_stream))

    bad_stream = valid_raw(); bad_stream["model"]["stream"] = "yes"
    expect_raises("stream not a bool", InvalidConfigValueError, lambda: validate_config(bad_stream))

    null_variant = valid_raw(); null_variant["agent"]["prompt_variant"] = None
    expect_raises("prompt_variant null", InvalidConfigValueError, lambda: validate_config(null_variant))

    str_turns = valid_raw(); str_turns["agent"]["max_turns"] = "lots"
    expect_raises("max_turns str", InvalidConfigValueError, lambda: validate_config(str_turns))

    bad_tools = valid_raw(); bad_tools["agent"]["tools"] = "lean_check"
    expect_raises("tools not a list", InvalidConfigValueError, lambda: validate_config(bad_tools))

    bad_tool_items = valid_raw(); bad_tool_items["agent"]["tools"] = ["ok", 3]
    expect_raises("tools list with non-str", InvalidConfigValueError, lambda: validate_config(bad_tool_items))

    bad_modules = valid_raw(); bad_modules["agent"]["tool_modules"] = "my.module"
    expect_raises("tool_modules not a list", InvalidConfigValueError, lambda: validate_config(bad_modules))

    bad_skills = valid_raw(); bad_skills["agent"]["skills"] = "skills/induction.md"
    expect_raises("skills not a list", InvalidConfigValueError, lambda: validate_config(bad_skills))

    narrate = valid_raw(); narrate["agent"]["narrate_tool_steps"] = True
    check("narrate_tool_steps bool allowed", validate_config(narrate).narrate_tool_steps is True)

    bad_narrate = valid_raw(); bad_narrate["agent"]["narrate_tool_steps"] = "yes"
    expect_raises("narrate_tool_steps not bool", InvalidConfigValueError, lambda: validate_config(bad_narrate))

    # mcp section
    mcp_both = valid_raw(); mcp_both["mcp"] = {"servers": {"x": {"command": "c", "url": "u"}}}
    expect_raises("mcp server with command+url", InvalidConfigValueError, lambda: validate_config(mcp_both))

    mcp_neither = valid_raw(); mcp_neither["mcp"] = {"servers": {"x": {"args": []}}}
    expect_raises("mcp server with neither", InvalidConfigValueError, lambda: validate_config(mcp_neither))

    mcp_badkey = valid_raw(); mcp_badkey["mcp"] = {"servers": {"x": {"command": "c", "nope": 1}}}
    expect_raises("mcp stdio unknown key", UnknownConfigKeyError, lambda: validate_config(mcp_badkey))

    mcp_transport = valid_raw(); mcp_transport["mcp"] = {"servers": {"x": {"url": "u", "transport": "ftp"}}}
    expect_raises("mcp bad transport", InvalidConfigValueError, lambda: validate_config(mcp_transport))

    mcp_servers_type = valid_raw(); mcp_servers_type["mcp"] = {"servers": ["nope"]}
    expect_raises("mcp servers not a mapping", ConfigFormatError, lambda: validate_config(mcp_servers_type))

    mcp_ok = valid_raw(); mcp_ok["mcp"] = {"servers": {"fs": {"command": "npx", "args": ["x"], "env": {}}}}
    check("mcp valid stdio server passes", validate_config(mcp_ok).mcp_servers["fs"]["command"] == "npx")

    expect_raises("top not a mapping", ConfigFormatError, lambda: validate_config("hello"))

    bad_section = valid_raw(); bad_section["model"] = ["not", "a", "mapping"]
    expect_raises("section not a mapping", ConfigFormatError, lambda: validate_config(bad_section))


def _write_tmp_yaml(text: str) -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
    f.write(text)
    f.close()
    return f.name


def test_overlay_merge():
    path = _write_tmp_yaml("model:\n  name: overridden-model\n")
    try:
        cfg = load_config(path)
        check("overlay: name overridden", cfg.model_name == "overridden-model")
        check("overlay: model_kwargs inherited", cfg.model_kwargs == {"max_tokens": 16384})
        check("overlay: prompt_variant inherited", cfg.prompt_variant == "default")
    finally:
        Path(path).unlink()


def test_overlay_rejects_unknown():
    path = _write_tmp_yaml("model:\n  nonsense: 1\n")
    try:
        expect_raises("overlay unknown key rejected", UnknownConfigKeyError, lambda: load_config(path))
    finally:
        Path(path).unlink()


def main():
    print("config layer tests:")
    test_defaults_match_today()
    test_valid_passes()
    test_null_and_empty_allowed()
    test_typed_errors()
    test_overlay_merge()
    test_overlay_rejects_unknown()
    print()
    if _FAILURES:
        print(f"FAILED ({len(_FAILURES)}): {', '.join(_FAILURES)}")
        sys.exit(1)
    print("All config tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
