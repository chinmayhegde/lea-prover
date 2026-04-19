def ackermann : Nat → Nat → Nat
| 0, n => n + 1
| m + 1, 0 => ackermann m 1
| m + 1, n + 1 => ackermann m (ackermann (m + 1) n)

theorem ack_zero (n : Nat) : ackermann 0 n = n + 1 := by rw [ackermann]
theorem ack_succ_zero (m : Nat) : ackermann (m + 1) 0 = ackermann m 1 := by rw [ackermann]
theorem ack_succ_succ (m n : Nat) : ackermann (m + 1) (n + 1) = ackermann m (ackermann (m + 1) n) := by rw [ackermann]

theorem ack_mono_and_gt (m : Nat) : (∀ n, ackermann m n > n) ∧ (∀ n, ackermann m (n + 1) > ackermann m n) := by
  induction m with
  | zero =>
    constructor
    · intro n; rw [ack_zero]; omega
    · intro n; rw [ack_zero, ack_zero]; omega
  | succ m ih =>
    have h_m_gt : ∀ x, ackermann m x > x := ih.1
    have h_mono : ∀ n, ackermann (m + 1) (n + 1) > ackermann (m + 1) n := by
      intro n
      rw [ack_succ_succ]
      exact h_m_gt _
    have h_gt : ∀ n, ackermann (m + 1) n > n := by
      intro n
      induction n with
      | zero =>
        rw [ack_succ_zero]
        have h1 := h_m_gt 1
        omega
      | succ n ih_n =>
        have step := h_mono n
        omega
    exact ⟨h_gt, h_mono⟩

theorem ackermann_gt_n (m n : Nat) : ackermann m n > n :=
  (ack_mono_and_gt m).1 n

theorem ackermann_mono (m n : Nat) : ackermann m (n + 1) > ackermann m n :=
  (ack_mono_and_gt m).2 n

theorem ack_1 (n : Nat) : ackermann 1 n = n + 2 := by
  induction n with
  | zero => rw [ack_succ_zero, ack_zero]
  | succ n ih => rw [ack_succ_succ, ih, ack_zero]

theorem ack_2 (n : Nat) : ackermann 2 n = 2 * n + 3 := by
  induction n with
  | zero => rw [ack_succ_zero, ack_1]
  | succ n ih => rw [ack_succ_succ, ih, ack_1]; omega

theorem ack_3_0 : ackermann 3 0 = 5 := by rw [ack_succ_zero, ack_2]
theorem ack_3_1 : ackermann 3 1 = 13 := by rw [ack_succ_succ, ack_3_0, ack_2]
theorem ack_3_2 : ackermann 3 2 = 29 := by rw [ack_succ_succ, ack_3_1, ack_2]
theorem ack_3_3 : ackermann 3 3 = 61 := by rw [ack_succ_succ, ack_3_2, ack_2]
theorem ack_3_4 : ackermann 3 4 = 125 := by rw [ack_succ_succ, ack_3_3, ack_2]
theorem ack_3_5 : ackermann 3 5 = 253 := by rw [ack_succ_succ, ack_3_4, ack_2]
theorem ack_3_6 : ackermann 3 6 = 509 := by rw [ack_succ_succ, ack_3_5, ack_2]
theorem ack_3_7 : ackermann 3 7 = 1021 := by rw [ack_succ_succ, ack_3_6, ack_2]
theorem ack_3_8 : ackermann 3 8 = 2045 := by rw [ack_succ_succ, ack_3_7, ack_2]
theorem ack_3_9 : ackermann 3 9 = 4093 := by rw [ack_succ_succ, ack_3_8, ack_2]
theorem ack_3_10 : ackermann 3 10 = 8189 := by rw [ack_succ_succ, ack_3_9, ack_2]
theorem ack_3_11 : ackermann 3 11 = 16381 := by rw [ack_succ_succ, ack_3_10, ack_2]
theorem ack_3_12 : ackermann 3 12 = 32765 := by rw [ack_succ_succ, ack_3_11, ack_2]
theorem ack_3_13 : ackermann 3 13 = 65533 := by rw [ack_succ_succ, ack_3_12, ack_2]

theorem ack_4_0 : ackermann 4 0 = 13 := by
  rw [ack_succ_zero]
  exact ack_3_1

theorem ackermann_4_1 : ackermann 4 1 = 65533 := by
  rw [ack_succ_succ, ack_4_0]
  exact ack_3_13
