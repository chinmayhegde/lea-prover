# third_party

Vendored dependencies. Source is checked into this repo; build artifacts (`.lake/`, `build/`, `*.olean`) are gitignored and rebuilt locally via `lake build`.

## SafeVerify

A Lean 4 tool that verifies a candidate proof against a canonical problem statement by kernel replay, per-declaration type/body match, and an axiom whitelist. Catches `local notation` shadows, `abbrev` redefinitions, `opaque`/`axiom` cheats, and `sorry` that plain `lake env lean` misses. Used by the FQB grader (`eval/utils/verify.py`) and is the same tool PutnamBench's official leaderboard uses.

- **Upstream:** https://github.com/GasStationManager/SafeVerify
- **Vendored branch:** `v4.29.0`
- **Commit:** `241dfb0d986baf8a3ba76cba14f10c16e8793e84`

### Modifications

Pinned down one point release so SafeVerify matches `FormalQualBench/lean-toolchain` — `.olean` files are toolchain-specific and won't cross-load between Lean versions. Upstream has no `v4.28.0` branch, so we took `v4.29.0` and bumped:

- `third_party/SafeVerify/lean-toolchain`: `leanprover/lean4:v4.29.0` → `leanprover/lean4:v4.28.0`
- `third_party/SafeVerify/lakefile.lean`: mathlib dep `@ "v4.29.0"` → `@ "v4.28.0"`

No code changes were needed — `Environment.replay` and `Kernel.check` APIs are stable across this delta. If FQB later bumps its toolchain, re-pin both files to the matching version and run `lake update && lake build`.

### Build

```bash
cd third_party/SafeVerify && lake update && lake build
```

Produces the `safe_verify` executable that `eval/utils/verify.py` invokes.
