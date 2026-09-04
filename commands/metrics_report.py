import json
import os
from datetime import datetime
from core.command import Command
from commands.complements.work_analysis import WorkAnalysis

from rich.console import Console
from rich.table import Table
from rich.panel import Panel


class MetricsReportCommand(Command):
    name = "metrics-report"
    description = "Exibe um relatório com as métricas do trimestre"
    help_text = "Uso: /metrics-report [--file <caminho>]\nOmite --file para usar o configurado em metrics_report_conf.json"

    def __init__(self):
        self.console = Console(
            color_system=None,   # 🚨 desativa ANSI
            markup=False         # evita parsing de tags
        )


    def execute(self, args):
        parsed = self.parse_args(args)
        metrics_file = parsed.get("file")

        if not metrics_file:
            metrics_file = self._resolve_from_config()

        if not metrics_file:
            self.console.print(
                "[bold red]Erro:[/] Informe --file ou configure o campo "
                "[yellow]\"metrics_file\"[/] em metrics_report_conf.json"
            )
            return False, {"error": "informe --file ou configure metrics_file"}

        return self.load_metrics(metrics_file)

    def _resolve_from_config(self):
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "metrics_report_conf.json"
        )
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            return config.get("metrics_file")
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    # -------------------------
    def load_metrics(self, metrics_file_path):
        try:
            with open(metrics_file_path, 'r') as metrics_file:
                daily_metrics = json.load(metrics_file)

            # Atualiza dias restantes
            goal_info = daily_metrics.get("goal_days_remaining", {})
            today_str = goal_info.get("today")
            days_remaining = goal_info.get("days", 0)
            current_date = datetime.now().strftime("%Y-%m-%d")

            if today_str != current_date:
                if days_remaining > 1:
                    goal_info["days"] = days_remaining - 1
                goal_info["today"] = current_date

            daily_metrics["goal_days_remaining"] = goal_info

            # Persiste
            with open(metrics_file_path, "w", encoding="utf-8") as f:
                json.dump(daily_metrics, f, indent=4, ensure_ascii=False)

            work_analysis = WorkAnalysis(
                daily_metrics=daily_metrics,
                logging_file='log.txt'
            )

            self.metrics_information = work_analysis.get_trimester_metrics()
            report = self._get_metrics_report_info()

            self._print_report(report)

            return True, {"metrics": report, "file": metrics_file_path}

        except FileNotFoundError:
            self.console.print("[bold red]Arquivo não encontrado.[/]")
            return False, {"error": f"arquivo não encontrado: {metrics_file_path}"}
        except Exception as e:
            self.console.print(f"[bold red]Erro ao processar métricas:[/] {e}")
            return False, {"error": str(e)}

    # -------------------------
    def _get_metrics_report_info(self):
        remaining_hours = (
            self.metrics_information.get("trimester_goal")
            - (
                self.metrics_information.get("trimester_hours_done")
                + self.metrics_information.get("trimester_hours_adjust")
            )
        )

        return {
            "goal": self.metrics_information.get("trimester_goal"),
            "done": self.metrics_information.get("trimester_hours_done"),
            "adjust": self.metrics_information.get("trimester_hours_adjust"),
            "total": (
                self.metrics_information.get("trimester_hours_done")
                + self.metrics_information.get("trimester_hours_adjust")
            ),
            "remaining_hours": remaining_hours if remaining_hours > 0 else 0,
            "remaining_days": self.metrics_information.get("trimester_remaining_days"),
            "hours_per_day": max(0, self.metrics_information.get("trimester_hours_per_day")),
            "percent": self.metrics_information.get("trimester_percent"),
        }

    # -------------------------
    def _print_report(self, report):
        def clean(v):
            if isinstance(v, str):
                return v.replace("|", "").strip()
            return v

        table = Table(title="📊 Relatório do Trimestre", show_lines=True)

        table.add_column("Métrica", style="cyan", no_wrap=True)
        table.add_column("Valor", justify="right")

        table.add_row("Meta total", str(clean(report["goal"])))
        table.add_row("Horas trabalhadas", str(clean(report["done"])))
        table.add_row("Ajustes", str(clean(report["adjust"])))
        table.add_row("Total realizado", str(clean(report["total"])))
        table.add_row("Progresso", f"{clean(report['percent'])}%")
        table.add_row("Horas restantes", str(clean(report["remaining_hours"])))
        table.add_row("Dias restantes", str(clean(report["remaining_days"])))
        table.add_row("Horas/dia necessárias", str(clean(report["hours_per_day"])))

        self.console.print(Panel(table, expand=False))