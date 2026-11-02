"""Testes das operações de ciclo de vida do plugin (ops/config_template)."""

from pathlib import Path

from commands.complements.harness import config_template, ops
from commands.complements.harness.runner import ProcessResult
from commands.complements.harness.types import TaskResult


def test_config_template_renders_plugin_root(tmp_path):
    root = tmp_path / "harness"
    root.mkdir()
    (root / "harness.example.yaml").write_text(
        "workspace: \"{{PLUGIN_ROOT}}/workspace\"\n", encoding="utf-8"
    )

    rendered = config_template.render(root)

    assert "{{PLUGIN_ROOT}}" not in rendered
    assert root.as_posix() in rendered


def test_write_default_config_keeps_existing_unless_forced(tmp_path):
    root = tmp_path / "harness"
    root.mkdir()
    (root / "harness.example.yaml").write_text("a: 1\n", encoding="utf-8")

    target = config_template.write_default_config(root)
    assert target.read_text(encoding="utf-8") == "a: 1\n"

    target.write_text("manual: true\n", encoding="utf-8")
    config_template.write_default_config(root)
    assert target.read_text(encoding="utf-8") == "manual: true\n"

    config_template.write_default_config(root, force=True)
    assert target.read_text(encoding="utf-8") == "a: 1\n"


def test_resolve_config_uses_env(tmp_path, monkeypatch):
    config = tmp_path / "custom.yaml"
    config.write_text("workspace: ws\n", encoding="utf-8")
    monkeypatch.setenv("HARNESS_CONFIG", str(config))

    assert ops.resolve_config() == str(config)


def test_install_calls_plugin_installer(tmp_path, monkeypatch):
    plugin = tmp_path / "harness"
    plugin.mkdir()
    (plugin / "install.ps1").write_text("# fake\n", encoding="utf-8")

    calls = {}

    def fake_run(cmd, cwd=None, timeout=60, shell=False, env=None):
        calls["cmd"] = cmd
        calls["cwd"] = cwd
        return ProcessResult(0, "ok", "")

    written = {}

    def fake_write(root, force=False):
        written["force"] = force
        return Path(root) / "workspace" / "harness.yaml"

    monkeypatch.setattr(ops, "PLUGIN_ROOT", plugin)
    monkeypatch.setattr(ops, "run_process", fake_run)
    monkeypatch.setattr(ops, "write_default_config", fake_write)

    result = ops.install(force=True)

    assert result.success is True
    assert calls["cmd"][:2] == ["powershell", "-NoProfile"]
    assert "-ForceConfig" in calls["cmd"]
    assert written["force"] is True


def test_install_reports_missing_installer(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "PLUGIN_ROOT", tmp_path)

    result = ops.install()

    assert result.success is False
    assert "instalador não encontrado" in result.summary


def _stub_start(monkeypatch, rag_result=None):
    calls = {"docker": 0, "powershell": 0, "tasks": []}

    monkeypatch.setattr(ops, "ensure_config", lambda *args, **kwargs: "cfg")
    monkeypatch.setattr(ops, "_set_db_env", lambda *args, **kwargs: None)

    def fake_docker():
        calls["docker"] += 1
        return True

    def fake_powershell(*args, **kwargs):
        calls["powershell"] += 1
        return ProcessResult(0, "fixture ok", "")

    def fake_task(config, task, params=None):
        calls["tasks"].append((task, params))
        return rag_result or TaskResult(True, "rag ok")

    monkeypatch.setattr(ops, "_docker_available", fake_docker)
    monkeypatch.setattr(ops, "_powershell", fake_powershell)
    monkeypatch.setattr(ops, "_run_task", fake_task)
    return calls


def test_start_no_docker_skips_fixture(monkeypatch):
    calls = _stub_start(monkeypatch)

    result = ops.start(no_docker=True)

    assert result.success is True
    assert calls["docker"] == 0
    assert calls["powershell"] == 0
    assert calls["tasks"] == [("rag:serve", {"action": "start"})]
    assert "fixture não iniciada" in result.summary


def test_start_no_docker_and_no_rag_is_noop(monkeypatch):
    calls = _stub_start(monkeypatch)

    result = ops.start(no_docker=True, skip_rag=True)

    assert result.success is True
    assert calls["docker"] == 0
    assert calls["powershell"] == 0
    assert calls["tasks"] == []
    assert "nada a iniciar" in result.summary


def test_start_no_docker_reports_rag_failure(monkeypatch):
    _stub_start(monkeypatch, rag_result=TaskResult(False, "rag falhou", exit_code=1))

    result = ops.start(no_docker=True)

    assert result.success is False
    assert result.summary == "API do RAG não iniciou"


def test_start_without_no_docker_starts_fixture(monkeypatch):
    calls = _stub_start(monkeypatch)

    result = ops.start()

    assert result.success is True
    assert calls["docker"] == 1
    assert calls["powershell"] == 1
    assert calls["tasks"] == [("rag:serve", {"action": "start"})]
    assert result.summary == "ambiente do harness no ar"
