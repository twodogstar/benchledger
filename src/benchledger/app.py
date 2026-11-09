"""The FastAPI application.

`create_app()` is a factory: tests build an app pointed at a temporary data folder,
while `benchledger serve` builds one from the normal settings.
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from benchledger import __version__
from benchledger.config import Settings, load_settings
from benchledger.db.migrate import current_revision
from benchledger.db.session import make_engine, make_session_factory
from benchledger.services import projects as project_service
from benchledger.web.deps import WEB_DIR, SessionDep, templates
from benchledger.web.routes import entries, history, projects, settings, tasks


def create_app(app_settings: Settings | None = None) -> FastAPI:
    app_settings = app_settings or load_settings()
    engine = make_engine(app_settings.database_url)

    app = FastAPI(title="BenchLedger", version=__version__)
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)

    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")
    app.include_router(projects.router)
    app.include_router(entries.router)
    app.include_router(tasks.router)
    app.include_router(settings.router)
    app.include_router(history.router)

    def schema_revision() -> str | None:
        try:
            return current_revision(engine)
        except SQLAlchemyError:
            return None

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, session: SessionDep):
        revision = schema_revision()
        active = []
        if revision is not None:
            active = project_service.list_projects(session, stage="Active")
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "active": "dashboard",
                "data_dir": app_settings.data_dir,
                "revision": revision,
                "active_projects": active,
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
