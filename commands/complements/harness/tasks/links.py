"""Tarefa db:links — extrai SQL embutido em PHP/JS e vínculos com tabelas.

Além do extrator, a tarefa resolve o símbolo (função/método) que contém cada
ocorrência usando o grafo do codeknow e gera visões em Markdown para o RAG:

* ``code-db-links.json`` — vínculos código ↔ tabela;
* ``fk-inferred.json`` — FKs sugeridas a partir de JOINs e convenções de nome;
* ``includes.json`` — ``include``/``require`` de PHP;
* ``code-db-links.md``, ``fk-inferred.md``, ``includes.md`` e ``tables/<tabela>.md``.
"""

import ast
import json
import os
import re
import shutil

import sqlglot
from sqlglot import exp

from ..catalog import register
from ..types import TaskResult, TaskSpec
from ..util import legacy_repo, read_text, workspace, write_json, write_text

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
SQL_KEYWORDS = re.compile(r"\b(SELECT|INSERT\s+INTO|UPDATE|DELETE|REPLACE\s+INTO)\b", re.I)
INCLUDE_RE = re.compile(
    r"\b(include|include_once|require|require_once)\b\s*\(?\s*([^;]+);",
    re.I,
)

# PHP heredoc/nowdoc: <<<SQL ... SQL; e <<<'SQL' ... SQL;
HEREDOC_RE = re.compile(
    r"<<<[ \t]*(['\"]?)([A-Za-z_]\w*)\1\r?\n(.*?)\r?\n[ \t]*\2\b",
    re.S,
)

# Parte de uma concatenação PHP: string literal, $var ou {$var}.
_PHP_PART = r"""(?:'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*"|\$[A-Za-z_]\w*|\{\$[A-Za-z_]\w*\})"""
CONCAT_RE = re.compile(rf"{_PHP_PART}(?:\s*\.\s*{_PHP_PART})+", re.S)
PART_RE = re.compile(_PHP_PART, re.S)

# Atribuição simples de literal: $tabela = 'tb_x';
ASSIGN_RE = re.compile(
    r"""\$([A-Za-z_]\w*)\s*=\s*(['"])((?:\\.|(?!\2).)*)\2\s*;""",
    re.S,
)

_TABLE_REF_RE = re.compile(
    r"\b(FROM|JOIN|INTO|UPDATE|USING)\s+(?:`?[A-Za-z_]\w*`?\s*\.\s*)?`?([A-Za-z_]\w*)`?",
    re.I,
)


# ---------------------------------------------------------------------------
# Helpers de arquivo
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Extração de candidatos a SQL (literais, heredocs e concatenações)
# ---------------------------------------------------------------------------
def _constant_strings(text: str) -> dict[str, str]:
    """Propaga atribuições simples ($var = 'literal';) sem ambiguidade."""
    values: dict[str, str | None] = {}
    for match in ASSIGN_RE.finditer(text):
        name, _quote, body = match.group(1), match.group(2), match.group(3)
        if "$" in body:
            continue
        if name in values and values[name] != body:
            values[name] = None
        else:
            values.setdefault(name, body)
    return {name: value for name, value in values.items() if value is not None}


def _expand_vars(sql: str, constants: dict[str, str]) -> str:
    if not constants:
        return sql

    def replace(match):
        name = match.group(1)
        return constants.get(name, match.group(0))

    sql = re.sub(r"\{\$([A-Za-z_]\w*)\}", replace, sql)
    return re.sub(r"\$([A-Za-z_]\w*)", replace, sql)


def _part_value(part: str, constants: dict[str, str]) -> str:
    if part.startswith("{"):
        name = part[2:-1]
        return constants.get(name, part)
    if part.startswith("$"):
        return constants.get(part[1:], part)
    return part[1:-1]


def _overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < other_end and end > other_start for other_start, other_end in spans)


