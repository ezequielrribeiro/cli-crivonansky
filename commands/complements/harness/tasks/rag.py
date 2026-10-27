"""Tarefas rag:sync e rag:search."""

import json
import os
import shutil
import urllib.error
import urllib.request

from ..catalog import register
from ..config import get_tool
from ..runner import run_process
from ..types import TaskResult, TaskSpec
from ..util import as_int, ensure_dir, read_text, workspace, write_text


def _copy_tree_files(src: str, dst: str, extension: str | None = None) -> int:
    if not os.path.isdir(src):
        return 0

    os.makedirs(dst, exist_ok=True)
    count = 0
    for name in sorted(os.listdir(src)):
        full = os.path.join(src, name)
        if not os.path.isfile(full):
            continue
        if extension and os.path.splitext(name)[1].lower() != extension:
            continue
        shutil.copy2(full, os.path.join(dst, name))
        count += 1
    return count


def _publish_tree(src: str, dst: str, extensions: set[str] | None = None) -> int:
    """Espelha uma árvore no RAG, removendo antes o destino (evita resíduos)."""
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    if not os.path.isdir(src):
        return 0

    count = 0
    for root, _dirs, files in os.walk(src):
        for name in sorted(files):
            extension = os.path.splitext(name)[1].lower()
            if extensions and extension not in extensions:
                continue
            full = os.path.join(root, name)
            relative = os.path.relpath(full, src)
            target = os.path.join(dst, relative)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            shutil.copy2(full, target)
            count += 1
    return count


def _links_markdown(ctx) -> str:
    path = os.path.join(workspace(ctx), "knowledge", "links", "code-db-links.json")
    if not os.path.isfile(path):
        return ""

    with open(path, "r", encoding="utf-8") as fh:
        links = json.load(fh)

    by_table: dict[str, list[dict]] = {}
    for link in links:
        by_table.setdefault(link["table"], []).append(link)

    parts = ["# Vínculos código↔tabela", ""]
    for table in sorted(by_table):
        parts.append(f"## Tabela: {table}")
        parts.append("")
        for link in by_table[table]:
            parts.append(
                f"- `{link['file']}:{link['line']}` — {link['operation']} "
                f"({link['statement_kind']})"
            )
        parts.append("")

    return "\n".join(parts)


def handle_sync(ctx, params):
    rag = (ctx.config.get("tools") or {}).get("rag") or {}
    rag_path = rag.get("path")
    rag_python = rag.get("python")
    if not rag_path or not rag_python:
        return TaskResult(False, "tools.rag.path/python ausentes no harness.yaml", exit_code=2)

    raw = os.path.join(rag_path, "data", "raw")
    ws = workspace(ctx)

    copied = 0
    copied += _copy_tree_files(
        os.path.join(ws, "knowledge", "db", "tables"),
        os.path.join(raw, "tech", "_harness", "db"),
        ".md",
    )
    copied += _copy_tree_files(
        os.path.join(ws, "knowledge", "docs", "manuals"),
        os.path.join(raw, "user", "_harness"),
    )
    copied += _copy_tree_files(
        os.path.join(ws, "knowledge", "docs", "tickets"),
        os.path.join(raw, "support", "_harness"),
        ".md",
    )

    links_md = _links_markdown(ctx)
    if links_md:
        write_text(os.path.join(raw, "tech", "_harness", "links", "code-db-links.md"), links_md)
        copied += 1

    # Código-fonte pré-processado por code:preprocess (PHP/Python/JavaScript).
    code_target = os.path.join(raw, "tech", "_harness", "code")
    code_copied = _publish_tree(
        os.path.join(ws, "knowledge", "code", "src"),
        os.path.join(code_target, "src"),
        {".php", ".py", ".js"},
    )
    copied += code_copied

    # Artefatos gerados pelo codeknow a partir do grafo AST.
    graph_out = os.path.join(ws, "knowledge", "code", "codegraph-out")
    report = os.path.join(graph_out, "GRAPH_REPORT.md")
    if os.path.isfile(report):
        os.makedirs(code_target, exist_ok=True)
        shutil.copy2(report, os.path.join(code_target, "CODE_GRAPH_REPORT.md"))
        copied += 1

    copied += _publish_tree(
        os.path.join(graph_out, "wiki"),
        os.path.join(code_target, "wiki"),
        {".md"},
    )

    cmd = [rag_python, "main.py", "ingest"]
    if params.get("full"):
        cmd.append("--full")

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"

    res = run_process(cmd, cwd=rag_path, timeout=7200, env=env)
    if res.timed_out:
        return TaskResult(False, "ingestão do RAG: timeout", details=res.combined, exit_code=124, status="timeout")
    if res.exit_code != 0:
        return TaskResult(False, "ingestão do RAG falhou", details=res.combined, exit_code=res.exit_code)

    summary = f"{copied} arquivo(s) publicados"
    if code_copied:
        summary += f" ({code_copied} fonte(s) de código)"
    summary += "; ingestão concluída"

    return TaskResult(
        True,
        summary,
        details=res.combined[-3000:],
    )


def handle_search(ctx, params):
    query = params.get("query")
    if not query:
        return TaskResult(False, "parâmetro 'query' obrigatório", exit_code=2)

    api = get_tool(ctx.config, "rag", "api")
    if not api:
        return TaskResult(False, "tools.rag.api ausente no harness.yaml", exit_code=2)

    payload = {
        "query": str(query),
        "doc_type": params.get("doc_type") or "auto",
        "top_k": as_int(params.get("top_k"), 5),
    }
    if params.get("source_kind"):
        payload["source_kind"] = params["source_kind"]
    request = urllib.request.Request(
        api.rstrip("/") + "/api/search",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return TaskResult(False, f"RAG respondeu {exc.code}", details=exc.read().decode("utf-8", "replace"), exit_code=exc.code)
    except Exception as exc:  # noqa: BLE001
        return TaskResult(False, "falha ao consultar o RAG", details=str(exc), exit_code=2)

    results = data.get("results") or []
    details_parts = []
    for index, item in enumerate(results, start=1):
        meta = item.get("metadata") or {}
        details_parts.append(
            f"### {index}. {meta.get('source', '?')}\n\n{item.get('page_content', '')}"
        )

    return TaskResult(
        True,
        f"{len(results)} trecho(s) encontrado(s) (doc_type={data.get('doc_type_used')})",
        details="\n\n".join(details_parts),
    )


register(
    TaskSpec(
        name="rag:sync",
        intent="read",
        description="Publica o workspace no RAG e dispara a ingestão",
        required=[],
        optional=["full"],
        handler=handle_sync,
    )
)

register(
    TaskSpec(
        name="rag:search",
        intent="read",
        description="Consulta o RAG por trechos relevantes",
        required=["query"],
        optional=["doc_type", "top_k", "source_kind"],
        handler=handle_search,
    )
)
