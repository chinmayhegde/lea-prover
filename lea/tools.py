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
        "description": "Semantic (natural-language) search over Mathlib declarations via LeanExplore. Use this when you know WHAT property you want but do NOT know the Lean lemma name — e.g. 'a transitive group action on a set of prime cardinality is primitive'. Returns the top-k Lean declarations with name, module, source text, and an AI-generated natural-language paraphrase (`informalization`). Prefer this over `bash grep` for concept→name lookup; use `bash grep` only when you already know a name fragment.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A natural-language description of the lemma/definition you want. Be specific about the mathematical objects (group/ring/action/topology/etc.) and the property. Do NOT paste raw Lean goal text with unfolded types — describe the intent. Good: 'Sylow p-subgroup is normal when unique'. Bad: '@Sylow G _ p _ → Subgroup.Normal _'.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 8).",
                    "default": 8,
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

    # Fast path: persistent LSP daemon (keeps Mathlib oleans warm). ~420×
    # speedup on in-place edits. See lea/lsp_daemon.py and tests/lsp/.
    if lake_root and not os.environ.get("LEA_DISABLE_LSP"):
        try:
            from lea.lsp_daemon import check_via_lsp
            return check_via_lsp(str(p), p.read_text(), lake_root)
        except Exception:
            pass  # fall through to subprocess

    if lake_root:
        cmd = ["lake", "env", "lean", str(p)]
        cwd = lake_root
    else:
        cmd = ["lean", str(p)]
        cwd = str(p.parent)

    timeout = int(os.environ.get("LEAN_CHECK_TIMEOUT", "900"))
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode == 0 and not output:
            return "OK — no errors, no warnings."
        return output if output else f"Exit code {result.returncode} (no output)."
    except subprocess.TimeoutExpired:
        return f"Error: lean timed out after {timeout}s."
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


def search_mathlib(query: str, limit: int = 8) -> str:
    """Semantic Mathlib search via LeanExplore's hosted API.

    Requires LEANEXPLORE_API_KEY in the environment — raise rather than
    silently falling back, so the caller knows to configure auth.
    """
    if not query or not query.strip():
        return "Error: query is empty. Provide a natural-language description of the lemma/definition you want."
    if not os.environ.get("LEANEXPLORE_API_KEY"):
        return (
            "Error: LEANEXPLORE_API_KEY is not set. Get a key at "
            "https://www.leanexplore.com and `export LEANEXPLORE_API_KEY=...`."
        )
    try:
        import asyncio
        from lean_explore.api import ApiClient
    except ImportError:
        return "Error: `lean-explore` package not installed. Run `uv sync` or `pip install lean-explore`."

    async def _run() -> str:
        client = ApiClient(timeout=20.0)
        resp = await client.search(query=query, limit=int(limit), packages=["Mathlib"])
        if not resp.results:
            return f"No semantic matches for {query!r}."
        out = [f"Found {resp.count} result(s) in {resp.processing_time_ms}ms:"]
        for i, r in enumerate(resp.results, 1):
            out.append(f"#{i} {r.name}  [{r.module}]")
            inf = (r.informalization or "").strip()
            if inf:
                first_para = inf.split("\n\n")[0].replace("\n", " ")
                if len(first_para) > 400:
                    first_para = first_para[:400].rstrip() + "…"
                out.append(f"  {first_para}")
            src = (r.source_text or "").strip()
            if src:
                snippet = "\n    ".join(src.split("\n")[:6])
                if len(src.split("\n")) > 6:
                    snippet += "\n    …"
                out.append(f"    {snippet}")
        return "\n".join(out)

    try:
        return asyncio.run(_run())
    except Exception as e:
        return f"Error: LeanExplore request failed: {e}"


# Dispatch table
TOOL_HANDLERS = {
    "bash": lambda args: bash(args["command"], args.get("timeout", 120)),
    "read_file": lambda args: read_file(args["path"], args.get("start_line"), args.get("end_line")),
    "write_file": lambda args: write_file(args["path"], args["content"]),
    "edit_file": lambda args: edit_file(args["path"], args["old_string"], args["new_string"]),
    "lean_check": lambda args: lean_check(args["path"]),
    "search_mathlib": lambda args: search_mathlib(args["query"], args.get("limit", 8)),
}
