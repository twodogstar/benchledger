# BenchLedger — Backlog: Iterations 1–3

Drafted Nov 8, 2026 from Requirements v1.0 and Design v0.1. The owner edits this file; the hive
works it top to bottom (see "Work session mode" in `CLAUDE.md`).

**How to read it**

- Each milestone is one iteration, on its own branch, ending in a release tag the owner makes.
- Each item is one commit. `Accept:` is the test that proves it is done.
- 🧑 marks owner-only steps. The hive stops when it reaches one.
- Dependencies named in Design v0.1 (markdown-it-py, nh3, numpy, uPlot, htmx, restic) are
  approved. Anything else is a stop-and-ask.

## Decisions needed before running

Defaults are filled in so the hive can work. Change any line you disagree with before starting.

| # | Question | Default |
| --- | --- | --- |
| D1 | Evidence labels for entries and faults (M2, M4) | `measured`, `observed`, `inferred`, `suspected`, managed in Settings → Lists like areas |
| D2 | How readings are stored | `REAL` (float64) in SQLite. A double holds 15+ significant digits, more than the 34401A's 6½. The raw file stays the exact record (N3). Recorded as ADR-0002 |
| D3 | Gap threshold (R4) | A jump in `elapsed_s` more than 3 × the run's median interval |
| D4 | Uploading a run package | A `.zip` of the package folder, or a single legacy `.csv`. Max 200 MB, set in config |
| D5 | Branches | One branch per milestone: `feat/iter1-notebook`, `feat/iter2-runs`, `feat/iter3-backups`. One PR per milestone |

---

## Milestone 1 — The notebook (Iteration 1 → v0.1.0)

Goal: everything you know about a project lives on its page, with full history.
Branch: `feat/iter1-notebook` from `main`.

- [x] 🧑 **1.0 Prep.** `uv add markdown-it-py nh3`. Vendor htmx (no CDN; N9 says it must run
  offline):
  `mkdir -p src/benchledger/web/static/vendor && curl -L -o src/benchledger/web/static/vendor/htmx.min.js https://unpkg.com/htmx.org@2/dist/htmx.min.js`.
  Commit both.
- [x] **1.1 Entry model.** Migration `0003`: `entries` (project, kind = observation / hypothesis /
  decision / note / question, title, body Markdown, evidence label, source, status, occurred_at
  UTC, author, soft delete), audited through the change log. Evidence labels as a managed list (D1).
  Accept: migration upgrades and downgrades cleanly; creating and editing an entry writes change-log rows.
- [x] **1.2 Entry service.** Create, edit, soft-delete, restore, and a timeline per project
  (newest first, filter by kind). Hypotheses default to `Untested`, questions to `Open`.
  Accept: unit tests for each operation, including "edit keeps the old text in history".
- [x] **1.3 Safe Markdown.** Render entry bodies with markdown-it-py, cleaned with nh3.
  Accept: tests show `<script>`, `onerror=` and `javascript:` links are stripped (N9).
- [x] **1.4 Notebook on the project page.** Entry timeline with kind and evidence badges, a quick-add
  bar (htmx, no page reload), a full edit page, and a History link per entry. Wire htmx into `base.html`.
  Accept: web tests add, edit and delete an entry through the routes; the page escapes user text.
- [x] **1.5 Hypotheses and questions (M3).** Status changes (Untested, Testing, Supported, Rejected;
  questions Open/Answered) from the timeline, each logged. A filter for open hypotheses and questions.
  Accept: a status change appears in History with before and after.
- [ ] **1.6 Tasks (M5).** Migration `0004`: `tasks` (project, text, done, due date optional, order,
  author, soft delete). A checklist on the project page: add, tick, reorder, delete.
  Accept: service and web tests; ticking a task is logged.
- [ ] **1.7 Faults (M4).** Migration `0005`: `faults` (project, symptom, status Open / Investigating /
  Resolved, evidence label, next test, resolution, author, soft delete). Faults section with its own
  edit page. Accept: service and web tests; resolving requires a resolution text.
- [ ] **1.8 Dashboard (M15 partial).** Replace the placeholder: active projects, recent entries,
  open faults, next tasks. Accept: web test with seeded data shows each tile.
- [ ] **1.9 Release prep.** Update CHANGELOG, README feature list, and the design's screens table status.
  Accept: `uv run pytest`, `ruff check`, `ruff format --check` all green. Then STOP.
- [ ] 🧑 **1.10** Review, push, PR, merge, tag `v0.1.0`, screenshots for the README.

---

## Milestone 2 — Runs and data (Iteration 2 → v0.2.0)

Goal: import the Oct 31 run, see it on its own page, chart it.
Branch: `feat/iter2-runs` from `main` after v0.1.0.

- [ ] 🧑 **2.0 Prep.** Merge `feat/m8-legacy-import` (parser + `.gitattributes` for
  `tests/fixtures/** -text`) after a real `uv run pytest` passes. `uv add numpy`. Vendor uPlot:
  `curl -L -o src/benchledger/web/static/vendor/uPlot.iife.min.js https://unpkg.com/uplot@1/dist/uPlot.iife.min.js`
  and `curl -L -o src/benchledger/web/static/vendor/uPlot.min.css https://unpkg.com/uplot@1/dist/uPlot.min.css`.
- [ ] **2.1 ADR-0002: storing readings** (D2), in `docs/adr/`. Accept: the file exists and states
  the precision argument and the "raw file is the record" rule.
