# Changelog

All notable changes to this project are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions
follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.0] - 2026-11-08

Iteration 1: the notebook. Everything known about a project lives on its page, with full
history.

### Added

- Projects: list with stage filter, create, view, edit, archive and restore (M1).
- Notebook entries on the project page (M2):
  - Observations, hypotheses, decisions, notes and questions, each with an evidence
    label, a source and the time it happened.
  - A quick-add bar that saves without a page reload (htmx) and also works without
    JavaScript.
  - A full edit page.
  - Kind filters and a "show deleted" view, with soft delete and restore.
- Hypothesis and question status (M3): Untested, Testing, Supported or Rejected; Open or
  Answered. Changed from the timeline, each change logged. There's a filter for open
  hypotheses and questions.
- Next-step task checklist per project (M5): add, tick, reorder and delete, with
  optional due dates and overdue marking.
- Fault tracker per project (M4): symptom, status (Open, Investigating, Resolved),
  evidence label, next test and resolution, on its own edit page. A fault can't be marked
  Resolved without a written resolution; the database enforces this too.
- Dashboard (M15, partial): projects at the Active stage, plus recent entries, open faults
  and next tasks across all non-archived projects.
- Safe Markdown in entry bodies (N9): markdown-it-py with raw HTML off, then an nh3
  allow-list. Scripts, event handlers and `javascript:` links are stripped.
- Time handling (N7): entry times are stored in UTC with the offset they were entered
  in, and shown in local time. Daylight-saving changes keep entries in order.
- Automatic change log: every insert, update and delete of an audited record is written
  to `change_log` in the same transaction, with before and after values (M2).
- History page for projects, entries, tasks, faults, areas and evidence labels.
- Settings → Lists: add, rename, reorder, retire and restore project areas and evidence
  labels (seeded with `measured`, `observed`, `inferred` and `suspected`).
- htmx, vendored under `static/vendor/` so the app runs offline (N9), and a visible
  message when an in-page request fails.
- Migrations:
  - `0002`: `areas` and `projects`.
  - `0003`: `evidence_labels` and `entries`.
  - `0004`: `tasks`.
  - `0005`: `faults`.

  Every migration downgrades cleanly.

### Fixed

- The change log compares and records datetimes in UTC, so re-saving an unchanged time
  no longer logs a false change.
- Record ids in URLs are range-checked: out-of-range ids get a client error instead of a
  server error.

## [0.0.1] - 2026-11-07

### Added

- Project skeleton: `pyproject.toml`, `src/` package layout, `benchledger` command (Typer).
- Settings from defaults, `~/.config/benchledger/config.toml` and environment variables.
- FastAPI app with a placeholder dashboard in the dark bench theme, and `/healthz`.
- SQLite database with WAL mode and foreign keys; Alembic migration `0001` creating
  `users` (with the owner account) and the add-only `change_log`.
- Tests for config, database, web app and CLI; ruff lint and format checks.
- GitHub Actions CI running lint, format check and tests on every push and pull request.
- ADR-0001 recording the tech stack decision.
