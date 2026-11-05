"""Operações de ciclo de vida do plugin harness.

Concentra instalação, subida/derrubada da fixture, preparação da base de
conhecimento e pré-processamento. Tudo fica dentro de
``commands/complements/harness``:

* ``.venv``        — dependências Python do plugin + codeknow
* ``vendor``       — clones de local-rag-system e codeknow
* ``workspace``    — harness.yaml, knowledge/ e runs/
* ``fixture``      — exemplo-locadora (RotaCar)

O módulo usa apenas a stdlib no import, para que ``/harness install`` funcione
mesmo antes de as dependências do plugin existirem.
"""

import os
from pathlib import Path

from .bootstrap import ensure_deps
from .config_template import config_path, write_default_config
from .progress import Progress
from .runner import run_process
from .task_types import TaskResult

PLUGIN_ROOT = Path(__file__).resolve().parent
FIXTURE_ROOT = PLUGIN_ROOT / "fixture" / "exemplo-locadora"


def plugin_root() -> Path:
    return PLUGIN_ROOT


def fixture_root() -> Path:
    return FIXTURE_ROOT


def resolve_config(config_path_arg: str | None = None) -> str | None:
    if config_path_arg:
        return config_path_arg

    env_path = os.environ.get("HARNESS_CONFIG")
    if env_path and os.path.isfile(env_path):
        return env_path

    target = config_path(PLUGIN_ROOT)
    if target.is_file():
        return str(target)

    return None


def ensure_config(config_path_arg: str | None = None, force: bool = False) -> str:
    existing = resolve_config(config_path_arg)
    if existing:
        return existing

    return str(write_default_config(PLUGIN_ROOT, force=force))


def config_info() -> dict:
    workspace = PLUGIN_ROOT / "workspace"
    return {
        "plugin": str(PLUGIN_ROOT),
        "config": str(config_path(PLUGIN_ROOT)),
        "workspace": str(workspace),
        "vendor": str(PLUGIN_ROOT / "vendor"),
        "fixture": str(FIXTURE_ROOT),
        "venv": str(PLUGIN_ROOT / ".venv"),
    }


def _set_db_env(config_path_arg: str) -> None:
    os.environ.setdefault("HARNESS_DB_USER", "rotacar_read")
    os.environ.setdefault("HARNESS_DB_PASSWORD", "readpass")
    os.environ["HARNESS_CONFIG"] = config_path_arg


def _powershell(
    script: Path,
    cwd: Path | None = None,
    timeout: float = 900,
    args=(),
    stream=None,
) -> object:
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        *args,
    ]
    return run_process(cmd, cwd=str(cwd) if cwd else None, timeout=timeout, stream=stream)


