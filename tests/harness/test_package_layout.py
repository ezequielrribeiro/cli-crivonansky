"""Guarda-corpo de layout: nenhum módulo do plugin pode sombrear a stdlib.

O plugin já teve um ``types.py``; quando o diretório do harness entrava no
``sys.path`` (subprocessos, builds do pip, execução a partir da pasta), o
``import types`` resolvia para o módulo do plugin e quebrava ferramentas que
esperam ``types.ModuleType``.
"""

import os
import sys

HARNESS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "commands",
    "complements",
    "harness",
)


def _top_level_modules():
    """Só os módulos do topo do plugin podem entrar no ``sys.path`` como top-level."""
    for entry in os.listdir(HARNESS):
        path = os.path.join(HARNESS, entry)
        if os.path.isfile(path) and entry.endswith(".py"):
            yield path, entry[: -len(".py")]


def test_types_module_was_renamed():
    assert not os.path.exists(os.path.join(HARNESS, "types.py"))
    assert os.path.exists(os.path.join(HARNESS, "task_types.py"))


def test_no_harness_module_shadows_stdlib():
    stdlib = set(sys.stdlib_module_names)
    clashes = sorted(
        os.path.relpath(path, HARNESS)
        for path, name in _top_level_modules()
        if name in stdlib
    )
    assert clashes == []
