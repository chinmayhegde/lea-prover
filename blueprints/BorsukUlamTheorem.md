1. **Reduce to the odd-map formulation.** Show that the theorem is equivalent to the statement: there is no continuous map `g : S^n → S^{n-1}` satisfying `g(-x) = -g(x)` (an "odd" or "equivariant" map). Indeed, if `f : S^n → ℝ^n` had `f(x) ≠ f(-x)` for all `x`, then `g(x) := (f(x) - f(-x)) / ‖f(x) - f(-x)‖` would be such a continuous odd map into `S^{n-1}`. So it suffices to prove no continuous odd map `S^n → S^{n-1}` exists, for all `n ≥ 1`. The case `n = 0` is trivial: `S^0 = {±1} ⊂ ℝ`, and `f : S^0 → ℝ^0 = {0}` is constant, so `f(1) = f(-1)`.

2. **Acknowledge the depth.** Borsuk–Ulam is a genuinely nontrivial topological theorem; every known proof uses some form of algebraic topology. Standard routes are:
   - **Degree theory / homology:** an odd self-map of `S^n` has odd degree, contradicting the fact that a map factoring through `S^{n-1}` has degree zero.
   - **`ℤ/2`-equivariant cohomology / Stiefel–Whitney classes:** uses `H^*(ℝP^n; ℤ/2) = ℤ/2[w]/(w^{n+1})`.
   - **Lusternik–Schnirelmann covering argument** combined with the non-existence of an `ℤ/2`-equivariant map `S^n → S^{n-1}`.
   The student should pick whichever route Mathlib best supports.

3. **Assess Mathlib availability.** As of current Mathlib, the full machinery needed is **largely absent or incomplete**:
   - Singular/cellular homology of spheres exists in some form, but a usable Brouwer degree theory for `S^n → S^n` with the property "odd maps have odd degree" is **not** available in general.
   - `ℝP^n` and its cohomology ring are not developed.
   - The 2-dimensional case (`n ≤ 2`) may be feasible via winding numbers / fundamental group of `S^1`, which Mathlib does have.
   The student should expect that proving the general-`n` theorem requires building substantial new infrastructure. This is a multi-month project, not a routine formalization.

4. **Suggested concrete strategy if attempting the full theorem.** Develop (or locate) the mod-2 degree of continuous self-maps of `S^n`: define it via mod-2 singular homology `H_n(S^n; ℤ/2) ≃ ℤ/2`. Prove (a) homotopy invariance, (b) degree of the antipodal map is `1 mod 2`, (c) degree is multiplicative under composition, (d) a map factoring through `S^{n-1}` has degree `0 mod 2`. Then if `g : S^n → S^{n-1}` were continuous and odd, extend/compose to get a self-map of `S^n` of odd degree factoring through `S^{n-1}`, a contradiction.

5. **Fallback.** If only low dimensions are needed, prove `n = 1` directly using the fundamental group of `S^1` (already in Mathlib via `Real.angle` / covering of `S^1` by `ℝ`): a continuous odd map `S^1 → S^0` is impossible by connectedness; a continuous odd self-map of `S^1` has odd winding number. State clearly in the final Lean file which dimensions are actually proved if the general case is left as `sorry`.
