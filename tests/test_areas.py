"""The editable areas list."""

import pytest

from benchledger.services import InvalidInput
from benchledger.services import areas as area_service

DEFAULTS = [
    "Retro computing",
    "Embedded",
    "Metrology",
    "Instrumentation",
    "Tool building",
    "RF/SDR",
    "Test equipment",
    "Other",
]


def names(session, **kwargs):
    return [a.name for a in area_service.list_areas(session, **kwargs)]


def test_defaults_are_seeded_in_order(session):
    assert names(session) == DEFAULTS


def test_add_goes_to_the_end(session):
    area_service.create_area(session, "Power supplies")
    assert names(session)[-1] == "Power supplies"


def test_names_are_unique_ignoring_case(session):
    with pytest.raises(InvalidInput):
        area_service.create_area(session, "metrology")


def test_rename_keeps_position(session):
    metrology = area_service.list_areas(session)[2]
    area_service.rename_area(session, metrology, "Metrology & references")
    assert names(session)[2] == "Metrology & references"


def test_move_up_and_down(session):
    embedded = area_service.list_areas(session)[1]
    area_service.move_area(session, embedded, "up")
    assert names(session)[:2] == ["Embedded", "Retro computing"]
    area_service.move_area(session, embedded, "down")
    assert names(session)[:2] == ["Retro computing", "Embedded"]


def test_moving_past_the_ends_does_nothing(session):
    first = area_service.list_areas(session)[0]
    area_service.move_area(session, first, "up")
    assert names(session) == DEFAULTS


def test_retire_and_restore(session):
    other = area_service.list_areas(session)[-1]
    area_service.archive_area(session, other)
    assert "Other" not in names(session)
    assert "Other" in names(session, include_archived=True)
    area_service.restore_area(session, other)
    assert "Other" in names(session)
