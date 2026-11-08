"""Migration 0003 (evidence labels and entries) and the change log for entries (M2, D1)."""

from datetime import UTC, datetime

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from benchledger.db.migrate import alembic_config, current_revision
from benchledger.db.models import Entry, EvidenceLabel
from benchledger.db.session import make_engine
from benchledger.services import InvalidInput
from benchledger.services import lists as list_service
from benchledger.services import projects as project_service
from benchledger.services.history import history_for


def _tables(settings) -> set[str]:
    engine = make_engine(settings.database_url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_migration_0003_upgrades_and_downgrades(migrated):
    assert {"entries", "evidence_labels"} <= _tables(migrated)

    cfg = alembic_config(migrated)
    command.downgrade(cfg, "0002")
    assert not {"entries", "evidence_labels"} & _tables(migrated)
    engine = make_engine(migrated.database_url)
    assert current_revision(engine) == "0002"
    engine.dispose()

    command.upgrade(cfg, "head")
    assert {"entries", "evidence_labels"} <= _tables(migrated)


def test_evidence_labels_are_seeded_in_order(session):
    names = [label.name for label in list_service.list_items(session, EvidenceLabel)]
    assert names == ["measured", "observed", "inferred", "suspected"]


def test_evidence_labels_are_a_managed_list(session):
    list_service.create_item(session, EvidenceLabel, "datasheet")
    with pytest.raises(InvalidInput, match="evidence label"):
        list_service.create_item(session, EvidenceLabel, "Measured")

    suspected = list_service.list_items(session, EvidenceLabel)[3]
    list_service.archive_item(session, suspected)
    names = [label.name for label in list_service.list_items(session, EvidenceLabel)]
    assert names == ["measured", "observed", "inferred", "datasheet"]


def _entry(session) -> Entry:
    project = project_service.create_project(session, {"name": "ADR1399 drift"})
    measured = list_service.list_items(session, EvidenceLabel)[0]
    entry = Entry(
        project_id=project.id,
        kind="observation",
        title="Output settles after 40 min",
        body="Within 1 ppm of final after **40 min**.",
        evidence_label_id=measured.id,
        source="34401A, NPLC 100",
        occurred_at=datetime(2026, 11, 1, 1, 20, tzinfo=UTC),
        occurred_offset_min=-420,
    )
    session.add(entry)
    session.commit()
    return entry


def _changes(session, entry):
    return [
        (c.action, c.field, c.old_value, c.new_value)
        for c in history_for(session, "entries", entry.id)
    ]


def test_creating_an_entry_writes_change_log_rows(session):
    entry = _entry(session)
    changes = _changes(session, entry)
    assert ("insert", "title", None, "Output settles after 40 min") in changes
    assert ("insert", "kind", None, "observation") in changes
    assert ("insert", "occurred_offset_min", None, "-420") in changes
    assert any(field == "occurred_at" for _, field, _, _ in changes)


def test_editing_an_entry_keeps_old_and_new_text(session):
    entry = _entry(session)
    entry.body = "Within 1 ppm of final after **45 min**."
    session.commit()

    updates = [c for c in _changes(session, entry) if c[0] == "update"]
    assert updates == [
        (
            "update",
            "body",
            "Within 1 ppm of final after **40 min**.",
            "Within 1 ppm of final after **45 min**.",
        )
    ]


def test_settings_page_manages_evidence_labels(client):
    page = client.get("/settings/lists")
    assert "Evidence labels" in page.text and "suspected" in page.text

    response = client.post(
        "/settings/evidence-labels", data={"name": "datasheet"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert "datasheet" in client.get("/settings/lists").text

    duplicate = client.post("/settings/evidence-labels", data={"name": "MEASURED"})
    assert duplicate.status_code == 400
    assert "already exists" in duplicate.text

    assert client.post("/settings/evidence-labels/1/archive").status_code == 200
    history = client.get("/history/evidence_labels/1")
    assert history.status_code == 200 and "archived at" in history.text


def test_unknown_list_is_404(client):
    assert client.post("/settings/nope", data={"name": "x"}).status_code == 404
    assert client.post("/settings/areas/999/archive").status_code == 404


def test_seeded_labels_survive_a_migration_round_trip(migrated):
    cfg = alembic_config(migrated)
    command.downgrade(cfg, "0002")
    command.upgrade(cfg, "head")
    engine = make_engine(migrated.database_url)
    with engine.connect() as conn:
        names = conn.execute(text("SELECT name FROM evidence_labels ORDER BY position")).scalars()
        assert list(names) == ["measured", "observed", "inferred", "suspected"]
    engine.dispose()


def test_soft_delete_is_logged_as_an_update(session):
    entry = _entry(session)
    entry.deleted_at = datetime(2026, 11, 8, tzinfo=UTC)
    session.commit()
    updates = [c for c in _changes(session, entry) if c[0] == "update"]
    assert [field for _, field, _, _ in updates] == ["deleted_at"]


@pytest.mark.parametrize("field, value", [("kind", "rumour"), ("occurred_offset_min", 99999)])
def test_database_refuses_impossible_values(session, field, value):
    entry = _entry(session)
    setattr(entry, field, value)
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_bad_move_direction_is_refused(client):
    response = client.post("/settings/evidence-labels/1/move", data={"direction": "sideways"})
    assert response.status_code == 400


def test_rename_error_keeps_the_typed_name(client):
    response = client.post("/settings/evidence-labels/1/rename", data={"name": "observed"})
    assert response.status_code == 400
    assert "already exists" in response.text
    # The rejected name is shown back in the measured row's box, not the old name.
    assert response.text.count('value="observed"') == 2
