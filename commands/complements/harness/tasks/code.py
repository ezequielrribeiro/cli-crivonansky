"""Tarefas de código: code:index, code:query e code:impact (codeknow)."""

import os

from ..catalog import register
from ..config import get_tool
from ..runner import run_process
from ..types import TaskResult, TaskSpec
from ..util import as_bool, as_int, ensure_dir, legacy_repo, workspace


def codeknow_bin(ctx) -> str:
    return get_tool(ctx.config, "codeknow") or "codeknow"


def out_dir(ctx) -> str:
    return ensure_dir(os.path.join(workspace(ctx), "knowledge", "code"))


def graph_path(ctx) -> str:
    out = out_dir(ctx)
    candidates = (
        os.path.join(out, "graph.json"),
        os.path.join(out, "codegraph-out", "graph.json"),
    )
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return candidates[0]


def process_env(ctx=None) -> dict:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    if ctx is not None:
        # O codeknow grava cache em <CODEGRAPH_OUT>/cache/ mesmo quando o
        # caminho vem de --out. Fixar o valor absoluto evita que o cache
        # apareça dentro do repositório legado (ex.: no modo incremental).
        env["CODEGRAPH_OUT"] = os.path.join(out_dir(ctx), "codegraph-out")
    return env


def extract_graph(ctx, force: bool = False) -> TaskResult:
    """Roda `codeknow extract` e valida a geração do graph.json."""
    repo = legacy_repo(ctx)
    if not os.path.isdir(repo):
        return TaskResult(False, f"repositório não encontrado: {repo}", exit_code=2)

    out = out_dir(ctx)
    cmd = [codeknow_bin(ctx), "extract", repo, "--code-only", "--out", out]
    if force:
        cmd.append("--force")

    # Executa fora do repo: o codeknow pode criar cache/codegraph-out no cwd
    # mesmo com --out absoluto, e o harness não deve escrever no legado.
    res = run_process(cmd, cwd=workspace(ctx), timeout=1800, env=process_env(ctx))
    if res.timed_out:
        return TaskResult(False, "codeknow extract: timeout", details=res.combined, exit_code=124, status="timeout")
    if res.exit_code != 0:
        return TaskResult(False, "codeknow extract falhou", details=res.combined, exit_code=res.exit_code)

    graph = graph_path(ctx)
    if not os.path.isfile(graph):
        return TaskResult(
            False,
            "graph.json não foi gerado",
            details=res.combined[-3000:],
            exit_code=1,
        )

    size = os.path.getsize(graph)
    return TaskResult(
        True,
        f"grafo de código gerado ({size} bytes)",
        details=res.combined[-3000:],
        artifacts=[graph],
    )


def handle_index(ctx, params):
    return extract_graph(ctx, force=as_bool(params.get("force")))


def _run_query(ctx, command: str, argument: str, params: dict):
    graph = graph_path(ctx)
    if not os.path.isfile(graph):
        return TaskResult(False, "graph.json não encontrado; rode code:index", exit_code=2)

    cmd = [codeknow_bin(ctx), command, argument, "--graph", graph]
    if command == "query":
        cmd.extend(["--budget", str(as_int(params.get("budget"), 2000))])

    res = run_process(cmd, cwd=workspace(ctx), timeout=180, env=process_env(ctx))
    if res.timed_out:
        return TaskResult(False, f"codeknow {command}: timeout", details=res.combined, exit_code=124, status="timeout")

    return TaskResult(
        success=res.exit_code == 0,
        summary=f"codeknow {command} (exit {res.exit_code})",
        details=res.combined,
        exit_code=res.exit_code,
    )


def handle_query(ctx, params):
    question = params.get("q")
    if not question:
        return TaskResult(False, "parâmetro 'q' obrigatório", exit_code=2)
    return _run_query(ctx, "query", str(question), params)


def handle_impact(ctx, params):
    symbol = params.get("symbol")
    if not symbol:
        return TaskResult(False, "parâmetro 'symbol' obrigatório", exit_code=2)
    return _run_query(ctx, "affected", str(symbol), params)


register(
    TaskSpec(
        name="code:index",
        intent="read",
        description="Gera o grafo de código com codeknow (sem LLM)",
        required=[],
        optional=["force"],
        handler=handle_index,
    )
)

register(
    TaskSpec(
        name="code:query",
        intent="read",
        description="Consulta o grafo de código com orçamento de tokens",
        required=["q"],
        optional=["budget"],
        handler=handle_query,
    )
)

register(
    TaskSpec(
        name="code:impact",
        intent="read",
        description="Analisa o impacto de alterar um símbolo",
        required=["symbol"],
        optional=[],
        handler=handle_impact,
    )
)
