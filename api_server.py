import argparse
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Optional

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core.bootstrap import build_executor

app = FastAPI(
    title="Crivonansky API",
    description="Executa comandos do framework Crivonansky CLI via REST",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ExecuteRequest(BaseModel):
    command: str
    timeout: Optional[float] = None


class CommandOut(BaseModel):
    name: str
    description: str


class CommandDetail(CommandOut):
    help_text: str


class ExecuteResponse(BaseModel):
    success: bool
    output: str
    data: Optional[dict] = None
    error: Optional[str] = None


class _TimeoutSentinel:
    pass


_TIMEOUT_SENTINEL = _TimeoutSentinel()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _available_commands() -> dict:
    executor = build_executor()
    return executor.registry.all()


def _run_with_timeout(fn, timeout: Optional[float]):
    if timeout is None:
        return fn()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            return _TIMEOUT_SENTINEL


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/commands", response_model=list[CommandOut])
def list_commands():
    commands = _available_commands()
    return [
        CommandOut(name=name, description=cmd.description)
        for name, cmd in sorted(commands.items())
    ]


@app.get("/commands/{name}", response_model=CommandDetail)
def command_detail(name: str):
    if not name.startswith("/"):
        name = f"/{name}"

    commands = _available_commands()
    cmd = commands.get(name)
    if cmd is None:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": f"comando não encontrado: {name}",
                "output": "",
                "data": None,
            },
        )

    return CommandDetail(
        name=name,
        description=cmd.description,
        help_text=cmd.get_usage(),
    )


@app.post("/execute")
def execute(req: ExecuteRequest):
    command_line = req.command.strip()

    if not command_line:
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "comando vazio",
                "output": "",
                "data": None,
            },
        )

    executor = build_executor()

    result = _run_with_timeout(lambda: executor.execute(command_line), req.timeout)

    if isinstance(result, _TimeoutSentinel):
        return JSONResponse(
            status_code=408,
            content={
                "success": False,
                "error": f"timeout após {req.timeout}s",
                "output": "",
                "data": None,
            },
        )

    success, data = executor.last_result

    if success is False and isinstance(data, dict) and data.get("error") == "comando não encontrado":
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "error": data["error"],
                "output": result,
                "data": data,
            },
        )

    return {
        "success": success,
        "output": result,
        "data": data,
        "error": data.get("error") if isinstance(data, dict) else None,
    }


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Crivonansky REST API")
    parser.add_argument("--host", default="127.0.0.1", help="Host de bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Porta (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Habilita hot-reload do uvicorn")
    args = parser.parse_args()

    uvicorn.run("api_server:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()