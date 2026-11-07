from pathlib import Path

import pytest

from benchledger.config import DEFAULT_HOST, DEFAULT_PORT, load_settings


def test_defaults_when_no_config_file(tmp_path):
    env = {"XDG_CONFIG_HOME": str(tmp_path)}  # empty folder: no config file
    settings = load_settings(env)
    assert settings.host == DEFAULT_HOST
    assert settings.port == DEFAULT_PORT
    assert settings.data_dir == Path("~/benchledger-data").expanduser().resolve()


def test_config_file_values(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(f'data_dir = "{tmp_path / "bench"}"\nport = 9000\n')
    settings = load_settings({"BENCHLEDGER_CONFIG": str(config)})
    assert settings.data_dir == (tmp_path / "bench").resolve()
    assert settings.port == 9000
    assert settings.database_path == (tmp_path / "bench" / "benchledger.db").resolve()


def test_environment_overrides_config_file(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("port = 9000\n")
    env = {"BENCHLEDGER_CONFIG": str(config), "BENCHLEDGER_PORT": "9100"}
    assert load_settings(env).port == 9100


def test_invalid_port_is_rejected(tmp_path):
    env = {"XDG_CONFIG_HOME": str(tmp_path), "BENCHLEDGER_PORT": "70000"}
    with pytest.raises(ValueError, match="port"):
        load_settings(env)
