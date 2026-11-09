"""Hypothesis and question status (M3)."""

import pytest

from benchledger.services import InvalidInput
from benchledger.services import entries as entry_service
from benchledger.services import projects as project_service
from benchledger.services.history import history_for

HTMX = {"HX-Request": "true"}


@pytest.fixture
def project(session):
    project = project_service.create_project(session, {"name": "ADR1399 drift"})
    session.commit()
    return project


def add(session, project, kind, title):
    entry = entry_service.create_entry(session, project, {"kind": kind, "title": title})
    session.commit()
    return entry


# ---- service ----


def test_status_change_is_in_history_with_before_and_after(session, project):
    entry = add(session, project, "hypothesis", "Board flex causes the steps")
    entry_service.set_status(session, entry, "Testing")
    session.commit()
    entry_service.set_status(session, entry, "Supported")
    session.commit()

    changes = [
        (c.old_value, c.new_value)
        for c in history_for(session, "entries", entry.id)
        if c.action == "update" and c.field == "status"
    ]
    assert changes == [("Testing", "Supported"), ("Untested", "Testing")]  # newest first


def test_question_statuses(session, project):
    entry = add(session, project, "question", "Does the meter drift too?")
    entry_service.set_status(session, entry, "Answered")
    assert entry.status == "Answered"
    with pytest.raises(InvalidInput):
        entry_service.set_status(session, entry, "Supported")  # a hypothesis status


def test_statuses_must_fit_the_kind(session, project):
    hypothesis = add(session, project, "hypothesis", "H")
    with pytest.raises(InvalidInput):
        entry_service.set_status(session, hypothesis, "Answered")
    with pytest.raises(InvalidInput):
        entry_service.set_status(session, hypothesis, "supported")  # case matters
    note = add(session, project, "note", "N")
    with pytest.raises(InvalidInput, match="has no status"):
        entry_service.set_status(session, note, "Open")


def test_deleted_entries_cannot_change_status(session, project):
    entry = add(session, project, "hypothesis", "H")
    entry_service.delete_entry(session, entry)
    with pytest.raises(InvalidInput):
        entry_service.set_status(session, entry, "Testing")


def test_open_filter_shows_unresolved_hypotheses_and_questions(session, project):
    untested = add(session, project, "hypothesis", "Untested one")
    testing = add(session, project, "hypothesis", "Testing one")
    entry_service.set_status(session, testing, "Testing")
    rejected = add(session, project, "hypothesis", "Rejected one")
    entry_service.set_status(session, rejected, "Rejected")
    question = add(session, project, "question", "Open question")
    answered = add(session, project, "question", "Answered question")
    entry_service.set_status(session, answered, "Answered")
    add(session, project, "observation", "Not a hypothesis")
    session.commit()

    shown = entry_service.timeline(session, project, kind=entry_service.OPEN_FILTER)
    assert set(shown) == {untested, testing, question}


# ---- pages ----


@pytest.fixture
def page(client):
    client.post("/projects/new", data={"name": "ADR1399 drift"})
    client.post(
        "/projects/adr1399-drift/entries",
        data={"kind": "hypothesis", "title": "Board flex causes the steps"},
    )
    client.post("/projects/adr1399-drift/entries", data={"kind": "note", "title": "A note"})
    return "/projects/adr1399-drift"


def test_timeline_has_a_status_picker_for_hypotheses_only(client, page):
    html = client.get(page).text
    assert 'action="/projects/adr1399-drift/entries/1/status"' in html
    assert 'action="/projects/adr1399-drift/entries/2/status"' not in html
    assert '<option value="Untested" selected>Untested</option>' in html


def test_status_change_with_htmx(client, page):
    response = client.post(f"{page}/entries/1/status", data={"status": "Testing"}, headers=HTMX)
    assert response.status_code == 200
    assert '<option value="Testing" selected>Testing</option>' in response.text

    history = client.get("/history/entries/1").text
    assert "Untested" in history and "Testing" in history


def test_status_change_without_javascript_redirects(client, page):
    response = client.post(
        f"{page}/entries/1/status",
        data={"status": "Rejected", "view_kind": "open"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"{page}?kind=open#notebook"
    # Rejected is no longer open, so the open view no longer lists it.
    assert "Board flex causes the steps" not in client.get(f"{page}?kind=open").text


def test_bad_status_is_a_400(client, page):
    assert client.post(f"{page}/entries/1/status", data={"status": "Maybe"}).status_code == 400
    assert client.post(f"{page}/entries/2/status", data={"status": "Open"}).status_code == 400


def test_open_filter_chip(client, page):
    html = client.get(f"{page}?kind=open").text
    assert 'class="chip on">Open hypotheses &amp; questions' in html
    assert "Board flex causes the steps" in html
    assert "A note" not in html


# ---- review fixes ----


def test_status_picker_saves_only_with_the_set_button(client, page):
    html = client.get(page).text
    form = html.split('action="/projects/adr1399-drift/entries/1/status"')[1].split("</form>")[0]
    assert "hx-trigger" not in form  # default trigger: submit only
    assert '<button class="btn small" type="submit">Set</button>' in form
    assert 'id="status-1"' in form  # stable id keeps focus across the swap


def test_per_entry_actions_swap_only_the_timeline(client, page):
    html = client.get(page).text
    assert '<div id="timeline">' in html
    for action in ("status", "delete"):
        form = html.split(f'action="/projects/adr1399-drift/entries/1/{action}"')[1].split(">")[0]
        assert 'hx-target="#timeline"' in form and 'hx-select="#timeline"' in form, action
    # Quick-add still refreshes the whole notebook (so its form resets after adding).
    quick = html.split('class="quick-add"')[1].split(">")[0]
    assert 'hx-target="#notebook"' in quick


def test_htmx_status_change_keeps_the_view(client, page):
    response = client.post(
        f"{page}/entries/1/status",
        data={"status": "Testing", "view_kind": "open", "view_deleted": "1"},
        headers=HTMX,
    )
    assert 'name="view_kind" value="open"' in response.text
    assert 'name="view_deleted" value="1"' in response.text


def test_status_of_a_deleted_entry_is_a_400(client, page):
    client.post(f"{page}/entries/1/delete")
    assert client.post(f"{page}/entries/1/status", data={"status": "Testing"}).status_code == 400


def test_setting_the_same_status_logs_nothing(session, project):
    entry = add(session, project, "hypothesis", "H")
    before = len(history_for(session, "entries", entry.id))
    entry_service.set_status(session, entry, "Untested")
    session.commit()
    assert len(history_for(session, "entries", entry.id)) == before


def test_kind_change_resets_status_and_logs_it(session, project):
    entry = add(session, project, "hypothesis", "H")
    entry_service.set_status(session, entry, "Supported")
    entry_service.update_entry(session, entry, {"kind": "note", "title": "H"})
    session.commit()
    status_changes = [
        (c.old_value, c.new_value)
        for c in history_for(session, "entries", entry.id)
        if c.field == "status"
    ]
    assert status_changes[0] == ("Supported", None)


def test_kind_chips_are_proper_plurals(client, page):
    html = client.get(page).text
    assert ">Hypotheses</a>" in html and "Hypothesiss" not in html
