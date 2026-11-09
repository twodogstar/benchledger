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

## 2026-11-08 · 1.4 Notebook on the project page

**Files changed**
- `src/benchledger/web/routes/entries.py`: new. Quick-add, edit page, delete and restore.
  htmx requests get the notebook fragment; plain posts are redirected.
- `src/benchledger/web/routes/projects.py`: the project page renders the notebook, with
  `?kind=` and `?deleted=1`.
- `src/benchledger/app.py`: registers the entries router.
- `src/benchledger/web/templates/projects/_notebook.html`: new. Filter chips, quick-add bar,
  timeline with kind, status and evidence badges, and Edit, History and Delete or Restore
  per entry.
- `src/benchledger/web/templates/entries/form.html`: new full edit page.
- `src/benchledger/web/templates/projects/detail.html`: the notebook replaces the placeholder.
- `src/benchledger/web/templates/base.html`: loads the vendored htmx and `js/benchledger.js`,
  and has an error box.
- `src/benchledger/web/static/js/benchledger.js`: new. Shows a message when an htmx request
  fails, using `textContent` only.
- `src/benchledger/web/static/css/benchledger.css`: notebook, badge and Markdown styles.
- `src/benchledger/web/templates/history.html`, `web/routes/history.py`,
  `services/history.py`: History covers entries, with a link back to the project.
- `src/benchledger/timeutil.py`: `display`, `display_utc`, `iso_utc`, `format_offset`.
- `src/benchledger/web/deps.py`: `localtime`, `utctime`, `isotime` and `utcoffset` filters,
  and a `RecordId` path type bounded to SQLite's integer range.
- `src/benchledger/web/routes/settings.py`: uses `RecordId`.
- `tests/test_web_entries.py`: new.

**Reviewer findings**
- High: none.
- Medium: none.
- Low, fixed:
  - An htmx add, delete or restore reset the kind filter and the "show deleted" view.
    Hidden view fields now keep it, and the plain-form redirect keeps it too.
  - `<time datetime>` wasn't machine-readable; it now uses ISO UTC.
  - The edit page's status hint referred to controls that don't exist yet; reworded.
  - htmx errors were invisible; a message box now appears.
  - The edit form for a deleted entry led to an unsaveable form; it now redirects to the
    deleted view.
  - Huge ids gave a 500; `RecordId` bounds them (422).
  - Test gaps: retired-label path, combined filters, and escaping on the edit form and the
    History page.
- Low, not changed:
  - Changing the kind drops the status without a warning. It is logged, and the edit page
    now explains it.
  - A whitespace-only title passes the browser's `required` check. The server refuses it
    with a message.

**Tester:** pytest 146 passed, 0 failed, 0 errors, 0 skipped, 1 warning (the same Starlette
TestClient deprecation as before). `ruff check` passed; `ruff format --check` passed.

The tester reported that a block of "MCP Server Instructions" showed up in its pytest
output. I checked: nothing in the repo or `.venv` contains that text, and pytest's output
mentions nothing about MCP. It most likely came from the subagent's own session context,
not the project. The subagent didn't act on it.

**Judgment calls**
- **htmx validation errors:** they come back as 200 with the errors in the fragment, because
  htmx only swaps 2xx. Plain form posts still get a 400 page.
- **Small script file:** `static/js/benchledger.js` is plain JS with no build step and no
  new dependency.
- **Ids out of range:** they return 422, FastAPI's validation status, rather than 404.

## 2026-11-08 · 1.5 Hypotheses and questions (M3)

**Files changed**
- `src/benchledger/services/entries.py`: `set_status` (validated per kind; refused on
  deleted entries), `OPEN_STATUSES`, the `OPEN_FILTER` timeline branch, `PLURALS`.
- `src/benchledger/web/routes/entries.py`: `POST …/entries/{id}/status`, `valid_filter`,
  and statuses, plurals and the open filter added to the notebook context.
- `src/benchledger/web/templates/projects/_notebook.html`: status picker with a Set button;
  "Open hypotheses & questions" chip; plural chip labels; the timeline is wrapped in
  `#timeline`, and per-entry actions swap only that part.
- `src/benchledger/web/templates/entries/form.html`: hint about where status changes.
- `src/benchledger/web/static/css/benchledger.css`: status picker styles.
- `tests/test_status.py`: new.

**Reviewer findings**

Round 1:
- High: none.
- Medium, both fixed:
  - Saving on `change` logged every status an arrow key passed, and the swap lost focus.
    The status now saves only with the Set button, and the select has a stable id.
  - A status change, delete or restore re-rendered the whole notebook and wiped a
    half-typed quick-add draft. Those actions now replace only `#timeline`, using
    `hx-select`.
- Low, fixed:
  - `in_()` was passed a dict; it now gets an explicit list, and the open statuses are sorted.
  - The chip read "Hypothesiss"; plural labels fixed.
  - Misleading comment on the 400 path corrected.
  - Test gaps: view kept through htmx, deleted entry gets a 400, a same-status change logs
    nothing, a kind change resets the status and is logged.
- Low, not changed: a stale second tab can overwrite a newer status without a warning.
  History records both changes, so nothing is lost.

Round 2 (re-review):
- High: none.
- Medium: none.
- Low, fixed: the template header comment; the empty-state wording uses plurals.
- Low, accepted: `hx-select` would swap in empty content if a response lacked `#timeline`.
  Every route returns the full notebook, so this can't happen today.

**Tester:** pytest 163 passed, 0 failed, 0 errors, 0 skipped, 1 warning (the same Starlette
TestClient deprecation as before). `ruff check` passed; `ruff format --check` passed.

**Judgment calls**
- **"Open" filter:** shows hypotheses that are Untested or Testing, plus questions that
  are Open.
