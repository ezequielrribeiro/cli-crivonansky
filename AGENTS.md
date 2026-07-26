# AGENTS.md — Crivonansky CLI

## Entrypoint & Run

- Entry: `crivonansky.py` — bootstraps registry, context, loader, executor, then launches TUI.
- Run: `python crivonansky.py` (or `.\run.ps1` which activates `.venv` first).
- Dependencies: `pip install -r requirements.txt` (Python 3.10+).

## Architecture

- **`core/`** — framework: `Command` (ABC), `CommandRegistry`, `CLIContext`, `CommandParser` (uses `shlex`), `CommandExecutor` (captures stdout via `io.StringIO`), `load_commands` (dynamic import via `importlib`).
- **`core/run/`** — task runner subsystem (gulp.js-style). `task`, `src`, `dest`, `series`, `parallel`, `watch`, `cmd`. Loads `runfile.py` dynamically. See dedicated section below.
- **`commands/`** — plugins auto-discovered by `loader.py`. Any `.py` file with a class inheriting `Command` is loaded.
- **`commands/complements/`** — internal dependencies of plugins (not auto-discovered). Sub-packages: `task_plugin/`, `db_tools_plugin/`, `load_app_plugin/` (includes `VirtualDesktop11.exe` binary).
- **TUI** (`tui_app.py`) — Textual app. Built-in commands `/clear` and `/quit` are handled in TUI, not as plugins. Dropdown on `/` key, history with `↑`/`↓`.
- **Config files** (root JSON): `environment_conf.json`, `workspace_conf.json`, `metrics_report_conf.json` — read by specific plugins.

## Commands

| Command | File | Notes |
|---|---|---|
| `/help` | `commands/help.py` | Lists all registered commands |
| `/task` | `commands/task.py` | Opens new PowerShell window. Subcommands: `start`, `resume`, `report`. Uses `commands/complements/task_plugin/` |
| `/environment` | `commands/environment.py` | Docker compose management. Reads `environment_conf.json` |
| `/metrics-report` | `commands/metrics_report.py` | Trimester metrics. Reads `metrics_report_conf.json`. Uses `commands/complements/work_analysis.py` |
| `/load-app` | `commands/load_app.py` | Launch apps & move to virtual desktops. Reads `workspace_conf.json`. Uses `commands/complements/load_app_plugin/VirtualDesktop11.exe` |
| `/db-tools` | `commands/db_tools.py` | MySQL dump optimizer/installer. Uses `commands/complements/db_tools_plugin/` |
| `/container-terminal` | `commands/container_terminal.py` | Opens PowerShell terminal in a Docker container |
| `/convert-site` | `commands/convert_site.py` | Scrapes a URL to Markdown via `requests` + `BeautifulSoup` |
| `/site-capture` | `commands/site_capture.py` | Opens a controlled Chrome (Selenium) session, captures current page as Markdown |
| `/generate-plugin` | `commands/generate_plugin.py` | Scaffolds a new command plugin |
| `/run` | `commands/run_command.py` | Task runner (gulp.js-style). Subcommands: `run <task>`, `--tasks`, `watch <task>`, `init`. Loads tasks from `runfile.py` via `core/run/` |

## Task Runner (`core/run/`)

A gulp.js-inspired task runner. Define tasks in `runfile.py` (project root) using the `core.run` API:

```python
from core.run import task, src, dest, series, parallel, watch, cmd

@task
def build():
    return src("src/**/*").pipe(dest("dist"))

@task(deps=["clean"])
def rebuild():
    return series(clean, build)
```

### API

| Function | Description |
|---|---|
| `task(name?, deps?)` | Decorator — registers a function as a task |
| `src(patterns, base?)` | Returns `PipeStream` — glob file matching |
| `dest(directory)` | Returns a transform — writes `VinylFile` to disk |
| `series(...tasks)` | Composite — runs tasks sequentially |
| `parallel(...tasks)` | Composite — runs tasks concurrently |
| `watch(patterns, ...tasks, debounce=200)` | Watches files, runs tasks on change |
| `cmd(command_line)` | Runs a registered CLI command (e.g., `cmd("/environment start dev")`) |

