from commands.complements.harness.runner import ProcessResult
from commands.complements.harness.tasks import rag
from commands.complements.harness.types import TaskContext


def _context(tmp_path):
    ws = tmp_path / "ws"
    rag_path = tmp_path / "rag"
    (rag_path / "data" / "raw").mkdir(parents=True)

    src = ws / "knowledge" / "code" / "src"
    (src / "cadastro").mkdir(parents=True)
    (src / "cadastro" / "cliente.php").write_text("<?php\n", encoding="utf-8")
    (src / "app.js").write_text("var x = 1;\n", encoding="utf-8")

    graph_out = ws / "knowledge" / "code" / "codegraph-out"
    (graph_out / "wiki").mkdir(parents=True)
    (graph_out / "GRAPH_REPORT.md").write_text("# Grafo\n", encoding="utf-8")
    (graph_out / "wiki" / "index.md").write_text("# Wiki\n", encoding="utf-8")

    return TaskContext(
        config={
            "legacy": {"repo_path": str(tmp_path / "repo")},
            "tools": {
                "rag": {
                    "path": str(rag_path),
                    "python": "rag-python",
                }
            },
        },
        workspace=str(ws),
        run_dir=str(tmp_path / "run"),
    )


def test_rag_sync_publishes_preprocessed_code(tmp_path, monkeypatch):
    ctx = _context(tmp_path)
    commands = []

    def fake_run(cmd, cwd=None, timeout=60, shell=False, env=None):
        commands.append(cmd)
        return ProcessResult(0, "ok", "")

    monkeypatch.setattr(rag, "run_process", fake_run)

    result = rag.handle_sync(ctx, {})

    assert result.success
    raw = tmp_path / "rag" / "data" / "raw" / "tech" / "_harness" / "code"
    assert (raw / "src" / "cadastro" / "cliente.php").is_file()
    assert (raw / "src" / "app.js").is_file()
    assert (raw / "CODE_GRAPH_REPORT.md").is_file()
    assert (raw / "wiki" / "index.md").is_file()
    assert commands == [["rag-python", "main.py", "ingest"]]


def test_rag_sync_removes_stale_published_code(tmp_path, monkeypatch):
    ctx = _context(tmp_path)
    stale = (
        tmp_path
        / "rag"
        / "data"
        / "raw"
        / "tech"
        / "_harness"
        / "code"
        / "src"
        / "obsoleto.php"
    )
    stale.parent.mkdir(parents=True)
    stale.write_text("<?php\n", encoding="utf-8")

    monkeypatch.setattr(rag, "run_process", lambda *a, **k: ProcessResult(0, "ok", ""))

    rag.handle_sync(ctx, {})

    assert not stale.exists()


def test_rag_sync_reports_missing_config(tmp_path):
    ctx = TaskContext(
        config={},
        workspace=str(tmp_path / "ws"),
        run_dir=str(tmp_path / "run"),
    )

    result = rag.handle_sync(ctx, {})

    assert result.success is False
    assert result.exit_code == 2
