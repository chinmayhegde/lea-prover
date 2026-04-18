import Lake
open Lake DSL

package lea where
  leanOptions := #[
    ⟨`autoImplicit, false⟩
  ]

@[default_target]
lean_lib Lea where
  srcDir := "proofs"

require mathlib from git
  "https://github.com/leanprover-community/mathlib4" @ "v4.29.0"
