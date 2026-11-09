# BenchLedger
Electronics-lab project notebook. Stack: FastAPI + server-rendered pages (Jinja2) + htmx,
SQLite via SQLAlchemy and Alembic, Typer CLI. Python, managed with uv.
Requirements: docs/requirements.md · Design: docs/design.md · Work queue: docs/BACKLOG.md

## Workflow rules
- Claude writes code and tests and commits them locally. The owner reviews, pushes,
  opens PRs, merges and tags releases.
- Never push, merge, rebase, tag, reset --hard, force anything, or change git config.
- Never use `git commit --no-verify` (or `-n`); never skip or bypass hooks.
- Never commit on main. Work only on the milestone branch named in docs/BACKLOG.md.
- Stage files by name (no `git add -A` or `git add .`). Never commit data files, .env,
  passwords, keys or anything from the data folder.
- Commit messages: Conventional Commits with requirement IDs, e.g.
  `feat: entry timeline on project page (M2)`. One backlog item per commit.
- Measurements must carry units and uncertainty; never silently drop either.
- Escape all user text in pages (N9). Timestamps stored in UTC with the source offset (N7).
- Every schema change is an Alembic migration that also downgrades.

## Change loop (every code change)
After every code change: run the reviewer subagent and fix high/medium findings, then run
the tester subagent. Checks that must pass:
  uv run pytest
  uv run ruff check .
  uv run ruff format --check .

## Work session mode
When told to "work the backlog":
1. Make sure you are on the milestone branch from docs/BACKLOG.md (create it from main with
   `git switch -c <branch>` only if it does not exist yet). Check `git status` is clean.
2. Take the first unchecked item. Plan it briefly.
3. Implement it with tests.
4. Run the change loop above. Everything must pass.
5. Append to docs/WORKLOG.md: date, item, files changed, judgment calls, and:
   - reviewer findings grouped by severity (high/medium/low, "none" if empty) and what
     was fixed for each (or why it was left)
   - tester results: pass/fail counts (e.g. "42 passed, 0 failed") plus ruff check and
     ruff format --check results
6. Tick the item in docs/BACKLOG.md.
7. Commit the item's files, BACKLOG.md and WORKLOG.md in one commit.
8. Continue with the next item.

STOP and wait for the owner when:
- the next item is marked 🧑 (owner step), or the milestone's release-prep item is done
- tests or lint still fail after 2 fix attempts (leave the work uncommitted, explain in WORKLOG)
- a requirements or design question comes up that the docs and backlog decisions don't answer
- a dependency not named in docs/design.md is needed
- the item limit given for the session is reached
When stopping, give a short summary: items done, commits made, anything the owner must decide.
