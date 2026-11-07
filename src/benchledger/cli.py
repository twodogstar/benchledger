"""The `benchledger` command.

    benchledger serve          start the web app (runs pending migrations first)
    benchledger db upgrade     bring the database schema up to date
    benchledger db current     show the schema revision
    benchledger version        print the version

More commands (import, snapshot, backup) arrive in later iterations.
"""

from typing import Annotated

import typer
import uvicorn

from benchledger import __version__
from benchledger.config import load_settings

app = typer.Typer(help="BenchLedger: electronic lab notebook for the bench.", no_args_is_help=True)
db_app = typer.Typer(help="Database commands.", no_args_is_help=True)
app.add_typer(db_app, name="db")

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


@app.command()
def version() -> None:
    """Print the BenchLedger version."""
    typer.echo(f"benchledger {__version__}")


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="Address to listen on.")] = None,
    port: Annotated[int | None, typer.Option(help="Port to listen on.")] = None,
) -> None:
    """Start the web app. Pending database migrations run first."""
    from benchledger.app import create_app
    from benchledger.db.migrate import upgrade

    settings = load_settings()
    host = host or settings.host
    port = port or settings.port

    if host not in LOOPBACK_HOSTS:
        typer.secho(
            f"Warning: listening on {host} makes BenchLedger reachable from other machines.",
            fg=typer.colors.YELLOW,
        )

    upgrade(settings)
    typer.echo(f"BenchLedger {__version__} at http://{host}:{port}/  (data: {settings.data_dir})")
    uvicorn.run(create_app(settings), host=host, port=port, log_level="info")


@db_app.command("upgrade")
def db_upgrade() -> None:
    """Create the database if needed and apply all migrations."""
    from benchledger.db.migrate import upgrade

    settings = load_settings()
    upgrade(settings)
    typer.echo(f"Database is up to date: {settings.database_path}")


@db_app.command("current")
def db_current() -> None:
    """Show which schema revision the database is at."""
    from benchledger.db.migrate import current_revision
    from benchledger.db.session import make_engine

    settings = load_settings()
    if not settings.database_path.exists():
        typer.echo(f"No database yet at {settings.database_path}. Run: benchledger db upgrade")
        raise typer.Exit(code=1)
    engine = make_engine(settings.database_url)
    typer.echo(current_revision(engine) or "not migrated")
    engine.dispose()
