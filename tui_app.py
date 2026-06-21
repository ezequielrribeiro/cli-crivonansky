from textual.app import App, ComposeResult
from textual.widgets import Input, RichLog, Label, ListView, ListItem
from textual.containers import Container


class MyCLIApp(App):
    TITLE = "CLI Crivonansky"

    CSS = """
    Screen {
        layout: vertical;
    }

    #header {
        layout: horizontal;
        height: 4;
        background: $primary;
        color: $text;
        padding: 0 1;
        align: center middle;
    }

    #pixel-art {
        layout: vertical;
        width: auto;
        margin-right: 1;
    }

    #pixel-art Label {
        height: 1;
        text-style: bold;
    }

    #app-title {
        content-align: center middle;
        text-style: bold;
        width: 1fr;
    }

    #output {
        width: 100%;
        height: 1fr;
        border: solid $primary;
    }

    #input-container {
        layout: horizontal;
        height: 3;
        background: $panel;
        border-top: solid $primary;
    }

    #prompt {
        width: 3;
        content-align: center middle;
        background: $panel;
        color: $primary;
        text-style: bold;
    }

    #input {
        width: 1fr;
        background: transparent;
        border: none;
        padding: 0 1;
    }

    #command-dropdown {
        display: none;
        height: auto;
        max-height: 12;
        min-width: 30;
        border: solid $primary;
        background: $panel;
        margin: 0 0 0 3;
    }

    #command-dropdown ListItem {
        padding: 0 1;
    }

    #command-dropdown ListItem.--highlight {
        background: $accent;
        color: $text;
        text-style: bold;
    }

    #status-bar {
        height: 1;
        background: $primary;
        color: $text;
    }

    #status-text {
        width: 100%;
        padding: 0 1;
    }
    """

    def __init__(self, executor):
        super().__init__()
        self.executor = executor

    def compose(self) -> ComposeResult:
        yield Container(
            Container(
                Label("    O    "),
                Label("🚬 /|\\ "),
                Label("   / \\   "),
                id="pixel-art"
            ),
            Label("CLI Crivonansky", id="app-title"),
            id="header"
        )
        yield RichLog(id="output", highlight=True, markup=True)
        yield Container(
            Label("❯", id="prompt"),
            Input(placeholder="", id="input"),
            id="input-container"
        )
        yield ListView(id="command-dropdown")
        yield Container(
            Label(" /help • /clear • /quit", id="status-text"),
            id="status-bar"
        )

    def on_mount(self):
        self.output = self.query_one("#output", RichLog)
        self.input = self.query_one("#input", Input)
        self.dropdown = self.query_one("#command-dropdown", ListView)
        self.dropdown.display = False
        self.command_history: list[str] = []
        self.history_index: int = -1

    def on_key(self, event) -> None:
        if self.dropdown.display:
            if event.key == "down":
                event.stop()
                self._dropdown_next()
            elif event.key == "up":
                event.stop()
                self._dropdown_prev()
            elif event.key == "escape":
                event.stop()
                self._hide_dropdown()
            return

        if event.key == "up":
            event.stop()
            self._history_prev()
        elif event.key == "down":
            event.stop()
            self._history_next()

    def on_input_changed(self, event: Input.Changed) -> None:
        value = event.value.strip()
        if value.startswith("/"):
            self._show_dropdown(value)
        else:
            self.dropdown.display = False

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if not self.dropdown.display:
            return
        label_widget = event.item.query_one(Label)
        command_name = str(label_widget.render()).strip()
        self.input.value = command_name
        self.input.cursor_position = len(command_name)
        self._hide_dropdown()
        self.input.focus()

    def _show_dropdown(self, prefix: str):
        all_cmds = list(self.executor.registry.all().keys())
        all_cmds.extend(["/clear", "/quit"])
        matching = sorted(set(c for c in all_cmds if c.startswith(prefix)))
        self.dropdown.clear()
        for cmd in matching:
            self.dropdown.append(ListItem(Label(cmd)))
        self.dropdown.display = bool(matching)
        if matching:
            self.dropdown.index = 0

    def _dropdown_next(self):
        if not self.dropdown.children:
            return
        idx = self.dropdown.index or 0
        self.dropdown.index = min(idx + 1, len(self.dropdown.children) - 1)

    def _dropdown_prev(self):
        if not self.dropdown.children:
            return
        idx = self.dropdown.index or 0
        self.dropdown.index = max(idx - 1, 0)

    def _hide_dropdown(self):
        self.dropdown.display = False

    def _history_prev(self):
        if not self.command_history:
            return
        if self.history_index == -1:
            self.history_index = len(self.command_history) - 1
        elif self.history_index > 0:
            self.history_index -= 1
        self.input.value = self.command_history[self.history_index]
        self.input.cursor_position = len(self.input.value)

    def _history_next(self):
        if not self.command_history or self.history_index == -1:
            return
        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self.input.value = self.command_history[self.history_index]
            self.input.cursor_position = len(self.input.value)
        else:
            self.history_index = -1
            self.input.value = ""

    async def on_input_submitted(self, event: Input.Submitted):
        command = event.value.strip()

        if not command:
            return

        if self.dropdown.display and self.dropdown.children:
            child = self.dropdown.highlighted_child
            if child is not None:
                label = child.query_one(Label)
                name = str(label.render()).strip()
                self.input.value = name
                self.input.cursor_position = len(name)
            self._hide_dropdown()
            self.input.focus()
            return

        if command == "/clear":
            self.output.clear()
            self.input.value = ""
            return

        if command == "/quit":
            self.exit()
            return

        if command not in ("/clear", "/quit"):
            if not self.command_history or self.command_history[-1] != command:
                self.command_history.append(command)
        self.history_index = -1

        self.output.write(f"[cyan]> {command}[/cyan]")

        # executa
        result = self.executor.execute(command)

        if result:
            self.output.write(result)

        # limpa input
        self.input.value = ""


