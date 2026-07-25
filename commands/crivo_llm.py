import os
import subprocess
import tempfile
from core.command import Command
from commands.complements.crivo_llm_plugin.config import load_config
from commands.complements.crivo_llm_plugin.indexer import (
    index_files,
    index_directory,
    list_indexed,
)
from commands.complements.crivo_llm_plugin.retriever import search


class CrivoLlmCommand(Command):
    name = "crivo-llm"
    description = (
        "Gera prompts com contexto de uma RAG local "
        "(multiplas bases de conhecimento)"
    )
    help_text = (
        "Uso: /crivo-llm prompt --context <texto> [--kb <base>] [--top-k <n>]\n"
        "     /crivo-llm add --file <caminho> [--kb <base>]\n"
        "     /crivo-llm add-dir <diretorio> [--kb <base>]\n"
        "     /crivo-llm search --query <texto> [--kb <base>] [--top-k <n>]\n"
        "     /crivo-llm list [--kb <base>]\n"
        "     /crivo-llm kbs"
    )

    def execute(self, args):
        subcommand = args[0] if args and not args[0].startswith("--") else "prompt"

        config = load_config()

        if subcommand == "prompt":
            self._prompt(args, config)
        elif subcommand == "add":
            self._add(args, config)
        elif subcommand == "add-dir":
            self._add_dir(args, config)
        elif subcommand == "search":
            self._search(args, config)
        elif subcommand == "list":
            self._list(args, config)
        elif subcommand == "kbs":
            self._kbs(config)
        else:
            print(f"[red]Subcomando desconhecido: {subcommand}[/red]")
            print(self.get_usage())

    def _get_kb(self, args, config):
        parsed = self.parse_args(args)
        kb_name = parsed.get("kb")
        kb = config.get_kb(kb_name) if kb_name else config.get_kb()
        if kb is None:
            names = config.list_kbs()
            if names:
                print(f"[yellow]Bases disponiveis: {', '.join(names)}[/yellow]")
        return kb

    def _prompt(self, args, config):
        parsed = self.parse_args(args)
        context = parsed.get("context")
        top_k = int(parsed.get("top-k", config.default_top_k))

        if not context:
            print("[red]Informe o contexto com --context <texto>[/red]")
            return

        kb = self._get_kb(args, config)
        if kb is None:
            return

        results = search(context, kb, top_k=top_k)

        if not results:
            print("[red]Nenhum resultado encontrado na RAG.[/red]")
            return

        prompt_parts = []
        prompt_parts.append(
            f"--- CONTEXTO (base: {kb.name}) ---"
        )
        for i, r in enumerate(results, 1):
            source_short = (
                os.path.relpath(r["source"])
                if os.path.exists(r["source"])
                else r["source"]
            )
            prompt_parts.append(f"\n[Fonte {i}: {source_short}]")
            prompt_parts.append(r["text"])

        prompt_parts.append("\n--- SUA PERGUNTA ---")
        prompt_parts.append(context)

        prompt_parts.append("\n--- INSTRUCAO ---")
        prompt_parts.append("Responda com base no contexto acima.")

        prompt = "\n".join(prompt_parts)

        print("\n" + prompt + "\n")

        self._copy_to_clipboard(prompt)
        print(
            "[green]Prompt copiado para a area de transferencia![/green]"
        )

    def _add(self, args, config):
        parsed = self.parse_args(args)
        file_path = parsed.get("file")

        if not file_path:
            print("[red]Informe o arquivo com --file <caminho>[/red]")
            return

        kb = self._get_kb(args, config)
        if kb is None:
            return

        index_files([file_path], kb)

    def _add_dir(self, args, config):
        dir_path = args[1] if len(args) > 1 and not args[1].startswith("--") else None

        if not dir_path:
            print("[red]Informe o diretorio para indexar[/red]")
            return

        kb = self._get_kb(args, config)
        if kb is None:
            return

        index_directory(dir_path, kb)

    def _search(self, args, config):
        parsed = self.parse_args(args)
        query = parsed.get("query")
        top_k = int(parsed.get("top-k", config.default_top_k))

        if not query:
            print("[red]Informe a consulta com --query <texto>[/red]")
            return

        kb = self._get_kb(args, config)
        if kb is None:
            return

        results = search(query, kb, top_k=top_k)

        if not results:
            return

        print(
            f"\n[bold]Top {len(results)} resultados "
            f"(base: {kb.name}) para:[/bold] {query}\n"
        )
        for i, r in enumerate(results, 1):
            source_short = (
                os.path.relpath(r["source"])
                if os.path.exists(r["source"])
                else r["source"]
            )
            print(
                f"[bold]{i}.[/bold] "
                f"[cyan]({r['score']:.4f})[/cyan] {source_short}"
            )
            if len(r["text"]) > 200:
                print(f"   {r['text'][:200]}...")
            else:
                print(f"   {r['text']}")
            print()

    def _list(self, args, config):
        kb = self._get_kb(args, config)
        if kb is None:
            return

        chunks = list_indexed(kb)
        if not chunks:
            print(
                f"[yellow]Base '{kb.name}' vazia. "
                "Nenhum documento indexado.[/yellow]"
            )
            return

        sources = {}
        for c in chunks:
            src = c["source"]
            if src not in sources:
                sources[src] = 0
            sources[src] += 1

        print(
            f"\n[bold]Base '{kb.name}' — "
            f"{len(chunks)} chunks no total:[/bold]\n"
        )
        for src, count in sorted(sources.items()):
            print(f"  {src} ({count} chunks)")

    def _kbs(self, config):
        names = config.list_kbs()
        if not names:
            print("[yellow]Nenhuma base de conhecimento configurada.[/yellow]")
            return

        print("\n[bold]Bases de conhecimento disponiveis:[/bold]\n")
        for name in names:
            kb = config.get_kb(name)
            if kb is None:
                continue
            dirs = ", ".join(kb.document_dirs)
            print(f"  [bold]{name}[/bold]")
            print(f"    Diretorios: {dirs}")
            print(f"    Indice: {kb.index_dir}")
            print()

    def _copy_to_clipboard(self, text: str):
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(suffix=".txt", text=True)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(text)
            safe = tmp.replace("'", "''")
            subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    f"Get-Content -LiteralPath '{safe}' -Raw -Encoding UTF8 | Set-Clipboard",
                ],
                check=True,
            )
        except Exception:
            print(
                "[yellow]Nao foi possivel copiar para o clipboard.[/yellow]"
            )
        finally:
            if tmp and os.path.exists(tmp):
                os.unlink(tmp)
