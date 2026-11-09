"""The entry service (M2, M3) and time handling (N7)."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from benchledger import timeutil
from benchledger.services import InvalidInput
from benchledger.services import entries as entry_service
from benchledger.services import lists as list_service
from benchledger.services import projects as project_service
from benchledger.services.history import history_for

LA = ZoneInfo("America/Los_Angeles")


@pytest.fixture
def project(session):
    project = project_service.create_project(session, {"name": "ADR1399 drift"})
    session.commit()
    return project


def add(session, project, **fields):
    data = {"kind": "observation", "title": "Warm-up done", **fields}
    entry = entry_service.create_entry(session, project, data, tz=LA)
    session.commit()
    return entry


# ---- time handling (N7) ----


def test_local_time_is_stored_as_utc_with_offset():
    utc, offset = timeutil.parse_local("2026-10-31T18:20", LA)
    assert utc == datetime(2026, 11, 1, 1, 20, tzinfo=UTC)
    assert offset == -420  # PDT


def test_fall_back_hour_reads_as_first_occurrence():
    # Nov 1, 2026: clocks went from 01:59 PDT back to 01:00 PST.
    utc, offset = timeutil.parse_local("2026-11-01T01:30", LA)
    assert (utc, offset) == (datetime(2026, 11, 1, 8, 30, tzinfo=UTC), -420)
    utc_after, offset_after = timeutil.parse_local("2026-11-01T02:30", LA)
    assert (utc_after, offset_after) == (datetime(2026, 11, 1, 10, 30, tzinfo=UTC), -480)


def test_offset_needs_aware_and_from_local_needs_naive():
    with pytest.raises(ValueError):
        timeutil.offset_minutes(datetime(2026, 11, 1))
    with pytest.raises(ValueError):
        timeutil.from_local(datetime(2026, 11, 1, tzinfo=UTC))


def test_values_read_back_from_sqlite_are_treated_as_utc():
    naive = datetime(2026, 11, 1, 1, 20)
    assert timeutil.as_utc(naive) == datetime(2026, 11, 1, 1, 20, tzinfo=UTC)
    assert timeutil.form_value(naive, LA) == "2026-10-31T18:20"


# ---- create ----


def test_create_stores_utc_and_source_offset(session, project):
    entry = add(session, project, occurred_at="2026-10-31T18:20")
    session.expire_all()  # read back from the database, not the identity map
    assert timeutil.as_utc(entry.occurred_at) == datetime(2026, 11, 1, 1, 20, tzinfo=UTC)
    assert entry.occurred_offset_min == -420
    assert entry.author_id == 1  # U1


def test_create_without_time_uses_now(session, project):
    before = timeutil.now_utc().replace(second=0, microsecond=0)
    entry = add(session, project)
    assert before <= timeutil.as_utc(entry.occurred_at) <= timeutil.now_utc()


def test_hypotheses_and_questions_get_a_default_status(session, project):
    assert add(session, project, kind="hypothesis").status == "Untested"
    assert add(session, project, kind="question").status == "Open"
    assert add(session, project, kind="decision").status is None


def test_create_validates_every_field(session, project):
    data = {
        "kind": "rumour",
        "title": "  ",
        "source": "x" * 301,
        "evidence_label_id": "999",
        "occurred_at": "yesterday",
    }
    with pytest.raises(InvalidInput) as exc:
        entry_service.create_entry(session, project, data, tz=LA)
    assert set(exc.value.errors) == {"kind", "title", "source", "evidence_label_id", "occurred_at"}


def test_retired_evidence_label_cannot_be_chosen(session, project):
    from benchledger.db.models import EvidenceLabel

    suspected = list_service.list_items(session, EvidenceLabel)[3]
    list_service.archive_item(session, suspected)
    with pytest.raises(InvalidInput):
        add(session, project, evidence_label_id=str(suspected.id))


# ---- edit ----


def test_edit_keeps_the_old_text_in_history(session, project):
    entry = add(session, project, body="σ looks like 0.6 ppm", occurred_at="2026-10-31T18:20")
    entry_service.update_entry(
        session,
        entry,
        {"kind": "observation", "title": "Warm-up done", "body": "σ over 11 min is 0.25 ppm"},
        tz=LA,
    )
    session.commit()

    assert entry.body == "σ over 11 min is 0.25 ppm"
    body_changes = [
        (c.old_value, c.new_value)
        for c in history_for(session, "entries", entry.id)
        if c.field == "body"
    ]
    assert ("σ looks like 0.6 ppm", "σ over 11 min is 0.25 ppm") in body_changes
    # Blank time on edit keeps the original time.
    assert timeutil.as_utc(entry.occurred_at) == datetime(2026, 11, 1, 1, 20, tzinfo=UTC)


def test_changing_kind_resets_a_status_that_no_longer_fits(session, project):
    entry = add(session, project, kind="hypothesis")
    entry_service.update_entry(session, entry, {"kind": "question", "title": "Is it warm-up?"})
    assert entry.status == "Open"
    entry_service.update_entry(session, entry, {"kind": "note", "title": "Is it warm-up?"})
    assert entry.status is None


def test_edit_keeps_a_retired_label_already_on_the_entry(session, project):
    from benchledger.db.models import EvidenceLabel

    suspected = list_service.list_items(session, EvidenceLabel)[3]
    entry = add(session, project, evidence_label_id=str(suspected.id))
    list_service.archive_item(session, suspected)
    data = {"kind": "observation", "title": "Edited", "evidence_label_id": str(suspected.id)}
    entry_service.update_entry(session, entry, data)
    assert entry.evidence_label_id == suspected.id


# ---- delete and restore ----


def test_soft_delete_and_restore(session, project):
    entry = add(session, project)
    entry_service.delete_entry(session, entry)
    session.commit()
    assert entry_service.timeline(session, project) == []
    assert entry_service.timeline(session, project, include_deleted=True) == [entry]
    # Still reachable by id, so it can be restored and its history viewed.
    assert entry_service.get_entry(session, project, entry.id) is entry

    entry_service.restore_entry(session, entry)
    session.commit()
    assert entry_service.timeline(session, project) == [entry]
    fields = [c.field for c in history_for(session, "entries", entry.id) if c.action == "update"]
    assert fields.count("deleted_at") == 2  # deleted, then restored


# ---- timeline ----


def test_timeline_is_newest_first_and_filters_by_kind(session, project):
    older = add(session, project, occurred_at="2026-10-31T18:20")
    newer = add(session, project, kind="hypothesis", occurred_at="2026-11-01T09:00")
    middle = add(session, project, kind="decision", occurred_at="2026-11-01T01:30")
    assert entry_service.timeline(session, project) == [newer, middle, older]
    assert entry_service.timeline(session, project, kind="hypothesis") == [newer]


def test_timeline_orders_across_the_dst_change(session, project):
    # 01:30 PDT happens before 01:10 PST the same night; UTC keeps them in order.
    first = add(session, project, occurred_at="2026-11-01T01:30")
    second = entry_service.create_entry(session, project, {"kind": "note", "title": "Later"}, tz=LA)
    second.occurred_at = datetime(2026, 11, 1, 9, 10, tzinfo=UTC)  # 01:10 PST
    session.commit()
    assert entry_service.timeline(session, project) == [second, first]


def test_entries_belong_to_their_project(session, project):
    other = project_service.create_project(session, {"name": "Z80 tester"})
    entry = add(session, project)
    assert entry_service.get_entry(session, other, entry.id) is None
    assert entry_service.timeline(session, other) == []


# ---- review fixes ----


def test_spring_forward_gap_gets_a_consistent_offset():
    # 02:30 on Mar 8, 2026 doesn't exist in Los Angeles; it lands on 03:30 PDT.
    utc, offset = timeutil.parse_local("2026-03-08T02:30", LA)
    assert utc == datetime(2026, 3, 8, 10, 30, tzinfo=UTC)
    assert offset == -420


@pytest.mark.parametrize("text", ["9999-12-31T23:59", "0001-01-01T00:00", "1899-06-01T12:00"])
def test_out_of_range_dates_are_a_validation_error(session, project, text):
    with pytest.raises(InvalidInput) as exc:
        add(session, project, occurred_at=text)
    assert set(exc.value.errors) == {"occurred_at"}


@pytest.mark.parametrize("raw", ["²", "①", "9" * 30, "-1", "1.0"])
def test_odd_evidence_label_ids_are_a_validation_error(session, project, raw):
    with pytest.raises(InvalidInput) as exc:
        add(session, project, evidence_label_id=raw)
    assert set(exc.value.errors) == {"evidence_label_id"}


def test_oversized_body_is_refused(session, project):
    with pytest.raises(InvalidInput) as exc:
        add(session, project, body="x" * (entry_service.MAX_BODY + 1))
    assert set(exc.value.errors) == {"body"}


def test_missing_fields_given_as_none_are_validation_errors(session, project):
    data = {"kind": "note", "title": None, "body": None, "source": None}
    with pytest.raises(InvalidInput) as exc:
        entry_service.create_entry(session, project, data, tz=LA)
    assert set(exc.value.errors) == {"title"}


def test_resubmitting_the_shown_time_changes_nothing(session, project):
    entry = add(session, project, occurred_at="2026-10-31T18:20")
    session.expire_all()  # occurred_at now comes back naive from SQLite
    shown = timeutil.form_value(entry.occurred_at, LA)
    data = {"kind": "observation", "title": "Warm-up done", "occurred_at": shown}
    entry_service.update_entry(session, entry, data, tz=LA)
    session.commit()
    assert [c for c in history_for(session, "entries", entry.id) if c.action == "update"] == []


def test_editing_an_entry_in_the_repeated_hour_keeps_its_time(session, project):
    # 01:30 PST, the second 01:30 of the fall-back night, can't be typed unambiguously.
    entry = add(session, project, occurred_at="2026-11-01T03:00")
    entry.occurred_at = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
    entry.occurred_offset_min = -480
    session.commit()
    session.expire_all()

    shown = timeutil.form_value(entry.occurred_at, LA)
    assert shown == "2026-11-01T01:30"
    data = {"kind": "observation", "title": "New title", "occurred_at": shown}
    entry_service.update_entry(session, entry, data, tz=LA)
    session.commit()
    session.expire_all()
    assert timeutil.as_utc(entry.occurred_at) == datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
    assert entry.occurred_offset_min == -480


def test_deleted_entries_cannot_be_edited(session, project):
    entry = add(session, project)
    entry_service.delete_entry(session, entry)
    with pytest.raises(InvalidInput):
        entry_service.update_entry(session, entry, {"kind": "note", "title": "Sneaky"})


def test_delete_refuses_a_naive_time(session, project):
    entry = add(session, project)
    with pytest.raises(ValueError):
        entry_service.delete_entry(session, entry, at=datetime(2026, 11, 8, 12, 0))


def test_delete_and_restore_twice_are_no_ops(session, project):
    entry = add(session, project)
    entry_service.delete_entry(session, entry, at=datetime(2026, 11, 8, tzinfo=UTC))
    entry_service.delete_entry(session, entry)
    session.commit()
    assert timeutil.as_utc(entry.deleted_at) == datetime(2026, 11, 8, tzinfo=UTC)
    entry_service.restore_entry(session, entry)
    entry_service.restore_entry(session, entry)
    session.commit()
    fields = [c.field for c in history_for(session, "entries", entry.id) if c.action == "update"]
    assert fields == ["deleted_at", "deleted_at"]


def test_project_area_ids_use_the_same_safe_parsing(session):
    with pytest.raises(InvalidInput) as exc:
        project_service.create_project(session, {"name": "Odd", "area_id": "²"})
    assert set(exc.value.errors) == {"area_id"}
