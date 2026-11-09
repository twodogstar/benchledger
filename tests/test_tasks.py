"""Next-step tasks (M5): migration, service and the checklist on the project page."""

from datetime import date

import pytest
from alembic import command
from sqlalchemy import inspect

from benchledger.db.migrate import alembic_config
from benchledger.db.session import make_engine
from benchledger.services import InvalidInput
from benchledger.services import projects as project_service
from benchledger.services import tasks as task_service
from benchledger.services.history import history_for

HTMX = {"HX-Request": "true"}


# ---- migration ----


def test_migration_0004_round_trips(migrated):
    def tables():
        engine = make_engine(migrated.database_url)
        try:
            return set(inspect(engine).get_table_names())
        finally:
            engine.dispose()

    assert "tasks" in tables()
    command.downgrade(alembic_config(migrated), "0003")
    assert "tasks" not in tables() and "entries" in tables()
    command.upgrade(alembic_config(migrated), "head")
    assert "tasks" in tables()


# ---- service ----


@pytest.fixture
def project(session):
    project = project_service.create_project(session, {"name": "ADR1399 drift"})
    session.commit()
    return project


def add(session, project, text, due_on=""):
    task = task_service.create_task(session, project, {"text": text, "due_on": due_on})
    session.commit()
    return task


def texts(session, project):
    return [t.text for t in task_service.checklist(session, project)]


def test_add_appends_in_order(session, project):
    add(session, project, "Order a Peltier plate")
    add(session, project, "Log overnight with the enclosure", due_on="2026-11-15")
    assert texts(session, project) == ["Order a Peltier plate", "Log overnight with the enclosure"]
    assert task_service.checklist(session, project)[1].due_on == date(2026, 11, 15)


def test_add_validates(session, project):
    with pytest.raises(InvalidInput) as exc:
        task_service.create_task(session, project, {"text": " ", "due_on": "someday"})
    assert set(exc.value.errors) == {"text", "due_on"}
    with pytest.raises(InvalidInput):
        task_service.create_task(session, project, {"text": "x" * 301})
    with pytest.raises(InvalidInput):
        task_service.create_task(session, project, {"text": "x", "due_on": "0001-01-01"})


def test_ticking_is_logged_and_moves_task_to_the_end(session, project):
    first = add(session, project, "First")
    add(session, project, "Second")
    task_service.set_done(session, first, True)
    session.commit()

    assert texts(session, project) == ["Second", "First"]
    changes = [
        (c.field, c.old_value, c.new_value)
        for c in history_for(session, "tasks", first.id)
        if c.action == "update"
    ]
    assert changes == [("done", "False", "True")]


def test_ticking_twice_logs_once(session, project):
    task = add(session, project, "Once")
    task_service.set_done(session, task, True)
    task_service.set_done(session, task, True)
    session.commit()
    assert len([c for c in history_for(session, "tasks", task.id) if c.action == "update"]) == 1


def test_reorder_open_tasks(session, project):
    a, b, c = (add(session, project, name) for name in "ABC")
    task_service.move_task(session, c, "up")
    assert texts(session, project) == ["A", "C", "B"]
    task_service.move_task(session, a, "down")
    assert texts(session, project) == ["C", "A", "B"]
    task_service.move_task(session, c, "up")  # already first: nothing happens
    assert texts(session, project) == ["C", "A", "B"]
    with pytest.raises(InvalidInput):
        task_service.move_task(session, a, "sideways")


def test_done_tasks_dont_move(session, project):
    a = add(session, project, "A")
    add(session, project, "B")
    task_service.set_done(session, a, True)
    task_service.move_task(session, a, "up")
    assert texts(session, project) == ["B", "A"]


def test_delete_is_soft_and_logged(session, project):
    task = add(session, project, "Gone")
    task_service.delete_task(session, task)
    session.commit()
    assert texts(session, project) == []
    assert task_service.get_task(session, project, task.id) is task  # still in the database
    assert any(c.field == "deleted_at" for c in history_for(session, "tasks", task.id))
    with pytest.raises(InvalidInput):
        task_service.set_done(session, task, True)


def test_overdue(session, project):
    task = add(session, project, "Late", due_on="2026-11-01")
    assert task_service.is_overdue(task, today=date(2026, 11, 2))
    assert not task_service.is_overdue(task, today=date(2026, 11, 1))
    task_service.set_done(session, task, True)
    assert not task_service.is_overdue(task, today=date(2026, 11, 2))