def _iter_sql(text: str):
    """Devolve (linha, sql) dos candidatos, sem duplicar literais consumidos."""
    constants = _constant_strings(text)
    consumed: list[tuple[int, int]] = []
    candidates: list[tuple[int, str]] = []

    for match in HEREDOC_RE.finditer(text):
        consumed.append(match.span())
        sql = _expand_vars(match.group(3), constants)
        if SQL_KEYWORDS.search(sql):
            candidates.append((_line_of(text, match.start()), sql))

    for match in CONCAT_RE.finditer(text):
        if _overlaps(match.span(), consumed):
            continue
        consumed.append(match.span())
        parts = PART_RE.findall(match.group(0))
        sql = "".join(_part_value(part, constants) for part in parts)
        if SQL_KEYWORDS.search(sql):
            candidates.append((_line_of(text, match.start()), sql))

    for match in STRING_RE.finditer(text):
        if _overlaps(match.span(), consumed):
            continue
        sql = _expand_vars(match.group(2), constants)
        if SQL_KEYWORDS.search(sql):
            candidates.append((_line_of(text, match.start()), sql))

    return sorted(candidates, key=lambda item: item[0])


# ---------------------------------------------------------------------------
# Análise do SQL
# ---------------------------------------------------------------------------
def _valid_table(name: str) -> bool:
    return bool(name) and not name.startswith("$") and "{" not in name and "}" not in name


def _target_table(stmt):
    target = stmt.this
    if isinstance(target, exp.Schema):
        target = target.this
    return target if isinstance(target, exp.Table) else None


def _write_entries(stmt, kind: str) -> set[tuple[str, str, str]]:
    """Alvo recebe write; demais tabelas (JOINs, USING, subqueries) recebem read."""
    target = _target_table(stmt)
    tables = list(stmt.find_all(exp.Table))
    entries: set[tuple[str, str, str]] = set()

    if target is None:
        for table in tables:
            entries.add((table.name, "read", kind))
        return entries

    target_name = target.name
    alias_matches = [
        table
        for table in tables
        if table.name != target_name and table.alias_or_name == target_name
    ]

    for table in tables:
        if table is not target and table.name == table.alias_or_name and any(
            other is not table
            and other.name != table.name
            and other.alias_or_name == table.name
            for other in tables
        ):
            # Referência ao alias em DELETE/UPDATE multi-tabela (ex.: "DELETE a FROM tb_a a").
            continue
        if table is target:
            entries.add((table.name, "write", kind))
        elif alias_matches:
            # DELETE/UPDATE multi-tabela apontando para um alias.
            if table in alias_matches:
                entries.add((table.name, "write", kind))
            elif not (table.name == target_name and table.alias_or_name == target_name):
                entries.add((table.name, "read", kind))
        else:
            entries.add((table.name, "read", kind))

    if not alias_matches:
        entries.add((target_name, "write", kind))
    return entries


def _analyze_heuristic(sql: str) -> set[tuple[str, str, str]]:
    upper = sql.upper()
    if "DELETE" in upper:
        kind = "DELETE"
    elif "UPDATE" in upper:
        kind = "UPDATE"
    elif "REPLACE" in upper:
        kind = "REPLACE"
    elif "INSERT" in upper:
        kind = "INSERT"
    else:
        kind = "SELECT"

    entries: set[tuple[str, str, str]] = set()
    for keyword, table in _TABLE_REF_RE.findall(sql):
        keyword = keyword.upper()
        if keyword in ("INTO", "UPDATE"):
            operation = "write"
        elif keyword == "FROM" and kind == "DELETE":
            operation = "write"
        else:
            operation = "read"
        entries.add((table, operation, kind))
    return entries


