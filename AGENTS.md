# AGENTS

This file defines workflow rules for coding agents working in this repository.

## Git Rules
- Work in clear, named phases.
- Create a commit after every successful phase.
- Keep commits focused to one phase/goal.
- Verify the phase before committing (tests or a smoke run).
- Keep `python_refactor.md` up to date as progress changes.
- Keep `python/docs/notes/` updated as phase progress changes.
- Do not commit secrets, credentials, or machine-specific files.
- Use descriptive commit messages that explain intent.
- Do not rewrite published history (no force-push or destructive reset).

## Commit Message Style
- Preferred format: `<type>: <why>`
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- Keep message concise and phase-oriented.

## Phase Completion Checklist
- Implementation for the phase is complete.
- Relevant tests/checks pass.
- Documentation/status notes are updated if needed.
- Changes are committed.
