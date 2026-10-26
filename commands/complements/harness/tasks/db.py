"""Tarefas de banco de dados: db:snapshot, db:schema e db:query."""

import json
import os
import re

import sqlglot
from sqlglot import exp

from ..catalog import register
from ..config import get_legacy
from ..runner import run_process
from ..types import TaskResult, TaskSpec
from ..util import (
    as_int,
    ensure_dir,
    legacy_repo,
    read_text,
    workspace,
    write_json,
    write_text,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _db_dir(ctx) -> str:
    return ensure_dir(os.path.join(workspace(ctx), "knowledge", "db"))


def _catalog_path(ctx) -> str:
    return os.path.join(_db_dir(ctx), "schema-catalog.json")


def _tables_dir(ctx) -> str:
    return ensure_dir(os.path.join(_db_dir(ctx), "tables"))


def _col_names(expressions) -> list[str]:
    names = []
    for item in expressions or []:
        if isinstance(item, exp.Identifier):
            names.append(item.name)
        elif isinstance(item, exp.Ordered):
            names.append(item.this.name)
        else:
            names.append(getattr(item, "name", str(item)))
    return names


def _literal(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, exp.Literal):
        return value.this
    return str(value)


def _parse_index_sql(text: str) -> dict | None:
    match = re.search(r"`([^`]+)`\s*\(([^)]*)\)", text)
    if not match:
        return None
    columns = [part.strip().strip("`") for part in match.group(2).split(",")]
    return {
        "name": match.group(1),
        "columns": columns,
        "unique": "UNIQUE" in text.upper(),
    }


def _table_comment(ddl: str) -> str | None:
    match = re.search(r"COMMENT\s*=\s*'((?:[^'\\]|\\.)*)'", ddl)
    return match.group(1) if match else None


def _parse_table(create) -> dict:
    name = create.this.this.name
    ddl = create.sql(dialect="mysql")

    columns = []
    for col in create.find_all(exp.ColumnDef):
        dtype = col.args.get("kind")
        nullable = True
        default = None
        comment = None
        key = None

        for constraint in col.args.get("constraints") or []:
            kind = constraint.args.get("kind")
            if isinstance(kind, exp.NotNullColumnConstraint):
                nullable = False
            elif isinstance(kind, exp.DefaultColumnConstraint):
                default = kind.this.sql(dialect="mysql") if kind.this is not None else None
            elif isinstance(kind, exp.CommentColumnConstraint):
                comment = _literal(kind.this)
            elif isinstance(kind, exp.PrimaryKeyColumnConstraint):
                key = "PRI"
            elif isinstance(kind, exp.UniqueColumnConstraint):
                key = "UNI"

        columns.append(
            {
                "name": col.name,
                "type": dtype.sql(dialect="mysql") if dtype is not None else "",
                "nullable": nullable,
                "default": default,
                "key": key,
                "comment": comment,
            }
        )

    indexes = []
    primary_columns: list[str] = []
    for node in create.this.expressions:
        if isinstance(node, exp.PrimaryKey):
            primary_columns = _col_names(node.expressions)
        elif isinstance(node, (exp.UniqueColumnConstraint, exp.IndexColumnConstraint)):
            parsed = _parse_index_sql(node.sql(dialect="mysql"))
            if parsed:
                indexes.append(parsed)

    if primary_columns:
        indexes.insert(
            0,
            {"name": "PRIMARY", "columns": primary_columns, "unique": True},
        )

    foreign_keys = []
    for fk in create.find_all(exp.ForeignKey):
        ref = fk.args.get("reference")
        ref_table = None
        ref_columns: list[str] = []

        if ref is not None:
            target = ref.this
            if isinstance(target, exp.Schema):
                ref_table = target.this.name if target.this is not None else None
                ref_columns = _col_names(target.expressions)
            elif isinstance(target, exp.Table):
                ref_table = target.name
                ref_columns = _col_names(ref.expressions)

        parent = fk.parent
        constraint_name = None
        if isinstance(parent, exp.Constraint) and parent.this is not None:
            constraint_name = parent.this.name

        foreign_keys.append(
            {
                "name": constraint_name,
                "columns": _col_names(fk.args.get("expressions")),
                "ref_table": ref_table,
                "ref_columns": ref_columns,
                "origin": "declared",
            }
        )

    return {
        "name": name,
        "engine": "InnoDB",
        "comment": _table_comment(ddl),
        "approx_rows": None,
        "columns": columns,
        "indexes": indexes,
        "foreign_keys": foreign_keys,
    }


def parse_dump(sql_text: str, database: str | None = None) -> dict:
    tables = []
    views = []
    routines = []
    db_name = database

    for stmt in sqlglot.parse(sql_text, read="mysql"):
        if stmt is None:
            continue

        if isinstance(stmt, exp.Use):
            db_name = stmt.this.name if stmt.this is not None else db_name
        elif isinstance(stmt, exp.Create):
            if stmt.kind == "TABLE":
                tables.append(_parse_table(stmt))
            elif stmt.kind == "VIEW":
                views.append(
                    {
                        "name": stmt.this.this.name if hasattr(stmt.this, "this") else str(stmt.this),
                        "definition": stmt.sql(dialect="mysql"),
                    }
                )
            elif stmt.kind in ("PROCEDURE", "FUNCTION"):
                routines.append({"name": str(stmt.this), "type": stmt.kind})

    return {
        "database": db_name or "unknown",
        "extracted_from": {"container": None, "server_version": "dump"},
        "tables": tables,
        "views": views,
        "routines": routines,
    }


# ---------------------------------------------------------------------------
# Snapshot ao vivo (docker exec)
# ---------------------------------------------------------------------------
def _mysql_rows(ctx, sql: str) -> list[list[str]]:
    container = get_legacy(ctx.config, "db_container")
    database = get_legacy(ctx.config, "db_name")
    user_env = get_legacy(ctx.config, "db_user_env")
    pass_env = get_legacy(ctx.config, "db_password_env")
    user = os.environ.get(user_env, "root") if user_env else "root"
    password = os.environ.get(pass_env, "") if pass_env else ""

    cmd = ["docker", "exec"]
    if password:
        cmd.extend(["-e", f"MYSQL_PWD={password}"])
    cmd.append(str(container))
    cmd.extend(["mysql", f"-u{user}", "-N", "-B", "-e", sql])
    if database:
        cmd.append(str(database))

    res = run_process(cmd, timeout=120)
    if res.exit_code != 0 or res.timed_out:
        raise RuntimeError(res.combined or "falha ao consultar o MySQL")

    rows = []
    for line in res.stdout.splitlines():
        if line.strip():
            rows.append(line.split("\t"))
    return rows


def snapshot_live(ctx) -> dict:
    database = get_legacy(ctx.config, "db_name") or "unknown"

    tables_rows = _mysql_rows(
        ctx,
        "SELECT TABLE_NAME, ENGINE, TABLE_COMMENT, TABLE_ROWS FROM information_schema.TABLES "
        f"WHERE TABLE_SCHEMA='{database}' AND TABLE_TYPE='BASE TABLE'",
    )
    columns_rows = _mysql_rows(
        ctx,
        "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, "
        "COLUMN_KEY, COLUMN_COMMENT FROM information_schema.COLUMNS "
        f"WHERE TABLE_SCHEMA='{database}' ORDER BY TABLE_NAME, ORDINAL_POSITION",
    )
    fk_rows = _mysql_rows(
        ctx,
        "SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME, "
        "CONSTRAINT_NAME FROM information_schema.KEY_COLUMN_USAGE "
        f"WHERE TABLE_SCHEMA='{database}' AND REFERENCED_TABLE_NAME IS NOT NULL",
    )
    index_rows = _mysql_rows(
        ctx,
        "SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, NON_UNIQUE FROM information_schema.STATISTICS "
        f"WHERE TABLE_SCHEMA='{database}'",
    )
    view_rows = _mysql_rows(
        ctx,
        "SELECT TABLE_NAME, VIEW_DEFINITION FROM information_schema.VIEWS "
        f"WHERE TABLE_SCHEMA='{database}'",
    )

    tables: dict[str, dict] = {}
    for row in tables_rows:
        row += [""] * (4 - len(row))
        tables[row[0]] = {
            "name": row[0],
            "engine": row[1] or None,
            "comment": row[2] or None,
            "approx_rows": int(row[3]) if row[3].isdigit() else None,
            "columns": [],
            "indexes": [],
            "foreign_keys": [],
        }

    for row in columns_rows:
        row += [""] * (7 - len(row))
        table = tables.get(row[0])
        if table is None:
            continue
        table["columns"].append(
            {
                "name": row[1],
                "type": row[2],
                "nullable": row[3].upper() == "YES",
                "default": row[4] or None,
                "key": row[5] or None,
                "comment": row[6] or None,
            }
        )

    for row in fk_rows:
        row += [""] * (5 - len(row))
        table = tables.get(row[0])
        if table is None:
            continue
        table["foreign_keys"].append(
            {
                "name": row[4] or None,
                "columns": [row[1]],
                "ref_table": row[2],
                "ref_columns": [row[3]],
                "origin": "declared",
            }
        )

    index_map: dict[tuple[str, str], dict] = {}
    for row in index_rows:
        row += [""] * (4 - len(row))
        table_name, index_name, column_name, non_unique = row[:4]
        if table_name not in tables:
            continue
        key = (table_name, index_name)
        entry = index_map.setdefault(
            key,
            {"name": index_name, "columns": [], "unique": non_unique == "0"},
        )
        entry["columns"].append(column_name)

    for (table_name, _), entry in index_map.items():
        tables[table_name]["indexes"].append(entry)

    views = []
    for row in view_rows:
        row += [""] * (2 - len(row))
        views.append({"name": row[0], "definition": row[1]})

    return {
        "database": database,
        "extracted_from": {"container": get_legacy(ctx.config, "db_container"), "server_version": "live"},
        "tables": list(tables.values()),
        "views": views,
        "routines": [],
    }


# ---------------------------------------------------------------------------
# Geração de Markdown por tabela
# ---------------------------------------------------------------------------
def _table_markdown(table: dict) -> str:
    lines = [f"# Tabela: {table['name']}", ""]
    if table.get("comment"):
        lines.append(f"- **Descrição:** {table['comment']}")
    lines.append(f"- **Engine:** {table.get('engine') or 'n/d'}")
    lines.append("")
    lines.append("## Campos")
    lines.append("")
    lines.append("| Campo | Tipo | Nulo | Default | Chave | Comentário |")
    lines.append("|---|---|---|---|---|---|")
    for col in table.get("columns") or []:
        lines.append(
            f"| `{col['name']}` | {col['type']} | {'sim' if col['nullable'] else 'não'} | "
            f"{col.get('default') or ''} | {col.get('key') or ''} | {col.get('comment') or ''} |"
        )

    if table.get("indexes"):
        lines.extend(["", "## Índices", ""])
        for idx in table["indexes"]:
            kind = "único" if idx.get("unique") else "comum"
            lines.append(f"- `{idx['name']}` ({kind}): {', '.join(idx['columns'])}")

    if table.get("foreign_keys"):
        lines.extend(["", "## Relacionamentos", ""])
        for fk in table["foreign_keys"]:
            lines.append(
                f"- ({fk.get('origin', 'declared')}) {', '.join(fk['columns'])} → "
                f"{fk['ref_table']}.{', '.join(fk['ref_columns'])}"
            )

    return "\n".join(lines) + "\n"


def _write_outputs(ctx, catalog: dict) -> list[str]:
    write_json(_catalog_path(ctx), catalog)
    artifacts = [_catalog_path(ctx)]
    tables_dir = _tables_dir(ctx)
    for table in catalog.get("tables") or []:
        path = os.path.join(tables_dir, f"{table['name']}.md")
        write_text(path, _table_markdown(table))
        artifacts.append(path)
    return artifacts


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------
def handle_snapshot(ctx, params):
    source = str(params.get("source") or "auto").lower()
    dump_path = get_legacy(ctx.config, "schema_dump")

    catalog = None
    error = None

    if source in ("auto", "live"):
        try:
            catalog = snapshot_live(ctx)
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            if source == "live":
                return TaskResult(
                    False,
                    "falha no snapshot ao vivo",
                    details=error,
                    exit_code=2,
                )

    if catalog is None and dump_path and os.path.isfile(dump_path):
        catalog = parse_dump(read_text(dump_path))
        catalog["extracted_from"]["source_file"] = dump_path

    if catalog is None:
        return TaskResult(
            False,
            "não foi possível obter o schema (Docker indisponível e dump ausente)",
            details=error or "",
            exit_code=2,
        )

    artifacts = _write_outputs(ctx, catalog)
    summary = (
        f"schema de '{catalog['database']}': {len(catalog['tables'])} tabela(s), "
        f"{len(catalog['views'])} view(s)"
    )
    if error:
        summary += " (via dump; Docker indisponível)"
    return TaskResult(True, summary, artifacts=artifacts)


def handle_schema(ctx, params):
    table_name = params.get("table")
    if not table_name:
        return TaskResult(False, "parâmetro 'table' obrigatório", exit_code=2)

    if not os.path.isfile(_catalog_path(ctx)):
        return TaskResult(False, "schema-catalog.json não encontrado; rode db:snapshot", exit_code=2)

    with open(_catalog_path(ctx), "r", encoding="utf-8") as fh:
        catalog = json.load(fh)

    table = next((t for t in catalog.get("tables", []) if t["name"] == table_name), None)
    if table is None:
        return TaskResult(False, f"tabela não encontrada: {table_name}", exit_code=2)

    markdown = _table_markdown(table)

    dictionary_dir = os.path.join(_db_dir(ctx), "dictionary")
    if os.path.isdir(dictionary_dir):
        for filename in sorted(os.listdir(dictionary_dir)):
            if filename.lower().endswith((".yaml", ".yml")):
                markdown += f"\n\n## Dicionário ({filename})\n\n```yaml\n"
                markdown += read_text(os.path.join(dictionary_dir, filename))
                markdown += "\n```\n"

    return TaskResult(True, f"schema da tabela {table_name}", details=markdown)


def handle_query(ctx, params):
    sql = params.get("sql")
    if not sql:
        return TaskResult(False, "parâmetro 'sql' obrigatório", exit_code=2)

    try:
        statements = sqlglot.parse(str(sql), read="mysql")
    except Exception as exc:  # noqa: BLE001
        return TaskResult(False, f"SQL inválido: {exc}", exit_code=2)

    allowed = (exp.Select, exp.Show, exp.Describe)
    if not statements or any(not isinstance(stmt, allowed) for stmt in statements):
        return TaskResult(
            False,
            "db:query aceita apenas SELECT/SHOW/DESCRIBE/EXPLAIN",
            exit_code=3,
            status="denied",
        )

    limit = as_int(params.get("limit"), 50)
    query = str(sql).strip().rstrip(";")
    if isinstance(statements[0], exp.Select) and "limit" not in query.lower():
        query = f"{query} LIMIT {limit}"

    try:
        rows = _mysql_rows(ctx, query)
    except Exception as exc:  # noqa: BLE001
        return TaskResult(False, "falha ao executar a consulta", details=str(exc), exit_code=2)

    details = "\n".join("\t".join(row) for row in rows)
    return TaskResult(True, f"{len(rows)} linha(s) retornada(s)", details=details)


register(
    TaskSpec(
        name="db:snapshot",
        intent="read",
        description="Extrai o schema do MySQL (ao vivo via docker exec ou do dump)",
        required=[],
        optional=["source"],
        handler=handle_snapshot,
    )
)

register(
    TaskSpec(
        name="db:schema",
        intent="read",
        description="Gera o Markdown de uma tabela a partir do schema-catalog",
        required=["table"],
        optional=[],
        handler=handle_schema,
    )
)

register(
    TaskSpec(
        name="db:query",
        intent="read",
        description="Executa uma consulta somente leitura no MySQL",
        required=["sql"],
        optional=["limit"],
        handler=handle_query,
    )
)
