"""Shared grader: run SafeVerify against a (target, submission) pair.

SafeVerify performs kernel replay, per-declaration type/body match, and axiom
whitelist — catching `local notation` shadows, `abbrev` redefinitions,
`opaque` axioms, and `sorry` that plain `lake env lean` lets through.

Reusable across FQB, Putnam, miniF2F, or any Lake-based benchmark.
"""

from pathlib import Path
import subprocess

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAFE_VERIFY_DIR = REPO_ROOT / "third_party" / "SafeVerify"


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
    safe_verify_timeout: int = 180,
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
                ["lake", "exe", "safe_verify",
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
        return False, output if output else f"SafeVerify exit code {result.returncode}"
    finally:
        for p in (target_olean, submission_olean, report_path):
            p.unlink(missing_ok=True)
