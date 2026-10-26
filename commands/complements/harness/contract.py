"""Parse e validação dos blocos crivonansky / crivonansky-result."""

import re
import uuid
from dataclasses import dataclass, field

import yaml

BLOCK_RE = re.compile(r"```crivonansky\s*\n(.*?)```", re.DOTALL)
RESULT_RE = re.compile(r"```crivonansky-result\s*\n(.*?)```", re.DOTALL)

ALLOWED_RETURNS = {"auto", "stdout", "clipboard", "file"}
ALLOWED_KEYS = {
    "harness",
    "id",
    "task",
    "intent",
    "params",
    "return",
    "timeout",
    "continue_on_failure",
}


class ContractError(Exception):
    pass


@dataclass
class CommandBlock:
    raw: str
    id: str
    task: str
    intent: str | None = None
    params: dict = field(default_factory=dict)
    return_to: str = "auto"
    timeout: float | None = None
    continue_on_failure: bool = False


def new_id() -> str:
    return f"c-{uuid.uuid4().hex[:8]}"


def extract_blocks(text: str) -> list[str]:
    return [match.group(1) for match in BLOCK_RE.finditer(text or "")]


def extract_results(text: str) -> list[str]:
    return [match.group(1) for match in RESULT_RE.finditer(text or "")]


def parse_block(raw: str, generated_id: str | None = None) -> CommandBlock:
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ContractError(f"YAML inválido: {exc}") from exc

    if not isinstance(data, dict):
        raise ContractError("o bloco deve ser um mapeamento YAML")

    unknown = sorted(set(data) - ALLOWED_KEYS)
    if unknown:
        raise ContractError(f"campos desconhecidos: {', '.join(unknown)}")

    if data.get("harness") != 1:
        raise ContractError("campo 'harness' deve ser 1")

    task = data.get("task")
    if not task or not isinstance(task, str):
        raise ContractError("campo 'task' obrigatório")

    params = data.get("params") or {}
    if not isinstance(params, dict):
        raise ContractError("campo 'params' deve ser um mapeamento")

    return_to = data.get("return", "auto")
    if return_to not in ALLOWED_RETURNS:
        raise ContractError(
            f"'return' inválido: {return_to} (use {', '.join(sorted(ALLOWED_RETURNS))})"
        )

    timeout = data.get("timeout")
    if timeout is not None:
        try:
            timeout = float(timeout)
        except (TypeError, ValueError) as exc:
            raise ContractError("'timeout' deve ser numérico") from exc
        if timeout <= 0:
            raise ContractError("'timeout' deve ser positivo")

    intent = data.get("intent")
    if intent is not None and intent not in ("read", "write"):
        raise ContractError("'intent' deve ser 'read' ou 'write'")

    return CommandBlock(
        raw=raw,
        id=str(data.get("id") or generated_id or new_id()),
        task=task,
        intent=intent,
        params=params,
        return_to=return_to,
        timeout=timeout,
        continue_on_failure=bool(data.get("continue_on_failure", False)),
    )
