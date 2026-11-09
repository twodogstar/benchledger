# BenchLedger

An electronic lab notebook for a home electronics and metrology bench. It keeps what was
measured, what was observed and what is only suspected clearly apart, and ties each one to
the raw data behind it.

BenchLedger records knowledge; separate bench software controls the instruments. The two
meet only through a documented file format (the *run package*), so an overnight logging run
never depends on the notebook being up.

> **Status:** v0.1.0, iteration 1 (the notebook). Runs and data import come in iteration 2,
> backups in iteration 3. See [the requirements](docs/requirements.md),
> [the design](docs/design.md) and [the backlog](docs/BACKLOG.md).

## Features

- **Projects**: goal, current state, setup, wiring and parts, with stage, priority and
  area. A list filters by stage, and archived projects are hidden but kept.
- **Notebook**: dated observations, hypotheses, decisions, notes and questions on each
  project.
  - Each entry has an evidence label (measured, observed, inferred, suspected) and a
    source, so what was measured stays apart from what is only suspected.
  - Entry bodies are Markdown.
  - Quick-add works without a page reload.
- **Hypotheses and questions** carry a status (Untested → Testing → Supported/Rejected;
  Open → Answered), with a filter for what's still open.
- **Faults**: symptom, status, evidence, the next test that would tell the explanations
  apart, and the resolution. A fault can't be closed without saying how.
- **Next steps**: a per-project checklist with optional due dates.
- **Dashboard**: active projects, recent entries, open faults and next tasks.
- **Full history**: every change to every record is kept with its before and after
  values and the time it changed, on each record's History page. Deleting only hides a
  record.
- **Settings → Lists**: edit the project areas and evidence labels offered in forms.
- **Local and offline**: one SQLite file, no internet needed, listening on 127.0.0.1 by
  default. User text is escaped, and Markdown in entries is sanitized.

## Quick start

Needs Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/twodogstar/benchledger.git
cd benchledger
uv sync                      # create .venv and install everything from uv.lock
uv run benchledger serve     # then open http://127.0.0.1:8765/
```

Data lives in `~/benchledger-data` by default. To change that or the port, copy
`config.example.toml` to `~/.config/benchledger/config.toml`.

## Commands

| Command | What it does |
| --- | --- |
| `benchledger serve` | Apply pending migrations, then start the web app |
| `benchledger db upgrade` | Create or update the database schema |
| `benchledger db current` | Show the schema revision |
| `benchledger version` | Print the version |

## Development

```bash
uv run pytest                # tests
uv run ruff check .          # lint
uv run ruff format .         # format
```

Every push and pull request runs the same checks on GitHub Actions.

Stack: FastAPI, Jinja2, SQLite (SQLAlchemy + Alembic), Typer. Why: [ADR-0001](docs/adr/0001-tech-stack.md).

## License

MIT
