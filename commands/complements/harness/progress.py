"""Relato de progresso das tarefas demoradas.

O ``CommandExecutor`` captura o ``stdout`` do comando em um ``StringIO``, então
um ``print`` só aparece quando a tarefa termina. Tarefas que varrem repositórios
grandes (``db:links``, ``code:preprocess``) usam este módulo para publicar o
andamento em tempo real por três canais:

* **sink** — callback registrado pelo host (a TUI escreve no ``RichLog``);
* **stderr** — quando ele é um terminal interativo e não há sink (modo CLI);
* **arquivo de log** — ``<run_dir>/progress.log``, sempre gravado, para
  conferir depois o que aconteceu.

A publicação nunca levanta exceção: se o log não puder ser escrito ou o sink
falhar, a tarefa continua.

Variáveis de ambiente:

===================  =====================================================
``HARNESS_PROGRESS``
``auto`` (padrão)    sink (se houver), senão stderr em terminal, e log
``log``              apenas o arquivo de log
``stderr``           log + stderr (ignora o sink)
``off``              não publica nada
===================  =====================================================
"""

import os
import sys
import time

MODE_ENV = "HARNESS_PROGRESS"
MODES = ("auto", "log", "stderr", "off")

_sink = None


def set_sink(callback) -> None:
    """Registra um callback ``(linha: str) -> None`` para o progresso."""
    global _sink
    _sink = callback


def clear_sink(callback=None) -> None:
    """Remove o sink; com ``callback``, só remove se ainda for o mesmo."""
    global _sink
    if callback is None or _sink == callback:
        _sink = None


def mode() -> str:
    value = (os.environ.get(MODE_ENV) or "auto").strip().lower()
    return value if value in MODES else "auto"


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_size(num_bytes: float) -> str:
    value = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


class Progress:
    """Progresso de uma tarefa, com atualização limitada por intervalo.

    ``total`` é o número de unidades (arquivos, bytes); ``unit`` só entra no
    texto (``arquivo(s)``, ``MB``).
    """

    def __init__(
        self,
        task: str,
        total: int = 0,
        log_path: str | None = None,
        interval: float = 2.0,
        unit: str = "arquivo(s)",
    ):
        self.task = task
        self.total = total
        self.log_path = log_path
        self.interval = interval
        self.unit = unit
        self.started = time.monotonic()
        self.current = 0
        self.bytes_read = 0
        self._last_emit = 0.0
        self._last_line = ""
        self._log_ready = False

    # ------------------------------------------------------------------
    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def start(self, message: str = "") -> None:
        text = message or f"{self.task}: iniciando"
        self._publish(f"[{self.task}] {text}")

    def update(
        self,
        current: int,
        total: int | None = None,
        note: str = "",
        force: bool = False,
    ) -> None:
        """Atualiza o progresso; só publica a cada ``interval`` segundos."""
        if total is not None:
            self.total = total
        self.current = current

        now = time.monotonic()
        finished = self.total and current >= self.total
        if not force and not finished and now - self._last_emit < self.interval:
            return
        self._last_emit = now

        self._publish(self._line(note))

    def log(self, message: str, force: bool = True) -> None:
        if not force and time.monotonic() - self._last_emit < self.interval:
            return
        self._publish(f"[{self.task}] {message}")

    def finish(self, message: str = "") -> None:
        elapsed = format_duration(self.elapsed())
        suffix = f" — {message}" if message else ""
        self._publish(f"[{self.task}] concluído em {elapsed}{suffix}")

    # ------------------------------------------------------------------
    def _line(self, note: str) -> str:
        elapsed = max(self.elapsed(), 0.001)
        parts = []

        if self.total:
            percent = 100.0 * self.current / self.total
            parts.append(f"{self.current}/{self.total} {self.unit} ({percent:.1f}%)")
        else:
            parts.append(f"{self.current} {self.unit}")

        if self.bytes_read:
            rate = self.bytes_read / elapsed
            parts.append(f"{format_size(self.bytes_read)} lidos")
            parts.append(f"{format_size(rate)}/s")

        if self.total and self.current < self.total:
            remaining = elapsed * (self.total - self.current) / max(self.current, 1)
            parts.append(f"ETA {format_duration(remaining)}")

        if note:
            parts.append(note)

        return f"[{self.task}] " + " — ".join(parts)

    def _publish(self, line: str) -> None:
        self._last_line = line
        current_mode = mode()
        if current_mode == "off":
            return

        self._write_log(line)

        if current_mode == "stderr":
            self._write_stderr(line, force=True)
            return

        if current_mode == "log":
            return

        if _sink is not None:
            try:
                _sink(line)
            except Exception:  # noqa: BLE001 - progresso nunca derruba a tarefa
                pass
            return

        self._write_stderr(line)

    def _write_stderr(self, line: str, force: bool = False) -> None:
        stream = sys.stderr
        try:
            if stream is None:
                return
            if not force and not stream.isatty():
                return
            print(line, file=stream, flush=True)
        except Exception:  # noqa: BLE001
            pass

    def _write_log(self, line: str) -> None:
        if not self.log_path:
            return
        try:
            if not self._log_ready:
                parent = os.path.dirname(os.path.abspath(self.log_path))
                os.makedirs(parent, exist_ok=True)
                self._log_ready = True
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(self.log_path, "a", encoding="utf-8") as handle:
                handle.write(f"{stamp} {line}\n")
        except OSError:
            self.log_path = None


def for_context(ctx, task: str, total: int = 0, unit: str = "arquivo(s)") -> Progress:
    """Cria um ``Progress`` gravando o log dentro do ``run_dir`` do contexto."""
    run_dir = getattr(ctx, "run_dir", None) or ""
    log_path = os.path.join(run_dir, "progress.log") if run_dir else None
    return Progress(task, total=total, log_path=log_path, unit=unit)