- **Status on the edit page:** it isn't editable there. It changes only from the timeline,
  so each change is a single deliberate step in History.

## 2026-11-08 · 1.6 Tasks (M5)

**Files changed**
- `src/benchledger/migrations/versions/0004_tasks.py`: new; creates `tasks`, downgrade
  drops it.
- `src/benchledger/db/models.py`: `Task` model.
- `src/benchledger/services/tasks.py`: new. Checklist (open first, then done), create
  with an optional due date, toggle done, move, soft delete, `is_overdue`.
- `src/benchledger/web/routes/tasks.py`: new. Add, done, move and delete routes; htmx
  gets the fragment, plain forms get a redirect.
- `src/benchledger/web/templates/projects/_tasks.html`: new "Next steps" panel.
- `src/benchledger/web/project_page.py`: new. Shared project-page contexts and helpers,
  moved out of `routes/entries.py` so the entry and task route modules don't import each
  other.
- `src/benchledger/web/routes/entries.py`, `routes/projects.py`: use `project_page`.
  `projects.py` drops its duplicate `_project_or_404`.
- `src/benchledger/web/routes/history.py`, `services/history.py`,
  `templates/history.html`: tasks in History. `_describe()` builds each record's label
  and back link in one place, replacing per-table template branches.
- `src/benchledger/app.py`, `templates/projects/detail.html`,
  `static/css/benchledger.css`: router, include and styles.
- `tests/test_tasks.py`: new.

**Reviewer findings**
- High: none.
- Medium: none.
- Low, fixed:
  - Moving a task renumbered every open task, adding spurious History rows. Now only
    the two tasks that swap are written, unless their positions tie.
  - A bad or missing `done` value was treated as "untick". Anything other than `1` or
    empty now gets a 400.
  - The tick button combined `aria-pressed` with an action label; it now has a fixed
    label ("Done: …").
  - Migration server defaults differ from the model's Python defaults; explained in a
    comment.
  - The duplicate `_project_or_404` was removed.
  - Type hints added on `task_or_404`.
- Low, not changed:
  - With JavaScript off, delete has no confirm. It's a soft delete and is logged.
  - Focus is lost after the `#tasks` swap. Optional, left for now.

**Tester:** pytest 183 passed, 0 failed, 0 errors, 0 skipped, 1 warning (the same Starlette
TestClient deprecation as before). `ruff check` passed; `ruff format --check` passed.

**Judgment calls**
- **No task restore button:** the item asks for add, tick, reorder and delete. Deleted
  tasks stay in the database and History.
- **Due date:** a plain calendar date with no time zone. "Overdue" compares it with
  today's local date.
- **No editing task text:** not in the item. Delete and re-add instead.
- **Checklist placement:** shown above the notebook so next steps are visible without
  scrolling past the timeline.

## 2026-11-08 · 1.7 Faults (M4)

**Files changed**
- `src/benchledger/migrations/versions/0005_faults.py`: new. Adds `faults` with CHECK
  constraints: the status must be valid, and a Resolved fault needs a non-blank
  resolution. The downgrade drops the table.
- `src/benchledger/db/models.py`: `Fault` model and `FAULT_STATUSES`. The model's status
  CHECK is built from that list.
- `src/benchledger/services/faults.py`: new.
  - `list_faults`: Open, then Investigating, then Resolved, newest first within each.
  - Create and update, with resolution required for Resolved.
  - Soft delete and restore.
  - `open_faults()` across non-archived projects, for 1.8.
- `src/benchledger/web/routes/faults.py`: new. New, edit, delete and restore. The edit
  page for a deleted fault redirects to where it can be restored.
- `src/benchledger/web/templates/faults/form.html`, `templates/projects/_faults.html`: new.
- `src/benchledger/web/project_page.py`: `faults_context`. The project page takes
  `?faults=all` to also show deleted faults.
- `src/benchledger/web/routes/projects.py`, `templates/projects/detail.html`: Tasks and
  Faults are shown side by side.
- `src/benchledger/app.py`, `services/history.py`, `web/routes/history.py`: faults in
  History, with long symptoms shortened in the title.
- `src/benchledger/web/static/css/benchledger.css`: fault styles; equal-height two-column
  panels.
- `tests/test_faults.py`: new.

**Reviewer findings**
- High: none.
- Medium: none.
- Low, fixed:
  - The model's CHECK duplicated the status list as a literal; it is now built from
    `FAULT_STATUSES`. The migration keeps a literal, since migrations stay frozen.
  - SQLite's `trim()` strips spaces only. The database check now treats tabs and newlines
    as blank too, with a test.
  - Status `<option>`s had no `value=`.
  - The equal-height CSS depended on the panel margin; it now uses flex.
- Low, not changed:
  - Migration server defaults are not mirrored on the model. Same as 0003 and 0004,
    explained in the migration comment.
  - Editing a deleted fault by POST shows "Restore this fault before editing it." Correct
    already.
- Note for 1.8: `open_faults()` doesn't eager-load `project`. The dashboard should use
  `selectinload` when it shows project names.

**Tester:** pytest 200 passed, 0 failed, 0 errors, 0 skipped, 1 warning (the same Starlette
TestClient deprecation as before). `ruff check` passed; `ruff format --check` passed.

**Judgment calls**
- **Plain text, not Markdown:** fault fields render as plain text with line breaks kept.
  They're short notes, and plain text keeps the escaping simple. Markdown can be added
  later through the same filter as entries.
- **No htmx:** faults use full-page post/redirect/get. The item asks for "its own edit
  page", so there's no inline editing.
- **Fault date:** shown as its `created_at` in local time. M4 lists no separate
  "occurred at" field for faults.
- **Restore:** faults have a restore button, like entries, because a deleted fault can
  be evidence.
