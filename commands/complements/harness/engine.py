"""Motor de execução do harness."""

import json
import time

from .catalog import get_task, load_tasks
from .config import get_output, get_workspace, load_config
from .contract import ContractError, extract_blocks, new_id, parse_block
from .formatter import format_result, mask_secrets
from .policy import check_policy
from .runs import RunStore
from .sinks import emit
from .types import TaskContext


class HarnessEngine:
    def __init__(
        self,
        config_path: str | None = None,
        interactive: bool = True,
        yes: bool = False,
        dry_run: bool = False,
        sinks: list[str] | None = None,
    ):
        self.config = load_config(config_path)
        self.workspace = get_workspace(self.config)
        self.output = get_output(self.config)
        self.interactive = interactive
        self.yes = yes
        self.dry_run = dry_run
        self.sinks = sinks or self.output.get("default_sinks", ["stdout"])
        self.runs = RunStore(self.workspace)
        self.max_chars = int((self.output.get("max_chars") or {}).get("clipboard", 12000))
        load_tasks()

    # ------------------------------------------------------------------
    def handle_text(self, text: str, yes_allowed: bool = False) -> tuple[list[dict], str | None]:
        blocks = extract_blocks(text)
        if not blocks:
            return [], "nenhum bloco ```crivonansky encontrado"

        results = []
        for raw in blocks:
            result_text, status = self.handle_block(raw, yes_allowed=yes_allowed)
            results.append({"text": result_text, "status": status})

            if status in ("failure", "error", "denied", "timeout"):
                try:
                    block = parse_block(raw)
                    if block.continue_on_failure:
                        continue
                except ContractError:
                    pass
                break

        return results, None

    # ------------------------------------------------------------------
    def handle_block(self, raw: str, yes_allowed: bool = False) -> tuple[str, str]:
        start = time.time()
        generated_id = new_id()

        try:
            block = parse_block(raw, generated_id=generated_id)
        except ContractError as exc:
            return self._finish(
                generated_id, "unknown", "error", 2, start, str(exc), str(exc), [], raw
            )

        spec = get_task(block.task)
        if spec is None:
            return self._finish(
                block.id,
                block.task,
                "denied",
                3,
                start,
                f"tarefa desconhecida: {block.task}",
                "",
                [],
                raw,
            )

        missing = [name for name in spec.required if name not in block.params]
        if missing:
            return self._finish(
                block.id,
                block.task,
                "error",
                2,
                start,
                f"parâmetros obrigatórios ausentes: {', '.join(missing)}",
                "",
                [],
                raw,
            )

        allowed = set(spec.required) | set(spec.optional)
        unknown = sorted(set(block.params) - allowed)
        if unknown:
            return self._finish(
                block.id,
                block.task,
                "error",
                2,
                start,
                f"parâmetros desconhecidos: {', '.join(unknown)}",
                "",
                [],
                raw,
            )

        decision, reason = check_policy(
            block, spec, self.config, self.interactive, yes_allowed, self.yes
        )
        if decision == "deny":
            return self._finish(
                block.id, block.task, "denied", 3, start, f"negado: {reason}", "", [], raw
            )

        if decision == "confirm" and not self._confirm(block):
            return self._finish(
                block.id, block.task, "denied", 3, start, "recusado pelo usuário", "", [], raw
            )

        if self.dry_run:
            return self._finish(
                block.id, block.task, "success", 0, start, "dry-run: não executado", "", [], raw
            )

        ctx = TaskContext(
            config=self.config,
            workspace=self.workspace,
            run_dir=self.runs.run_dir(block.id),
            interactive=self.interactive,
            yes=self.yes,
            dry_run=self.dry_run,
        )

        try:
            result = spec.handler(ctx, block.params)
        except PermissionError as exc:
            return self._finish(block.id, block.task, "denied", 3, start, str(exc), "", [], raw)
        except Exception as exc:  # noqa: BLE001
            return self._finish(
                block.id, block.task, "error", 1, start, f"erro ao executar: {exc}", str(exc), [], raw
            )

        status = result.status or ("success" if result.success else "failure")
        return self._finish(
            block.id,
            block.task,
            status,
            result.exit_code,
            start,
            result.summary,
            result.details,
            result.artifacts,
            raw,
        )

    # ------------------------------------------------------------------
    def _confirm(self, block) -> bool:
        print(f"\n[harness] tarefa de escrita: {block.task}")
        print(json.dumps(block.params, ensure_ascii=False, indent=2))
        try:
            answer = input("Executar? [y/N] ").strip().lower()
        except EOFError:
            return False
        return answer in ("y", "yes", "s", "sim")

    def _finish(
        self,
        block_id: str,
        task: str,
        status: str,
        exit_code: int,
        start: float,
        summary: str,
        details: str,
        artifacts: list[str],
        raw: str,
    ) -> tuple[str, str]:
        duration = int((time.time() - start) * 1000)
        summary = mask_secrets(summary, self.config)
        details = mask_secrets(details, self.config)

        text, _truncated = format_result(
            block_id,
            task,
            status,
            exit_code,
            duration,
            summary,
            details,
            artifacts,
            self.max_chars,
        )

        try:
            self.runs.write(block_id, raw, text, details)
            self.runs.append_index(
                {
                    "id": block_id,
                    "task": task,
                    "status": status,
                    "duration_ms": duration,
                    "approved_by": "none" if status == "denied" else "auto",
                    "sinks": self.sinks,
                }
            )
        except OSError:
            pass

        emit(text, self.sinks)
        return text, status
