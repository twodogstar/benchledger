"""Settings -> Lists: manage the editable lists (project areas, evidence labels).

Each list has the same routes under /settings/<list_name>/, where list_name is a key of
services.lists.LISTS ("areas", "evidence-labels").
"""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from benchledger.services import InvalidInput
from benchledger.services import lists as list_service
from benchledger.web.deps import SessionDep, form_data, redirect, templates

router = APIRouter(prefix="/settings")


def _lists_page(request: Request, session, *, errors=None, values=None, status_code=200):
    sections = [
        {
            "name": name,
            "spec": spec,
            "items": list_service.list_items(session, spec.model, include_archived=True),
            # Change-log table name, for the History links.
            "table": spec.model.__tablename__,
        }
        for name, spec in list_service.LISTS.items()
    ]
    return templates.TemplateResponse(
        request,
        "settings/lists.html",
        {
            "active": "settings",
            "sections": sections,
            # errors and values are keyed "<list_name>:new" or "<list_name>:<item id>".
            "errors": errors or {},
            "values": values or {},
        },
        status_code=status_code,
    )


def _spec_or_404(list_name: str) -> list_service.ListSpec:
    spec = list_service.LISTS.get(list_name)
    if spec is None:
        raise HTTPException(status_code=404, detail="No such list")
    return spec


def _item_or_404(session, list_name: str, item_id: int):
    item = list_service.get_item(session, _spec_or_404(list_name).model, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/lists", response_class=HTMLResponse)
def lists(request: Request, session: SessionDep):
    return _lists_page(request, session)


# Catch-all for list names: any fixed POST route under /settings must be declared above.
@router.post("/{list_name}")
async def add_item(request: Request, session: SessionDep, list_name: str):
    spec = _spec_or_404(list_name)
    data = await form_data(request, ["name"])
    try:
        list_service.create_item(session, spec.model, data["name"])
    except InvalidInput as exc:
        session.rollback()
        key = f"{list_name}:new"
        return _lists_page(
            request,
            session,
            errors={key: exc.errors["name"]},
            values={key: data["name"]},
            status_code=400,
        )
    session.commit()
    return redirect("/settings/lists")


@router.post("/{list_name}/{item_id}/rename")
async def rename_item(request: Request, session: SessionDep, list_name: str, item_id: int):
    item = _item_or_404(session, list_name, item_id)
    data = await form_data(request, ["name"])
    try:
        list_service.rename_item(session, item, data["name"])
    except InvalidInput as exc:
        session.rollback()
        key = f"{list_name}:{item_id}"
        return _lists_page(
            request,
            session,
            errors={key: exc.errors["name"]},
            values={key: data["name"]},
            status_code=400,
        )
    session.commit()
    return redirect("/settings/lists")


@router.post("/{list_name}/{item_id}/move")
async def move_item(request: Request, session: SessionDep, list_name: str, item_id: int):
    item = _item_or_404(session, list_name, item_id)
    data = await form_data(request, ["direction"])
    try:
        list_service.move_item(session, item, data["direction"])
    except InvalidInput as exc:
        raise HTTPException(status_code=400, detail=exc.errors["direction"]) from exc
    session.commit()
    return redirect("/settings/lists")


@router.post("/{list_name}/{item_id}/archive")
def archive_item(session: SessionDep, list_name: str, item_id: int):
    list_service.archive_item(session, _item_or_404(session, list_name, item_id))
    session.commit()
    return redirect("/settings/lists")


@router.post("/{list_name}/{item_id}/restore")
def restore_item(session: SessionDep, list_name: str, item_id: int):
    list_service.restore_item(session, _item_or_404(session, list_name, item_id))
    session.commit()
    return redirect("/settings/lists")
