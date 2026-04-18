import Mathlib

theorem cube_root_3_irrational : Irrational ((3 : ℝ) ^ (1 / 3 : ℝ)) := by
  have hxr : ((3 : ℝ) ^ (1 / 3 : ℝ)) ^ 3 = (3 : ℤ) := by
    rw [← Real.rpow_natCast, ← Real.rpow_mul]
    · norm_num
    · norm_num
  have hnpos : 0 < 3 := by norm_num
  apply irrational_nrt_of_notint_nrt 3 3 hxr
  · rintro ⟨y, hy⟩
    have hy3 : (y : ℝ) ^ 3 = 3 := by
      rw [← hy]
      exact hxr
    have hy3_int : y ^ 3 = 3 := by
      exact_mod_cast hy3
    -- now we have `y ^ 3 = 3` in ℤ, which is impossible
    sorry
  · exact hnpos
