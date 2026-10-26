from commands.complements.harness.tasks import db


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
