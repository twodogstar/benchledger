"""Project service rules (M1)."""

import pytest

from benchledger.services import InvalidInput
from benchledger.services import areas as area_service
from benchledger.services import projects as project_service


def test_create_sets_slug_and_defaults(session):
    project = project_service.create_project(session, {"name": "  Mega 2560   PWM tests "})
    assert project.name == "Mega 2560 PWM tests"
    assert project.slug == "mega-2560-pwm-tests"
    assert project.stage == "Idea"
    assert project.priority == "Medium"


def test_slugs_stay_unique(session):
    first = project_service.create_project(session, {"name": "RTL-SDR"})
    second = project_service.create_project(session, {"name": "RTL SDR"})
    assert (first.slug, second.slug) == ("rtl-sdr", "rtl-sdr-2")


def test_reserved_slug_is_avoided(session):
    project = project_service.create_project(session, {"name": "New"})
    assert project.slug == "new-2"


def test_validation_collects_every_error(session):
    with pytest.raises(InvalidInput) as exc:
        project_service.create_project(
            session, {"name": "", "stage": "Someday", "priority": "Urgent", "area_id": "999"}
        )
    assert set(exc.value.errors) == {"name", "stage", "priority", "area_id"}


def test_text_keeps_line_breaks(session):
    project = project_service.create_project(
        session, {"name": "Wiring test", "wiring": "Rear HI -> SMA centre\r\nRear LO -> shield\r\n"}
    )
    assert project.wiring == "Rear HI -> SMA centre\nRear LO -> shield"


def test_list_filters_by_stage_and_hides_archived(session):
    active = project_service.create_project(session, {"name": "A", "stage": "Active"})
    project_service.create_project(session, {"name": "B", "stage": "Paused"})
    gone = project_service.create_project(session, {"name": "C", "stage": "Active"})
    project_service.archive_project(session, gone)

    assert project_service.list_projects(session, stage="Active") == [active]
    assert gone in project_service.list_projects(session, include_archived=True)


def test_retired_area_stays_on_existing_project_but_not_new_ones(session):
    area = area_service.create_area(session, "Power supplies")
    project = project_service.create_project(session, {"name": "PSU", "area_id": str(area.id)})
    area_service.archive_area(session, area)

    # Saving the existing project with its retired area is fine...
    project_service.update_project(session, project, {"name": "PSU v2", "area_id": str(area.id)})
    assert project.area_id == area.id
    # ...but a new project can't pick it.
    with pytest.raises(InvalidInput) as exc:
        project_service.create_project(session, {"name": "Another", "area_id": str(area.id)})
    assert "area_id" in exc.value.errors
