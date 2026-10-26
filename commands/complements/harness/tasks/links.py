"""Tarefa db:links — extrai SQL embutido em PHP/JS e vínculos com tabelas."""

import json
import os
import re

import sqlglot
from sqlglot import exp

from ..catalog import register
from ..types import TaskResult, TaskSpec
from ..util import legacy_repo, read_text, workspace, write_json

SKIP_DIRS = {
    ".git",
    "vendor",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
    "coverage",
}

EXTENSIONS = {".php", ".js", ".ts", ".jsx", ".tsx"}

STRING_RE = re.compile(r"""(['"])((?:\\.|(?!\1).)*)\1""", re.S)
SQL_KEYWORDS = re.compile(r"\b(SELECT|INSERT\s+INTO|UPDATE|DELETE\s+FROM|REPLACE\s+INTO)\b", re.I)
INCLUDE_RE = re.compile(
    r"\b(include|include_once|require|require_once)\b\s*\(?\s*([^;]+);",
    re.I,
)


def _iter_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS]
        for filename in filenames:
            if os.path.splitext(filename)[1].lower() in EXTENSIONS:
                yield os.path.join(dirpath, filename)


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _load_pk_map(ctx) -> dict[str, set[str]]:
    path = os.path.join(workspace(ctx), "knowledge", "db", "schema-catalog.json")
    if not os.path.isfile(path):
        return {}

    with open(path, "r", encoding="utf-8") as fh:
        catalog = json.load(fh)

    pk_map: dict[str, set[str]] = {}
    for table in catalog.get("tables") or []:
        pks = {col["name"] for col in table.get("columns") or [] if col.get("key") == "PRI"}
        for index in table.get("indexes") or []:
            if index.get("name") == "PRIMARY":
                pks.update(index.get("columns") or [])
        pk_map[table["name"]] = pks

    return pk_map


def _is_fk_like(name: str) -> bool:
    return name.endswith("_id") or (name.startswith("id_") and name != "id")


def _suffix(name: str) -> str:
    if name.startswith("id_"):
        return name[3:]
    if name.endswith("_id"):
        return name[:-3]
    return ""


def _analyze_sql(sql: str) -> list[tuple[str, str, str]]:
    try:
        statements = sqlglot.parse(sql, read="mysql")
    except Exception:  # noqa: BLE001
        statements = []

    entries: set[tuple[str, str, str]] = set()

    if not statements:
        upper = sql.upper()
        kind, operation = "SELECT", "read"
        if "INSERT" in upper:
            kind, operation = "INSERT", "write"
        elif "UPDATE" in upper:
            kind, operation = "UPDATE", "write"
        elif "DELETE" in upper:
            kind, operation = "DELETE", "write"
        for match in re.finditer(r"\b(?:FROM|JOIN|INTO|UPDATE)\s+`?([A-Za-z_][\w]*)`?", sql, re.I):
            entries.add((match.group(1), operation, kind))
        return sorted(entries)

    for stmt in statements:
        if stmt is None:
            continue

        if isinstance(stmt, exp.Select):
            for table in stmt.find_all(exp.Table):
                entries.add((table.name, "read", "SELECT"))
        elif isinstance(stmt, exp.Insert):
            target = stmt.this
            if isinstance(target, exp.Table):
                entries.add((target.name, "write", "INSERT"))
            for table in stmt.find_all(exp.Table):
                entries.add((table.name, "read", "INSERT"))
        elif isinstance(stmt, exp.Update):
            target = stmt.this
            if isinstance(target, exp.Table):
                entries.add((target.name, "write", "UPDATE"))
            for table in stmt.find_all(exp.Table):
                entries.add((table.name, "read", "UPDATE"))
        elif isinstance(stmt, exp.Delete):
            target = stmt.this
            if isinstance(target, exp.Table):
                entries.add((target.name, "write", "DELETE"))
        else:
            for table in stmt.find_all(exp.Table):
                entries.add((table.name, "read", "OTHER"))

    return sorted(entries)


