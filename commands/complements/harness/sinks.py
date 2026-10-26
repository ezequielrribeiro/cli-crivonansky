"""Destinos de saída: stdout, clipboard e arquivo."""

import os


def emit(text: str, sinks: list[str], file_path: str | None = None) -> None:
    for sink in sinks:
        if sink == "stdout":
            print(text)
        elif sink == "clipboard":
            try:
                import pyperclip

                pyperclip.copy(text)
            except Exception:
                pass
        elif sink == "file" and file_path:
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as fh:
                fh.write(text)
