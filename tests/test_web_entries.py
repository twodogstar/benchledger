"""The notebook on the project page, driven the way a browser (with and without htmx) would."""

import re

import pytest

HTMX = {"HX-Request": "true"}


@pytest.fixture
def project(client):
    client.post("/projects/new", data={"name": "ADR1399 drift", "stage": "Active"})
    return "/projects/adr1399-drift"


def add(client, project, headers=None, **fields):
    data = {"kind": "observation", "title": "Output settles after 40 min", **fields}
    return client.post(
        f"{project}/entries", data=data, headers=headers or {}, follow_redirects=False
    )


def test_base_page_loads_vendored_htmx(client):
    page = client.get("/").text
    assert "/static/vendor/htmx.min.js" in page
    assert "unpkg.com" not in page  # no CDN (N9: runs offline)
    assert client.get("/static/vendor/htmx.min.js").status_code == 200


def test_project_page_shows_empty_notebook_and_quick_add(client, project):
    page = client.get(project).text
    assert 'id="notebook"' in page
    assert 'hx-post="/projects/adr1399-drift/entries"' in page
    assert "No entries yet" in page


def test_quick_add_with_htmx_returns_the_notebook_fragment(client, project):
    response = add(client, project, headers=HTMX, evidence_label_id="1")
    assert response.status_code == 200
    assert response.text.lstrip().startswith('<section class="panel notebook" id="notebook">')
    assert "<html" not in response.text  # a fragment, not a whole page
    assert "Output settles after 40 min" in response.text
    assert "measured" in response.text
    # The form is reset for the next entry.
    assert 'name="title" value=""' in response.text


def test_quick_add_without_javascript_redirects(client, project):
    response = add(client, project)
    assert response.status_code == 303
    assert response.headers["location"] == f"{project}#notebook"
    assert "Output settles after 40 min" in client.get(project).text


def test_quick_add_error_with_htmx_keeps_input(client, project):
    response = add(client, project, headers=HTMX, title="", body="keep this text")
    assert response.status_code == 200  # htmx swaps only 2xx; the errors are in the fragment
    assert "Title is required." in response.text
    assert "keep this text" in response.text


def test_quick_add_error_without_javascript_is_a_400_page(client, project):
    response = add(client, project, title="", kind="rumour")
    assert response.status_code == 400
    assert "Title is required." in response.text
    assert "Pick a kind from the list." in response.text
    assert "<html" in response.text


