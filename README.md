# BenchLedger

An electronic lab notebook for a home electronics and metrology bench. It keeps what was
measured, what was observed and what is only suspected clearly apart, and ties each one to
the raw data behind it.

BenchLedger records knowledge; separate bench software controls the instruments. The two
meet only through a documented file format (the *run package*), so an overnight logging run
never depends on the notebook being up.

> **Status:** iteration 0. The app runs and the database is set up; features start in
> iteration 1. See [the requirements](docs/requirements.md) and [the design](docs/design.md).

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
