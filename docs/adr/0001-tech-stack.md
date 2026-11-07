# ADR-0001: Tech stack

- **Status:** Accepted
- **Date:** 2026-11-07

## Context

BenchLedger is a single-user lab notebook that runs on an MX Linux PC (AMD Phenom II X6,
Python 3.11). It must import long time-series logs (up to about 2.3 million readings per
channel), keep raw data unchanged, run without internet access, and be ready to self-host
later. The owner reviews every change, so the code should stay in as few languages as
possible. The companion bench software (GPIB instrument control) is also Python.

Two options were considered:

- **A:** FastAPI with server-rendered Jinja2 pages and htmx; mostly Python, no front-end build.
- **B:** Flask with a React front end (the stack of an earlier project).

## Decision

Option A:

| Layer | Choice |
| --- | --- |
| Web framework | FastAPI + Uvicorn |
| Pages | Jinja2 templates + htmx (vendored, no CDN) |
| Charts | uPlot |
| Database | SQLite in WAL mode via SQLAlchemy 2.0 |
| Migrations | Alembic |
| Statistics | numpy; Allan deviation written in-house and checked against `allantools` in tests |
| Command line | Typer |
| Tests and quality | pytest, ruff, GitHub Actions |
| Packaging | `pyproject.toml` with uv |
| Backups | restic, run by systemd timers |
| Running it | systemd user service bound to 127.0.0.1 |

## Consequences

- One main language to read and review; shared with the bench software.
- No Node toolchain or build step; light enough for the Phenom II.
- FastAPI's typed endpoints and automatic API docs give a ready path to a logger API (C5).
- Interactive pieces (chart zoom, live updates) need small amounts of JavaScript; htmx and
  uPlot keep that contained.
- SQLite limits concurrent writers to one, which suits a single user. A move to PostgreSQL
  would be a new ADR if multi-user cloud hosting ever happens.
