from .storage import create, load, append_event
from .domain import rebuild, now, TaskState, build_report


class TaskService:

    def start_new(self, codigo):
        create(codigo)
        append_event(codigo, {
            "type": "started",
            "at": now()
        })

    def validate_resume(self, codigo):
        data = load(codigo)
        state, _, _ = rebuild(data["events"])

        if state != TaskState.PAUSED:
            raise Exception("Só é possível retomar tarefas pausadas")

    def pause(self, codigo, note):
        if not note:
            raise Exception("Nota da pausa é obrigatória")

        append_event(codigo, {
            "type": "paused",
            "at": now(),
            "note": note
        })

    def resume(self, codigo):
        append_event(codigo, {
            "type": "resumed",
            "at": now()
        })

    def stop(self, codigo, note):
        if not note:
            raise Exception("Resumo final é obrigatório")

        append_event(codigo, {
            "type": "stopped",
            "at": now(),
            "note": note
        })

    def report(self, codigo):
        data = load(codigo)
        report = build_report(data["events"])
        return report

