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

## 2026-11-08 · 1.2 Entry service

**Files changed**
- `src/benchledger/timeutil.py`: new. N7 helpers convert a local form time to UTC plus the
  source offset, read values back as UTC, and handle DST edges and the year range.
- `src/benchledger/services/entries.py`: new. Create, edit, soft-delete, restore, get, and a
  timeline that is newest first, can filter by kind and includes deleted entries on request.
- `src/benchledger/services/__init__.py`: `parse_id`, a safe form-id parser.
- `src/benchledger/services/projects.py`: uses `parse_id` (same bug as entries, see below).
- `src/benchledger/db/audit.py`: datetimes are logged as UTC, and an update is detected by
  comparing the logged text.
- `tests/test_entries.py`: new.

**Reviewer findings**

Round 1:
- High: none.
- Medium, all fixed:
  - Editing an entry stored in the repeated fall-back hour (01:30 PST) moved it back an hour.
    Fixed: a resubmitted time that matches what the form showed is kept as stored.
  - Odd ids (`"²"`, 30 digits) and extreme years (`9999-12-31`) gave a 500. Fixed:
    `parse_id`, and years are limited to 1900–2200. The same id bug in `projects.py`
    (area id) is fixed too.
  - Every edit logged a false `occurred_at` change: SQLite returns naive datetimes, and a
    naive datetime never equals an aware one. Fixed in `audit.py`, so it applies to every
    table.
- Low, all fixed:
  - `delete_entry` now rejects a naive `at`.
  - A time in the spring-forward gap now gets an offset consistent with its instant.
  - The body is capped at 100,000 characters.
  - Fields passed as `None` are handled.
  - Editing a deleted entry is refused.
  - Added tests for no-op repeat delete and restore, and for each fix.

Round 2 (re-review):
- High: none. Medium: none.
- Low, fixed: the `parse_id` docstring wording.
- Low, deferred:
  - The "Restore before editing" error has no form field: 1.4's page must show form-level
    errors.
  - Windows `OSError` for pre-1970 times: Linux-only app, ignored.
- Low, accepted: an entry at 01:30 PST can't be deliberately moved to 01:30 PDT through the
  form. This follows from the fold=0 choice.

**Tester:** pytest 91 passed, 0 failed, 0 errors, 0 skipped, 1 warning (the same Starlette
TestClient deprecation as before). `ruff check` passed; `ruff format --check` passed.

**Judgment calls**
- **Local time zone:** "local" (N7 display, form input) is the machine's own zone; there's no
  config setting for it.
- **Ambiguous fall-back hour:** a time typed in the repeated hour is read as its first
  occurrence (PDT). The second occurrence can only be stored by an import, not typed.
- **Blank time:** on create, the time defaults to now (to the minute); on edit, a blank time
  keeps the existing one.
- **Kind change:** if an edit changes the kind, a status that no longer fits resets to the new
  kind's default (or none).
- **Audit fix:** the `audit.py` change affects all tables. A naive datetime and an aware one
  that are the same instant are no longer logged as a change.

## 2026-11-08 · 1.3 Safe Markdown

**Files changed**
- `src/benchledger/web/markdown.py`: new. markdown-it-py (CommonMark + tables +
  strikethrough, raw HTML off) followed by an nh3 allow-list clean; links limited to
  http/https/mailto, with `rel="noopener noreferrer nofollow"`.
- `src/benchledger/web/deps.py`: registers the `markdown` Jinja filter.
- `tests/test_markdown.py`: new.

**Reviewer findings**

Round 1:
- High: none.
- Medium: none.
- Low, fixed:
  - Documented that the output is safe as element content only.
  - Images silently vanished: they now render as a link labelled "image: alt".
  - Extra regression tests: tab- and entity-obfuscated `javascript:`, a style value with a
    non-alignment property, a bad link in a table cell, relative links.
- Low, not changed:
  - Relative and protocol-relative links stay allowed, so entries can link to
    `/projects/…`. Not script execution.
  - No `class` on `code` (no syntax highlighting yet).
  - linkify off: bare URLs aren't clickable.

Round 2 (re-review of the image rule):
- High: none.
- Medium: none.
- Low, not changed: the render-rule parameters are unannotated; the image title is dropped.

**Tester:** pytest 118 passed, 0 failed, 0 errors, 0 skipped, 1 warning (the same Starlette
TestClient deprecation as before). `ruff check` passed; `ruff format --check` passed.

**Judgment calls**
- **Images:** not displayed until M12 provides local file storage. Loading external images
  would need internet access (N9) and could track reads.
- **`markupsafe`:** imported directly. It is a required dependency of Jinja2, already
  installed, so this is not a new dependency.
- **Two failing first-draft tests:** both outputs were already safe; the assertions were
  wrong. One looked for the `onerror=` text inside escaped output; the other put a `<th>`
  outside a table. Both were corrected, not the code.
