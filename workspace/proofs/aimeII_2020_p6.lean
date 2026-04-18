import Mathlib

set_option maxHeartbeats 0

open BigOperators Real Nat Topology Rat

theorem aimeII_2020_p6 (t : ℕ → ℚ) (h₀ : t 1 = 20) (h₁ : t 2 = 21)
  (h₂ : ∀ n ≥ 3, t n = (5 * t (n - 1) + 1) / (25 * t (n - 2))) :
  ↑(t 2020).den + (t 2020).num = 626 := by
  have h3 : t 3 = 53 / 250 := by
    have := h₂ 3 (by norm_num)
    norm_num at this
    rw [h₁, h₀] at this
    norm_num at this
    exact this

  have h4 : t 4 = 103 / 26250 := by
    have := h₂ 4 (by norm_num)
    norm_num at this
    rw [h3, h₁] at this
    norm_num at this
    exact this

  have h5 : t 5 = 101 / 525 := by
    have := h₂ 5 (by norm_num)
    norm_num at this
    rw [h4, h3] at this
    norm_num at this
    exact this

  have h6 : t 6 = 20 := by
    have := h₂ 6 (by norm_num)
    norm_num at this
    rw [h5, h4] at this
    norm_num at this
    exact this

  have h7 : t 7 = 21 := by
    have := h₂ 7 (by norm_num)
    norm_num at this
    rw [h6, h5] at this
    norm_num at this
    exact this

  have h_period : ∀ k : ℕ, k ≥ 1 → t k = t (k + 5) ∧ t (k + 1) = t (k + 6) := by
    intro k
    induction' k with k ih
    · intro h; norm_num at h
    · intro hk
      by_cases hk1 : k = 0
      · subst hk1
        norm_num
        have e1 : t 1 = t 6 := h₀.trans h6.symm
        have e2 : t 2 = t 7 := h₁.trans h7.symm
        exact ⟨e1, e2⟩
      · have hk_ge_1 : k ≥ 1 := by omega
        obtain ⟨ih1, ih2⟩ := ih hk_ge_1
        refine ⟨ih2, ?_⟩
        have h_k2 : k + 2 ≥ 3 := by omega
        have h_k7 : k + 7 ≥ 3 := by omega
        have eq1 := h₂ (k + 2) h_k2
        have eq2 := h₂ (k + 7) h_k7
        have eq1' : t (k + 2) = (5 * t (k + 1) + 1) / (25 * t k) := by
          have H1 : k + 2 - 1 = k + 1 := by omega
          have H2 : k + 2 - 2 = k := by omega
          rw [H1, H2] at eq1
          exact eq1
        have eq2' : t (k + 7) = (5 * t (k + 6) + 1) / (25 * t (k + 5)) := by
          have H1 : k + 7 - 1 = k + 6 := by omega
          have H2 : k + 7 - 2 = k + 5 := by omega
          rw [H1, H2] at eq2
          exact eq2
        rw [eq1', eq2']
        rw [← ih2, ← ih1]

  have h_2020 : t 2020 = t 5 := by
    have H : ∀ m : ℕ, t 5 = t (5 + m * 5) := by
      intro m
      induction' m with m ihm
      · norm_num
      · have : 5 + (m + 1) * 5 = (5 + m * 5) + 5 := by omega
        rw [this]
        have h_ge : 5 + m * 5 ≥ 1 := by omega
        have periodic := (h_period (5 + m * 5) h_ge).1
        rw [← periodic]
        exact ihm
    have H2 := H 403
    have : 5 + 403 * 5 = 2020 := by omega
    rw [this] at H2
    exact H2.symm

  rw [h_2020, h5]
  norm_num