### Modules in `core/run/`

| File | Contents |
|---|---|
| `vinyl.py` | `VinylFile` — virtual file (path, relative, base, contents, cwd) |
| `task_registry.py` | `TaskRegistry` — stores task name → `TaskDefinition` |
| `task.py` | `TaskDefinition` — name, fn, deps, run() |
| `series_parallel.py` | `Composite`, `series()`, `parallel()` |
| `pipeline.py` | `PipeStream` — `.pipe()`, `.dest()`, `.through()` |
| `src.py` | `src()` — glob → generator of `VinylFile` |
| `dest.py` | `dest()` — writes files to disk |
| `transforms.py` | Built-in transforms: `rename`, `replace`, `filter`, `through` |
| `api.py` | Public user-facing API (`task`, `src`, `dest`, etc.) |
| `watcher.py` | Watch mode (watchdog) |
| `loader.py` | `load_runfile()` — dynamic import of `runfile.py` |

### /run command

| Subcommand | Description |
|---|---|
| `/run init` | Scaffolds a `runfile.py` with examples |
| `/run --tasks` or `list` | Lists all registered tasks |
| `/run run <taskname>` | Executes a task (default: `default`) |
| `/run watch <taskname>` | Runs the task then watches for changes |

### Execution model

- `TaskDefinition.run()` resolves deps first, then executes the function.
- If the function returns a `Composite` (from `series`/`parallel`), it is executed.
- `series()` runs tasks sequentially; if one fails, the rest are aborted.
- `parallel()` runs tasks in threads via `threading.Thread`.
- `cmd()` calls `CommandExecutor.execute()` internally, bridging CLI commands as tasks.

## Key conventions

- **Plugin naming**: kebab-case for command name (`name = "my-command"`), snake_case for filename (`my_command.py`), PascalCase + `Command` suffix for class (`MyCommandCommand`).
- **Plugin discovery**: any `.py` in `commands/` with a class inheriting `Command` (not `Command` itself) is auto-loaded. Subdirs like `commands/complements/` are NOT auto-discovered.
- **Config files**: root JSON files (`environment_conf.json`, `workspace_conf.json`, `metrics_report_conf.json`) are read by specific plugins. No shared config loader.
- **`--help` / `-h`**: intercepted by `CommandExecutor` before `execute()` is called. Plugins override `help_text` class attribute to customize.
- **`parse_args`**: built into `Command` base class. Handles `--flag value` and `--bool-flag`. Does NOT use `shlex` (the parser in `core/parser.py` uses `shlex` for the command line, but `Command.parse_args` does not).
- **Output**: commands use `print()` — stdout is captured by `CommandExecutor` via `io.StringIO` and displayed in the TUI's `RichLog`.
- **Error display**: use `print("[red]...[/red]")` — Rich markup is rendered by the TUI.

## Windows-specific

- **PowerShell spawning**: several commands open new PowerShell windows via `start powershell -NoExit -Command "..."`. The `task` command also activates the venv before running.
- **Virtual desktops**: `load-app` uses `commands/complements/load_app_plugin/VirtualDesktop11.exe` (binary committed) to move windows between desktops.
- **Docker**: `environment` and `container-terminal` commands assume Docker is available.

## Testing

- No test framework is set up. No test files exist.
- Validation is manual: `python crivonansky.py` then type commands.
- Syntax check: `.venv\Scripts\python.exe -m py_compile <file>`.

## Config files (root)

| File | Used by |
|---|---|
| `environment_conf.json` | `/environment` — Docker compose paths |
| `workspace_conf.json` | `/load-app --workspace` — app launch configs |
| `metrics_report_conf.json` | `/metrics-report` — metrics file path |
