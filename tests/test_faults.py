"""The fault tracker (M4): migration, service and pages."""

import pytest
from alembic import command
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError

from benchledger.db.migrate import alembic_config
from benchledger.db.models import EvidenceLabel, Fault
from benchledger.db.session import make_engine
from benchledger.services import InvalidInput
from benchledger.services import faults as fault_service
from benchledger.services import lists as list_service
from benchledger.services import projects as project_service
from benchledger.services.history import history_for

# ---- migration ----


def test_migration_0005_round_trips(migrated):
    def tables():
        engine = make_engine(migrated.database_url)
        try:
            return set(inspect(engine).get_table_names())
        finally:
            engine.dispose()

    assert "faults" in tables()
    command.downgrade(alembic_config(migrated), "0004")
    assert "faults" not in tables() and "tasks" in tables()
    command.upgrade(alembic_config(migrated), "head")
    assert "faults" in tables()


# ---- service ----


@pytest.fixture
def project(session):
    project = project_service.create_project(session, {"name": "CH341 programmer"})
    session.commit()
    return project


def add(session, project, **fields):
    data = {"symptom": "Reads 0xFF from every address", **fields}
    fault = fault_service.create_fault(session, project, data)
    session.commit()
    return fault


def test_create_defaults_to_open(session, project):
    fault = add(session, project, next_test="Scope /CS while reading")
    assert fault.status == "Open"
    assert fault.next_test == "Scope /CS while reading"
    assert fault.author_id == 1


def test_resolving_requires_a_resolution(session, project):
    fault = add(session, project)
    with pytest.raises(InvalidInput) as exc:
        fault_service.update_fault(
            session, fault, {"symptom": fault.symptom, "status": "Resolved", "resolution": "  "}
        )
    assert set(exc.value.errors) == {"resolution"}
    session.rollback()

    fault_service.update_fault(
        session,
        fault,
        {"symptom": fault.symptom, "status": "Resolved", "resolution": "WP# was floating"},
    )
    session.commit()
    assert fault.status == "Resolved"


def test_cannot_be_created_resolved_without_a_resolution(session, project):
    with pytest.raises(InvalidInput):
        add(session, project, status="Resolved")


def test_database_also_refuses_resolved_without_resolution(session, project):
    fault = add(session, project)
    fault.status = "Resolved"  # bypassing the service
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_validation(session, project):
    with pytest.raises(InvalidInput) as exc:
        fault_service.create_fault(
            session,
            project,
            {
                "symptom": "",
                "status": "Fixed?",
                "evidence_label_id": "²",
                "next_test": "x" * 20_001,
            },
        )
    assert set(exc.value.errors) == {"symptom", "status", "evidence_label_id", "next_test"}


def test_status_changes_are_logged(session, project):
    fault = add(session, project)
    data = {"symptom": fault.symptom, "status": "Investigating"}
    fault_service.update_fault(session, fault, data)
    session.commit()
    changes = [
        (c.field, c.old_value, c.new_value)
        for c in history_for(session, "faults", fault.id)
        if c.action == "update"
    ]
    assert ("status", "Open", "Investigating") in changes


def test_list_order_and_soft_delete(session, project):
    resolved = add(session, project, status="Resolved", resolution="Reflowed U3")
    open_one = add(session, project, symptom="Intermittent USB drop")
    investigating = add(session, project, symptom="Wrong chip ID", status="Investigating")
    assert fault_service.list_faults(session, project) == [open_one, investigating, resolved]

    fault_service.delete_fault(session, open_one)
    session.commit()
    assert open_one not in fault_service.list_faults(session, project)
    assert open_one in fault_service.list_faults(session, project, include_deleted=True)
    with pytest.raises(InvalidInput):
        fault_service.update_fault(session, open_one, {"symptom": "x"})
    fault_service.restore_fault(session, open_one)
    assert open_one in fault_service.list_faults(session, project)


def test_open_faults_across_projects(session, project):
    add(session, project, symptom="Open here")
    add(session, project, symptom="Done here", status="Resolved", resolution="Fixed")
    archived = project_service.create_project(session, {"name": "Old"})
    add(session, archived, symptom="On an archived project")
    project_service.archive_project(session, archived)
    session.commit()
    assert [f.symptom for f in fault_service.open_faults(session)] == ["Open here"]


