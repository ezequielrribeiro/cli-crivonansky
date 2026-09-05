import subprocess
from pathlib import Path

from core.run import task, series


SCRIPT_DIR = Path(__file__).resolve().parent / "scripts" / "maintenance"


def _run_elevated(script_name: str):
    script = SCRIPT_DIR / script_name
    inner = (
        f"Start-Process powershell -Verb RunAs "
        f"-ArgumentList '-ExecutionPolicy','Bypass','-File','{script}'"
    )
    subprocess.Popen(f'start powershell -NoExit -Command "{inner}"', shell=True)


@task
def sync_clock():
    """Sincroniza o relogio do sistema (W32Time)"""
    _run_elevated("sync_clock.ps1")


@task
def update_apps():
    """Atualiza os aplicativos do computador via winget"""
    _run_elevated("update_apps.ps1")


@task
def clean_temp():
    """Remove arquivos temporarios e esvazia a lixeira"""
    _run_elevated("clean_temp.ps1")


@task
def cleanup_weekly():
    """Limpeza semanal de arquivos temporarios do sistema"""
    _run_elevated("clean_temp_weekly.ps1")


@task
def maintenance():
    """Manutencao do computador (relogio, aplicativos e limpeza)"""
    return series("sync_clock", "update_apps", "clean_temp")


@task
def default():
    """Task padrao (executada com /run run)"""
    maintenance()