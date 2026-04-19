import Mathlib.Data.List.Basic

inductive Expr
| const : Nat → Expr
| add : Expr → Expr → Expr
| mul : Expr → Expr → Expr
deriving Repr

def eval : Expr → Nat
| Expr.const n => n
| Expr.add e1 e2 => eval e1 + eval e2
| Expr.mul e1 e2 => eval e1 * eval e2

inductive Inst
| push : Nat → Inst
| add : Inst
| mul : Inst
deriving Repr

def exec : Inst → List Nat → List Nat
| Inst.push n, stack => n :: stack
| Inst.add, x :: y :: rest => (x + y) :: rest
| Inst.add, stack => stack
| Inst.mul, x :: y :: rest => (x * y) :: rest
| Inst.mul, stack => stack

def execList : List Inst → List Nat → List Nat
| [], stack => stack
| i :: is, stack => execList is (exec i stack)

@[simp]
theorem execList_nil (stack : List Nat) : execList [] stack = stack := rfl

@[simp]
theorem execList_cons (i : Inst) (is : List Inst) (stack : List Nat) :
  execList (i :: is) stack = execList is (exec i stack) := rfl

@[simp]
theorem execList_append (is1 is2 : List Inst) (stack : List Nat) :
  execList (is1 ++ is2) stack = execList is2 (execList is1 stack) := by
  induction is1 generalizing stack with
  | nil => rfl
  | cons i is ih => simp [ih]

def compile : Expr → List Inst
| Expr.const n => [Inst.push n]
| Expr.add e1 e2 => compile e2 ++ compile e1 ++ [Inst.add]
| Expr.mul e1 e2 => compile e2 ++ compile e1 ++ [Inst.mul]

theorem compile_correct (e : Expr) (stack : List Nat) :
  execList (compile e) stack = eval e :: stack := by
  induction e generalizing stack with
  | const n => rfl
  | add e1 e2 ih1 ih2 =>
    simp [compile, eval, ih1, ih2]
    rfl
  | mul e1 e2 ih1 ih2 =>
    simp [compile, eval, ih1, ih2]
    rfl
