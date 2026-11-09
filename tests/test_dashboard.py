"""The dashboard (M15, partly): active projects, recent entries, open faults, next tasks."""

import pytest
from fastapi.testclient import TestClient

from benchledger.app import create_app
from benchledger.services import entries as entry_service
from benchledger.services import faults as fault_service
from benchledger.services import projects as project_service
from benchledger.services import tasks as task_service


def tile(html: str, tile_id: str) -> str:
    """The HTML of one dashboard tile."""
    start = html.index(f'id="{tile_id}"')
    end = html.find('<div class="panel tile"', start)
    return html[start : end if end != -1 else len(html)]


@pytest.fixture
def seeded(client):
    """A bench with one active project, one archived one, and a bit of everything."""
    client.post("/projects/new", data={"name": "ADR1399 drift", "stage": "Active"})
    client.post("/projects/new", data={"name": "Z80 tester", "stage": "Paused"})
    client.post("/projects/new", data={"name": "Old CRT", "stage": "Active"})
    p, z, old = "/projects/adr1399-drift", "/projects/z80-tester", "/projects/old-crt"

    client.post(
        f"{p}/entries",
        data={
            "kind": "observation",
            "title": "Settles after 40 min",
            "evidence_label_id": "1",
            "occurred_at": "2026-11-01T09:00",
        },
    )
    client.post(
        f"{z}/entries",
        data={"kind": "hypothesis", "title": "Clock line rings", "occurred_at": "2026-11-02T09:00"},
    )
    client.post(
        f"{p}/entries",
        data={"kind": "note", "title": "Deleted note", "occurred_at": "2026-11-03T09:00"},
    )
    client.post(f"{p}/entries/3/delete")

    client.post(f"{p}/faults/new", data={"symptom": "Steps of 2 ppm at night"})
    client.post(
        f"{z}/faults/new",
        data={"symptom": "Fixed already", "status": "Resolved", "resolution": "Reseated"},
    )

    client.post(f"{p}/tasks", data={"text": "Order a Peltier plate"})
    client.post(f"{z}/tasks", data={"text": "Probe the clock", "due_on": "2026-11-10"})
    client.post(f"{p}/tasks", data={"text": "Already done"})
    client.post(f"{p}/tasks/3/done", data={"done": "1"})

    # Everything on an archived project stays off the dashboard.
    client.post(f"{old}/entries", data={"kind": "note", "title": "Archived entry"})
    client.post(f"{old}/faults/new", data={"symptom": "Archived fault"})
    client.post(f"{old}/tasks", data={"text": "Archived task"})
    client.post(f"{old}/archive")
    return client.get("/").text


def test_each_tile_shows_seeded_data(seeded):
    projects = tile(seeded, "tile-projects")
    assert "ADR1399 drift" in projects
    assert "Z80 tester" not in projects  # paused, not active

    entries = tile(seeded, "tile-entries")
    assert "Settles after 40 min" in entries and "measured" in entries
    assert "Clock line rings" in entries and "Untested" in entries
    assert entries.index("Clock line rings") < entries.index("Settles after 40 min")  # newest first
    assert "Deleted note" not in entries

    faults = tile(seeded, "tile-faults")
    assert "Steps of 2 ppm at night" in faults
    assert "Fixed already" not in faults
    assert 'href="/projects/adr1399-drift#fault-1"' in faults

    tasks = tile(seeded, "tile-tasks")
    assert "Probe the clock" in tasks and "Order a Peltier plate" in tasks
    assert tasks.index("Probe the clock") < tasks.index("Order a Peltier plate")  # dated first
    assert "Already done" not in tasks


def test_archived_projects_stay_off_the_dashboard(seeded):
    for text in ("Old CRT", "Archived entry", "Archived fault", "Archived task"):
        assert text not in seeded, text


def test_empty_dashboard_has_friendly_empty_states(client):
    html = client.get("/").text
    for text in (
        "No active projects",
        "No notebook entries yet",
        "No open faults",
        "Nothing on the list",
    ):
        assert text in html


def test_dashboard_escapes_user_text(client):
    payload = "<script>alert(1)</script>"
    client.post("/projects/new", data={"name": "XSS", "stage": "Active"})
    client.post("/projects/xss/entries", data={"kind": "note", "title": payload})
    client.post("/projects/xss/faults/new", data={"symptom": payload})
    client.post("/projects/xss/tasks", data={"text": payload})
    html = client.get("/").text
    assert payload not in html
    assert html.count("&lt;script&gt;alert(1)&lt;/script&gt;") == 3


def test_unmigrated_database_shows_the_upgrade_hint_not_an_error(settings):
    settings.data_dir.mkdir(parents=True)
    app = create_app(settings)  # no upgrade() on purpose
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Run: benchledger db upgrade" in response.text
    app.state.engine.dispose()


# ---- service queries ----


def test_tile_queries_respect_limits(session):
    project = project_service.create_project(session, {"name": "Busy", "stage": "Active"})
    for n in range(12):
        entry_service.create_entry(session, project, {"kind": "note", "title": f"E{n}"})
        task_service.create_task(session, project, {"text": f"T{n}"})
        fault_service.create_fault(session, project, {"symptom": f"F{n}"})
    session.commit()
    assert len(entry_service.recent_entries(session, limit=8)) == 8
    assert len(task_service.next_tasks(session, limit=8)) == 8
    assert len(fault_service.open_faults(session, limit=8)) == 8


def test_next_tasks_order(session):
    a = project_service.create_project(session, {"name": "A"})
    b = project_service.create_project(session, {"name": "B"})
    undated_a = task_service.create_task(session, a, {"text": "undated A"})
    later = task_service.create_task(session, b, {"text": "later", "due_on": "2026-12-01"})
    sooner = task_service.create_task(session, a, {"text": "sooner", "due_on": "2026-11-20"})
    undated_b = task_service.create_task(session, b, {"text": "undated B"})
    session.commit()
    assert task_service.next_tasks(session) == [sooner, later, undated_a, undated_b]


# ---- review fixes ----


def test_active_projects_tile_is_capped_with_a_link(client):
    for n in range(10):
        client.post("/projects/new", data={"name": f"Project {n}", "stage": "Active"})
    projects = tile(client.get("/").text, "tile-projects")
    assert projects.count("<li>") == 8
    assert 'href="/projects?stage=Active"' in projects


def test_few_active_projects_have_no_more_link(client):
    client.post("/projects/new", data={"name": "Only one", "stage": "Active"})
    assert "All active projects" not in client.get("/").text


def test_partly_migrated_database_shows_the_upgrade_hint(settings):
    from benchledger.db.migrate import upgrade

    upgrade(settings, revision="0002")  # projects exist, entries/tasks/faults don't
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert "Run: benchledger db upgrade" in response.text
    app.state.engine.dispose()


def test_active_projects_query_loads_areas_up_front(session):
    from sqlalchemy import event

    for n in range(5):
        project_service.create_project(
            session, {"name": f"P{n}", "stage": "Active", "area_id": str(n + 1)}
        )
    session.commit()
    session.expire_all()

    statements = []
    engine = session.get_bind()
    listener = lambda *args: statements.append(args[2])  # noqa: E731
    event.listen(engine, "before_cursor_execute", listener)
    try:
        projects = project_service.list_projects(session, stage="Active")
        names = [p.area.name for p in projects]
    finally:
        event.remove(engine, "before_cursor_execute", listener)
    assert len(names) == 5
    assert len(statements) == 2  # projects, then all their areas in one go
