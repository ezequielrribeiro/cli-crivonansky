import json

from commands.complements.harness.tasks import links
from commands.complements.harness.types import TaskContext


def _context(tmp_path, extra_files=None, graph=None):
    repo = tmp_path / "repo"
    repo.mkdir()
    files = {
        "pedido.php": (
            "<?php\n"
            '$sql = "SELECT * FROM tb_pedidos p JOIN tb_clientes c ON c.id_cli = p.id_cli";\n'
        ),
        "includes.php": "<?php\nrequire_once __DIR__ . '/config.php';\n",
    }
    files.update(extra_files or {})
    for name, content in files.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    workspace = tmp_path / "ws"
    (workspace / "knowledge" / "db").mkdir(parents=True)
    catalog = {
        "tables": [
            {
                "name": "tb_clientes",
                "columns": [{"name": "id_cli", "key": "PRI"}],
                "indexes": [],
            },
            {
                "name": "tb_pedidos",
                "columns": [{"name": "id_cli", "key": None}],
                "indexes": [],
            },
        ]
    }
    (workspace / "knowledge" / "db" / "schema-catalog.json").write_text(
        json.dumps(catalog), encoding="utf-8"
    )

    if graph is not None:
        graph_dir = workspace / "knowledge" / "code" / "codegraph-out"
        graph_dir.mkdir(parents=True)
        (graph_dir / "graph.json").write_text(json.dumps(graph), encoding="utf-8")

    return TaskContext(
        config={"legacy": {"repo_path": str(repo)}},
        workspace=str(workspace),
        run_dir=str(tmp_path / "run"),
    )


def _links(tmp_path):
    return json.loads(
        (tmp_path / "ws" / "knowledge" / "links" / "code-db-links.json").read_text(
            encoding="utf-8"
        )
    )


def _by_table(items, table):
    return [item for item in items if item["table"] == table]


def test_db_links_extracts_tables(tmp_path):
    ctx = _context(tmp_path)
    result = links.handle(ctx, {})

    assert result.success
    tables = {item["table"] for item in _links(tmp_path)}
    assert "tb_pedidos" in tables
    assert "tb_clientes" in tables


def test_db_links_infers_fk_from_join(tmp_path):
    ctx = _context(tmp_path)
    links.handle(ctx, {})

    fks = json.loads(
        (tmp_path / "ws" / "knowledge" / "links" / "fk-inferred.json").read_text(
            encoding="utf-8"
        )
    )
    assert any(
        fk["table"] == "tb_pedidos" and fk["ref_table"] == "tb_clientes"
        for fk in fks
    )


def test_db_links_extracts_includes(tmp_path):
    ctx = _context(tmp_path)
    links.handle(ctx, {})

    includes = json.loads(
        (tmp_path / "ws" / "knowledge" / "links" / "includes.json").read_text(
            encoding="utf-8"
        )
    )
    assert any(item["target"] == "/config.php" for item in includes)


def test_insert_with_column_list_is_write_only(tmp_path):
    ctx = _context(
        tmp_path,
        {
            "insert.php": (
                "<?php\n"
                '$sql = "INSERT INTO tb_nf (id_cli, total) VALUES (1, 2)";\n'
            )
        },
    )
    links.handle(ctx, {})

    entries = {(item["operation"], item["statement_kind"]) for item in _by_table(_links(tmp_path), "tb_nf")}
    assert entries == {("write", "INSERT")}


def test_update_target_is_write_and_join_is_read(tmp_path):
    ctx = _context(
        tmp_path,
        {
            "update.php": (
                "<?php\n"
                '$sql = "UPDATE tb_nf n JOIN tb_extra e ON e.id_cli = n.id_cli '
                'SET n.st = 2";\n'
            )
        },
    )
    links.handle(ctx, {})

    links_data = _links(tmp_path)
    nf = {(item["operation"], item["statement_kind"]) for item in _by_table(links_data, "tb_nf")}
    extra = {(item["operation"], item["statement_kind"]) for item in _by_table(links_data, "tb_extra")}
    assert nf == {("write", "UPDATE")}
    assert extra == {("read", "UPDATE")}


def test_delete_target_is_write(tmp_path):
    ctx = _context(
        tmp_path,
        {"delete.php": '<?php\n$sql = "DELETE FROM tb_nf WHERE id = 1";\n'},
    )
    links.handle(ctx, {})

    entries = {(item["operation"], item["statement_kind"]) for item in _by_table(_links(tmp_path), "tb_nf")}
    assert entries == {("write", "DELETE")}