def test_tasks_belong_to_their_project(session, project):
    task = add(session, project, "Mine")
    other = project_service.create_project(session, {"name": "Z80 tester"})
    assert task_service.get_task(session, other, task.id) is None
    assert texts(session, other) == []


# ---- pages ----


@pytest.fixture
def page(client):
    client.post("/projects/new", data={"name": "ADR1399 drift"})
    return "/projects/adr1399-drift"


def test_project_page_has_a_checklist(client, page):
    html = client.get(page).text
    assert 'id="tasks"' in html and "No tasks yet" in html


def test_add_tick_reorder_delete_with_htmx(client, page):
    response = client.post(f"{page}/tasks", data={"text": "Order a Peltier plate"}, headers=HTMX)
    assert response.status_code == 200
    assert response.text.lstrip().startswith('<section class="panel tasks" id="tasks">')
    client.post(f"{page}/tasks", data={"text": "Log overnight"}, headers=HTMX)

    response = client.post(f"{page}/tasks/2/move", data={"direction": "up"}, headers=HTMX)
    assert response.text.index("Log overnight") < response.text.index("Order a Peltier plate")

    response = client.post(f"{page}/tasks/2/done", data={"done": "1"}, headers=HTMX)
    assert 'class="task done"' in response.text

    response = client.post(f"{page}/tasks/1/delete", headers=HTMX)
    assert "Order a Peltier plate" not in response.text


def test_plain_posts_redirect_back_to_the_checklist(client, page):
    response = client.post(f"{page}/tasks", data={"text": "No JS"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"{page}#tasks"
    response = client.post(f"{page}/tasks/1/done", data={"done": "1"}, follow_redirects=False)
    assert response.status_code == 303


def test_ticking_shows_in_history(client, page):
    client.post(f"{page}/tasks", data={"text": "Tick me"})
    client.post(f"{page}/tasks/1/done", data={"done": "1"})
    client.post(f"{page}/tasks/1/done", data={"done": ""})  # untick
    history = client.get("/history/tasks/1")
    assert history.status_code == 200
    assert "Task history: Tick me" in history.text
    # Three "done" rows: False on insert, then ticked, then unticked.
    assert history.text.count(">done<") == 3
    assert history.text.count('class="badge action-update"') == 2
    assert 'href="/projects/adr1399-drift#tasks"' in history.text


def test_add_errors(client, page):
    response = client.post(f"{page}/tasks", data={"text": "", "due_on": "soon"}, headers=HTMX)
    assert response.status_code == 200
    assert "Write what needs doing." in response.text
    response = client.post(f"{page}/tasks", data={"text": "", "due_on": "soon"})
    assert response.status_code == 400
    assert "Write what needs doing." in response.text and 'id="notebook"' in response.text


def test_task_text_is_escaped(client, page):
    client.post(f"{page}/tasks", data={"text": '"><script>alert(1)</script>'})
    for url in (page, "/history/tasks/1"):
        html = client.get(url).text
        assert "<script>alert(1)</script>" not in html, url


def test_deleted_or_foreign_tasks_are_404(client, page):
    client.post(f"{page}/tasks", data={"text": "Mine"})
    client.post("/projects/new", data={"name": "Z80 tester"})
    assert client.post("/projects/z80-tester/tasks/1/done", data={"done": "1"}).status_code == 404
    client.post(f"{page}/tasks/1/delete")
    assert client.post(f"{page}/tasks/1/done", data={"done": "1"}).status_code == 404
    assert client.post(f"{page}/tasks/1/move", data={"direction": "up"}).status_code == 404


def test_bad_move_direction_is_400(client, page):
    client.post(f"{page}/tasks", data={"text": "Mine"})
    assert client.post(f"{page}/tasks/1/move", data={"direction": "left"}).status_code == 400


def test_moving_writes_only_the_two_tasks_that_move(session, project):
    a, b, c, d = (add(session, project, name) for name in "ABCD")
    task_service.delete_task(session, b)  # leaves a gap in the positions
    session.commit()
    task_service.move_task(session, d, "up")
    session.commit()
    assert texts(session, project) == ["A", "D", "C"]

    def position_rows(task):
        return [x for x in history_for(session, "tasks", task.id) if x.field == "position"]

    assert len(position_rows(a)) == 1  # just its insert
    assert len(position_rows(c)) == 2 and len(position_rows(d)) == 2


def test_bad_done_value_is_400(client, page):
    client.post(f"{page}/tasks", data={"text": "Mine"})
    assert client.post(f"{page}/tasks/1/done", data={"done": "yes"}).status_code == 400
    assert client.post(f"{page}/tasks/1/done").status_code == 200  # missing = not done
