"""Run-directory layout + state for the Lea-Ralph loop.

A run lives *inside* the workspace Lake project so the agent's tools and the
gates (`lake env lean`, SafeVerify) all see the same files:

    workspace/proofs/ralph_<theorem>_<ts>/
      target.lean     # FROZEN: the theorem's exact signature (never edited)
      work.lean       # evolving proof; open `sorry`s = open leaves
      worklist.json   # per-leaf metadata (status, attempts, stuck_count)
      notes.md        # distilled failure-memory
      heartbeat.json  # liveness/progress
      log/            # raw per-iteration transcripts (debug only)
      .git/           # checkpoints — ONE commit per accepted change

The run dir is a *nested* git repo: `workspace/proofs/*` is gitignored by the
parent lea-prover repo, so these checkpoints never touch lea-prover's tree.

The `sorry`s in `work.lean` are the source of truth for open goals
(`lea.sketch.extract_sorrys`); `worklist.json` only annotates them. A leaf's id
is a stable hash of `(enclosing-name, normalized-type)` so it survives edits
that shift line numbers (RALPH.md open question Q6).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from lea.sketch import extract_sorrys

DEFAULT_AXIOMS = ["propext", "Classical.choice", "Quot.sound"]


# ----------------------------- atomic json/jsonl -----------------------------
# (lifted from the xcelsa ralph/state.py — same write-then-rename discipline so a
# reader never sees a half-written file)

def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json_atomic(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(obj, f, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def append_jsonl(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(obj) + "\n")


# ----------------------------------- paths -----------------------------------

def target_path(run: Path) -> Path: return Path(run) / "target.lean"
def work_path(run: Path) -> Path: return Path(run) / "work.lean"
def worklist_path(run: Path) -> Path: return Path(run) / "worklist.json"
def notes_path(run: Path) -> Path: return Path(run) / "notes.md"
def heartbeat_path(run: Path) -> Path: return Path(run) / "heartbeat.json"
def log_dir(run: Path) -> Path: return Path(run) / "log"


# ------------------------------- leaf identity -------------------------------

def normalize_type(type_str: str | None) -> str:
    """Collapse whitespace so a leaf id is stable across reflows."""
    return " ".join(type_str.split()) if type_str else ""


def leaf_id(name: str | None, type_str: str | None) -> str:
    key = f"{name or '?'}::{normalize_type(type_str)}"
    return hashlib.sha1(key.encode()).hexdigest()[:12]


# ----------------------------------- init ------------------------------------

def init_run(
    target_lean: Path,
    theorem: str,
    workspace: Path,
    allowed_axioms: list[str] | None = None,
    runs_root: Path | None = None,
    timestamp: str | None = None,
) -> Path:
    """Create a fresh run dir from a target `.lean` file.

    `work.lean` starts identical to the frozen `target.lean`; the target's
    top-level `sorry` is the first open leaf. `timestamp` is injectable for
    deterministic tests.
    """
    target_lean = Path(target_lean)
    workspace = Path(workspace)
    ts = timestamp or time.strftime("%Y%m%d-%H%M%S")
    runs_root = Path(runs_root) if runs_root else (workspace / "proofs")
    run = runs_root / f"ralph_{theorem}_{ts}"
    run.mkdir(parents=True, exist_ok=False)

    src = target_lean.read_text()
    target_path(run).write_text(src)   # frozen reference, never edited
    work_path(run).write_text(src)     # evolving copy, starts identical
    log_dir(run).mkdir(exist_ok=True)
    notes_path(run).write_text(
        f"# Failure-memory for `{theorem}`\n\n"
        "Distilled facts only (dead lemma names, timed-out tactics, route\n"
        "decisions, rejected cheats). NOT transcripts.\n\n"
    )

    wl = {
        "target": theorem,
        "allowed_axioms": allowed_axioms or list(DEFAULT_AXIOMS),
        "created": ts,
        "workspace": str(workspace.resolve()),
        "leaves": {},
    }
    save_worklist(run, wl)
    sync_worklist(run)                 # populate leaves from the initial sorrys

    _git(run, "init", "-q")
    checkpoint(run, "init: frozen target + work")
    heartbeat(run, status="init", theorem=theorem)
    return run


# --------------------------------- worklist ----------------------------------

def load_worklist(run: Path) -> dict:
    return read_json(worklist_path(run), {}) or {}


def save_worklist(run: Path, wl: dict) -> None:
    write_json_atomic(worklist_path(run), wl)


def sync_worklist(run: Path) -> dict:
    """Reconcile worklist.json with the actual `sorry`s in work.lean.

    - a `sorry` with no leaf yet  -> new `open` leaf
    - a leaf whose `sorry` is gone -> `closed` (unless `axiomatized`)
    - a `closed` leaf whose `sorry` reappeared -> back to `open`

    Counts (attempts/stuck_count) are preserved across syncs.
    """
    wl = load_worklist(run)
    leaves: dict = wl.setdefault("leaves", {})

    present: dict[str, dict] = {}
    for s in extract_sorrys(work_path(run)):
        lid = leaf_id(s["name"], s.get("type"))
        present[lid] = s
        leaf = leaves.get(lid)
        if leaf is None:
            leaves[lid] = {
                "name": s["name"],
                "type": s.get("type"),
                "status": "open",
                "attempts": 0,
                "stuck_count": 0,
                "last_error": None,
                "line": s["line"],
            }
        else:
            leaf["line"] = s["line"]               # refresh location
            if leaf["status"] == "closed":
                leaf["status"] = "open"            # reappeared

    for lid, leaf in leaves.items():
        if lid not in present and leaf["status"] != "axiomatized":
            leaf["status"] = "closed"

    save_worklist(run, wl)
    return wl


def update_leaf(run: Path, lid: str, **fields) -> dict:
    """Patch a single leaf's metadata and persist."""
    wl = load_worklist(run)
    leaf = wl.get("leaves", {}).get(lid)
    if leaf is not None:
        leaf.update(fields)
        save_worklist(run, wl)
    return wl


def bump(run: Path, lid: str, field: str, by: int = 1) -> dict:
    wl = load_worklist(run)
    leaf = wl.get("leaves", {}).get(lid)
    if leaf is not None:
        leaf[field] = int(leaf.get(field, 0)) + by
        save_worklist(run, wl)
    return wl


def leaves_by_status(run: Path, status: str) -> dict[str, dict]:
    wl = load_worklist(run)
    return {lid: l for lid, l in wl.get("leaves", {}).items()
            if l.get("status") == status}


def open_leaves(run: Path) -> dict[str, dict]:
    return leaves_by_status(run, "open")


# -------------------------- checkpoint (nested git) --------------------------

def _git(run: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(run), capture_output=True, text=True,
    )


def checkpoint(run: Path, msg: str) -> None:
    """One commit of the whole run dir. `--allow-empty` so a checkpoint never
    hard-fails the loop when nothing changed."""
    _git(run, "add", "-A")
    _git(
        run, "-c", "user.name=ralph", "-c", "user.email=ralph@lea",
        "commit", "-q", "--allow-empty", "-m", msg,
    )


# --------------------------------- heartbeat ---------------------------------

def heartbeat(run: Path, **fields) -> None:
    hb = read_json(heartbeat_path(run), {}) or {}
    hb.update(fields)
    hb["ts"] = time.time()
    write_json_atomic(heartbeat_path(run), hb)
