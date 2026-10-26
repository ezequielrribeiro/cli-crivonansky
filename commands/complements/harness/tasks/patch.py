"""Tarefa patch:apply — aplica um diff unificado e verifica."""

import os

from ..catalog import get_task, register
from ..runner import run_process
from ..types import TaskResult, TaskSpec
from ..util import ensure_dir, legacy_repo, write_text


def handle(ctx, params):
    diff = params.get("diff")
    if not diff:
        return TaskResult(False, "parâmetro 'diff' obrigatório", exit_code=2)

    repo = legacy_repo(ctx)
    patch_path = os.path.join(ctx.run_dir, "patch.diff")
    ensure_dir(ctx.run_dir)
    write_text(patch_path, str(diff))

    check = run_process(["git", "apply", "--check", patch_path], cwd=repo, timeout=60)
    if check.exit_code != 0 or check.timed_out:
        return TaskResult(
            False,
            "o diff não se aplica limpo",
            details=check.combined,
            exit_code=check.exit_code or 1,
        )

    apply = run_process(["git", "apply", patch_path], cwd=repo, timeout=60)
    if apply.exit_code != 0 or apply.timed_out:
        return TaskResult(
            False,
            "falha ao aplicar o diff",
            details=apply.combined,
            exit_code=apply.exit_code or 1,
        )

    details = ["diff aplicado com sucesso"]
    ok = True

    if params.get("verify"):
        spec = get_task("verify")
        if spec is None:
            details.append("pipeline 'verify' não encontrada")
            ok = False
        else:
            result = spec.handler(ctx, {})
            details.append(f"[verify] {result.summary}")
            if result.details:
                details.append(result.details)
            ok = result.success

    return TaskResult(
        success=ok,
        summary="patch aplicado" + (" e verificado" if params.get("verify") else ""),
        details="\n".join(details),
        exit_code=0 if ok else 1,
    )


register(
    TaskSpec(
        name="patch:apply",
        intent="write",
        description="Aplica um diff unificado e opcionalmente roda verify",
        required=["diff"],
        optional=["verify"],
        handler=handle,
    )
)