def test_edit_page_and_history(client, project):
    add(client, project, body="σ looks like 0.6 ppm", occurred_at="2026-10-31T18:20")
    form = client.get(f"{project}/entries/1/edit")
    assert form.status_code == 200
    assert "σ looks like 0.6 ppm" in form.text
    assert 'value="2026-10-31T18:20"' in form.text  # shown back in local time

    response = client.post(
        f"{project}/entries/1/edit",
        data={
            "kind": "observation",
            "title": "Output settles after 45 min",
            "body": "σ over 11 min is 0.25 ppm",
            "occurred_at": "2026-10-31T18:20",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"{project}#entry-1"
    assert "Output settles after 45 min" in client.get(project).text

    history = client.get("/history/entries/1")
    assert history.status_code == 200
    assert "Entry history: Output settles after 45 min" in history.text
    assert "σ looks like 0.6 ppm" in history.text and "σ over 11 min is 0.25 ppm" in history.text
    assert 'href="/projects/adr1399-drift#entry-1"' in history.text
    # The time was resubmitted unchanged: only its insert row, no false update row.
    assert history.text.count(">occurred at<") == 1


def test_edit_errors_show_on_the_form(client, project):
    add(client, project)
    response = client.post(f"{project}/entries/1/edit", data={"kind": "note", "title": ""})
    assert response.status_code == 400
    assert "Title is required." in response.text


def test_delete_and_restore_with_htmx(client, project):
    add(client, project)
    response = client.post(f"{project}/entries/1/delete", headers=HTMX)
    assert response.status_code == 200
    assert "Output settles after 40 min" not in response.text

    deleted_view = client.get(f"{project}?deleted=1").text
    assert "Output settles after 40 min" in deleted_view and "Restore" in deleted_view

    response = client.post(f"{project}/entries/1/restore", headers=HTMX)
    assert response.status_code == 200
    assert "Output settles after 40 min" in response.text
    assert "Output settles after 40 min" in client.get(project).text


def test_delete_without_javascript_redirects(client, project):
    add(client, project)
    response = client.post(f"{project}/entries/1/delete", follow_redirects=False)
    assert response.status_code == 303
    assert "Output settles after 40 min" not in client.get(project).text


def test_deleted_entry_cannot_be_edited_and_says_why(client, project):
    add(client, project)
    client.post(f"{project}/entries/1/delete")
    response = client.post(f"{project}/entries/1/edit", data={"kind": "note", "title": "x"})
    assert response.status_code == 400
    assert "Restore this entry before editing it." in response.text


def test_kind_filter(client, project):
    add(client, project)
    add(client, project, kind="hypothesis", title="Board flex causes the steps")
    page = client.get(f"{project}?kind=hypothesis").text
    assert "Board flex causes the steps" in page
    assert "Output settles after 40 min" not in page
    assert "Untested" in page  # default status badge
    # An unknown kind shows everything rather than failing.
    assert "Output settles after 40 min" in client.get(f"{project}?kind=rumour").text


def test_user_text_is_escaped(client, project):
    add(
        client,
        project,
        title="<script>alert('t')</script>",
        source='<img src=x onerror="alert(1)">',
        body="<script>alert('b')</script>\n\n[x](javascript:alert(1))",
    )
    page = client.get(project).text
    assert "<script>alert" not in page
    assert "&lt;script&gt;alert(&#39;t&#39;)&lt;/script&gt;" in page
    assert '<img src=x onerror="alert(1)">' not in page
    assert 'href="javascript' not in page
    # No real tag in the page carries an event handler.
    assert not re.search(r"<[a-z][^>]*\son\w+\s*=", page, re.IGNORECASE)


def test_markdown_body_is_rendered(client, project):
    add(client, project, body="Within **1 ppm** of final")
    assert "Within <strong>1 ppm</strong> of final" in client.get(project).text


def test_entries_are_scoped_to_their_project(client, project):
    add(client, project)
    client.post("/projects/new", data={"name": "Z80 tester"})
    assert client.get("/projects/z80-tester/entries/1/edit").status_code == 404
    assert client.post("/projects/z80-tester/entries/1/delete").status_code == 404
    assert (
        client.post("/projects/nope/entries", data={"kind": "note", "title": "x"}).status_code
        == 404
    )


def test_time_shows_local_with_utc_tooltip(client, project):
    add(client, project, occurred_at="2026-10-31T18:20")
    page = client.get(project).text
    assert "2026-10-31 18:20" in page
    assert re.search(r'title="2026-1\d-\d\d \d\d:20 UTC · entered at UTC[+-]\d\d:\d\d"', page)


# ---- review fixes ----


def test_htmx_add_keeps_the_kind_filter(client, project):
    add(client, project, kind="hypothesis", title="Board flex causes the steps")
    response = add(
        client, project, headers=HTMX, kind="note", title="A note", view_kind="hypothesis"
    )
    assert "Board flex causes the steps" in response.text
    assert "A note" not in response.text  # still filtered to hypotheses
    assert 'name="view_kind" value="hypothesis"' in response.text


def test_plain_delete_returns_to_the_same_view(client, project):
    add(client, project, kind="hypothesis", title="H1")
    response = client.post(
        f"{project}/entries/1/delete", data={"view_kind": "hypothesis"}, follow_redirects=False
    )
    assert response.headers["location"] == f"{project}?kind=hypothesis#notebook"


def test_restore_stays_on_the_deleted_view(client, project):
    add(client, project)
    client.post(f"{project}/entries/1/delete")
    response = client.post(f"{project}/entries/1/restore", data={"view_deleted": "1"}, headers=HTMX)
    assert 'class="chip on">Show deleted' in response.text


def test_deleted_and_kind_filters_combine(client, project):
    add(client, project, kind="hypothesis", title="Deleted hypothesis")
    add(client, project, kind="note", title="Deleted note")
    client.post(f"{project}/entries/1/delete")
    client.post(f"{project}/entries/2/delete")
    page = client.get(f"{project}?kind=hypothesis&deleted=1").text
    assert "Deleted hypothesis" in page and "Deleted note" not in page


def test_time_element_has_iso_datetime(client, project):
    add(client, project, occurred_at="2026-10-31T18:20")
    assert re.search(r'<time [^>]*datetime="2026-1\d-\d\dT\d\d:20:00Z"', client.get(project).text)


def test_edit_page_for_a_deleted_entry_redirects_to_restore(client, project):
    add(client, project)
    client.post(f"{project}/entries/1/delete")
    response = client.get(f"{project}/entries/1/edit", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"{project}?deleted=1#entry-1"


@pytest.mark.parametrize(
    "url",
    [
        "/history/entries/99999999999999999999",
        "/projects/adr1399-drift/entries/99999999999999999999/edit",
        "/history/entries/0",
    ],
)
def test_out_of_range_ids_are_client_errors_not_500(client, project, url):
    assert 400 <= client.get(url).status_code < 500


def test_page_has_an_htmx_error_box_and_script(client, project):
    page = client.get(project).text
    assert 'id="htmx-error"' in page
    assert "/static/js/benchledger.js" in page
    assert client.get("/static/js/benchledger.js").status_code == 200


def test_retired_label_stays_selectable_on_its_entry(client, project):
    add(client, project, evidence_label_id="4")  # suspected
    client.post("/settings/evidence-labels/4/archive")
    form = client.get(f"{project}/entries/1/edit").text
    assert "suspected (retired)" in form
    # ...but isn't offered for new entries.
    assert ">suspected<" not in client.get(project).text.split('id="notebook"')[1].split("<ol")[0]


def test_user_text_is_escaped_on_edit_form_and_history(client, project):
    payload = '"><script>alert(1)</script>'
    add(client, project, title=payload, source=payload, body=payload)
    for url in (f"{project}/entries/1/edit", "/history/entries/1"):
        page = client.get(url).text
        assert "<script>alert(1)</script>" not in page, url
        assert "&#34;&gt;&lt;script&gt;" in page or "&quot;&gt;&lt;script&gt;" in page, url
