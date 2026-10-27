"""Tarefa code:preprocess — prepara o código-fonte para a ingestão no RAG.

O RAG sabe chunkificar PHP/Python/JavaScript, mas o `rag:sync` só publicava
schema, manuais e tickets. Esta tarefa fecha a lacuna:

1. copia o código-fonte suportado do repositório legado (sem vendor) para o
   workspace, preservando a árvore de diretórios;
2. gera/atualiza o grafo AST com o codeknow (`code:index`);
3. gera o relatório arquitetural e os artigos wiki do codeknow.

O `rag:sync` publica `knowledge/code/src` e os artefatos do codeknow em
`data/raw/tech/_harness/code/` antes de rodar a ingestão.
"""

import os
import re
import shutil

from ..catalog import register
from ..types import TaskResult, TaskSpec
from ..util import as_bool, ensure_dir, legacy_repo, workspace, write_json
from . import code as code_task

# Formatos que o local-rag-system sabe chunkificar hoje (EXTENSION_MAP).
SOURCE_EXTENSIONS = {".php", ".py", ".js"}

# Mesma lista de exclusão de terceiros/artefatos usada pelo RAG e por db:links.
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "vendor",
    "node_modules",
    "site-packages",
    "dist",
    "build",
    ".next",
    "coverage",
}

ARTIFACT_RE = re.compile(r"\.(?:min|bundle|pack)\.js$", re.IGNORECASE)


def _iter_sources(repo: str, skipped: dict):
    """Percorre o repo legado devolvendo apenas fontes indexáveis pelo RAG."""
    for dirpath, dirnames, filenames in os.walk(repo):
        kept = []
        for name in sorted(dirnames):
            if name.lower() in SKIP_DIRS:
                skipped["vendor_dirs"] += 1
                continue
            if name.startswith("."):
                skipped["hidden_dirs"] += 1
                continue
            kept.append(name)
        dirnames[:] = kept

        for filename in sorted(filenames):
            path = os.path.join(dirpath, filename)
            extension = os.path.splitext(filename)[1].lower()

            if extension not in SOURCE_EXTENSIONS:
                skipped["unsupported"][extension or "<sem extensão>"] = (
                    skipped["unsupported"].get(extension or "<sem extensão>", 0) + 1
                )
                continue
            if ARTIFACT_RE.search(filename):
                skipped["build_artifacts"] += 1
                continue

            yield path


def _copy_sources(repo: str, destination: str) -> tuple[list[dict], dict]:
    """Reescreve a árvore de fontes no workspace, removendo arquivos obsoletos."""
    if os.path.isdir(destination):
        shutil.rmtree(destination)
    ensure_dir(destination)

    copied: list[dict] = []
    skipped = {
        "vendor_dirs": 0,
        "hidden_dirs": 0,
        "build_artifacts": 0,
        "unsupported": {},
    }

    for path in _iter_sources(repo, skipped):
        relative = os.path.relpath(path, repo).replace("\\", "/")
        target = os.path.join(destination, relative)
        ensure_dir(os.path.dirname(target))
        shutil.copy2(path, target)
        copied.append(
            {
                "source": relative,
                "workspace_path": os.path.relpath(target, destination).replace("\\", "/"),
                "size": os.path.getsize(target),
            }
        )

    return copied, skipped


def _run_cluster_report(ctx) -> tuple[bool, str]:
    """Gera GRAPH_REPORT.md a partir do graph.json (codeknow cluster-only)."""
    code_dir = os.path.join(workspace(ctx), "knowledge", "code")
    cmd = [code_task.codeknow_bin(ctx), "cluster-only", code_dir, "--no-viz"]
    res = code_task.run_process(
        cmd,
        cwd=code_dir,
        timeout=900,
        env=code_task.process_env(ctx),
    )
    return res.exit_code == 0, res.combined