def _run_task(config_path_arg: str, task: str, params: dict | None = None) -> TaskResult:
    """Executa uma tarefa do catálogo e devolve o resultado dela."""
    if not ensure_deps():
        return TaskResult(
            False,
            "dependências do plugin não instaladas; rode /harness install",
            exit_code=2,
        )

    import yaml

    from .catalog import load_tasks
    from .engine import HarnessEngine

    load_tasks()
    engine = HarnessEngine(
        config_path=config_path_arg,
        interactive=False,
        yes=True,
    )

    block = {"harness": 1, "task": task, "params": params or {}}
    raw = yaml.safe_dump(block, allow_unicode=True, sort_keys=False)
    _text, status = engine.handle_block(raw, yes_allowed=True)

    return TaskResult(
        success=status == "success",
        summary=f"{task}: {status}",
        details="",
        exit_code=0 if status == "success" else 1,
        status=None if status == "success" else status,
    )


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------
def install(
    force: bool = False,
    skip_docker: bool = False,
    check_only: bool = False,
    python_exe: str | None = None,
) -> TaskResult:
    script = PLUGIN_ROOT / "install.ps1"
    if not script.is_file():
        return TaskResult(False, f"instalador não encontrado: {script}", exit_code=2)

    args = []
    if force:
        args.append("-ForceConfig")
    if skip_docker:
        args.append("-SkipDocker")
    if check_only:
        args.append("-CheckOnly")
    if python_exe:
        args.extend(["-PythonExe", str(python_exe)])

    # O install.ps1 pode demorar (clones + pip); o log fica no workspace e as
    # linhas são publicadas em tempo real (stderr na CLI, RichLog na TUI).
    progress = Progress(
        "install",
        log_path=str(PLUGIN_ROOT / "workspace" / "install.log"),
    )
    progress.start("executando install.ps1")

    result = _powershell(
        script,
        cwd=PLUGIN_ROOT,
        timeout=3600,
        args=args,
        stream=progress.log,
    )
    if getattr(result, "timed_out", False):
        progress.finish("timeout")
        return TaskResult(
            False,
            "instalação: timeout",
            details=getattr(result, "combined", ""),
            exit_code=124,
            status="timeout",
        )

    ok = result.exit_code == 0
    if ok and not check_only:
        target = write_default_config(PLUGIN_ROOT, force=force)
        details = getattr(result, "combined", "")
        details = (details + f"\nconfig: {target}").strip()
    else:
        details = getattr(result, "combined", "")

    if check_only:
        progress.finish("verificação concluída" if ok else "falha na verificação")
        summary = "dependências OK (check-only)" if ok else "falha na verificação das dependências"
    else:
        progress.finish("plugin instalado" if ok else "falha na instalação")
        summary = "plugin instalado" if ok else "falha na instalação do plugin"

    return TaskResult(
        ok,
        summary,
        details=details,
        exit_code=result.exit_code,
    )


# ---------------------------------------------------------------------------
# start / stop
# ---------------------------------------------------------------------------
def start(
    skip_rag: bool = False,
    no_docker: bool = False,
    config_path_arg: str | None = None,
) -> TaskResult:
    config = ensure_config(config_path_arg)
    _set_db_env(config)

    details: list[str] = []
    fixture_started = False

    if no_docker:
        details.append("fixture ignorada (--no-docker)")
    else:
        compose = FIXTURE_ROOT / "docker-compose.yml"
        setup = FIXTURE_ROOT / "setup.ps1"
        if not compose.is_file() or not setup.is_file():
            return TaskResult(False, f"fixture não encontrada em {FIXTURE_ROOT}", exit_code=2)

        if not _docker_available():
            return TaskResult(False, "Docker Desktop não está em execução", exit_code=2)

        started = _powershell(setup, cwd=FIXTURE_ROOT, timeout=900)
        if getattr(started, "timed_out", False):
            return TaskResult(
                False,
                "subida da fixture: timeout",
                details=getattr(started, "combined", ""),
                exit_code=124,
                status="timeout",
            )
        if started.exit_code != 0:
            return TaskResult(
                False,
                "falha ao subir a fixture",
                details=getattr(started, "combined", ""),
                exit_code=started.exit_code,
            )

        fixture_started = True
        details.append(getattr(started, "combined", ""))

    rag_started = False
    if not skip_rag:
        rag = _run_task(config, "rag:serve", {"action": "start"})
        details.append(rag.summary)
        if not rag.success:
            if fixture_started:
                summary = "fixture no ar, mas a API do RAG não iniciou"
            else:
                summary = "API do RAG não iniciou"
            return TaskResult(
                False,
                summary,
                details="\n".join(part for part in details if part),
                exit_code=rag.exit_code,
                status=rag.status,
            )
        rag_started = True
    elif not no_docker:
        details.append("RAG ignorado (--no-rag)")

    if not fixture_started and not rag_started:
        summary = "nada a iniciar (--no-docker e --no-rag)"
    elif not fixture_started:
        summary = "API do RAG no ar (fixture não iniciada)"
    elif not rag_started:
        summary = "fixture no ar (RAG não iniciado)"
    else:
        summary = "ambiente do harness no ar"

    return TaskResult(
        True,
        summary,
        details="\n".join(part for part in details if part),
    )