def _analyze_sql(sql: str) -> tuple[list[tuple[str, str, str]], str]:
    """Devolve (entradas, confiança), com confiança parsed | heuristic."""
    try:
        statements = sqlglot.parse(sql, read="mysql")
    except Exception:  # noqa: BLE001
        return sorted(_analyze_heuristic(sql)), "heuristic"

    entries: set[tuple[str, str, str]] = set()
    confidence = "parsed"

    for stmt in statements:
        if stmt is None:
            continue

        if isinstance(stmt, exp.Command):
            # sqlglot não modela tudo (ex.: REPLACE INTO com lista de colunas).
            entries |= _analyze_heuristic(sql)
            confidence = "heuristic"
        elif isinstance(stmt, exp.Select):
            for table in stmt.find_all(exp.Table):
                entries.add((table.name, "read", "SELECT"))
        elif isinstance(stmt, exp.Insert):
            entries |= _write_entries(stmt, "INSERT")
        elif isinstance(stmt, exp.Update):
            entries |= _write_entries(stmt, "UPDATE")
        elif isinstance(stmt, exp.Delete):
            entries |= _write_entries(stmt, "DELETE")
        else:
            for table in stmt.find_all(exp.Table):
                entries.add((table.name, "read", "OTHER"))

    if not entries:
        entries |= _analyze_heuristic(sql)
        if entries:
            confidence = "heuristic"

    return sorted(entries), confidence


# ---------------------------------------------------------------------------
# FKs inferidas
# ---------------------------------------------------------------------------
def _is_fk_like(name: str) -> bool:
    return name.endswith("_id") or (name.startswith("id_") and name != "id")


def _suffix(name: str) -> str:
    if name.startswith("id_"):
        return name[3:]
    if name.endswith("_id"):
        return name[:-3]
    return ""


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


# ---------------------------------------------------------------------------
# Símbolos (função/método) via grafo do codeknow
# ---------------------------------------------------------------------------
def _graph_path(ctx) -> str | None:
    base = os.path.join(workspace(ctx), "knowledge", "code")
    for candidate in (
        os.path.join(base, "codegraph-out", "graph.json"),
        os.path.join(base, "graph.json"),
    ):
        if os.path.isfile(candidate):
            return candidate
    return None


def _brace_block_end(text: str, start_line: int) -> int | None:
    if start_line < 1:
        return None

    offset = 0
    for _ in range(start_line - 1):
        newline = text.find("\n", offset)
        if newline == -1:
            return None
        offset = newline + 1

    state = "code"
    depth = 0
    opened = False
    line_no = start_line
    index = offset

    while index < len(text):
        char = text[index]
        nxt = text[index + 1] if index + 1 < len(text) else ""

        if state == "code":
            if char == "'":
                state = "single"
            elif char == '"':
                state = "double"
            elif char == "/" and nxt == "/":
                state = "line_comment"
                index += 1
            elif char == "#":
                state = "line_comment"
            elif char == "/" and nxt == "*":
                state = "block_comment"
                index += 1
            elif char == "{":
                depth += 1
                opened = True
            elif char == "}":
                if opened:
                    depth -= 1
                    if depth == 0:
                        return line_no
            elif char == "\n":
                line_no += 1
        elif state in ("single", "double"):
            quote = "'" if state == "single" else '"'
            if char == "\\":
                index += 1
            elif char == quote:
                state = "code"
            elif char == "\n":
                line_no += 1
        elif state == "line_comment":
            if char == "\n":
                state = "code"
                line_no += 1
        elif state == "block_comment":
            if char == "*" and nxt == "/":
                state = "code"
                index += 1
            elif char == "\n":
                line_no += 1

        index += 1

    return None


def _python_block_end(text: str, start_line: int) -> int | None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.lineno == start_line:
                return getattr(node, "end_lineno", None)
    return None


def _block_end(rel: str, start: int, text: str | None) -> int | None:
    if text is None:
        return None
    if rel.lower().endswith(".py"):
        return _python_block_end(text, start)
    return _brace_block_end(text, start)


