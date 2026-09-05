import subprocess
import shlex
from core.command import Command
from commands.complements.task_plugin.services import TaskService
from commands.complements.task_plugin.domain import TaskState


class TaskCommand(Command):
    name = "task"
    description = "Executa a ferramenta de controle de tarefas em uma nova janela"
    help_text = ("Uso: /task start <codigo>\n"
                 "     /task resume <codigo>\n"
                 "     /task report <codigo>\n"
                 "     /task list")

    def execute(self, args):
        """
        Exemplo de uso:
        task start ABC123
        task resume ABC123
        task report ABC123
        task list
        """

        if (not args or (args[0] not in ['start', 'resume', 'report', 'list'])
             or (args[0] != 'list' and len(args) < 2)):
            print("Uso: task <start|resume|report|list> <codigo>")
            return False, {"error": "uso incompleto"}

        if args[0] == "list":
            service = TaskService()
            tasks = service.list_all()

            if not tasks:
                print("Nenhuma task cadastrada.")
                return True, {"tasks": []}

            print("📋 TASKS CADASTRADAS\n")
            for t in tasks:
                status = self._format_status(t["status"])
                print(f"  • {t['codigo']}    {status}    {self._fmt(t['total'])}")

            return True, {"tasks": tasks}
        elif args[0] == "report":
            codigo = args[1] if len(args) > 1 else None
            if not codigo:
                print("Informe o código da task")
                return False, {"error": "código não informado"}
            service = TaskService()

            report = service.report(codigo)
            self._print_report(report)
            return True, {"report": report}
        else:
            # Monta comando da tool
            cmd = ["py -m ", "commands.complements.task_plugin.cli"] + args

            # Monta comando PowerShell
            ps_command = f"(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& .venv\\Scripts\\Activate.ps1);" + " ".join(cmd)

            # Abre nova janela do PowerShell
            if not self._run_in_powershell(ps_command, width=70, height=20):
                return False, {"error": "falha ao abrir o PowerShell"}
            print("Task iniciada em nova janela.")
            return True, {"action": args[0], "code": args[1], "opened": True}

    def _run_in_powershell(self, command: str, width: int | None = None, height: int | None = None):
        """
        Executa um comando em uma nova janela do PowerShell, opcionalmente configurando tamanho.

        :param command: Comando a ser executado
        :param width: Largura da janela (colunas)
        :param height: Altura da janela (linhas)
        """

        try:
            # Monta comando de resize apenas se parâmetros forem informados
            resize_cmd = ""
            if width and height:
                resize_cmd = (
                    f"$size = New-Object System.Management.Automation.Host.Size({width},{height}); "
                    "$host.UI.RawUI.WindowSize = $size; "
                    "$host.UI.RawUI.BufferSize = $size; "
                )

            full_command = resize_cmd + command

            ps_command = f'start powershell -NoExit -Command "{full_command}"'

            subprocess.Popen(ps_command, shell=True)
            return True

        except Exception as e:
            print(f"[ERRO] Falha ao executar comando: {e}")
            return False

    def _fmt(self, td):
        s = int(td.total_seconds())
        return f"{s//3600:02}:{(s%3600)//60:02}:{s%60:02}"

    def _format_status(self, state):
        if state == TaskState.RUNNING:
            return "▶ running"
        elif state == TaskState.PAUSED:
            return "⏸ paused"
        elif state == TaskState.FINISHED:
            return "✔ finished"
        else:
            return "○ idle"

    def _print_report(self, report):
        def fmt(td):
            s = int(td.total_seconds())
            return f"{s//3600:02}:{(s%3600)//60:02}:{s%60:02}"

        print("\n📊 RELATÓRIO\n")

        print(f"⏱ Total: {fmt(report['total_time'])}")
        print(f"📦 Sessões: {report['session_count']}")
        print(f"⏸ Pausas: {report['pause_count']}")

        print("\n📈 Sessões:")
        for i, s in enumerate(report["sessions"], 1):
            print(f"  {i}. {fmt(s)}")

        print("\n📝 Pausas:")
        for p in report["pauses"]:
            print(f"  - {p['at']} → {p.get('note','')}")
