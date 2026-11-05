"""Testes do runner de subprocessos (captura, streaming e timeout)."""

import os
import sys

import pytest

from commands.complements.harness.runner import run_process


def test_captures_stdout_stderr_and_exit_code():
    code = "import sys; print('saida'); print('aviso', file=sys.stderr); raise SystemExit(3)"
    result = run_process([sys.executable, "-c", code], timeout=60)

    assert result.exit_code == 3
    assert "saida" in result.stdout
    assert "aviso" in result.stderr
    assert "saida" in result.combined
    assert result.timed_out is False


def test_stream_receives_lines_in_real_time():
    lines: list[str] = []
    code = "print('primeira'); print('segunda')"

    result = run_process([sys.executable, "-u", "-c", code], timeout=60, stream=lines.append)

    assert result.exit_code == 0
    assert lines == ["primeira", "segunda"]


def test_stream_failure_does_not_break_the_result():
    def boom(_line):
        raise RuntimeError("host fora do ar")

    result = run_process(
        [sys.executable, "-u", "-c", "print('ok')"],
        timeout=60,
        stream=boom,
    )

    assert result.exit_code == 0
    assert "ok" in result.stdout


def test_timeout_kills_the_process():
    result = run_process(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        timeout=1,
    )

    assert result.timed_out is True


def test_spawn_failure_reports_command_and_cwd():
    with pytest.raises(OSError) as info:
        run_process(["python-que-nao-existe-xyz.exe"], cwd=os.getcwd(), timeout=10)

    message = str(info.value)
    assert "python-que-nao-existe-xyz.exe" in message
    assert "comando:" in message
    assert "cwd:" in message
