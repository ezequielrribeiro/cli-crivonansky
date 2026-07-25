import argparse
from .app import run_app
from .services import TaskService


def main():
    parser = argparse.ArgumentParser(prog="task")
    sub = parser.add_subparsers(dest="command")

    start = sub.add_parser("start")
    start.add_argument("codigo")

    resume = sub.add_parser("resume")
    resume.add_argument("codigo")

    report = sub.add_parser("report")
    report.add_argument("codigo")

    args = parser.parse_args()
    service = TaskService()

    if args.command == "start":
        service.start_new(args.codigo)
        run_app(args.codigo)

    elif args.command == "resume":
        service.validate_resume(args.codigo)
        run_app(args.codigo)

    elif args.command == "report":
        report = service.report(args.codigo)
        print_report(report)

    else:
        parser.print_help()

def format_duration(td):
    seconds = int(td.total_seconds())
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"

def print_report(report):
    print("\n📊 RELATÓRIO DA TASK\n")

    print(f"⏱ Tempo total: {format_duration(report['total_time'])}")
    print(f"📦 Sessões: {report['session_count']}")
    print(f"⏸ Pausas: {report['pause_count']}")

    print("\n📈 Tempo por sessão:")
    for i, s in enumerate(report["sessions"], 1):
        print(f"  {i}. {format_duration(s)}")

    print("\n📝 Pausas:")
    for p in report["pauses"]:
        ts = p["at"]
        note = p.get("note", "")
        print(f"  - {ts} → {note}")


if __name__ == "__main__":
    main()
