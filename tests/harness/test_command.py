"""Testes do comando /harness (helpers de contexto e help)."""

import json
from types import SimpleNamespace

from commands.harness import HarnessCommand
from commands.complements.harness.types import TaskResult


def test_help_lists_lifecycle_and_contract_subcommands():
    text = HarnessCommand().help_text

    for subcommand in (
        "install",
        "start",
        "stop",
        "prepare",
        "preprocess",
        "config",
        "exec",
        "run",
        "ask",
        "tasks",
        "runs",
        "hooks",
        "env:check",
    ):
        assert subcommand in text


def test_start_forwards_no_docker_flag(monkeypatch):
    captured = {}

    def fake_start(**kwargs):
        captured.update(kwargs)
        return TaskResult(True, "ok")

    monkeypatch.setattr("commands.harness.ops.start", fake_start)

    ok, data = HarnessCommand().execute(["start", "--no-docker"])

    assert ok is True
    assert captured["no_docker"] is True
    assert captured["skip_rag"] is False
    assert data["summary"] == "ok"


def test_db_context_summarizes_schema_catalog(tmp_path):
    knowledge = tmp_path / "knowledge" / "db"
    knowledge.mkdir(parents=True)
    (knowledge / "schema-catalog.json").write_text(
        json.dumps(
            {
                "tables": [
                    {
                        "name": "tb_clientes",
                        "comment": "Clientes",
                        "columns": [
                            {"name": "id_cli", "type": "INT"},
                            {"name": "nome", "type": "VARCHAR(120)"},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    text = HarnessCommand()._db_context(SimpleNamespace(workspace=str(tmp_path)))

    assert "### tb_clientes" in text
    assert "Clientes" in text
    assert "id_cli INT" in text
    assert "nome VARCHAR(120)" in text


def test_db_context_reports_missing_catalog(tmp_path):
    text = HarnessCommand()._db_context(SimpleNamespace(workspace=str(tmp_path)))

    assert "schema-catalog.json não encontrado" in text
