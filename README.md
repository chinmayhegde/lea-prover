# Lea

A minimal Lean 4 theorem proving agent, inspired by [pi](https://github.com/badlogic/pi-mono/tree/main/packages/coding-agent).

Lea translates natural-language math statements into Lean 4 proofs that compile with zero errors and zero `sorry`s.

## Setup

Requires Python 3.13+, [Lean 4](https://leanprover.github.io/lean4/doc/setup.html), and a Google API key.

```bash
# Install
pip install -e .

# Build the Lean workspace (downloads Mathlib — takes a while the first time)
cd workspace && lake build

# Set your API key
export GOOGLE_API_KEY=...
```

## Usage

```bash
lea "Prove that the square root of 2 is irrational"
lea "Prove that for all natural numbers n, n + 0 = n"
lea -v "Prove that 2 + 3 = 5"  # verbose mode
```

## How it works

Lea runs a simple loop:

1. Write a `.lean` file with a first-attempt proof using basic tactics (`norm_num`, `simp`, `omega`, `linarith`, `decide`)
2. Compile with `lean_check`
3. If it compiles — done. If not — read the errors, edit, retry.
4. If stuck, search Mathlib for relevant lemmas.

Five tools: `read_file`, `write_file`, `edit_file`, `lean_check`, `search_mathlib`.
