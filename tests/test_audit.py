"""The automatic change log (M2): every audited change leaves a trace."""

from benchledger.db.models import OWNER_ID
from benchledger.services import projects as project_service
from benchledger.services.history import history_for


def _changes(session, project):
    return [
        (c.action, c.field, c.old_value, c.new_value)
        for c in history_for(session, "projects", project.id)
    ]


def test_insert_logs_each_filled_field(session):
    project = project_service.create_project(session, {"name": "Z80 NOP tester", "stage": "Active"})
    session.commit()

    changes = _changes(session, project)
    assert ("insert", "name", None, "Z80 NOP tester") in changes
    assert ("insert", "stage", None, "Active") in changes
    assert ("insert", "slug", None, "z80-nop-tester") in changes
    # Empty text fields are not logged on insert.
    assert not any(field == "wiring" for _, field, _, _ in changes)


def test_update_logs_old_and_new_values(session):
    project = project_service.create_project(session, {"name": "ADR1399 drift", "goal": "Log it"})
    session.commit()

    data = {"name": "ADR1399 drift", "goal": "Log it overnight", "stage": "Active"}
    project_service.update_project(session, project, data)
    session.commit()

    updates = [c for c in _changes(session, project) if c[0] == "update"]
    assert ("update", "goal", "Log it", "Log it overnight") in updates
    assert ("update", "stage", "Idea", "Active") in updates
    # Unchanged fields are not logged.
    assert not any(field == "name" for _, field, _, _ in updates)


def test_saving_without_changes_logs_nothing(session):
    project = project_service.create_project(session, {"name": "Same"})
    session.commit()
    before = len(history_for(session, "projects", project.id))

    project_service.update_project(session, project, {"name": "Same"})
    session.commit()
    assert len(history_for(session, "projects", project.id)) == before


def test_archive_is_logged_and_author_is_owner(session):
    project = project_service.create_project(session, {"name": "Archive me"})
    session.commit()
    project_service.archive_project(session, project)
    session.commit()

    rows = history_for(session, "projects", project.id)
    assert rows[0].action == "update" and rows[0].field == "archived_at"
    assert rows[0].old_value is None and rows[0].new_value
    assert all(r.author_id == OWNER_ID for r in rows)


def test_failed_transaction_leaves_no_log(session):
    project = project_service.create_project(session, {"name": "Rolled back"})
    project_id = project.id
    session.rollback()  # never committed: the project and its log rows both vanish
    assert history_for(session, "projects", project_id) == []
