import os
from pathlib import Path

from core.command import Command
from core.run.loader import load_runfile
from core.run.api import get_registry


class RunCommand(Command):
    name = "run"
    description = "Executa o sistema de tasks"
    help_text = (
        "Uso: /run [--tasks]\n"
        "     /run run <taskname>\n"
        "     /run watch <taskname>\n"
        "     /run init"
    )

    def execute(self, args):
        executor = self.context.executor if hasattr(self.context, 'executor') else None

        if not args:
            return self._list_tasks(executor)

        subcommand = args[0].lower()

        if subcommand in ("--tasks", "list"):
            return self._list_tasks(executor)
        elif subcommand == "run":
            task_name = args[1] if len(args) > 1 else "default"
            return self._run_task(executor, task_name)
        elif subcommand == "watch":
            task_name = args[1] if len(args) > 1 else "default"
            return self._run_watch(executor, task_name)
        elif subcommand == "init":
            return self._init_runfile()
        else:
            print(f"[red]Subcomando desconhecido: {subcommand}[/red]")
            print()
            print(self.help_text)
            return False, {"error": f"subcomando desconhecido: {subcommand}"}

    def _list_tasks(self, executor):
        loaded = load_runfile(executor)
        if not loaded:
            print("[yellow]Nenhum runfile.py encontrado[/yellow]")
            print("Crie um com: /run init")
            return False, {"error": "runfile não encontrado"}

        registry = get_registry()
        tasks = registry.all()

        if not tasks:
            print("[yellow]Nenhuma task registrada no runfile.py[/yellow]")
            return True, {"tasks": []}

        print("[green]Tasks disponiveis:[/green]")
        for name, task_def in sorted(tasks.items()):
            desc = f" — {task_def.description}" if task_def.description else ""
            deps = f" [deps: {', '.join(task_def.deps)}]" if task_def.deps else ""
            print(f"  {name}{deps}{desc}")

        return True, {"tasks": sorted(tasks.keys())}

    def _run_task(self, executor, task_name):
        loaded = load_runfile(executor)
        if not loaded:
            print("[red]Arquivo runfile.py nao encontrado[/red]")
            print("Crie um com: /run init")
            return False, {"error": "runfile não encontrado"}

        registry = get_registry()
        task_def = registry.get(task_name)

        if task_def is None:
            print(f"[red]Task '{task_name}' nao encontrada[/red]")
            print()
            self._list_tasks(executor)
            return False, {"error": f"task '{task_name}' não encontrada"}

        print(f"[cyan]Executando task:[/cyan] {task_name}")
        try:
            task_def.run(registry)
            return True, {"task": task_name}
        except Exception as e:
            print(f"[red]Erro na task '{task_name}': {e}[/red]")
            return False, {"task": task_name, "error": str(e)}

    def _run_watch(self, executor, task_name):
        loaded = load_runfile(executor)
        if not loaded:
            print("[red]Arquivo runfile.py nao encontrado[/red]")
            print("Crie um com: /run init")
            return False, {"error": "runfile não encontrado"}

        registry = get_registry()
        task_def = registry.get(task_name)

        if task_def is None:
            print(f"[red]Task '{task_name}' nao encontrada[/red]")
            return False, {"error": f"task '{task_name}' não encontrada"}

        print(f"[cyan]Executando task com watch:[/cyan] {task_name}")
        try:
            task_def.run(registry)
            return True, {"task": task_name, "watch": True}
        except Exception as e:
            print(f"[red]Erro na task '{task_name}': {e}[/red]")
            return False, {"task": task_name, "error": str(e)}

    def _init_runfile(self):
        path = Path.cwd() / "runfile.py"
        if path.exists():
            print(f"[red]runfile.py ja existe em {path}[/red]")
            return False, {"error": "runfile.py já existe", "path": str(path)}

        content = '''from core.run import task, src, dest, series, parallel, watch, cmd


@task
def clean():
    """Remove artefatos de build"""
    import shutil
    for d in ["dist", "build"]:
        shutil.rmtree(d, ignore_errors=True)


@task
def build():
    """Compila arquivos para dist"""
    return src("src/**/*").pipe(dest("dist"))


@task(deps=["clean"])
def rebuild():
    """Clean + build em sequencia"""
    return series(clean, build)


@task
def dev():
    """Watch mode"""
    watch("src/**/*", build)


@task
def up():
    """Sobe ambiente via CLI"""
    cmd("/environment start dev")


@task
def down():
    """Desce ambiente via CLI"""
    cmd("/environment stop dev")


@task
def default():
    """Task padrao (executada com /run run)"""
    build()
'''

        try:
            path.write_text(content, encoding="utf-8")
            print(f"[green]runfile.py criado em {path}[/green]")
            return True, {"path": str(path)}
        except Exception as e:
            print(f"[red]Erro ao criar runfile.py: {e}[/red]")
            return False, {"error": str(e)}
