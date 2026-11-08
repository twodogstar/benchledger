# BenchLedger — Work log

One entry per backlog item, newest at the bottom. Written by Claude during work sessions
(see "Work session mode" in `CLAUDE.md`).

## 2026-11-08 · 1.1 Entry model

Branch `feat/iter1-notebook`. Before starting, `CLAUDE.md` (worklog and `--no-verify` rules) and
`.claude/settings.json` (removed the `uv run python` allow rule) were uncommitted on `main`.
The owner chose to commit them as the first commit on this branch.

**Files changed**
- `src/benchledger/db/models.py`: `EvidenceLabel` and `Entry` models, `ENTRY_KINDS`
- `src/benchledger/migrations/versions/0003_entries.py`: new; seeds the D1 labels
- `src/benchledger/services/lists.py`: new; generic managed-list service
- `src/benchledger/services/areas.py`: now thin wrappers over `lists.py` (same API)
- `src/benchledger/services/history.py`, `web/routes/history.py`, `web/templates/history.html`:
  evidence-label history
- `src/benchledger/web/routes/settings.py`, `web/templates/settings/lists.html`: one section per
  list, routes under `/settings/<list_name>/…` (old `/settings/areas/…` URLs unchanged)
- `tests/test_entries_model.py`: new
- `tests/conftest.py`, `tests/test_db.py`, `tests/test_app.py`, `tests/test_cli.py`: a
  `head_revision` fixture replaces the hard-coded `"0002"`

**Reviewer findings**
- High: none.
- Medium: none.
- Low, fixed:
  - `move` accepted any direction; it now gives a 400 unless the direction is `up` or `down`.
  - Kind and offset were unconstrained; the database now refuses an unknown kind and any
    offset outside ±14 h (CHECK constraints in 0003).
  - List service functions are now type-annotated, and the dead `"item"` fallback is removed.
  - A rejected rename now keeps the typed name in the box.
  - The catch-all route got a comment.
  - Added tests for soft-delete logging and for the seeded labels surviving a migration
    round trip.
- Low, deferred:
  - Always convert `occurred_at` to UTC and reject naive datetimes: in 1.2, where the service
    writes it.
  - Add entries to the History view, with a title fallback for `record.name`: in 1.4.

**Tester:** pytest 58 passed, 0 failed, 0 errors, 0 skipped, 1 warning (Starlette's `httpx`
TestClient deprecation, already present before this item). `ruff check` passed;
`ruff format --check` passed.

**Judgment calls**
- **Evidence label is optional** on an entry (nullable). A note or question often has no
  evidence basis, and M2 doesn't say every entry must have one.
- **N7 offset:** stored as `occurred_offset_min`, the UTC offset in minutes at the time the
  entry was dated.
- **Managed lists:** made the areas list code generic instead of copying it for evidence
  labels. Faults (1.7) can reuse the same labels.
- **Database-level checks:** kinds are also enforced by the database, so adding a kind later
  needs a migration.
