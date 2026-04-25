1. **Reduce to the Maynard–Tao bounded gaps statement.** The conclusion is logically equivalent to: there exists a constant B such that the set S = { p prime : ∃ q prime, p < q ≤ p+B } is infinite. Indeed, if S is infinite then for any N we can pick p ∈ S with p ≥ N, and the witnessing q gives q − p ≤ B with p < q. Conversely, the conclusion of the theorem clearly implies S is infinite. The student should record this reduction as a small lemma; it is purely first-order logic plus the fact that infinite sets of naturals contain elements above every N.

2. **Invoke the Maynard–Tao theorem.** The deep input is Maynard's 2013 result (independently Tao): liminf_{n→∞} (p_{n+1} − p_n) ≤ 600 (Maynard's original bound; later improved to 246 by Polymath8b, but any explicit finite bound suffices here). In particular, there is some explicit B (e.g., B = 600) such that infinitely many primes p have another prime in (p, p+B]. This is a multi-paper argument involving:
   - The Selberg/GPY sieve with multidimensional weights,
   - Construction of an admissible k-tuple H with k large,
   - Sharp estimates for sums S₁ = Σ wₙ and S₂ = Σ (Σ_{i} 𝟙_{n+hᵢ prime}) wₙ over n ∈ [N, 2N], using the Bombieri–Vinogradov theorem,
   - A variational/eigenvalue argument showing the ratio S₂/S₁ exceeds 1 for suitable weights when k is sufficiently large.
   
   This is genuinely a long proof (tens of pages). Do not attempt to reprove it.

3. **Check Mathlib's status.** As of current Mathlib, the Maynard–Tao theorem is **not** formalized. Neither is the weaker Zhang theorem, nor the Bombieri–Vinogradov theorem, nor the GPY sieve machinery. The student has three realistic options:
   (a) Add the Maynard–Tao theorem as an `axiom` (or `sorry`) at the appropriate abstraction level — e.g., `axiom maynard_tao : ∃ B, ∀ N, ∃ p, N ≤ p ∧ p.Prime ∧ ∃ q, q.Prime ∧ p < q ∧ q - p ≤ B`.
   (b) Formalize the entire Maynard sieve argument from scratch (a multi-year project, comparable in scale to the Liquid Tensor Experiment).
   (c) Prove a much weaker but Mathlib-tractable variant if the surrounding project allows weakening (e.g., infinitude of primes gives no bound on gaps, so this does not help — there is no easy substitute).

4. **Assemble the final theorem.** Given the Maynard–Tao statement from step 3, the proof of `MainTheorem` is a few lines: take B from Maynard–Tao, note B > 0 (since gaps between distinct primes are ≥ 1, and the explicit constant 246 or 600 is positive), and for each N extract the witnessing p, q.

5. **Recommendation.** Unless this is part of a major formalization effort, instruct the student to take route (a): introduce the Maynard–Tao result as an axiom with a clear citation comment (Maynard, *Small gaps between primes*, Annals of Math. 181 (2015), 383–413), and derive `MainTheorem` from it in under ten lines. Flag clearly in the file that the deep number-theoretic content is axiomatized.
