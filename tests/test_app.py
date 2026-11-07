from fastapi.testclient import TestClient

from benchledger import __version__
from benchledger.app import create_app


def test_dashboard_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "BENCH<em>LEDGER</em>" in response.text
    assert "0002" in response.text  # schema revision shown


def test_healthz_reports_ok(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": __version__, "schema_revision": "0002"}


def test_healthz_reports_unmigrated_database(settings):
    settings.data_dir.mkdir(parents=True)
    app = create_app(settings)  # no upgrade() on purpose
    with TestClient(app) as client:
        response = client.get("/healthz")
    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    app.state.engine.dispose()


def test_stylesheet_is_served(client):
    response = client.get("/static/css/benchledger.css")
    assert response.status_code == 200
    assert "--mint" in response.text
