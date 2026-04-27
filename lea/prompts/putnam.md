# Putnam-Specific Instructions

Putnam problems often phrase claims in terms of Mathlib-specific operations
(`Rat.num`, `Rat.den`, `Nat.dist`, `Int.natAbs`, `Finset.Coprime`, `Nat.Coprime`,
etc.). When a helper lemma mentions one of these, the FIRST attempt must be
`by exact?` or `by apply?` — the answer is usually a named Mathlib lemma, not
a computation. Only fall back to manual rewriting (`zify`, `push_cast`, case
splits) if both fail.
