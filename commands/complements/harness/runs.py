"""Registro de execuções em runs/<id>/ e runs.jsonl."""

import json
import os


class RunStore:
    def __init__(self, workspace: str):
        self.root = os.path.join(workspace, "runs")
        os.makedirs(self.root, exist_ok=True)
        self.index_path = os.path.join(self.root, "runs.jsonl")

    def run_dir(self, run_id: str) -> str:
        path = os.path.join(self.root, run_id)
        os.makedirs(path, exist_ok=True)
        return path

    def write(
        self,
        run_id: str,
        command_text: str,
        result_text: str,
        full_log: str | None = None,
    ) -> str:
        path = self.run_dir(run_id)
        with open(os.path.join(path, "command.yaml"), "w", encoding="utf-8") as fh:
            fh.write(command_text)
        with open(os.path.join(path, "result.md"), "w", encoding="utf-8") as fh:
            fh.write(result_text)
        if full_log is not None:
            with open(os.path.join(path, "full.log"), "w", encoding="utf-8") as fh:
                fh.write(full_log)
        return path

    def append_index(self, record: dict) -> None:
        with open(self.index_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def last(self, count: int = 10) -> list[dict]:
        if not os.path.isfile(self.index_path):
            return []
        records = []
        with open(self.index_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records[-count:]
