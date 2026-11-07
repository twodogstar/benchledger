"""Shared pieces for routes: templates, the database session dependency, form helpers."""

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from benchledger import __version__

WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=WEB_DIR / "templates")
templates.env.globals["version"] = __version__  # shown in the sidebar on every page


def get_session(request: Request) -> Iterator[Session]:
    """One database session per request. Routes call session.commit() when they change data."""
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


async def form_data(request: Request, fields: list[str]) -> dict[str, str]:
    """Read the named fields from a submitted form as plain strings ('' if missing)."""
    form = await request.form()
    return {field: str(form.get(field, "")) for field in fields}


def redirect(url: str) -> RedirectResponse:
    """After a successful POST, send the browser to a page with GET (post/redirect/get)."""
    return RedirectResponse(url, status_code=303)
