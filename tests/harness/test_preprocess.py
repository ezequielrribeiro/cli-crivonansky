import json

from commands.complements.harness.tasks import preprocess
from commands.complements.harness.types import TaskContext, TaskResult


def _context(tmp_path):
    repo = tmp_path / "repo"
    (repo / "vendor").mkdir(parents=True)
    (repo / "node_modules").mkdir()
    (repo / "app.php").write_text("<?php\nfunction login() {}\n", encoding="utf-8")
    (repo / "lib.js").write_text("function carregar() {}\n", encoding="utf-8")
    (repo / "tool.py").write_text("def somar(a, b):\n    return a + b\n", encoding="utf-8")
    (repo / "style.css").write_text("body {}\n", encoding="utf-8")
    (repo / "app.min.js").write_text("var a=1;\n", encoding="utf-8")
    (repo / "vendor" / "lib.php").write_text("<?php\n", encoding="utf-8")
    (repo / "node_modules" / "dep.js").write_text("var b=2;\n", encoding="utf-8")

    workspace = tmp_path / "ws"
    return TaskContext(
        config={"legacy": {"repo_path": str(repo)}},
        workspace=str(workspace),
        run_dir=str(tmp_path / "run"),
    )


def test_preprocess_copies_only_supported_sources(tmp_path):
    ctx = _context(tmp_path)
    result = preprocess.handle(ctx, {"no_codeknow": True})

    assert result.success
    src = tmp_path / "ws" / "knowledge" / "code" / "src"
    assert (src / "app.php").is_file()
    assert (src / "lib.js").is_file()
    assert (src / "tool.py").is_file()
    assert not (src / "style.css").exists()
    assert not (src / "app.min.js").exists()
    assert not (src / "vendor").exists()
    assert not (src / "node_modules").exists()

    manifest = json.loads(
        (tmp_path / "ws" / "knowledge" / "code" / "preprocess.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(manifest["files"]) == 3
    assert manifest["graph"] is None
    assert manifest["skipped"]["build_artifacts"] == 1
    assert manifest["skipped"]["unsupported"][".css"] == 1


def test_preprocess_removes_stale_sources(tmp_path):
    ctx = _context(tmp_path)
    stale = tmp_path / "ws" / "knowledge" / "code" / "src" / "obsoleto.php"
    stale.parent.mkdir(parents=True)
    stale.write_text("<?php\n", encoding="utf-8")

    preprocess.handle(ctx, {"no_codeknow": True})

    assert not stale.exists()


def test_preprocess_runs_codeknow_and_exports_artifacts(tmp_path, monkeypatch):
    ctx = _context(tmp_path)
    calls = []

    def fake_extract(ctx, force=False):
        calls.append(("extract", force))
        code_dir = tmp_path / "ws" / "knowledge" / "code"
        graph = code_dir / "codegraph-out" / "graph.json"
        graph.parent.mkdir(parents=True)
        graph.write_text("{}", encoding="utf-8")
        return TaskResult(True, "grafo de código gerado", artifacts=[str(graph)])

    def fake_report(ctx):
        calls.append(("report", None))
        return True, "ok"

    def fake_wiki(ctx):
        calls.append(("wiki", None))
        wiki = tmp_path / "ws" / "knowledge" / "code" / "codegraph-out" / "wiki"
        wiki.mkdir(parents=True)
        (wiki / "index.md").write_text("# Wiki\n", encoding="utf-8")
        return True, "ok"

    monkeypatch.setattr(preprocess.code_task, "extract_graph", fake_extract)
    monkeypatch.setattr(preprocess, "_run_cluster_report", fake_report)
    monkeypatch.setattr(preprocess, "_run_export_wiki", fake_wiki)

    result = preprocess.handle(ctx, {"force": True})

    assert result.success
    assert ("extract", True) in calls
    assert ("report", None) in calls
    assert ("wiki", None) in calls

    manifest = json.loads(
        (tmp_path / "ws" / "knowledge" / "code" / "preprocess.json").read_text(
            encoding="utf-8"
        )
    )
    assert manifest["graph"].endswith("graph.json")
    assert manifest["wiki_articles"] == 1
