"""Shared grader: run SafeVerify against a (target, submission) pair.

SafeVerify performs kernel replay, per-declaration type/body match, and axiom
whitelist — catching `local notation` shadows, `abbrev` redefinitions,
`opaque` axioms, and `sorry` that plain `lake env lean` lets through.

Reusable across FQB, Putnam, miniF2F, or any Lake-based benchmark.

Known limitation: SafeVerify compares declaration types syntactically, not up
to alpha-renaming of universe parameters or instance hygiene names. When the
submission file has helper lemmas before MainTheorem that consume universe
parameters first, MainTheorem's auto-allocated `u_3, u_4` doesn't textually
match the target's `u_1, u_2`. This wrapper detects and accepts that specific
false-positive class (see `_universe_alpha_equiv` below).
"""

from pathlib import Path
import re
import subprocess

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAFE_VERIFY_DIR = REPO_ROOT / "third_party" / "SafeVerify"


_UNIV_RE = re.compile(r"\bu_\d+\b")
_HYG_RE = re.compile(r"inst\._@\.[\w.\-]+\._hygCtx\._hyg\.\d+")


def _normalize_for_alpha(s: str) -> str:
    """Canonicalize universe-param names and instance hygiene names so two
    types that differ only in those auto-generated identifiers compare equal."""
    seen_u: dict[str, str] = {}
    def _u(m: re.Match) -> str:
        name = m.group(0)
        if name not in seen_u:
            seen_u[name] = f"u_X{len(seen_u)}"
        return seen_u[name]
    seen_h: dict[str, str] = {}
    def _h(m: re.Match) -> str:
        name = m.group(0)
        if name not in seen_h:
            seen_h[name] = f"inst._@.HYG_{len(seen_h)}"
        return seen_h[name]
    s = _UNIV_RE.sub(_u, s)
    s = _HYG_RE.sub(_h, s)
    return s


def _universe_alpha_equiv(safe_verify_output: str) -> bool:
    """Return True iff SafeVerify's failure is a universe/hygiene-only
    false positive — i.e., the Expected and Got types are alpha-equivalent
    after canonicalizing universe parameter names and instance hygiene names.
    Anything else (real shadows, axiom additions, structural mismatches)
    falls through to a normal FAIL."""
    m = re.search(
        r"Expected type:\s*(.*?)\s*Got type:\s*(.*?)(?:\s*Expected level params|\s*-{3,}|\Z)",
        safe_verify_output, re.DOTALL,
    )
    if not m:
        return False
    expected = _normalize_for_alpha(m.group(1).strip())
    got = _normalize_for_alpha(m.group(2).strip())
    return expected == got


def _compile_to_olean(source: Path, out: Path, lake_project: Path, timeout: int) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["lake", "env", "lean", "-o", str(out.resolve()), str(source.resolve())],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(lake_project),
        )
    except subprocess.TimeoutExpired:
        return False, f"Compilation timed out ({timeout}s)"
    output = (result.stdout + "\n" + result.stderr).strip()
    if result.returncode != 0 or not out.exists():
        return False, output if output else f"Exit code {result.returncode}"
    return True, output


def verify_proof(
    target_src: Path,
    submission_src: Path,
    lake_project: Path,
    scratch_dir: Path | None = None,
    compile_timeout: int = 600,
    safe_verify_timeout: int = 600,
) -> tuple[bool, str]:
    """Verify `submission_src` against `target_src` using SafeVerify.

    `lake_project` is the Lake project (with Mathlib) that both files compile
    in. `scratch_dir` defaults to `<lake_project>/.sv_scratch/`. Returns
    `(success, detail)`. Cleans up scratch oleans on exit.
    """
    if not submission_src.exists():
        return False, "Proof file not found"
    if not target_src.exists():
        return False, f"Target file not found: {target_src}"

    scratch = scratch_dir or (lake_project / ".sv_scratch")
    scratch.mkdir(parents=True, exist_ok=True)
    stem = submission_src.stem
    target_olean = scratch / f"{stem}_target.olean"
    submission_olean = scratch / f"{stem}_submission.olean"
    report_path = scratch / f"{stem}_report.json"

    try:
        ok, out = _compile_to_olean(target_src, target_olean, lake_project, compile_timeout)
        if not ok:
            return False, f"Target compile failed: {out}"

        ok, out = _compile_to_olean(submission_src, submission_olean, lake_project, compile_timeout)
        if not ok:
            return False, f"Submission compile failed: {out}"

        try:
            result = subprocess.run(
                ["lake", "exe", "safe_verify", "-v",
                 str(target_olean.resolve()), str(submission_olean.resolve()),
                 "--disallow-partial", "-s", str(report_path.resolve())],
                capture_output=True, text=True, timeout=safe_verify_timeout,
                cwd=str(SAFE_VERIFY_DIR),
            )
        except subprocess.TimeoutExpired:
            return False, f"SafeVerify timed out ({safe_verify_timeout}s)"

        output = (result.stdout + "\n" + result.stderr).strip()
        if result.returncode == 0:
            return True, "OK (SafeVerify passed)"
        if "theorem type mismatch" in output and _universe_alpha_equiv(output):
            return True, "OK (SafeVerify rejected on universe/hygiene-only naming difference; types alpha-equivalent)"
        return False, output if output else f"SafeVerify exit code {result.returncode}"
    finally:
        for p in (target_olean, submission_olean, report_path):
            p.unlink(missing_ok=True)
