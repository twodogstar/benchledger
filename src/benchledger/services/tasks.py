"""Next-step tasks per project (requirement M5).

A checklist: open tasks first in the owner's order, then done ones. Ticking, moving and
deleting are ordinary changes, so the change log records each one. Deleting only sets
`deleted_at`.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from benchledger import timeutil
from benchledger.db.models import Project, Task
from benchledger.services import InvalidInput

MAX_TEXT = 300


def checklist(session: Session, project: Project) -> list[Task]:
    """Open tasks in order, then done tasks in order. Deleted tasks are left out."""
    query = (
        select(Task)
        .where(Task.project_id == project.id, Task.deleted_at.is_(None))
        .order_by(Task.done, Task.position, Task.id)
    )
    return list(session.scalars(query))


def next_tasks(session: Session, limit: int = 8) -> list[Task]:
    """Open tasks across all non-archived projects (for the dashboard).

    Dated tasks first, soonest due first; then undated ones in each checklist's order.
    """
    query = (
        select(Task)
        .join(Project, Project.id == Task.project_id)
        .where(
            Task.done.is_(False),
            Task.deleted_at.is_(None),
            Project.archived_at.is_(None),
        )
        .order_by(Task.due_on.is_(None), Task.due_on, Task.project_id, Task.position, Task.id)
        .options(selectinload(Task.project))
        .limit(limit)
    )
    return list(session.scalars(query))


def get_task(session: Session, project: Project, task_id: int) -> Task | None:
    task = session.get(Task, task_id)
    if task is None or task.project_id != project.id:
        return None
    return task


def _parse_due(raw: str | None) -> date | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return timeutil.parse_date(raw)
    except ValueError as exc:
        raise InvalidInput({"due_on": str(exc)}) from exc


def create_task(session: Session, project: Project, data: dict[str, str]) -> Task:
    errors: dict[str, str] = {}
    text = " ".join((data.get("text") or "").split())
    if not text:
        errors["text"] = "Write what needs doing."
    elif len(text) > MAX_TEXT:
        errors["text"] = f"Keep it under {MAX_TEXT} characters."
    try:
        due_on = _parse_due(data.get("due_on"))
    except InvalidInput as exc:
        errors.update(exc.errors)
        due_on = None
    if errors:
        raise InvalidInput(errors)

    last = session.scalar(select(func.max(Task.position)).where(Task.project_id == project.id))
    task = Task(project_id=project.id, text=text, due_on=due_on, position=(last or 0) + 1)
    session.add(task)
    session.flush()
    return task


def set_done(session: Session, task: Task, done: bool) -> None:
    if task.deleted_at is not None:
        raise InvalidInput({"task": "This task was deleted."})
    if task.done != done:
        task.done = done
        session.flush()


def move_task(session: Session, task: Task, direction: str) -> None:
    """Swap with the neighbouring open task. direction is 'up' or 'down'."""
    if direction not in ("up", "down"):
        raise InvalidInput({"direction": "Move up or down."})
    if task.done or task.deleted_at is not None:
        return
    project = session.get(Project, task.project_id)
    open_tasks = [t for t in checklist(session, project) if not t.done]
    i = open_tasks.index(task)
    j = i - 1 if direction == "up" else i + 1
    if not 0 <= j < len(open_tasks):
        return
    a, b = open_tasks[i], open_tasks[j]
    if a.position == b.position:
        # Only if two positions tie: renumber so a swap means something. Otherwise only the
        # two tasks that move are written, so untouched tasks get no History rows.
        for n, t in enumerate(open_tasks, start=1):
            t.position = n
    a.position, b.position = b.position, a.position
    session.flush()


def delete_task(session: Session, task: Task) -> None:
    """Soft delete: gone from the checklist, kept in the database and its history."""
    if task.deleted_at is None:
        task.deleted_at = timeutil.now_utc()
        session.flush()


def is_overdue(task: Task, today: date | None = None) -> bool:
    """An open task whose due date has passed (local calendar day)."""
    if task.done or task.due_on is None:
        return False
    today = today or timeutil.to_local(timeutil.now_utc()).date()
    return task.due_on < today
