from datetime import datetime, timedelta


class TaskState:
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"


def rebuild(events):
    """
    Reconstrói estado e tempo total a partir dos eventos
    """
    state = TaskState.IDLE
    total = timedelta()
    last_start = None

    for e in events:
        t = e["type"]
        at = datetime.fromisoformat(e["at"])

        if t == "started":
            state = TaskState.RUNNING
            last_start = at

        elif t == "resumed":
            state = TaskState.RUNNING
            last_start = at

        elif t == "paused":
            if last_start:
                total += at - last_start
            state = TaskState.PAUSED
            last_start = None

        elif t == "stopped":
            if last_start:
                total += at - last_start
            state = TaskState.FINISHED
            last_start = None

    return state, total, last_start


def now():
    return datetime.now().isoformat()

def build_report(events):
    """
    Gera métricas a partir dos eventos
    """
    state, total, last_start = rebuild(events)

    sessions = []
    pauses = []

    current_start = None

    for e in events:
        t = e["type"]
        at = datetime.fromisoformat(e["at"])

        if t in ("started", "resumed"):
            current_start = at

        elif t == "paused":
            if current_start:
                duration = at - current_start
                sessions.append(duration)
                current_start = None

            pauses.append(e)

        elif t == "stopped":
            if current_start:
                duration = at - current_start
                sessions.append(duration)
                current_start = None

    return {
        "total_time": total,
        "sessions": sessions,
        "pauses": pauses,
        "session_count": len(sessions),
        "pause_count": len(pauses)
    }
