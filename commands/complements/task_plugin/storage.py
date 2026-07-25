import json
from pathlib import Path

DB_PATH = Path("tasks.json")


def _load_db() -> dict:
    if not DB_PATH.exists():
        return {}
    return json.loads(DB_PATH.read_text(encoding="utf-8"))


def _save_db(data: dict):
    DB_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load(codigo: str) -> dict:
    db = _load_db()
    task = db.get(codigo)
    if task is None:
        raise Exception("Task não encontrada")
    return task


def save(codigo: str, data: dict):
    db = _load_db()
    db[codigo] = data
    _save_db(db)


def append_event(codigo: str, event: dict):
    data = load(codigo)
    data["events"].append(event)
    save(codigo, data)


def create(codigo: str):
    db = _load_db()
    if codigo in db:
        raise Exception("Task já existe")
    db[codigo] = {
        "codigo": codigo,
        "events": []
    }
    _save_db(db)
