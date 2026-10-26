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
    return path


def _block(task):
    return f"```crivonansky\nharness: 1\ntask: {task}\nparams: {{}}\n```"


def test_handle_text_processes_multiple_blocks(tmp_path):
    load_tasks()
    register(
        TaskSpec(
            name="test:ok",
            intent="read",
            description="",
            required=[],
            optional=[],
            handler=lambda ctx, params: TaskResult(True, "ok"),
        )
    )
    engine = HarnessEngine(config_path=str(_config(tmp_path)), interactive=False)

    results, error = engine.handle_text(_block("test:ok") + "\n" + _block("test:ok"))

    assert error is None
    assert len(results) == 2
    assert all(item["status"] == "success" for item in results)


def test_handle_text_stops_on_failure(tmp_path):
    load_tasks()
    register(
        TaskSpec(
            name="test:ok2",
            intent="read",
            description="",
            required=[],
            optional=[],
            handler=lambda ctx, params: TaskResult(True, "ok"),
        )
    )
    register(
        TaskSpec(
            name="test:fail",
            intent="read",
            description="",
            required=[],
            optional=[],
            handler=lambda ctx, params: TaskResult(False, "nope"),
        )
    )
    engine = HarnessEngine(config_path=str(_config(tmp_path)), interactive=False)

    results, _ = engine.handle_text(_block("test:fail") + "\n" + _block("test:ok2"))

    assert len(results) == 1
    assert results[0]["status"] == "failure"


def test_handle_text_without_blocks_returns_error(tmp_path):
    load_tasks()
    engine = HarnessEngine(config_path=str(_config(tmp_path)), interactive=False)

    results, error = engine.handle_text("texto livre sem bloco")

    assert results == []
    assert error is not None
