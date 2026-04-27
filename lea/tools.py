"""Lea's six tools — the minimum surface area for Lean formalization."""

import os
import subprocess
import tempfile
from pathlib import Path

TOOLS_SCHEMA = [
    {
        "name": "read_file",
        "description": "Read the contents of a file. Optionally restrict to a line range (1-indexed, inclusive) to avoid pulling large files into context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read."},
                "start_line": {"type": "integer", "description": "Optional 1-indexed first line to include."},
                "end_line": {"type": "integer", "description": "Optional 1-indexed last line to include (inclusive)."},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Create or overwrite a file with the given content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to write."},
                "content": {"type": "string", "description": "Full file content."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "edit_file",
        "description": "Replace an exact substring in a file with new text.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to edit."},
                "old_string": {"type": "string", "description": "Exact text to find."},
                "new_string": {"type": "string", "description": "Replacement text."},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
    {
        "name": "lean_check",
        "description": "Compile a .lean file and return diagnostics (errors, warnings, goals). Uses `lake env lean` if inside a Lake project, otherwise `lean` directly.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the .lean file to check."}
            },
            "required": ["path"],
        },
    },
    {
        "name": "bash",
        "description": "Run a shell command and return stdout + stderr. Use for `lake build`, git, file I/O outside the dedicated tools, etc. Do NOT use for Lean compilation (use `lean_check`) or Mathlib search (use `search_mathlib`).",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute."},
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default 120).",
                    "default": 120,
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "search_mathlib",
        "description": "Search Mathlib for lemmas/theorems matching a query. Greps Mathlib source files for the query string. If you are proving in a specific Lake project (e.g., miniF2F, FormalQualBench), pass `path` so the search uses THAT project's Mathlib version — different projects pin different Mathlib versions, and a hit in the wrong version is worse than no hit.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term — a lemma name fragment, type signature pattern, or keyword.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return.",
                    "default": 10,
                },
                "path": {
                    "type": "string",
                    "description": "Optional path to a .lean file or directory inside a Lake project. If provided, search Mathlib in that project's Lake packages instead of the default workspace Mathlib.",
                },
            },
            "required": ["query"],
        },
    },
]


def _find_lake_root(path: str) -> str | None:
    """Walk up from path looking for lakefile.lean or lakefile.toml."""
    p = Path(path).resolve()
    for parent in [p.parent, *p.parent.parents]:
        if (parent / "lakefile.lean").exists() or (parent / "lakefile.toml").exists():
            return str(parent)
    return None


def read_file(path: str, start_line: int | None = None, end_line: int | None = None) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"Error: {p} does not exist."
    text = p.read_text()
    if start_line is None and end_line is None:
        return text
    lines = text.splitlines(keepends=True)
    s = max(0, (start_line or 1) - 1)
    e = end_line if end_line is not None else len(lines)
    sliced = "".join(lines[s:e])
    header = f"# lines {s + 1}-{min(e, len(lines))} of {len(lines)} in {p}\n"
    return header + sliced


def write_file(path: str, content: str) -> str:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Wrote {len(content)} bytes to {p}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"Error: {p} does not exist."
    text = p.read_text()
    count = text.count(old_string)
    if count == 0:
        return "Error: old_string not found in file."
    if count > 1:
        return f"Error: old_string appears {count} times. Provide more context to make it unique."
    p.write_text(text.replace(old_string, new_string, 1))
    return "OK"


def lean_check(path: str) -> str:
    p = Path(path).resolve()
    if not p.exists():
        return f"Error: {p} does not exist."

    lake_root = _find_lake_root(str(p))
    if lake_root:
        cmd = ["lake", "env", "lean", str(p)]
        cwd = lake_root
    else:
        cmd = ["lean", str(p)]
        cwd = str(p.parent)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, cwd=cwd
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode == 0 and not output:
            return "OK — no errors, no warnings."
        return output if output else f"Exit code {result.returncode} (no output)."
    except subprocess.TimeoutExpired:
        return "Error: lean timed out after 120s."
    except FileNotFoundError:
        return "Error: `lean` or `lake` not found. Is Lean 4 installed?"


def bash(command: str, timeout: int = 120) -> str:
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        output = (result.stdout + result.stderr).strip()
        if not output:
            return f"(no output, exit code {result.returncode})"
        if len(output) > 10000:
            output = output[:10000] + "\n... (truncated)"
        return output
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s."


WORKSPACE = Path(__file__).resolve().parent.parent / "workspace"


def _mathlib_for_lake_root(lake_root: Path) -> Path | None:
    for sub in (".lake/packages/mathlib/Mathlib", "lake-packages/mathlib/Mathlib"):
        candidate = lake_root / sub
        if candidate.exists():
            return candidate
    return None


def search_mathlib(query: str, max_results: int = 10, path: str | None = None) -> str:
    search_dir = None
    project_label = "default workspace"

    if path:
        lake_root_str = _find_lake_root(path)
        if lake_root_str:
            mathlib = _mathlib_for_lake_root(Path(lake_root_str))
            if mathlib:
                search_dir = str(mathlib)
                project_label = lake_root_str
            else:
                return f"Error: Mathlib not found under Lake project at {lake_root_str}. Ensure Mathlib is a Lake dependency."
        else:
            return f"Error: no Lake project (lakefile.lean/lakefile.toml) found above {path}."

    if not search_dir:
        for candidate in (
            WORKSPACE / ".lake" / "packages" / "mathlib" / "Mathlib",
            WORKSPACE / "lake-packages" / "mathlib" / "Mathlib",
        ):
            if candidate.exists():
                search_dir = str(candidate)
                break

    if not search_dir:
        return "Error: Mathlib source not found. Ensure Mathlib is a Lake dependency."

    try:
        result = subprocess.run(
            ["grep", "-r", "-n", "--include=*.lean", "-l", query, search_dir],
            capture_output=True,
            text=True,
            timeout=30,
        )
        files = result.stdout.strip().split("\n")
        files = [f for f in files if f][:max_results]
        if not files:
            return f"No Mathlib results for '{query}' in {project_label}."

        # Get matching lines from each file
        lines = []
        for f in files[:max_results]:
            grep_result = subprocess.run(
                ["grep", "-n", query, f],
                capture_output=True,
                text=True,
                timeout=10,
            )
            for line in grep_result.stdout.strip().split("\n")[:2]:
                short_path = f.split("Mathlib/")[-1] if "Mathlib/" in f else f
                lines.append(f"  Mathlib/{short_path}:{line}")
                if len(lines) >= max_results:
                    break
            if len(lines) >= max_results:
                break

        return f"Found {len(lines)} matches in {project_label}:\n" + "\n".join(lines)
    except subprocess.TimeoutExpired:
        return "Error: search timed out."


# Dispatch table
TOOL_HANDLERS = {
    "bash": lambda args: bash(args["command"], args.get("timeout", 120)),
    "read_file": lambda args: read_file(args["path"], args.get("start_line"), args.get("end_line")),
    "write_file": lambda args: write_file(args["path"], args["content"]),
    "edit_file": lambda args: edit_file(args["path"], args["old_string"], args["new_string"]),
    "lean_check": lambda args: lean_check(args["path"]),
    "search_mathlib": lambda args: search_mathlib(args["query"], args.get("max_results", 10), args.get("path")),
}
