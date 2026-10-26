"""Política de aprovação e bloqueio de comandos perigosos."""

import json
import re


def check_policy(
    block,
    spec,
    config: dict,
    interactive: bool,
    yes_allowed: bool,
    yes: bool,
) -> tuple[str, str]:
    """Devolve (decisão, motivo), com decisão em allow | deny | confirm."""

    policy = config.get("policy") or {}
    payload = json.dumps(block.params, ensure_ascii=False, default=str)

    for pattern in policy.get("deny_patterns") or []:
        try:
            if re.search(pattern, payload):
                return "deny", f"padrão proibido: {pattern}"
        except re.error:
            continue

    intent = spec.intent
    if spec.intent_fn is not None:
        intent = spec.intent_fn(block.params)
    # O bloco pode elevar para escrita, mas nunca rebaixar.
    if block.intent == "write":
        intent = "write"

    if intent == "read":
        return "allow", "leitura"

    if yes_allowed and yes:
        return "allow", "--yes"

    if not interactive:
        return "deny", "escrita requer confirmação interativa"

    return "confirm", "escrita requer confirmação"
