1. **Reformulate as a counting problem via Burnside.** Let $G$ act transitively on the finite set $\alpha$ with $|\alpha| = n \geq 2$. For each $g \in G$, let $\operatorname{fix}(g) = |\{x \in \alpha : g \cdot x = x\}|$. Burnside's lemma (the Cauchy–Frobenius formula) says
$$\frac{1}{|G|} \sum_{g \in G} \operatorname{fix}(g) = \text{(number of orbits)} = 1,$$
since the action is transitive. Hence $\sum_{g \in G} \operatorname{fix}(g) = |G|$.

2. **Isolate the contribution of the identity.** The identity element fixes all $n$ points, contributing $n$ to the sum. Thus
$$\sum_{g \neq 1} \operatorname{fix}(g) = |G| - n.$$
Since $n \geq 2$, we have $|G| - n < |G| - 1$, i.e., the non-identity elements contribute strictly less than $|G| - 1$ in total.

3. **Derive existence of a fixed-point-free element by averaging.** There are $|G| - 1$ non-identity elements, and their fixed-point counts are nonnegative integers summing to $|G| - n < |G| - 1$. By pigeonhole, at least one non-identity $g \in G$ must satisfy $\operatorname{fix}(g) = 0$; otherwise every non-identity element would contribute $\geq 1$, giving a sum $\geq |G| - 1$, contradiction. Note we also need $|G| \geq n \geq 2$, which follows from transitivity on a set of size $\geq 2$ (the orbit-stabilizer argument shows $n \mid |G|$, in particular $|G| \geq n$).

4. **Translate back to `derangements α`.** A permutation is a derangement iff it has no fixed points, i.e., `∀ x, g x ≠ x`. The element $g$ from step 3, viewed as an element of `Equiv.Perm α` via the subgroup inclusion, is the desired derangement and lies in $G$.

5. **Formalization notes.**
   - The proof requires `Fintype α` for the counting; `Finite α` + classical choice upgrades to `Fintype`. The student should pick a `Fintype` instance early.
   - Burnside's lemma is in Mathlib (look under `MulAction` / orbit-counting / Cauchy–Frobenius). It is typically stated in terms of `Nat.card` of orbits and fixed-point sets.
   - The key inequality step is pure arithmetic on `Finset.sum` once the sum identity is in hand; splitting off the identity term uses `Finset.sum_eq_sum_diff_singleton_add` or similar.
   - To produce `g ∈ Equiv.Perm α`, note that elements of the subgroup $G$ coerce to `Equiv.Perm α`; use this coercion and transport the fixed-point-free property.
   - The hypothesis `IsPretransitive G α` gives exactly one orbit; be careful whether Mathlib's Burnside statement is phrased for the action of `G` as a subgroup versus the ambient `Equiv.Perm α`—the student may need to transfer between these. The action of a subgroup on $\alpha$ inherits pretransitivity, and fixed-point sets are the same.
   - Membership `g ∈ derangements α` unfolds to `∀ x, g x ≠ x`, which is directly the "fixed-point-free" condition.