def test_multi_table_delete_marks_target_write_and_join_read(tmp_path):
    ctx = _context(
        tmp_path,
        {
            "delete_join.php": (
                "<?php\n"
                '$sql = "DELETE n FROM tb_nf n JOIN tb_extra e ON e.id_nf = n.id";\n'
            )
        },
    )
    links.handle(ctx, {})

    links_data = _links(tmp_path)
    nf = {(item["operation"], item["statement_kind"]) for item in _by_table(links_data, "tb_nf")}
    extra = {(item["operation"], item["statement_kind"]) for item in _by_table(links_data, "tb_extra")}
    assert nf == {("write", "DELETE")}
    assert extra == {("read", "DELETE")}
    assert "n" not in {item["table"] for item in links_data}


def test_unparseable_sql_is_marked_heuristic(tmp_path):
    ctx = _context(
        tmp_path,
        {"invalido.php": '<?php\n$sql = "SELECT * FROM tb_nf WHERE id = === 1";\n'},
    )
    links.handle(ctx, {})

    entries = _by_table(_links(tmp_path), "tb_nf")
    assert entries
    assert {item["confidence"] for item in entries} == {"heuristic"}


def test_heredoc_sql_is_detected(tmp_path):
    ctx = _context(
        tmp_path,
        {
            "heredoc.php": (
                "<?php\n"
                "$sql = <<<SQL\n"
                "SELECT * FROM tb_nf\n"
                "WHERE id = 1\n"
                "SQL;\n"
            )
        },
    )
    links.handle(ctx, {})

    entries = _by_table(_links(tmp_path), "tb_nf")
    assert entries
    assert entries[0]["line"] == 2
    assert entries[0]["confidence"] == "parsed"


def test_concatenation_with_literal_variable_is_resolved(tmp_path):
    ctx = _context(
        tmp_path,
        {
            "concat.php": (
                "<?php\n"
                "$tabela = 'tb_nf';\n"
                '$sql = "SELECT * FROM " . $tabela . " WHERE id = 1";\n'
            )
        },
    )
    links.handle(ctx, {})

    entries = _by_table(_links(tmp_path), "tb_nf")
    assert entries
    assert entries[0]["operation"] == "read"
    assert entries[0]["confidence"] == "parsed"


def test_unknown_variable_table_is_not_reported(tmp_path):
    ctx = _context(
        tmp_path,
        {
            "dinamico.php": (
                "<?php\n"
                '$sql = "SELECT * FROM " . $tabela;\n'
            )
        },
    )
    links.handle(ctx, {})

    assert "tb_nf" not in {item["table"] for item in _links(tmp_path)}
    assert "$tabela" not in {item["table"] for item in _links(tmp_path)}


def test_symbol_resolved_from_codeknow_graph(tmp_path):
    source = (
        "<?php\n"
        "function salvar_nf() {\n"
        '    $sql = "INSERT INTO tb_nf (id_cli) VALUES (1)";\n'
        "    return $sql;\n"
        "}\n"
        '$sql = "SELECT * FROM tb_fora";\n'
    )
    graph = {
        "nodes": [
            {
                "label": "salvar_nf()",
                "_callable": True,
                "source_file": "funcoes.php",
                "source_location": "L2",
            }
        ]
    }
    ctx = _context(tmp_path, {"funcoes.php": source}, graph=graph)
    links.handle(ctx, {})

    links_data = _links(tmp_path)
    inside = _by_table(links_data, "tb_nf")
    outside = _by_table(links_data, "tb_fora")
    assert inside and inside[0]["symbol"] == "salvar_nf()"
    assert outside and outside[0]["symbol"] is None


def test_generates_rag_markdown_and_table_views(tmp_path):
    ctx = _context(tmp_path)
    links.handle(ctx, {})

    links_dir = tmp_path / "ws" / "knowledge" / "links"
    assert (links_dir / "code-db-links.md").is_file()
    assert (links_dir / "fk-inferred.md").is_file()
    assert (links_dir / "includes.md").is_file()

    table_md = (links_dir / "tables" / "tb_pedidos.md").read_text(encoding="utf-8")
    assert "# Vínculos: tb_pedidos" in table_md
    assert "## Relações inferidas" in table_md
    assert "tb_pedidos" in (links_dir / "fk-inferred.md").read_text(encoding="utf-8")


def test_removes_stale_table_views(tmp_path):
    ctx = _context(tmp_path)
    stale = tmp_path / "ws" / "knowledge" / "links" / "tables" / "tb_obsoleta.md"
    stale.parent.mkdir(parents=True)
    stale.write_text("# velho\n", encoding="utf-8")

    links.handle(ctx, {})

    assert not stale.exists()
