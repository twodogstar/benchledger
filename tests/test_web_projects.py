"""Project, history and settings pages, driven the way a browser would."""


def create(client, **fields):
    data = {"name": "Z80 NOP tester", "stage": "Active", "priority": "High", **fields}
    return client.post("/projects/new", data=data, follow_redirects=False)


def test_empty_project_list(client):
    response = client.get("/projects")
    assert response.status_code == 200
    assert "No projects yet" in response.text


def test_create_redirects_to_the_new_project(client):
    response = create(client, goal="Free-run the Z80 and watch A0–A15 count.")
    assert response.status_code == 303
    assert response.headers["location"] == "/projects/z80-nop-tester"

    page = client.get("/projects/z80-nop-tester")
    assert page.status_code == 200
    assert "Z80 NOP tester" in page.text
    assert "watch A0–A15 count" in page.text


def test_invalid_form_shows_errors_and_keeps_input(client):
    response = create(client, name="", goal="keep me")
    assert response.status_code == 400
    assert "Name is required." in response.text
    assert "keep me" in response.text


def test_edit_and_history(client):
    create(client)
    response = client.post(
        "/projects/z80-nop-tester/edit",
        data={"name": "Z80 NOP tester", "stage": "Blocked", "priority": "High"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/projects/z80-nop-tester")
    assert "Blocked" in page.text

    history = client.get("/history/projects/1")
    assert history.status_code == 200
    assert "Active" in history.text and "Blocked" in history.text


def test_user_text_is_escaped(client):
    create(client, name="<script>alert(1)</script>")
    page = client.get("/projects/script-alert-1-script")
    assert "<script>alert(1)</script>" not in page.text
    assert "&lt;script&gt;" in page.text


def test_archive_hides_from_list_and_restore_brings_back(client):
    create(client)
    client.post("/projects/z80-nop-tester/archive")
    assert "Z80 NOP tester" not in client.get("/projects").text
    assert "Z80 NOP tester" in client.get("/projects?archived=1").text

    client.post("/projects/z80-nop-tester/restore")
    assert "Z80 NOP tester" in client.get("/projects").text


def test_stage_filter(client):
    create(client)
    create(client, name="ADR1399 drift", stage="Paused")
    page = client.get("/projects?stage=Paused").text
    assert "ADR1399 drift" in page
    assert "Z80 NOP tester" not in page


def test_unknown_project_is_404(client):
    assert client.get("/projects/nope").status_code == 404


def test_dashboard_lists_active_projects(client):
    create(client)
    assert "Z80 NOP tester" in client.get("/").text


def test_settings_add_area_and_use_it(client):
    response = client.post(
        "/settings/areas", data={"name": "Power supplies"}, follow_redirects=False
    )
    assert response.status_code == 303
    assert "Power supplies" in client.get("/settings/lists").text
    assert "Power supplies" in client.get("/projects/new").text


def test_settings_duplicate_area_shows_error(client):
    response = client.post("/settings/areas", data={"name": "Metrology"})
    assert response.status_code == 400
    assert "already exists" in response.text