- [ ] **2.2 File store.** `files/ab/cd/<sha256>` under the data folder; `files` and `file_links`
  tables (role: raw data, run package, photo…). Writes are atomic, files are read-only after
  storing, an existing hash is never overwritten. Accept: tests for store, dedupe, checksum verify (N3).
- [ ] **2.3 Run models.** Migration: `runs`, `channels` (name, unit, instrument text, description),
  `readings` (channel, t_utc, t_offset, elapsed_s, value; index on channel + elapsed),
  `run_events`, plus run warnings and end status. Accept: migration round-trips; a 1,000-row insert test.
- [ ] **2.4 Legacy import service (M8, R1, R4, R5).** Store the raw file, create the run
  (end status `unknown (legacy)`), channel `volts` in V, readings, parser warnings, detected gaps
  (D3) as events. The same file twice is refused by checksum. Accept: importing the Oct 31 fixture
  gives 1,224 readings; a second import is refused; a fixture with a hole produces a gap event.
- [ ] **2.5 Run package spec (R6).** Move the spec from the design into `docs/run-package-spec.md`.
  Build a v1 fixture package from the Oct 31 data, with temperature and humidity channels as
  test-only made-up values clearly labelled synthetic.
- [ ] **2.6 Run package v1 import (R2, R3).** Read `run.json`, `data.csv`, `events.csv`; refuse
  unknown `format_version`; `running` with no end becomes `incomplete`; duplicate `run_id` refused.
  Accept: tests for the fixture plus each refusal.
- [ ] **2.7 CLI.** `benchledger import PATH` for a folder, zip or legacy CSV, printing the preview
  and asking to confirm (`--yes` to skip). Accept: CLI tests.
- [ ] **2.8 Import page.** Upload (D4) → preview (metadata, channels, row count, gaps, checksum,
  duplicate warning) → confirm. Checks file type and size (N9). Accept: web tests for good,
  duplicate, oversized and wrong-type uploads.
- [ ] **2.9 Runs tab and run page (M7).** Project runs table; run page with metadata, instrument
  settings, warnings, events and files. Accept: web tests with the imported fixture.
- [ ] **2.10 Chart data endpoint (M9, N2).** JSON for chosen channels over a time window, thinned
  to about 2,000 points per channel with min/max per bucket so spikes survive; stored data untouched.
  Accept: tests that a spike inside a bucket still appears; a 2.3-million-reading synthetic channel
  answers in under 1 s on the laptop (mark the test `slow`, skipped in CI).
- [ ] **2.11 Chart on the run page.** uPlot multi-channel chart, shared time axis, zoom refetches
  finer data, gaps and events marked. Accept: page loads offline; manual check listed in the PR template.
- [ ] **2.12 Release prep.** CHANGELOG, README. All checks green. Then STOP.
- [ ] 🧑 **2.13** Import the real Oct 31 file through the page, review, push, merge, tag `v0.2.0`.

---

## Milestone 3 — Backups (Iteration 3 → v0.3.0)

Goal: data can't be lost before real runs pile up. The hive builds the tooling; the owner wires
up drives, accounts and timers.
Branch: `feat/iter3-backups` from `main` after v0.2.0.

- [ ] 🧑 **3.0 Prep.** `sudo apt install restic`. Choose the cloud provider (open question in the
  design) — not needed until 3.7.
- [ ] **3.1 Snapshot (B2).** `benchledger snapshot` writes a consistent copy of the database with
  SQLite's backup API while the app is running. Accept: test snapshots during writes and the copy
  passes `PRAGMA integrity_check`.
- [ ] **3.2 Full export (M16).** `benchledger export` → one dated zip: database snapshot, files
  folder, config without secrets, and a manifest of SHA-256 checksums. Accept: test unzips and
  verifies every checksum.
- [ ] **3.3 Backup command (B1, B3).** `benchledger backup --target usb|cloud` runs snapshot, then
  restic, with repository locations in config and the password from an environment file outside
  the repo (never logged). Accept: tests with restic mocked; a test that no secret appears in logs.
- [ ] **3.4 Backup records and dashboard (B7).** A `backup_runs` table (target, start, end, result,
  snapshot id). Dashboard tile per target; warning after 48 hours without success. Accept: web tests
  for fresh, stale and failed states.
- [ ] **3.5 Verify and restore drill (B8).** `benchledger verify --target …` runs `restic check`,
  restores a sample to a temp folder, compares checksums, and records the result. Accept: tests
  with restic mocked; a failed comparison is recorded as a failure.
- [ ] **3.6 Retention (B5).** `benchledger prune` applying 7 daily / 4 weekly / 12 monthly /
  yearly, refusing to run without the separate admin credential (B4). Accept: tests check the
  restic arguments and the refusal.
- [ ] **3.7 Deploy files and runbook.** `deploy/` with systemd user units and timers (serve,
  nightly backup, monthly verify) and `docs/backup.md`: USB setup with LUKS, cloud bucket with an
  append-only key, where the password lives (B6), and step-by-step restore. Accept: units pass
  `systemd-analyze verify` when available.
- [ ] **3.8 Release prep.** CHANGELOG, README. All checks green. Then STOP.
- [ ] 🧑 **3.9** Set up the USB drive and cloud bucket, install the timers, run a real restore
  drill, push, merge, tag `v0.3.0`.

---

**Next after these:** Iteration 4, statistics (M10, M11: windowed stats, ppm from baseline, drift,
Allan deviation checked against `allantools`, tempco), then 5 (instruments, M6) and 6 (files,
templates, reports, search).
