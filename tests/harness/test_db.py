import json

from commands.complements.harness.tasks import db
from commands.complements.harness.task_types import TaskContext


def test_db_query_rejects_update():
    result = db.handle_query(None, {"sql": "UPDATE tb_alugueis SET st = 2"})
    assert result.success is False
    assert result.status == "denied"


def test_db_query_rejects_delete():
    result = db.handle_query(None, {"sql": "DELETE FROM tb_alugueis"})
    assert result.success is False
    assert result.status == "denied"


def test_db_query_rejects_drop():
    result = db.handle_query(None, {"sql": "DROP TABLE tb_alugueis"})
    assert result.success is False
    assert result.status == "denied"


def test_db_schema_includes_code_links(tmp_path):
    workspace = tmp_path / "ws"
    (workspace / "knowledge" / "db").mkdir(parents=True)
    catalog = {
        "tables": [
            {
                "name": "tb_x",
                "engine": "InnoDB",
                "comment": None,
                "approx_rows": None,
                "columns": [
                    {
                        "name": "id",
                        "type": "int",
                        "nullable": False,
                        "default": None,
                        "key": "PRI",
                        "comment": None,
                    }
                ],
                "indexes": [],
                "foreign_keys": [],
            }
        ]
    }
    (workspace / "knowledge" / "db" / "schema-catalog.json").write_text(
        json.dumps(catalog), encoding="utf-8"
    )

    links_dir = workspace / "knowledge" / "links"
    links_dir.mkdir(parents=True)
    (links_dir / "code-db-links.json").write_text(
        json.dumps(
            [
                {
                    "file": "app.php",
                    "line": 10,
                    "symbol": "salvar()",
                    "table": "tb_x",
                    "operation": "write",
                    "statement_kind": "UPDATE",
                    "confidence": "parsed",
                    "snippet": "UPDATE tb_x SET id = 1",
                }
            ]
        ),
        encoding="utf-8",
    )
    (links_dir / "fk-inferred.json").write_text(
        json.dumps(
            [
                {
                    "table": "tb_x",
                    "columns": ["id_y"],
                    "ref_table": "tb_y",
                    "ref_columns": ["id"],
                    "origin": "inferred",
                    "evidence": ["app.php:10"],
                }
            ]
        ),
        encoding="utf-8",
    )

    ctx = TaskContext(
        config={}, workspace=str(workspace), run_dir=str(tmp_path / "run")
    )
    result = db.handle_schema(ctx, {"table": "tb_x"})

    assert result.success
    assert "## Vínculos no código" in result.details
    assert "app.php:10" in result.details
    assert "salvar()" in result.details
    assert "tb_x.id_y" in result.details
