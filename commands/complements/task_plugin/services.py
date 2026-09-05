from .storage import create, load, save, append_event, list_all, exists
from .domain import rebuild, now, TaskState, build_report
from datetime import datetime


class TaskService:

    def start_new(self, codigo):
        if exists(codigo):
            return self.resume(codigo)

        create(codigo)
        append_event(codigo, {
            "type": "started",
            "at": now()
        })

    def validate_resume(self, codigo):
        state = self._to_paused_if_finished(codigo)

        if state != TaskState.PAUSED:
            raise Exception("Só é possível retomar tarefas pausadas ou finalizadas")

    def pause(self, codigo, note):
        if not note:
            raise Exception("Nota da pausa é obrigatória")

        append_event(codigo, {
            "type": "paused",
            "at": now(),
            "note": note
        })

    def resume(self, codigo):
        state = self._to_paused_if_finished(codigo)

        if state == TaskState.PAUSED:
            append_event(codigo, {
                "type": "resumed",
                "at": now()
            })

    def _to_paused_if_finished(self, codigo):
        data = load(codigo)
        state, _, _ = rebuild(data["events"])

        if state == TaskState.FINISHED:
            self._unstop(codigo)
            return TaskState.PAUSED

        return state

    def _unstop(self, codigo):
        data = load(codigo)
        events = data["events"]

        for i in range(len(events) - 1, -1, -1):
            if events[i]["type"] == "stopped":
                events[i] = dict(events[i], type="paused")
                break

        save(codigo, data)

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

    def list_all(self):
        tasks = []
        for codigo, data in list_all().items():
            state, total, last_start = rebuild(data["events"])
            if state == TaskState.RUNNING and last_start:
                total += datetime.now() - last_start
            tasks.append({
                "codigo": codigo,
                "status": state,
                "total": total
            })
        return tasks

