from core.command import Command
import subprocess
import os
import shutil


class DbtoolsCommand(Command):
    name = "db-tools"
    description = "Utilitário de banco de dados padrão SGG"
    help_text = (
        "Uso: /db-tools --optimize <dump.sql>\n"
        "     /db-tools --install <dump.sql> [--host <host>] [--user <user>]\n"
        "                           [--password <pass>] [--database <db>] [--port <port>]"
    )

    def execute(self, args):
        print("Executando db-tools")

        parsed_args = self.parse_args(args)

        if not parsed_args:
            print("[INFO] Nenhuma ação especificada.")
            return

        if "optimize" in parsed_args:
            self._handle_optimize(parsed_args["optimize"])
            return

        if "install" in parsed_args:
            self._handle_install(parsed_args)
            return

        print("[ERRO] Ação inválida.")

    # --------------------------
    # OPTIMIZE (abre nova janela)
    # --------------------------
    def _handle_optimize(self, dump_path: str):
        if not os.path.exists(dump_path):
            print(f"[ERRO] Arquivo não encontrado: {dump_path}")
            return

        script_path = ""

        command = (
            f'py -m commands.complements.db_tools_plugin.dump_insert_optimizer '
            f'--input_file "{dump_path}"'
        )

        self._run_in_powershell(command)

    # --------------------------
    # INSTALL (nova janela)
    # --------------------------
    def _handle_install(self, args: dict):
        dump_path = args.get("install")

        if not dump_path or not os.path.exists(dump_path):
            print(f"[ERRO] Arquivo não encontrado: {dump_path}")
            return

        mysql_bin = self._resolve_mysql_binary()
        if not mysql_bin:
            print("[ERRO] mysql não encontrado.")
            return

        host = args.get("host", "localhost")
        user = args.get("user", "root")
        password = args.get("password", "")
        database = args.get("database")
        port = args.get("port")

        if not database:
            print("[ERRO] --database é obrigatório")
            return

        port_part = f"-P {port}" if port else ""
        password_part = f"-p{password}" if password else "-p"

        command = (
            f'"{mysql_bin}" '
            f'-h {host} {port_part} '
            f'-u {user} {password_part} '
            f'{database} < "{dump_path}"'
        )

        self._run_in_powershell(command)

    # --------------------------
    # POWERSHELL
    # --------------------------
    def _run_in_powershell(self, command: str, no_exit: bool = False):
        no_exit_str = ""

        if no_exit:
            no_exit_str =   "-NoExit"
         
        try:
            ps_command = f'start powershell {no_exit_str} -Command "(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; (& .venv\\Scripts\\Activate.ps1); {command}"'
            subprocess.Popen(ps_command, shell=True)
        except Exception as e:
            print(f"[ERRO] Falha ao executar: {e}")

    # --------------------------
    # MYSQL
    # --------------------------
    def _resolve_mysql_binary(self):
        local_path = os.path.join(
            os.path.dirname(__file__),
            "bin",
            "mysql",
            "bin",
            "mysql.exe"
        )

        if os.path.exists(local_path):
            return local_path

        mysql_path = shutil.which("mysql")
        if mysql_path:
            return mysql_path

        return None