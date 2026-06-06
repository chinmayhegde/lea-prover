"""Skills — procedural-knowledge markdown fragments injected into the system prompt.

A skill is just a markdown file (a tactic recipe, a naming convention, a
project's house rules). `agent.skills` in config lists the files to inject, in
order; `load_skills` reads them and returns one block to append to the system
prompt. This is the explicit, config-driven generalization of the implicit
`lea.md` append (which still works — see prompt.load_system_prompt).
"""

from pathlib import Path

from .errors import SkillError


def load_skills(paths: list[str]) -> str:
    """Read each skill file and return a single block to append to the prompt.

    Each file's content is placed under a `## Skill: <stem>` header, in the order
    given. Paths are resolved relative to the current working directory. Returns
    "" for an empty list. Raises SkillError if a file is missing or unreadable.
    """
    if not paths:
        return ""
    blocks: list[str] = []
    for p in paths:
        path = Path(p).expanduser()
        try:
            text = path.read_text()
        except OSError as e:
            raise SkillError(f"could not read skill {p!r}: {e}") from e
        blocks.append(f"## Skill: {path.stem}\n{text.strip()}")
    return "\n\n" + "\n\n".join(blocks)
