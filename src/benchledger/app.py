"""The FastAPI application.

`create_app()` is a factory: tests build an app pointed at a temporary data folder,
while `benchledger serve` builds one from the normal settings.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import SQLAlchemyError

from benchledger import __version__
from benchledger.config import Settings, load_settings
from benchledger.db.migrate import current_revision
from benchledger.db.session import make_engine, make_session_factory

WEB_DIR = Path(__file__).resolve().parent / "web"
templates = Jinja2Templates(directory=WEB_DIR / "templates")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    engine = make_engine(settings.database_url)

    app = FastAPI(title="BenchLedger", version=__version__)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)

    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")

    def schema_revision() -> str | None:
        try:
            return current_revision(engine)
        except SQLAlchemyError:
            return None

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "version": __version__,
                "data_dir": settings.data_dir,
                "revision": schema_revision(),
            },
        )

    @app.get("/healthz")
    def healthz():
        """Machine-readable status, for scripts and the future backup monitor."""
        revision = schema_revision()
        ok = revision is not None
        return JSONResponse(
            status_code=200 if ok else 503,
            content={
                "status": "ok" if ok else "degraded",
                "version": __version__,
                "schema_revision": revision,
            },
        )

    return app
