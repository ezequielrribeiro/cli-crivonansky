from commands.complements.harness.runner import ProcessResult
from commands.complements.harness.tasks import code
from commands.complements.harness.types import TaskContext


def test_extract_runs_outside_repo_and_pins_codegraph_out(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    workspace = tmp_path / "ws"
    graph = workspace / "knowledge" / "code" / "codegraph-out" / "graph.json"
    graph.parent.mkdir(parents=True)
    graph.write_text("{}", encoding="utf-8")

    ctx = TaskContext(
        config={
            "legacy": {"repo_path": str(repo)},
            "tools": {"codeknow": "codeknow"},
        },
        workspace=str(workspace),
        run_dir=str(tmp_path / "run"),
    )
    captured = {}

    def fake_run(cmd, cwd=None, timeout=60, shell=False, env=None):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["env"] = env
        return ProcessResult(0, "ok", "")

    monkeypatch.setattr(code, "run_process", fake_run)

    result = code.extract_graph(ctx)

    assert result.success
    assert captured["cwd"] == str(workspace)
    assert captured["env"]["CODEGRAPH_OUT"] == str(graph.parent)
    assert captured["cmd"][0] == "codeknow"
    assert "--out" in captured["cmd"]
