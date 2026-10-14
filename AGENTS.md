# Development instructions

- Use the project-local Python 3.11 `.venv` for every package installation and command.
  Never install Python packages globally or with `--user`.
- Use `.venv/Scripts/python.exe -m pip`, not an unqualified pip command.
- Keep inference outside UI widgets; preserve authoritative non-destructive state.
- Keep weights, personal images, caches and generated output out of Git.
- Never invent masks, identity scores, model availability or benchmark numbers.
- Update docs/STATUS.md with verified functionality and limitations.
- Run meaningful tests and a desktop launch smoke test after relevant changes.
- Work in the current agent; do not spawn sub-agents unless the user requests delegation.
