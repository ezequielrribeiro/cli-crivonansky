from textual.app import App, ComposeResult
from textual.widgets import Static, Button, Input, Footer, RichLog
from textual.containers import Grid, Horizontal
from datetime import datetime
from rich.text import Text

from .services import TaskService
from .storage import load
from .domain import rebuild, TaskState


class TaskApp(App):

    CSS = """
    Screen {
        background: #1e1e1e;
    }

    #grid {
        layout: grid;
        grid-size: 2 5;
        grid-columns: 1fr 1fr;
        grid-rows: auto auto auto 1fr auto;
        padding: 1 2;
    }

    #title {
        column-span: 2;
        text-style: bold;
    }

    #status {
        column-span: 2;
    }

    #timer {
        column-span: 2;
        text-style: bold;
        content-align: center middle;
        height: 3;
        background: #2a2a2a;
        border: solid #444;
    }

    #history {
        column-span: 2;
        border: solid #3a3a3a;
        height: 100%;
    }

    #actions {
        column-span: 2;
        height: auto;
    }

    #actions Button {
        width: 1fr;
        margin: 1;
        height: 3;
    }
    """

    BINDINGS = [
        ("s", "start", "Start/Resume"),
        ("p", "pause", "Pause"),
        ("q", "stop", "Stop"),
    ]

    def __init__(self, codigo):
        super().__init__()
        self.codigo = codigo
        self.service = TaskService()
        self.input_widget = None
        self._input_callback = None

    # ========================
    # Layout
    # ========================
    def compose(self) -> ComposeResult:
        with Grid(id="grid"):
            yield Static(f"📌 Tarefa: {self.codigo}", id="title")
            yield Static("Status: ---", id="status")
            yield Static("00:00:00", id="timer")

            yield RichLog(id="history", wrap=True, highlight=True)

            with Horizontal(id="actions"):
                yield Button("▶ Start", id="start")
                yield Button("⏸ Pause", id="pause")
                yield Button("⏹ Stop", id="stop")

        yield Footer()

    # ========================
    # Lifecycle
    # ========================
    def on_mount(self):
        self.set_interval(1, self.refresh_ui)

    # ========================
    # Atualização UI
    # ========================
    def refresh_ui(self):
        data = load(self.codigo)
        state, total, last_start = rebuild(data["events"])

        if state == TaskState.RUNNING and last_start:
            total += datetime.now() - last_start

        seconds = int(total.total_seconds())
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60

        self.query_one("#timer", Static).update(f"{h:02}:{m:02}:{s:02}")
        self.query_one("#status", Static).update(self.format_status(state))

        self.update_buttons(state)
        self.update_history(data["events"])

    # ========================
    # Status com cor
    # ========================
    def format_status(self, state):
        if state == TaskState.RUNNING:
            return "[green]● RUNNING[/green]"
        elif state == TaskState.PAUSED:
            return "[yellow]● PAUSED[/yellow]"
        elif state == TaskState.FINISHED:
            return "[red]● FINISHED[/red]"
        else:
            return "[grey]● IDLE[/grey]"

    # ========================
    # Botões
    # ========================
    def update_buttons(self, state):
        self.query_one("#start", Button).disabled = state != TaskState.PAUSED
        self.query_one("#pause", Button).disabled = state != TaskState.RUNNING
        self.query_one("#stop", Button).disabled = state != TaskState.RUNNING

    # ========================
    # Histórico bonito
    # ========================
    def update_history(self, events):
        history = self.query_one("#history", RichLog)
        history.clear()

        for i, e in enumerate(events):
            ts = datetime.fromisoformat(e["at"]).strftime("%H:%M:%S")

            if e["type"] == "started":
                text = Text(f"{ts} ▶ started", style="green")

            elif e["type"] == "resumed":
                text = Text(f"{ts} ▶ resumed", style="cyan")

            elif e["type"] == "paused":
                text = Text(f"{ts} ⏸ pause | {e.get('note','')}", style="yellow")

            elif e["type"] == "stopped":
                text = Text(f"{ts} ⏹ stop | {e.get('note','')}", style="red")

            else:
                text = Text(f"{ts} {e}")

            # destaque da última ação
            if i == len(events) - 1:
                text.stylize("bold")

            history.write(text)

    # ========================
    # Ações
    # ========================
    async def on_button_pressed(self, event: Button.Pressed):
        await self.handle_action(event.button.id)

    async def action_start(self):
        await self.handle_action("start")

    async def action_pause(self):
        await self.handle_action("pause")

    async def action_stop(self):
        await self.handle_action("stop")

    async def handle_action(self, action):
        state, _, _ = rebuild(load(self.codigo)["events"])

        if action == "start" and state == TaskState.PAUSED:
            self.service.resume(self.codigo)

        elif action == "pause" and state == TaskState.RUNNING:
            await self.ask_input("Motivo da pausa", self._pause)

        elif action == "stop" and state == TaskState.RUNNING:
            await self.ask_input("Resumo final", self._stop)

    # ========================
    # Input (modal simples)
    # ========================
    async def ask_input(self, placeholder, callback):
        self.input_widget = Input(placeholder=placeholder)
        await self.mount(self.input_widget)
        self.input_widget.focus()
        self._input_callback = callback

    async def on_input_submitted(self, event: Input.Submitted):
        value = event.value

        if self.input_widget != None:
            await self.input_widget.remove()
            self.input_widget = None

        if self._input_callback:
            await self._input_callback(value)

    async def _pause(self, note):
        self.service.pause(self.codigo, note)

    async def _stop(self, note):
        self.service.stop(self.codigo, note)
        self.exit()


def run_app(codigo):
    TaskApp(codigo).run()