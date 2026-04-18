import Mathlib

set_option maxHeartbeats 0
set_option linter.unusedVariables false

open BigOperators Real Nat Topology Rat

theorem aimeII_2001_p3 (x : ℕ → ℤ) (h₀ : x 1 = 211) (h₂ : x 2 = 375) (h₃ : x 3 = 420)
  (h₄ : x 4 = 523) (h₆ : ∀ n ≥ 5, x n = x (n - 1) - x (n - 2) + x (n - 3) - x (n - 4)) :
  x 531 + x 753 + x 975 = 898 := by
  have hp : ∀ n ≥ 1, x (n + 5) = - x n := by
    intro n hn
    have eq1 : x (n + 5) = x (n + 4) - x (n + 3) + x (n + 2) - x (n + 1) := by
      have h := h₆ (n + 5) (by omega)
      have hr1 : n + 5 - 1 = n + 4 := by omega
      have hr2 : n + 5 - 2 = n + 3 := by omega
      have hr3 : n + 5 - 3 = n + 2 := by omega
      have hr4 : n + 5 - 4 = n + 1 := by omega
      rw [hr1, hr2, hr3, hr4] at h
      exact h
    have eq2 : x (n + 4) = x (n + 3) - x (n + 2) + x (n + 1) - x n := by
      have h := h₆ (n + 4) (by omega)
      have hr1 : n + 4 - 1 = n + 3 := by omega
      have hr2 : n + 4 - 2 = n + 2 := by omega
      have hr3 : n + 4 - 3 = n + 1 := by omega
      have hr4 : n + 4 - 4 = n := by omega
      rw [hr1, hr2, hr3, hr4] at h
      exact h
    linarith

  have hp10 : ∀ n ≥ 1, x (n + 10) = x n := by
    intro n hn
    have h1 := hp n hn
    have h2 := hp (n + 5) (by omega)
    linarith

  have h_period : ∀ k n, n ≥ 1 → x (n + 10 * k) = x n := by
    intro k
    induction k with
    | zero =>
      intro n hn
      simp
    | succ k ih =>
      intro n hn
      have h1 : n + 10 * (k + 1) = (n + 10 * k) + 10 := by omega
      rw [h1]
      have h2 := hp10 (n + 10 * k) (by omega)
      rw [h2]
      exact ih n hn

  have h531 : x 531 = x 1 := by
    have h_eq : 531 = 1 + 10 * 53 := by omega
    rw [h_eq]
    exact h_period 53 1 (by omega)

  have h753 : x 753 = x 3 := by
    have h_eq : 753 = 3 + 10 * 75 := by omega
    rw [h_eq]
    exact h_period 75 3 (by omega)

  have h975 : x 975 = x 5 := by
    have h_eq : 975 = 5 + 10 * 97 := by omega
    rw [h_eq]
    exact h_period 97 5 (by omega)

  have h5 : x 5 = x 4 - x 3 + x 2 - x 1 := by
    have h := h₆ 5 (by omega)
    have hr1 : 5 - 1 = 4 := by rfl
    have hr2 : 5 - 2 = 3 := by rfl
    have hr3 : 5 - 3 = 2 := by rfl
    have hr4 : 5 - 4 = 1 := by rfl
    rw [hr1, hr2, hr3, hr4] at h
    exact h

  linarith
