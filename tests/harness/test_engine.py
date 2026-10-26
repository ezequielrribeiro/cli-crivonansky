import yaml

from commands.complements.harness.catalog import load_tasks, register
from commands.complements.harness.engine import HarnessEngine
from commands.complements.harness.types import TaskResult, TaskSpec


def _config(tmp_path):
    workspace = tmp_path / "ws"
    config = {
        "harness_version": 1,
        "workspace": str(workspace),
        "output": {"default_sinks": ["stdout"], "max_chars": {"clipboard": 1000}},
        "policy": {"deny_patterns": [], "auto_approve": ["read"], "confirm": ["write"]},
        "legacy": {"repo_path": str(tmp_path)},
    }
    path = tmp_path / "harness.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path, workspace


def test_engine_runs_read_task(tmp_path):
    load_tasks()
    register(
        TaskSpec(
            name="test:echo",
            intent="read",
            description="",
            required=["value"],
            optional=[],
            handler=lambda ctx, params: TaskResult(True, params["value"], details=params["value"]),
        )
    )
    config, _ = _config(tmp_path)
    engine = HarnessEngine(config_path=str(config), interactive=False, sinks=["stdout"])

    text, status = engine.handle_block(
        "harness: 1\ntask: test:echo\nparams:\n  value: oi\n"
    )

    assert status == "success"
    assert 'summary: "oi"' in text


def test_engine_denies_write_when_not_interactive(tmp_path):
    load_tasks()
    register(
        TaskSpec(
            name="test:write",
            intent="write",
            description="",
            required=[],
            optional=[],
            handler=lambda ctx, params: TaskResult(True, "ok"),
        )
    )
    config, _ = _config(tmp_path)
    engine = HarnessEngine(config_path=str(config), interactive=False)

    _text, status = engine.handle_block("harness: 1\ntask: test:write\nparams: {}\n")

    assert status == "denied"


def test_engine_reports_unknown_task(tmp_path):
    load_tasks()
    config, _ = _config(tmp_path)
    engine = HarnessEngine(config_path=str(config), interactive=False)

    _text, status = engine.handle_block("harness: 1\ntask: nope\nparams: {}\n")

    assert status == "denied"


def test_engine_reports_unknown_param(tmp_path):
    load_tasks()
    register(
        TaskSpec(
            name="test:echo2",
            intent="read",
            description="",
            required=[],
            optional=["value"],
            handler=lambda ctx, params: TaskResult(True, "ok"),
        )
    )
    config, _ = _config(tmp_path)
    engine = HarnessEngine(config_path=str(config), interactive=False)

    _text, status = engine.handle_block("harness: 1\ntask: test:echo2\nparams:\n  nope: 1\n")

    assert status == "error"


def test_engine_writes_run_artifacts(tmp_path):
    load_tasks()
    register(
        TaskSpec(
            name="test:echo3",
            intent="read",
            description="",
            required=[],
            optional=[],
            handler=lambda ctx, params: TaskResult(True, "ok"),
        )
    )
    config, workspace = _config(tmp_path)
    engine = HarnessEngine(config_path=str(config), interactive=False)

    engine.handle_block("harness: 1\ntask: test:echo3\nparams: {}\n")

    assert (workspace / "runs" / "runs.jsonl").is_file()
