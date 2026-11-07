"""Settings -> Lists: manage the editable areas list."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from benchledger.services import InvalidInput
from benchledger.services import areas as area_service
from benchledger.web.deps import SessionDep, form_data, redirect, templates

router = APIRouter(prefix="/settings")


def _lists_page(request: Request, session, *, errors=None, values=None, status_code=200):
    return templates.TemplateResponse(
        request,
        "settings/lists.html",
        {
            "active": "settings",
            "areas": area_service.list_areas(session, include_archived=True),
            "errors": errors or {},
            "values": values or {},
        },
        status_code=status_code,
    )


def _area_or_404(session, area_id: int):
    area = area_service.get_area(session, area_id)
    if area is None:
        raise HTTPException(status_code=404, detail="Area not found")
    return area


@router.get("/lists", response_class=HTMLResponse)
def lists(request: Request, session: SessionDep):
    return _lists_page(request, session)


@router.post("/areas")
async def add_area(request: Request, session: SessionDep):
    data = await form_data(request, ["name"])
    try:
        area_service.create_area(session, data["name"])
    except InvalidInput as exc:
        session.rollback()
        return _lists_page(
            request, session, errors={"new": exc.errors["name"]}, values=data, status_code=400
        )
    session.commit()
    return redirect("/settings/lists")


@router.post("/areas/{area_id}/rename")
async def rename_area(request: Request, session: SessionDep, area_id: int):
    area = _area_or_404(session, area_id)
    data = await form_data(request, ["name"])
    try:
        area_service.rename_area(session, area, data["name"])
    except InvalidInput as exc:
        session.rollback()
        return _lists_page(request, session, errors={area_id: exc.errors["name"]}, status_code=400)
    session.commit()
    return redirect("/settings/lists")


@router.post("/areas/{area_id}/move")
async def move_area(request: Request, session: SessionDep, area_id: int):
    area = _area_or_404(session, area_id)
    data = await form_data(request, ["direction"])
    area_service.move_area(session, area, data["direction"])
    session.commit()
    return redirect("/settings/lists")


@router.post("/areas/{area_id}/archive")
def archive_area(session: SessionDep, area_id: int):
    area_service.archive_area(session, _area_or_404(session, area_id))
    session.commit()
    return redirect("/settings/lists")


@router.post("/areas/{area_id}/restore")
def restore_area(session: SessionDep, area_id: int):
    area_service.restore_area(session, _area_or_404(session, area_id))
    session.commit()
    return redirect("/settings/lists")
