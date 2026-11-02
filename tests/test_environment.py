import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from commands.environment import EnvironmentCommand, SAMPLE_CONFIG


@pytest.fixture
def command(tmp_path, monkeypatch):
    config = tmp_path / "environment_conf.json"
    monkeypatch.setattr(EnvironmentCommand, "_config_path", lambda self: str(config))
    return EnvironmentCommand(), config


def test_init_creates_sample_config(command, capsys):
    cmd, config = command

    ok, data = cmd.execute(["init"])

    assert ok is True
    assert data == {"path": str(config), "created": True}
    payload = json.loads(config.read_text(encoding="utf-8"))
    assert payload == SAMPLE_CONFIG
    assert cmd.environments == SAMPLE_CONFIG["environments"]
    assert "environment_conf.json criado" in capsys.readouterr().out


def test_init_keeps_existing_config_without_force(command, capsys):
    cmd, config = command
    existing = {"dev": "C:/dev/docker-compose.yml"}
    config.write_text(json.dumps({"environments": existing}), encoding="utf-8")
    cmd.environments = dict(existing)

    ok, data = cmd.execute(["init"])

    assert ok is False
    assert "já existe" in data["error"]
    assert json.loads(config.read_text(encoding="utf-8"))["environments"] == existing
    assert "/environment init --force" in capsys.readouterr().out


def test_init_force_overwrites_existing_config(command):
    cmd, config = command
    config.write_text('{"environments": {"dev": "C:/dev/docker-compose.yml"}}', encoding="utf-8")
    cmd.environments = {"dev": "C:/dev/docker-compose.yml"}

    ok, _ = cmd.execute(["init", "--force"])

    assert ok is True
    assert json.loads(config.read_text(encoding="utf-8")) == SAMPLE_CONFIG
    assert "dev" not in cmd.environments


def test_list_suggests_init_when_no_environments(command, capsys):
    cmd, _ = command

    ok, data = cmd.execute(["list"])

    assert ok is True
    assert data == {"environments": {}}
    assert "/environment init" in capsys.readouterr().out
