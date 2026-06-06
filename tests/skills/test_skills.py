"""Unit tests for skills: load_skills() and its wiring into load_system_prompt.

Covers empty input, ordered injection under per-skill headers, the missing-file
SkillError, and that load_system_prompt appends skills after the base prompt.
No network.

Run:  uv run python -m tests.skills.test_skills
Exits 0 if every check passes, 1 otherwise.
"""

import sys
import tempfile
from pathlib import Path

from lea.skills import load_skills
from lea.prompt import load_system_prompt
from lea.errors import SkillError

_FAILURES: list[str] = []


def check(name: str, cond: bool) -> None:
    print(f"  ok   {name}" if cond else f"  FAIL {name}")
    if not cond:
        _FAILURES.append(name)


def expect_raises(name: str, err_type: type, fn) -> None:
    try:
        fn()
    except err_type:
        print(f"  ok   {name}")
    except Exception as e:
        print(f"  FAIL {name} (raised {type(e).__name__}, expected {err_type.__name__})")
        _FAILURES.append(name)
    else:
        print(f"  FAIL {name} (no error raised, expected {err_type.__name__})")
        _FAILURES.append(name)


def _write(name: str, text: str) -> str:
    d = Path(tempfile.mkdtemp())
    p = d / name
    p.write_text(text)
    return str(p)


def test_empty():
    check("empty list → empty string", load_skills([]) == "")


def test_order_and_headers():
    a = _write("induction.md", "Use induction on n.")
    b = _write("cascade.md", "Try nlinarith then polyrith.")
    out = load_skills([a, b])
    check("contains first skill body", "Use induction on n." in out)
    check("contains second skill body", "Try nlinarith then polyrith." in out)
    check("header uses file stem", "## Skill: induction" in out and "## Skill: cascade" in out)
    check("order preserved", out.index("induction") < out.index("cascade"))


def test_missing_file():
    expect_raises("missing skill → SkillError", SkillError, lambda: load_skills(["/no/such/skill.md"]))


def test_wired_into_prompt():
    s = _write("house_rules.md", "ALWAYS_NAME_LEMMAS_SNAKE_CASE")
    base = load_system_prompt("default", None)
    with_skill = load_system_prompt("default", [s])
    check("skill appended to system prompt", "ALWAYS_NAME_LEMMAS_SNAKE_CASE" in with_skill)
    check("base prompt unchanged without skills", "ALWAYS_NAME_LEMMAS_SNAKE_CASE" not in base)
    check("skill comes after base content", with_skill.startswith(base[:200]))


def main():
    print("skills tests:")
    test_empty()
    test_order_and_headers()
    test_missing_file()
    test_wired_into_prompt()
    print()
    if _FAILURES:
        print(f"FAILED ({len(_FAILURES)}): {', '.join(_FAILURES)}")
        sys.exit(1)
    print("All skills tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
