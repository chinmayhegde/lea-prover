import Mathlib

open Real

lemma aime_helper (x y z m : ℝ)
  (h₀ : 0 < x ∧ 0 < y ∧ 0 < z)
  (h₁ : x * y * z = 1)
  (h₂ : x + 1 / z = 5)
  (h₃ : y + 1 / x = 29)
  (h₄ : z + 1 / y = m) :
  144 * m = 36 := by
  have hx_nz : x ≠ 0 := ne_of_gt h₀.1
  have hy_nz : y ≠ 0 := ne_of_gt h₀.2.1
  have hz_nz : z ≠ 0 := ne_of_gt h₀.2.2

  have h1 : x + x * y = 5 := by
    calc x + x * y = x + x * y * z / z := by rw [mul_div_cancel_right₀ (x*y) hz_nz]
      _ = x + 1 / z := by rw [h₁]
      _ = 5 := h₂

  have h2 : y + y * z = 29 := by
    calc y + y * z = y + x * y * z / x := by
          have : x * y * z = x * (y * z) := by ring
          rw [this, mul_div_cancel_left₀ (y*z) hx_nz]
      _ = y + 1 / x := by rw [h₁]
      _ = 29 := h₃

  have h3 : z + z * x = m := by
    calc z + z * x = z + x * y * z / y := by
          have : x * y * z = y * (z * x) := by ring
          rw [this, mul_div_cancel_left₀ (z*x) hy_nz]
      _ = z + 1 / y := by rw [h₁]
      _ = m := h₄

  calc 144 * m = 145 * m - m := by ring
    _ = (x + x * y) * (y + y * z) * (z + z * x) - m := by rw [h1, h2, h3]; ring
    _ = (x * y * z) * (1 + x + y + z + x * y + y * z + z * x + x * y * z) - m := by ring
    _ = 1 * (1 + (x + x * y) + (y + y * z) + (z + z * x) + x * y * z) - m := by rw [h₁]; ring
    _ = 1 * (1 + 5 + 29 + m + 1) - m := by rw [h1, h2, h3, h₁]
    _ = 36 := by ring
