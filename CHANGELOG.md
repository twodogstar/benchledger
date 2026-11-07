# Changelog

All notable changes to this project are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions
follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
