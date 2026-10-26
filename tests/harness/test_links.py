import json

from commands.complements.harness.tasks import links
from commands.complements.harness.types import TaskContext


def _context(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pedido.php").write_text(
        '<?php\n'
        '$sql = "SELECT * FROM tb_pedidos p JOIN tb_clientes c ON c.id_cli = p.id_cli";\n',
        encoding="utf-8",
    )
    (repo / "includes.php").write_text(
        "<?php\nrequire_once __DIR__ . '/config.php';\n",
        encoding="utf-8",
    )

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

    return TaskContext(
        config={"legacy": {"repo_path": str(repo)}},
        workspace=str(workspace),
        run_dir=str(tmp_path / "run"),
    )


def test_db_links_extracts_tables(tmp_path):
    ctx = _context(tmp_path)
    result = links.handle(ctx, {})

    assert result.success
    data = json.loads(
        (tmp_path / "ws" / "knowledge" / "links" / "code-db-links.json").read_text(
            encoding="utf-8"
        )
    )
    tables = {item["table"] for item in data}
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