def _infer_fks(sql: str, pk_map: dict[str, set[str]]) -> list[dict]:
    try:
        statements = sqlglot.parse(sql, read="mysql")
    except Exception:  # noqa: BLE001
        return []

    suggestions = []
    for stmt in statements:
        if stmt is None:
            continue

        alias_map = {table.alias_or_name: table.name for table in stmt.find_all(exp.Table)}

        for eq in stmt.find_all(exp.EQ):
            left, right = eq.this, eq.expression
            if not (isinstance(left, exp.Column) and isinstance(right, exp.Column)):
                continue

            left_table = alias_map.get(left.table)
            right_table = alias_map.get(right.table)
            if not left_table or not right_table or left_table == right_table:
                continue

            left_pk = left.name in pk_map.get(left_table, set())
            right_pk = right.name in pk_map.get(right_table, set())

            if left_pk and not right_pk:
                suggestions.append(_fk(right_table, right.name, left_table, left.name))
            elif right_pk and not left_pk:
                suggestions.append(_fk(left_table, left.name, right_table, right.name))
            elif _is_fk_like(left.name) and not _is_fk_like(right.name):
                suggestions.append(_fk(left_table, left.name, right_table, right.name))
            elif _is_fk_like(right.name) and not _is_fk_like(left.name):
                suggestions.append(_fk(right_table, right.name, left_table, left.name))
            elif _is_fk_like(left.name) and _is_fk_like(right.name):
                left_suffix = _suffix(left.name)
                right_suffix = _suffix(right.name)
                if left_suffix and left_suffix in left_table.lower():
                    suggestions.append(_fk(right_table, right.name, left_table, left.name))
                elif right_suffix and right_suffix in right_table.lower():
                    suggestions.append(_fk(left_table, left.name, right_table, right.name))

    return suggestions


def _fk(table: str, column: str, ref_table: str, ref_column: str) -> dict:
    return {
        "table": table,
        "columns": [column],
        "ref_table": ref_table,
        "ref_columns": [ref_column],
        "origin": "inferred",
    }


def handle(ctx, params):
    root = legacy_repo(ctx)
    if not os.path.isdir(root):
        return TaskResult(False, f"repositório não encontrado: {root}", exit_code=2)

    only_file = params.get("file")
    only_table = params.get("table")
    pk_map = _load_pk_map(ctx)

    links = []
    includes = []
    fk_suggestions: dict[tuple[str, tuple[str, ...]], dict] = {}

    for path in _iter_files(root):
        rel = os.path.relpath(path, root).replace("\\", "/")
        if only_file and rel != str(only_file).replace("\\", "/"):
            continue

        text = read_text(path)

        for match in INCLUDE_RE.finditer(text):
            expression = match.group(2).strip()
            quoted = re.search(r"""['"]([^'"]+)['"]""", expression)
            includes.append(
                {
                    "file": rel,
                    "line": _line_of(text, match.start()),
                    "type": match.group(1).lower(),
                    "target": quoted.group(1) if quoted else expression,
                }
            )

        for match in STRING_RE.finditer(text):
            sql = match.group(2)
            if not SQL_KEYWORDS.search(sql):
                continue

            line = _line_of(text, match.start())

            for table, operation, kind in _analyze_sql(sql):
                if only_table and table != only_table:
                    continue
                links.append(
                    {
                        "file": rel,
                        "line": line,
                        "symbol": None,
                        "table": table,
                        "operation": operation,
                        "statement_kind": kind,
                        "confidence": "parsed",
                        "snippet": sql.strip()[:200],
                    }
                )

            for suggestion in _infer_fks(sql, pk_map):
                if only_table and suggestion["table"] != only_table:
                    continue
                key = (suggestion["table"], tuple(suggestion["columns"]))
                entry = fk_suggestions.setdefault(
                    key,
                    {
                        "table": suggestion["table"],
                        "columns": suggestion["columns"],
                        "ref_table": suggestion["ref_table"],
                        "ref_columns": suggestion["ref_columns"],
                        "origin": "inferred",
                        "evidence": [],
                    },
                )
                evidence = f"{rel}:{line}"
                if evidence not in entry["evidence"]:
                    entry["evidence"].append(evidence)

    out_dir = os.path.join(workspace(ctx), "knowledge", "links")
    write_json(os.path.join(out_dir, "code-db-links.json"), links)
    write_json(os.path.join(out_dir, "includes.json"), includes)
    write_json(
        os.path.join(out_dir, "fk-inferred.json"),
        sorted(fk_suggestions.values(), key=lambda item: (item["table"], item["columns"])),
    )

    summary = (
        f"{len(links)} vínculo(s) código↔tabela, {len(fk_suggestions)} FK(s) inferida(s), "
        f"{len(includes)} include/require"
    )
    return TaskResult(
        True,
        summary,
        artifacts=[
            os.path.join(out_dir, "code-db-links.json"),
            os.path.join(out_dir, "includes.json"),
            os.path.join(out_dir, "fk-inferred.json"),
        ],
    )


register(
    TaskSpec(
        name="db:links",
        intent="read",
        description="Extrai SQL embutido em PHP/JS e vínculos com tabelas",
        required=[],
        optional=["file", "table"],
        handler=handle,
    )
)