def _load_symbols(ctx, repo: str) -> dict[str, list[tuple[int, int, str]]]:
    graph_file = _graph_path(ctx)
    if not graph_file:
        return {}

    try:
        with open(graph_file, "r", encoding="utf-8") as fh:
            graph = json.load(fh)
    except (OSError, ValueError):
        return {}

    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    if not isinstance(nodes, list):
        return {}

    sources: dict[str, str | None] = {}
    ranges: dict[str, list[tuple[int, int, str]]] = {}

    for node in nodes:
        if not isinstance(node, dict) or not node.get("_callable"):
            continue

        rel = str(node.get("source_file") or "").replace("\\", "/")
        label = node.get("label") or node.get("norm_label")
        if not rel or not label:
            continue

        numbers = [int(value) for value in re.findall(r"\d+", str(node.get("source_location") or ""))]
        if not numbers:
            continue
        start = numbers[0]

        if rel not in sources:
            try:
                with open(os.path.join(repo, rel), "r", encoding="utf-8", errors="replace") as fh:
                    sources[rel] = fh.read()
            except OSError:
                sources[rel] = None

        end = _block_end(rel, start, sources[rel])
        ranges.setdefault(rel, []).append((start, end or start, str(label)))

    return ranges


def _resolve_symbol(
    ranges: dict[str, list[tuple[int, int, str]]], rel: str, line: int
) -> str | None:
    best: tuple[int, str] | None = None
    for start, end, label in ranges.get(rel, ()):
        if start <= line <= end and (best is None or start >= best[0]):
            best = (start, label)
    return best[1] if best else None


# ---------------------------------------------------------------------------
# Markdown para o RAG
# ---------------------------------------------------------------------------
def _flat(text: str | None, limit: int = 160) -> str:
    flat = " ".join((text or "").split())
    if len(flat) > limit:
        flat = flat[:limit].rstrip() + "..."
    return flat.replace("`", "'")


def _link_bullet(link: dict) -> str:
    symbol = f" em `{link['symbol']}`" if link.get("symbol") else ""
    snippet = _flat(link.get("snippet"))
    suffix = f" — {snippet}" if snippet else ""
    return (
        f"- `{link['file']}:{link['line']}` — **{link['statement_kind']}** "
        f"({link['operation']}){symbol}{suffix}"
    )


def _links_markdown(links: list[dict]) -> str:
    parts = ["# Vínculos código↔tabela", ""]
    if not links:
        parts.append("Nenhum vínculo encontrado.")
        return "\n".join(parts) + "\n"

    by_table: dict[str, list[dict]] = {}
    for link in links:
        by_table.setdefault(link["table"], []).append(link)

    for table in sorted(by_table):
        parts.append(f"## Tabela: {table}")
        parts.append("")
        for link in sorted(
            by_table[table],
            key=lambda item: (item["operation"] != "write", item["file"], item["line"]),
        ):
            parts.append(_link_bullet(link))
        parts.append("")

    return "\n".join(parts)


def _table_markdown(table: str, table_links: list[dict], table_fks: list[dict]) -> str:
    writes = [link for link in table_links if link["operation"] == "write"]
    reads = [link for link in table_links if link["operation"] != "write"]

    parts = [f"# Vínculos: {table}", ""]
    parts.append(
        f"- **Escritas:** {len(writes)} · **Leituras:** {len(reads)} · "
        f"**FKs inferidas:** {len(table_fks)}"
    )
    parts.append("")

    for title, group in (("Escritas (write)", writes), ("Leituras (read)", reads)):
        if not group:
            continue
        parts.append(f"## {title}")
        parts.append("")
        for link in sorted(group, key=lambda item: (item["file"], item["line"])):
            parts.append(_link_bullet(link))
        parts.append("")

    if table_fks:
        parts.append("## Relações inferidas")
        parts.append("")
        for fk in sorted(table_fks, key=lambda item: (item["ref_table"], item["columns"])):
            columns = ", ".join(fk["columns"])
            ref_columns = ", ".join(fk["ref_columns"])
            parts.append(
                f"- `{fk['table']}.{columns}` → `{fk['ref_table']}.{ref_columns}`"
            )
            for evidence in fk.get("evidence") or []:
                parts.append(f"  - evidência: `{evidence}`")
        parts.append("")

    return "\n".join(parts)