def _run_export_wiki(ctx) -> tuple[bool, str]:
    """Exporta artigos Markdown por arquivo/símbolo a partir do grafo."""
    graph = code_task.graph_path(ctx)
    if not os.path.isfile(graph):
        return False, "graph.json não encontrado para exportar a wiki"

    cmd = [
        code_task.codeknow_bin(ctx),
        "export",
        "wiki",
        "--graph",
        graph,
    ]
    res = code_task.run_process(
        cmd,
        cwd=workspace(ctx),
        timeout=900,
        env=code_task.process_env(ctx),
    )
    return res.exit_code == 0, res.combined


def _wiki_count(ctx) -> int:
    wiki_dir = os.path.join(
        workspace(ctx), "knowledge", "code", "codegraph-out", "wiki"
    )
    if not os.path.isdir(wiki_dir):
        return 0
    return sum(
        1
        for name in os.listdir(wiki_dir)
        if os.path.isfile(os.path.join(wiki_dir, name)) and name.endswith(".md")
    )


def handle(ctx, params):
    repo = legacy_repo(ctx)
    if not os.path.isdir(repo):
        return TaskResult(False, f"repositório não encontrado: {repo}", exit_code=2)

    code_dir = ensure_dir(os.path.join(workspace(ctx), "knowledge", "code"))
    source_dir = os.path.join(code_dir, "src")

    copied, skipped = _copy_sources(repo, source_dir)

    notes: list[str] = []
    graph_ok = False
    has_codeknow = not as_bool(params.get("no_codeknow"))

    if has_codeknow:
        index_result = code_task.extract_graph(
            ctx,
            force=as_bool(params.get("force")),
        )
        graph_ok = index_result.success
        notes.append(index_result.summary)
        if not graph_ok:
            # A cópia já está pronta; o grafo pode ser refeito depois.
            write_json(
                os.path.join(code_dir, "preprocess.json"),
                {
                    "repo": repo,
                    "files": copied,
                    "skipped": skipped,
                    "graph": None,
                    "error": index_result.details[-2000:],
                },
            )
            return TaskResult(
                False,
                "código copiado, mas o codeknow falhou",
                details=index_result.details,
                artifacts=[source_dir],
                exit_code=index_result.exit_code,
                status=index_result.status,
            )

        report_ok, report_details = _run_cluster_report(ctx)
        notes.append("relatório gerado" if report_ok else "relatório indisponível")
        if not report_ok:
            notes.append(report_details[-500:])

        wiki_ok = False
        if not as_bool(params.get("no_wiki")):
            wiki_ok, wiki_details = _run_export_wiki(ctx)
            notes.append(
                f"{_wiki_count(ctx)} artigo(s) wiki"
                if wiki_ok
                else "wiki indisponível"
            )
            if not wiki_ok:
                notes.append(wiki_details[-500:])

    graph_file = code_task.graph_path(ctx)
    report_file = os.path.join(code_dir, "codegraph-out", "GRAPH_REPORT.md")

    manifest = {
        "repo": repo,
        "extensions": sorted(SOURCE_EXTENSIONS),
        "files": copied,
        "skipped": skipped,
        "codeknow_run": has_codeknow,
        "graph": graph_file if os.path.isfile(graph_file) else None,
        "report": report_file if os.path.isfile(report_file) else None,
        "wiki_articles": _wiki_count(ctx),
    }
    write_json(os.path.join(code_dir, "preprocess.json"), manifest)

    summary = (
        f"{len(copied)} fonte(s) copiada(s)"
        + (f"; {', '.join(note for note in notes if note)}" if notes else "")
    )
    return TaskResult(
        True,
        summary,
        details="\n".join(note for note in notes if note),
        artifacts=[source_dir],
    )


register(
    TaskSpec(
        name="code:preprocess",
        intent="read",
        description="Pré-processa o código-fonte (cópia filtrada + codeknow) para o RAG",
        required=[],
        optional=["force", "no_codeknow", "no_wiki"],
        handler=handle,
    )
)