def stop(purge: bool = False, config_path_arg: str | None = None) -> TaskResult:
    config = resolve_config(config_path_arg)
    details: list[str] = []

    if config:
        _set_db_env(config)
        rag = _run_task(config, "rag:serve", {"action": "stop"})
        details.append(rag.summary)

    compose = FIXTURE_ROOT / "docker-compose.yml"
    if not compose.is_file():
        return TaskResult(False, f"docker-compose.yml não encontrado: {compose}", exit_code=2)

    cmd = ["docker", "compose", "-f", str(compose), "down"]
    if purge:
        cmd.append("-v")

    result = run_process(cmd, cwd=str(FIXTURE_ROOT), timeout=300)
    if getattr(result, "timed_out", False):
        return TaskResult(
            False,
            "parada da fixture: timeout",
            details=getattr(result, "combined", ""),
            exit_code=124,
            status="timeout",
        )

    details.append(getattr(result, "combined", ""))
    ok = result.exit_code == 0
    return TaskResult(
        ok,
        "ambiente parado" + (" (volume removido)" if purge else "") if ok else "falha ao parar a fixture",
        details="\n".join(part for part in details if part),
        exit_code=result.exit_code,
    )


# ---------------------------------------------------------------------------
# prepare / preprocess
# ---------------------------------------------------------------------------
def prepare(
    full: bool = False,
    skip_rag: bool = False,
    config_path_arg: str | None = None,
) -> TaskResult:
    started = start(skip_rag=skip_rag, config_path_arg=config_path_arg)
    if not started.success:
        return started

    config = ensure_config(config_path_arg)
    _set_db_env(config)

    tasks = [
        ("db:snapshot", {}),
        ("db:links", {}),
        ("docs:import", {}),
        ("code:preprocess", {}),
        ("rag:sync", {"full": True} if full else {}),
    ]

    details = [started.summary]
    progress = Progress("prepare", log_path=str(PLUGIN_ROOT / "workspace" / "prepare.log"))
    progress.start(f"base de conhecimento: {len(tasks)} etapa(s)")

    for task, params in tasks:
        progress.log(f"executando {task}")
        result = _run_task(config, task, params)
        details.append(result.summary)
        if not result.success:
            progress.finish(f"interrompido em {task}")
            return TaskResult(
                False,
                f"preparação interrompida em {task}",
                details="\n".join(details),
                exit_code=result.exit_code,
                status=result.status,
            )
        progress.log(f"{task}: {result.summary}")

    progress.finish("base de conhecimento preparada")
    return TaskResult(True, "base de conhecimento preparada", details="\n".join(details))


def preprocess(
    sync: bool = False,
    full: bool = False,
    no_codeknow: bool = False,
    no_wiki: bool = False,
    config_path_arg: str | None = None,
) -> TaskResult:
    config = ensure_config(config_path_arg)
    _set_db_env(config)

    params = {
        "force": full,
        "no_codeknow": no_codeknow,
        "no_wiki": no_wiki,
    }
    result = _run_task(config, "code:preprocess", params)
    details = [result.summary]
    if not result.success:
        return TaskResult(
            False,
            "pré-processamento falhou",
            details="\n".join(details),
            exit_code=result.exit_code,
            status=result.status,
        )

    if sync:
        synced = _run_task(config, "rag:sync", {"full": True} if full else {})
        details.append(synced.summary)
        if not synced.success:
            return TaskResult(
                False,
                "código pré-processado, mas o rag:sync falhou",
                details="\n".join(details),
                exit_code=synced.exit_code,
                status=synced.status,
            )

    return TaskResult(True, "pré-processamento concluído", details="\n".join(details))


def _docker_available() -> bool:
    result = run_process(["docker", "info"], timeout=20)
    return result.exit_code == 0 and not getattr(result, "timed_out", False)