def _fk_markdown(fks: list[dict]) -> str:
    parts = ["# FKs inferidas", ""]
    if not fks:
        parts.append("Nenhuma FK inferida.")
        return "\n".join(parts) + "\n"

    parts.append(
        "Relações sugeridas a partir de JOINs e convenções de nome "
        "(não declaradas no schema)."
    )
    parts.append("")
    for fk in sorted(fks, key=lambda item: (item["table"], item["columns"])):
        columns = ", ".join(fk["columns"])
        ref_columns = ", ".join(fk["ref_columns"])
        parts.append(f"- `{fk['table']}.{columns}` → `{fk['ref_table']}.{ref_columns}`")
        for evidence in fk.get("evidence") or []:
            parts.append(f"  - evidência: `{evidence}`")
    parts.append("")

    return "\n".join(parts)


def _includes_markdown(includes: list[dict]) -> str:
    parts = ["# Includes e requires (PHP)", ""]
    if not includes:
        parts.append("Nenhum include/require encontrado.")
        return "\n".join(parts) + "\n"

    by_file: dict[str, list[dict]] = {}
    for include in includes:
        by_file.setdefault(include["file"], []).append(include)

    for filename in sorted(by_file):
        parts.append(f"## {filename}")
        parts.append("")
        for include in sorted(by_file[filename], key=lambda item: item["line"]):
            parts.append(
                f"- `{include['file']}:{include['line']}` — {include['type']} → "
                f"`{include['target']}`"
            )
        parts.append("")

    return "\n".join(parts)


def _safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------
def handle(ctx, params):
    root = legacy_repo(ctx)
    if not os.path.isdir(root):
        return TaskResult(False, f"repositório não encontrado: {root}", exit_code=2)

    only_file = params.get("file")
    only_table = params.get("table")
    pk_map = _load_pk_map(ctx)
    symbols = _load_symbols(ctx, root)

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

        for line, sql in _iter_sql(text):
            entries, confidence = _analyze_sql(sql)
            symbol = _resolve_symbol(symbols, rel, line)

            for table, operation, kind in entries:
                if not _valid_table(table):
                    continue
                if only_table and table != only_table:
                    continue
                links.append(
                    {
                        "file": rel,
                        "line": line,
                        "symbol": symbol,
                        "table": table,
                        "operation": operation,
                        "statement_kind": kind,
                        "confidence": confidence,
                        "snippet": sql.strip()[:200],
                    }
                )

            for suggestion in _infer_fks(sql, pk_map):
                if not _valid_table(suggestion["table"]):
                    continue
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

    fks = sorted(fk_suggestions.values(), key=lambda item: (item["table"], item["columns"]))

    out_dir = os.path.join(workspace(ctx), "knowledge", "links")
    write_json(os.path.join(out_dir, "code-db-links.json"), links)
    write_json(os.path.join(out_dir, "includes.json"), includes)
    write_json(os.path.join(out_dir, "fk-inferred.json"), fks)

    write_text(os.path.join(out_dir, "code-db-links.md"), _links_markdown(links))
    write_text(os.path.join(out_dir, "fk-inferred.md"), _fk_markdown(fks))
    write_text(os.path.join(out_dir, "includes.md"), _includes_markdown(includes))

    tables_dir = os.path.join(out_dir, "tables")
    if os.path.isdir(tables_dir):
        shutil.rmtree(tables_dir)
    os.makedirs(tables_dir, exist_ok=True)

    tables = sorted({link["table"] for link in links})
    for table in tables:
        table_links = [link for link in links if link["table"] == table]
        table_fks = [fk for fk in fks if fk["table"] == table or fk["ref_table"] == table]
        write_text(
            os.path.join(tables_dir, f"{_safe_filename(table)}.md"),
            _table_markdown(table, table_links, table_fks),
        )

    summary = (
        f"{len(links)} vínculo(s) código↔tabela, {len(fks)} FK(s) inferida(s), "
        f"{len(includes)} include/require"
    )
    return TaskResult(
        True,
        summary,
        artifacts=[
            os.path.join(out_dir, "code-db-links.json"),
            os.path.join(out_dir, "includes.json"),
            os.path.join(out_dir, "fk-inferred.json"),
            tables_dir,
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