def test_retired_label_kept_on_edit_but_not_for_new(session, project):
    suspected = list_service.list_items(session, EvidenceLabel)[3]
    fault = add(session, project, evidence_label_id=str(suspected.id))
    list_service.archive_item(session, suspected)
    fault_service.update_fault(
        session, fault, {"symptom": "Still", "evidence_label_id": str(suspected.id)}
    )
    assert fault.evidence_label_id == suspected.id
    with pytest.raises(InvalidInput):
        add(session, project, evidence_label_id=str(suspected.id))


# ---- pages ----


@pytest.fixture
def page(client):
    client.post("/projects/new", data={"name": "CH341 programmer"})
    return "/projects/ch341-programmer"


def test_project_page_has_a_fault_panel(client, page):
    html = client.get(page).text
    assert 'id="faults"' in html and "No faults recorded" in html
    assert f'href="{page}/faults/new"' in html


def test_create_edit_and_resolve_through_the_pages(client, page):
    assert client.get(f"{page}/faults/new").status_code == 200
    response = client.post(
        f"{page}/faults/new",
        data={"symptom": "Reads 0xFF", "evidence_label_id": "2", "next_test": "Scope /CS"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"{page}#fault-1"
    html = client.get(page).text
    assert "Reads 0xFF" in html and "Scope /CS" in html and "observed" in html

    form = client.get(f"{page}/faults/1/edit")
    assert form.status_code == 200 and "Reads 0xFF" in form.text

    refused = client.post(
        f"{page}/faults/1/edit", data={"symptom": "Reads 0xFF", "status": "Resolved"}
    )
    assert refused.status_code == 400
    assert "Say how it was resolved" in refused.text
    assert "Reads 0xFF" in refused.text  # input kept

    response = client.post(
        f"{page}/faults/1/edit",
        data={"symptom": "Reads 0xFF", "status": "Resolved", "resolution": "WP# floating"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "WP# floating" in client.get(page).text

    history = client.get("/history/faults/1").text
    assert "Fault history: Reads 0xFF" in history
    assert "Open" in history and "Resolved" in history


def test_delete_and_restore(client, page):
    client.post(f"{page}/faults/new", data={"symptom": "Gone soon"})
    client.post(f"{page}/faults/1/delete")
    assert "Gone soon" not in client.get(page).text
    assert "Gone soon" in client.get(f"{page}?faults=all").text
    edit = client.get(f"{page}/faults/1/edit", follow_redirects=False)
    assert edit.status_code == 303  # deleted: sent to where it can be restored
    client.post(f"{page}/faults/1/restore")
    assert "Gone soon" in client.get(page).text


def test_fault_text_is_escaped(client, page):
    payload = '"><script>alert(1)</script>'
    client.post(
        f"{page}/faults/new", data={"symptom": payload, "next_test": payload, "resolution": payload}
    )
    for url in (page, f"{page}/faults/1/edit", "/history/faults/1"):
        assert "<script>alert(1)</script>" not in client.get(url).text, url


def test_foreign_and_missing_faults_are_404(client, page):
    client.post(f"{page}/faults/new", data={"symptom": "Mine"})
    client.post("/projects/new", data={"name": "Z80 tester"})
    assert client.get("/projects/z80-tester/faults/1/edit").status_code == 404
    assert client.post("/projects/z80-tester/faults/1/delete").status_code == 404
    assert client.get(f"{page}/faults/99/edit").status_code == 404


def test_long_symptom_is_shortened_in_history_title(session, project):
    from benchledger.web.routes.history import _describe

    fault = add(session, project, symptom="x" * 200)
    assert isinstance(fault, Fault)

    label, _, _ = _describe("faults", fault)
    assert len(label) == 80 and label.endswith("…")


def test_database_treats_whitespace_only_resolution_as_blank(session, project):
    fault = add(session, project)
    fault.status = "Resolved"
    fault.resolution = "\n\t \r\n"  # bypassing the service's strip()
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
