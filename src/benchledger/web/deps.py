"""Shared pieces for routes: templates, the database session dependency, form helpers."""

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request
from fastapi import Path as PathParam
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from benchledger import __version__, timeutil
from benchledger.web.markdown import render_markdown

WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=WEB_DIR / "templates")
templates.env.globals["version"] = __version__  # shown in the sidebar on every page
# {{ entry.body | markdown }}: rendered and cleaned (N9). Never use |safe on user text.
templates.env.filters["markdown"] = render_markdown
# Times are stored in UTC; pages show local time (N7).
templates.env.filters["localtime"] = timeutil.display
templates.env.filters["utctime"] = timeutil.display_utc
templates.env.filters["isotime"] = timeutil.iso_utc
templates.env.filters["utcoffset"] = timeutil.format_offset


def get_session(request: Request) -> Iterator[Session]:
    """One database session per request. Routes call session.commit() when they change data."""
    with request.app.state.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

# A record id in a URL. The bounds keep huge numbers from overflowing SQLite's 64-bit
# integer (a 500); out-of-range ids get a 422 before any database lookup.
RecordId = Annotated[int, PathParam(ge=1, le=2**63 - 1)]


async def form_data(request: Request, fields: list[str]) -> dict[str, str]:
    """Read the named fields from a submitted form as plain strings ('' if missing)."""
    form = await request.form()
    return {field: str(form.get(field, "")) for field in fields}


def redirect(url: str) -> RedirectResponse:
    """After a successful POST, send the browser to a page with GET (post/redirect/get)."""
    return RedirectResponse(url, status_code=303)
