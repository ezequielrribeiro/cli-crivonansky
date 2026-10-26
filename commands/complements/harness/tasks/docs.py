"""Tarefa docs:import — manuais e tickets para o workspace."""

import json
import os
import shutil

from ..catalog import register
from ..config import get_legacy
from ..types import TaskResult, TaskSpec
from ..util import ensure_dir, workspace, write_json, write_text

MANUAL_EXTENSIONS = {".pdf", ".md", ".txt"}
ATTACHMENT_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".pdf"}


def _copy_manuals(ctx) -> list[str]:
    src = get_legacy(ctx.config, "manuals_path")
    dst = ensure_dir(os.path.join(workspace(ctx), "knowledge", "docs", "manuals"))
    copied = []

    if src and os.path.isdir(src):
        for name in sorted(os.listdir(src)):
            full = os.path.join(src, name)
            if os.path.isfile(full) and os.path.splitext(name)[1].lower() in MANUAL_EXTENSIONS:
                shutil.copy2(full, os.path.join(dst, name))
                copied.append(name)

    return copied


def _ticket_markdown(ticket: dict) -> str:
    lines = [f"# Ticket {ticket.get('id', '')}: {ticket.get('titulo', '')}", ""]
    lines.append(f"- **ID:** {ticket.get('id', '')}")
    lines.append(f"- **Testadores:** {', '.join(ticket.get('testadores') or [])}")
    lines.append(f"- **Desenvolvedores:** {', '.join(ticket.get('desenvolvedores') or [])}")
    lines.append(f"- **Tags:** {', '.join(ticket.get('tags') or [])}")
    lines.extend(["", "## Descrição", "", ticket.get("descricao", "")])

    if ticket.get("anexos"):
        lines.extend(["", "## Anexos", ""])
        for attachment in ticket["anexos"]:
            lines.append(f"- {attachment}")

    if ticket.get("comentarios"):
        lines.extend(["", "## Comentários", ""])
        for comment in ticket["comentarios"]:
            lines.append(
                f"- **{comment.get('autor', '')}** ({comment.get('data', '')}): "
                f"{comment.get('texto', '')}"
            )

    return "\n".join(lines) + "\n"


def _load_tickets(src: str) -> list[dict]:
    if not src or not os.path.isdir(src):
        return []

    candidates = [os.path.join(src, "tickets.json")]
    candidates.extend(
        os.path.join(src, name)
        for name in sorted(os.listdir(src))
        if name.lower().endswith(".json")
    )

    for candidate in candidates:
        if os.path.isfile(candidate):
            with open(candidate, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data.get("tickets") or []
            if isinstance(data, list):
                return data

    return []


def _copy_attachments(src: str, dst: str, tickets: list[dict]) -> int:
    copied = 0
    if not src:
        return copied

    for ticket in tickets:
        for attachment in ticket.get("anexos") or []:
            candidate = attachment if os.path.isabs(attachment) else os.path.join(src, attachment)
            if os.path.isfile(candidate) and os.path.splitext(candidate)[1].lower() in ATTACHMENT_EXTENSIONS:
                target = os.path.join(dst, os.path.basename(candidate))
                shutil.copy2(candidate, target)
                copied += 1

    return copied


def handle(ctx, params):
    manuals = _copy_manuals(ctx)

    tickets_src = get_legacy(ctx.config, "tickets_path")
    tickets_dir = ensure_dir(os.path.join(workspace(ctx), "knowledge", "docs", "tickets"))
    attachments_dir = ensure_dir(os.path.join(tickets_dir, "anexos"))

    tickets = _load_tickets(tickets_src)
    for ticket in tickets:
        filename = f"{ticket.get('id', 'ticket')}.md"
        write_text(os.path.join(tickets_dir, filename), _ticket_markdown(ticket))

    attachments = _copy_attachments(tickets_src, attachments_dir, tickets)

    manifest = {
        "manuals": manuals,
        "tickets": [ticket.get("id") for ticket in tickets],
        "attachments": attachments,
        "sources": {
            "manuals_path": tickets_src and get_legacy(ctx.config, "manuals_path"),
            "tickets_path": tickets_src,
        },
    }
    write_json(os.path.join(workspace(ctx), "knowledge", "docs", "manifest.json"), manifest)

    summary = (
        f"{len(manuals)} manual(is), {len(tickets)} ticket(s), "
        f"{attachments} anexo(s)"
    )
    return TaskResult(True, summary)


register(
    TaskSpec(
        name="docs:import",
        intent="read",
        description="Importa manuais e tickets para o workspace",
        required=[],
        optional=["source", "kind"],
        handler=handle,
    )
)
