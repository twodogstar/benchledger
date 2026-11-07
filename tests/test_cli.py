from typer.testing import CliRunner

from benchledger import __version__
from benchledger.cli import app

runner = CliRunner()


def test_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for command in ("serve", "db", "version"):
        assert command in result.output


def test_db_upgrade_then_current(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCHLEDGER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))  # ignore any real config file

    result = runner.invoke(app, ["db", "upgrade"])
    assert result.exit_code == 0, result.output

    result = runner.invoke(app, ["db", "current"])
    assert result.exit_code == 0
    assert "0002" in result.output
