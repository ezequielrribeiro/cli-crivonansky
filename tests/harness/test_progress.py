"""Testes do relato de progresso das tarefas longas."""

import os

from commands.complements.harness import progress


def _reset(monkeypatch):
    monkeypatch.setenv(progress.MODE_ENV, "auto")
    progress.clear_sink()


def test_sink_receives_start_update_and_finish(monkeypatch):
    _reset(monkeypatch)
    lines: list[str] = []
    progress.set_sink(lines.append)
    try:
        reporter = progress.Progress("db:links", total=10, interval=0)
        reporter.start("iniciando")
        reporter.update(5, note="metade")
        reporter.finish("fim")
    finally:
        progress.clear_sink()

    assert any("iniciando" in line for line in lines)
    assert any("5/10" in line and "metade" in line for line in lines)
    assert any("concluído" in line for line in lines)


def test_update_is_throttled_but_finishes(monkeypatch):
    _reset(monkeypatch)
    lines: list[str] = []
    progress.set_sink(lines.append)
    try:
        reporter = progress.Progress("t", total=100, interval=60)
        reporter.update(1)
        reporter.update(2)
        assert len(lines) == 1

        reporter.update(100)
        assert len(lines) == 2
    finally:
        progress.clear_sink()


def test_off_disables_sink_and_log(monkeypatch, tmp_path):
    _reset(monkeypatch)
    monkeypatch.setenv(progress.MODE_ENV, "off")
    lines: list[str] = []
    progress.set_sink(lines.append)
    log = tmp_path / "progress.log"
    try:
        reporter = progress.Progress("t", total=1, log_path=str(log), interval=0)
        reporter.start()
        reporter.update(1)
    finally:
        progress.clear_sink()

    assert lines == []
    assert not log.exists()


def test_log_file_is_written(monkeypatch, tmp_path):
    _reset(monkeypatch)
    monkeypatch.setenv(progress.MODE_ENV, "log")
    log = tmp_path / "nested" / "progress.log"

    reporter = progress.Progress("code:preprocess", total=2, log_path=str(log), interval=0)
    reporter.start("copiando")
    reporter.update(1, note="50%")
    reporter.finish("pronto")

    text = log.read_text(encoding="utf-8")
    assert "copiando" in text
    assert "1/2" in text
    assert "pronto" in text


def test_sink_failure_does_not_raise(monkeypatch):
    _reset(monkeypatch)

    def boom(_line):
        raise RuntimeError("falha do host")

    progress.set_sink(boom)
    try:
        reporter = progress.Progress("t", total=1, interval=0)
        reporter.start()
        reporter.update(1)
        reporter.finish()
    finally:
        progress.clear_sink()


def test_unwritable_log_does_not_raise(monkeypatch, tmp_path):
    _reset(monkeypatch)
    monkeypatch.setenv(progress.MODE_ENV, "log")
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")

    reporter = progress.Progress("t", total=1, log_path=str(blocker / "progress.log"))
    reporter.start()
    reporter.finish()


def test_for_context_uses_run_dir(tmp_path):
    class Ctx:
        run_dir = str(tmp_path / "run")

    reporter = progress.for_context(Ctx(), "db:links", total=3)
    assert reporter.log_path == os.path.join(Ctx.run_dir, "progress.log")


def test_format_helpers():
    assert progress.format_duration(0) == "00:00"
    assert progress.format_duration(65) == "01:05"
    assert progress.format_duration(3661) == "1:01:01"
    assert progress.format_size(512) == "512 B"
    assert progress.format_size(1536) == "1.5 KB"
    assert progress.format_size(5 * 1024 * 1024) == "5.0 MB"
