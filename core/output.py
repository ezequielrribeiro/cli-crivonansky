"""Utilitários de saída em texto puro (sem marcação Rich)."""


def strip_markup(text: str) -> str:
    """Remove a marcação Rich de um texto, devolvendo texto puro."""
    if not text:
        return text
    try:
        from rich.text import Text

        return Text.from_markup(text).plain
    except Exception:
        return text
