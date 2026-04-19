inductive PropForm
  | var (n : String) : PropForm
  | not (p : PropForm) : PropForm
  | and (p q : PropForm) : PropForm
  | or (p q : PropForm) : PropForm
  | imp (p q : PropForm) : PropForm

def eval (v : String → Prop) : PropForm → Prop
  | PropForm.var n => v n
  | PropForm.not p => ¬(eval v p)
  | PropForm.and p q => eval v p ∧ eval v q
  | PropForm.or p q => eval v p ∨ eval v q
  | PropForm.imp p q => eval v p → eval v q

def evalCtx (v : String → Prop) : List PropForm → Prop
  | [] => True
  | p :: ps => eval v p ∧ evalCtx v ps

def InCtx (p : PropForm) : List PropForm → Prop
  | [] => False
  | q :: qs => p = q ∨ InCtx p qs

inductive Proof : List PropForm → PropForm → Type
  | hyp (ctx : List PropForm) (p : PropForm) (h : InCtx p ctx) : Proof ctx p
  | and_intro {ctx p q} : Proof ctx p → Proof ctx q → Proof ctx (.and p q)
  | and_elim_l {ctx p q} : Proof ctx (.and p q) → Proof ctx p
  | and_elim_r {ctx p q} : Proof ctx (.and p q) → Proof ctx q
  | or_intro_l {ctx p} (q : PropForm) : Proof ctx p → Proof ctx (.or p q)
  | or_intro_r {ctx q} (p : PropForm) : Proof ctx q → Proof ctx (.or p q)
  | or_elim {ctx p q r} : Proof ctx (.or p q) → Proof (p :: ctx) r → Proof (q :: ctx) r → Proof ctx r
  | imp_intro {ctx p q} : Proof (p :: ctx) q → Proof ctx (.imp p q)
  | imp_elim {ctx p q} : Proof ctx (.imp p q) → Proof ctx p → Proof ctx q
  | not_intro {ctx p q} : Proof (p :: ctx) q → Proof (p :: ctx) (.not q) → Proof ctx (.not p)
  | not_elim {ctx p} (q : PropForm) : Proof ctx p → Proof ctx (.not p) → Proof ctx q

theorem in_ctx_eval {v : String → Prop} {ctx : List PropForm} {p : PropForm} (h : InCtx p ctx) (hctx : evalCtx v ctx) : eval v p := by
  induction ctx with
  | nil => contradiction
  | cons q qs ih =>
    cases h with
    | inl heq =>
      subst heq
      exact hctx.1
    | inr hin =>
      exact ih hin hctx.2

theorem soundness {ctx : List PropForm} {p : PropForm} (pr : Proof ctx p) (v : String → Prop) (hctx : evalCtx v ctx) : eval v p := by
  induction pr with
  | hyp ctx p h => exact in_ctx_eval h hctx
  | and_intro pr1 pr2 ih1 ih2 => exact ⟨ih1 hctx, ih2 hctx⟩
  | and_elim_l pr ih => exact (ih hctx).1
  | and_elim_r pr ih => exact (ih hctx).2
  | or_intro_l q pr ih => exact Or.inl (ih hctx)
  | or_intro_r p pr ih => exact Or.inr (ih hctx)
  | or_elim pr1 pr2 pr3 ih1 ih2 ih3 =>
    cases ih1 hctx with
    | inl hp => exact ih2 ⟨hp, hctx⟩
    | inr hq => exact ih3 ⟨hq, hctx⟩
  | imp_intro pr ih =>
    intro hp
    exact ih ⟨hp, hctx⟩
  | imp_elim pr1 pr2 ih1 ih2 =>
    exact (ih1 hctx) (ih2 hctx)
  | not_intro pr1 pr2 ih1 ih2 =>
    intro hp
    have hq := ih1 ⟨hp, hctx⟩
    have hnq := ih2 ⟨hp, hctx⟩
    exact hnq hq
  | not_elim q pr1 pr2 ih1 ih2 =>
    have hp := ih1 hctx
    have hnp := ih2 hctx
    contradiction
