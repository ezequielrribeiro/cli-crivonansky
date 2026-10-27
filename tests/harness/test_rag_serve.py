from commands.complements.harness.tasks import rag_serve
from commands.complements.harness.types import TaskContext


def _context(tmp_path):
    rag_path = tmp_path / "rag"
    rag_path.mkdir()
    rag_python = rag_path / "python.exe"
    rag_python.write_text("", encoding="utf-8")

    return TaskContext(
        config={
            "tools": {
                "rag": {
                    "path": str(rag_path),
                    "python": str(rag_python),
                    "api": "http://127.0.0.1:8111",
                }
            }
        },
        workspace=str(tmp_path / "ws"),
        run_dir=str(tmp_path / "run"),
    )


def test_status_reports_running(tmp_path, monkeypatch):
    ctx = _context(tmp_path)
    monkeypatch.setattr(
        rag_serve,
        "_health",
        lambda *a, **k: (
            True,
            {"status": "ok", "vector_index_loaded": True, "num_chunks": 160},
        ),
    )

    result = rag_serve.handle(ctx, {"action": "status"})

    assert result.success
    assert "rodando" in result.summary
    assert "160" in result.details


def test_status_reports_stopped(tmp_path, monkeypatch):
    ctx = _context(tmp_path)
    monkeypatch.setattr(rag_serve, "_health", lambda *a, **k: (False, "connection refused"))

    result = rag_serve.handle(ctx, {"action": "status"})

    assert result.success
    assert "parada" in result.summary


def test_start_is_idempotent(tmp_path, monkeypatch):
    ctx = _context(tmp_path)
    monkeypatch.setattr(
        rag_serve,
        "_health",
        lambda *a, **k: (True, {"status": "ok", "num_chunks": 1}),
    )
    monkeypatch.setattr(
        rag_serve.subprocess,
        "Popen",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria iniciar")),
    )

    result = rag_serve.handle(ctx, {"action": "start"})

    assert result.success
    assert "já está rodando" in result.summary


def test_start_spawns_and_waits_for_health(tmp_path, monkeypatch):
    ctx = _context(tmp_path)
    responses = iter([(False, "off"), (True, {"status": "ok", "num_chunks": 2})])
    calls = []

    class FakeProc:
        pid = 4242

        def poll(self):
            return None

    def fake_popen(cmd, **kwargs):
        calls.append(cmd)
        return FakeProc()

    monkeypatch.setattr(rag_serve, "_health", lambda *a, **k: next(responses))
    monkeypatch.setattr(rag_serve, "_pids_on_port", lambda port: [])
    monkeypatch.setattr(rag_serve, "_port_in_use", lambda *a, **k: False)
    monkeypatch.setattr(rag_serve.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(rag_serve.time, "sleep", lambda *_: None)

    result = rag_serve.handle(ctx, {"action": "start"})

    assert result.success
    assert "PID 4242" in result.summary
    assert calls[0][1:] == ["main.py", "serve", "--host", "127.0.0.1", "--port", "8111"]
    assert rag_serve._read_pid(ctx) == 4242


def test_start_refuses_busy_port(tmp_path, monkeypatch):
    ctx = _context(tmp_path)
    monkeypatch.setattr(rag_serve, "_health", lambda *a, **k: (False, "off"))
    monkeypatch.setattr(rag_serve, "_port_in_use", lambda *a, **k: True)

    result = rag_serve.handle(ctx, {"action": "start"})

    assert result.success is False
    assert result.exit_code == 2
    assert "ocupada" in result.summary


def test_stop_kills_pid_listening_on_port(tmp_path, monkeypatch):
    ctx = _context(tmp_path)
    rag_serve._write_pid(ctx, 99)
    killed = []
    health_calls = {"n": 0}

    def fake_health(*args, **kwargs):
        health_calls["n"] += 1
        if health_calls["n"] == 1:
            return True, {"status": "ok"}
        return False, "off"

    monkeypatch.setattr(rag_serve, "_kill_pid", lambda pid: killed.append(pid) or True)
    monkeypatch.setattr(rag_serve, "_pids_on_port", lambda port: [99])
    monkeypatch.setattr(rag_serve, "_health", fake_health)
    monkeypatch.setattr(rag_serve, "_port_in_use", lambda *a, **k: False)
    monkeypatch.setattr(rag_serve.time, "sleep", lambda *_: None)

    result = rag_serve.handle(ctx, {"action": "stop"})

    assert result.success
    assert killed == [99]
    assert rag_serve._read_pid(ctx) is None


def test_stop_ignores_stale_pid_file(tmp_path, monkeypatch):
    ctx = _context(tmp_path)
    rag_serve._write_pid(ctx, 99)
    killed = []

    monkeypatch.setattr(rag_serve, "_kill_pid", lambda pid: killed.append(pid) or True)
    monkeypatch.setattr(rag_serve, "_pids_on_port", lambda port: [])

    result = rag_serve.handle(ctx, {"action": "stop"})

    assert result.success
    assert killed == []
    assert rag_serve._read_pid(ctx) is None


def test_stop_does_not_kill_unknown_process_on_port(tmp_path, monkeypatch):
    ctx = _context(tmp_path)
    killed = []

    monkeypatch.setattr(rag_serve, "_kill_pid", lambda pid: killed.append(pid) or True)
    monkeypatch.setattr(rag_serve, "_pids_on_port", lambda port: [123])
    monkeypatch.setattr(rag_serve, "_health", lambda *a, **k: (False, "off"))

    result = rag_serve.handle(ctx, {"action": "stop"})

    assert result.success is False
    assert result.exit_code == 2
    assert killed == []


def test_rejects_invalid_action(tmp_path):
    ctx = _context(tmp_path)

    result = rag_serve.handle(ctx, {"action": "explode"})

    assert result.success is False
    assert result.exit_code == 2
