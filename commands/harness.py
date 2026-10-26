"""Comando /harness — ponto de entrada do harness de desenvolvimento assistido."""

import json
import sys

import yaml

from core.command import Command

from .complements.harness.catalog import all_tasks, get_task, load_tasks
from .complements.harness.engine import HarnessEngine
from .complements.harness.types import TaskContext


class HarnessCommand(Command):
    name = "harness"
    description = "Executa o harness de desenvolvimento assistido"
    help_text = """Uso:
  /harness exec --clip | --file F | --stdin [--yes] [--dry-run]
  /harness run <task> [--param k=v ...] [--yes] [--dry-run]
  /harness ask "<pergunta>" [--context rag,code,db]
  /harness prompt
  /harness tasks
  /harness runs [--last N]
  /harness hooks install|uninstall|status
  /harness env:check
  (opção global: --config CAMINHO)"""

    # ------------------------------------------------------------------
    def execute(self, args):
        args = list(args)
        load_tasks()

        config_path = None
        if "--config" in args:
            index = args.index("--config")
            if index + 1 < len(args):
                config_path = args[index + 1]
                del args[index : index + 2]

        sub = args[0] if args else "help"
        rest = args[1:]

        if sub in ("help", "--help", "-h"):
            print(self.get_usage())
            return True, {"help": True}

        if sub == "tasks":
            specs = all_tasks()
            for spec in specs:
                print(f"{spec.name:<14} [{spec.intent:<5}] {spec.description}")
            return True, {"count": len(specs)}

        try:
            if sub == "exec":
                return self._exec(config_path, rest)
            if sub == "run":
                return self._run(config_path, rest)
            if sub == "ask":
                return self._ask(config_path, rest)
            if sub == "prompt":
                return self._single(config_path, "prompt", {})
            if sub == "runs":
                return self._runs(config_path, rest)
            if sub == "hooks":
                return self._hooks(config_path, rest)
            if sub == "env:check":
                return self._single(config_path, "env:check", {})
        except Exception as exc:  # noqa: BLE001
            print(f"[harness] erro: {exc}")
            return False, {"error": str(exc)}

        print(f"[harness] subcomando desconhecido: {sub}")
        print(self.get_usage())
        return False, {"error": "subcomando desconhecido"}

    # ------------------------------------------------------------------
    def _exec(self, config_path, args):
        yes = "--yes" in args
        dry_run = "--dry-run" in args

        source = "clip"
        path = None
        if "--file" in args:
            index = args.index("--file")
            if index + 1 < len(args):
                path = args[index + 1]
            source = "file"
        elif "--stdin" in args:
            source = "stdin"

        text = self._read_source(source, path)
        engine = HarnessEngine(config_path=config_path, interactive=True, yes=yes, dry_run=dry_run)
        results, error = engine.handle_text(text, yes_allowed=False)

        if error:
            print(f"[harness] {error}")
            return False, {"error": error}

        statuses = [item["status"] for item in results]
        ok = all(status == "success" for status in statuses)
        return ok, {"count": len(results), "statuses": statuses}

    def _run(self, config_path, args):
        task, params, flags = self._parse_run_args(args)
        if not task:
            print("[harness] informe a tarefa")
            return False, {"error": "tarefa ausente"}

        return self._single(
            config_path,
            task,
            params,
            yes_allowed=True,
            yes=flags["yes"],
            dry_run=flags["dry_run"],
        )

    def _single(
        self,
        config_path,
        task,
        params,
        yes_allowed=True,
        yes=False,
        dry_run=False,
    ):
        engine = HarnessEngine(
            config_path=config_path,
            interactive=True,
            yes=yes,
            dry_run=dry_run,
        )
        block = {"harness": 1, "task": task, "params": params or {}}
        raw = yaml.safe_dump(block, allow_unicode=True, sort_keys=False)
        _text, status = engine.handle_block(raw, yes_allowed=yes_allowed)
        return status == "success", {"status": status}

    def _ask(self, config_path, args):
        context = "rag,code"
        question_parts = []
        index = 0
        while index < len(args):
            if args[index] == "--context" and index + 1 < len(args):
                context = args[index + 1]
                index += 2
            else:
                question_parts.append(args[index])
                index += 1

        question = " ".join(question_parts).strip()
        if not question:
            print("[harness] informe a pergunta")
            return False, {"error": "pergunta ausente"}

        engine = HarnessEngine(config_path=config_path, interactive=True)
        ctx = TaskContext(
            config=engine.config,
            workspace=engine.workspace,
            run_dir=engine.workspace,
        )

        parts = [f"Pergunta: {question}", ""]

        if "rag" in context:
            spec = get_task("rag:search")
            if spec is not None:
                result = spec.handler(ctx, {"query": question, "top_k": 5})
                parts.extend(["## Contexto do RAG", "", result.details or result.summary, ""])

        if "code" in context:
            spec = get_task("code:query")
            if spec is not None:
                result = spec.handler(ctx, {"q": question})
                parts.extend(["## Contexto do código", "", result.details or result.summary, ""])

        prompt = "\n".join(parts)

        copied = False
        try:
            import pyperclip

            pyperclip.copy(prompt)
            copied = True
        except Exception:  # noqa: BLE001
            copied = False

        print(prompt)
        return True, {"copied": copied}

    def _hooks(self, config_path, args):
        from .complements.harness import hooks

        action = args[0] if args else "status"
        engine = HarnessEngine(config_path=config_path, interactive=False)

        if action == "install":
            installed = hooks.install(engine.config)
            print(f"hooks instalados: {', '.join(installed)}")
            return True, {"installed": installed}

        if action == "uninstall":
            removed = hooks.uninstall(engine.config)
            print(f"hooks removidos: {', '.join(removed) if removed else 'nenhum'}")
            return True, {"removed": removed}

        if action == "status":
            state = hooks.status(engine.config)
            for name in ("post-commit", "post-merge"):
                print(f"{name}: {'instalado' if state.get(name) else 'ausente'}")
            print(f"log: {state['log']}")
            return True, state

        print(f"[harness] acao de hooks desconhecida: {action}")
        return False, {"error": "acao desconhecida"}

    def _runs(self, config_path, args):
        count = 10
        if "--last" in args:
            index = args.index("--last")
            if index + 1 < len(args):
                try:
                    count = int(args[index + 1])
                except ValueError:
                    count = 10

        engine = HarnessEngine(config_path=config_path, interactive=True)
        records = engine.runs.last(count)
        for record in records:
            print(
                f"{record.get('id')}  {record.get('task'):<12} "
                f"{record.get('status'):<8} {record.get('duration_ms')}ms"
            )
        return True, {"count": len(records)}

    # ------------------------------------------------------------------
    def _read_source(self, source: str, path: str | None) -> str:
        if source == "file":
            if not path:
                raise ValueError("informe o caminho com --file")
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()

        if source == "stdin":
            return sys.stdin.read()

        import pyperclip

        return pyperclip.paste()

    def _parse_run_args(self, args):
        task = None
        params = {}
        flags = {"yes": False, "dry_run": False}

        index = 0
        while index < len(args):
            item = args[index]

            if item == "--yes":
                flags["yes"] = True
            elif item == "--dry-run":
                flags["dry_run"] = True
            elif item == "--param":
                index += 1
                if index < len(args):
                    key, _, value = args[index].partition("=")
                    params[key] = value
            elif item.startswith("--"):
                key = item[2:]
                if index + 1 < len(args) and not args[index + 1].startswith("--"):
                    params[key] = args[index + 1]
                    index += 1
                else:
                    params[key] = True
            elif task is None:
                task = item

            index += 1

        return task, params, flags
