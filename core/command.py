from abc import ABC, abstractmethod


class Command(ABC):
    name: str = ""
    description: str = ""
    help_text: str = ""

    def __init__(self):
        self.context = None

    def get_usage(self) -> str:
        lines = [f"/{self.name} - {self.description}"]
        if self.help_text:
            lines.append("")
            lines.append(self.help_text)
        return "\n".join(lines)

    def parse_args(self, args: list[str]) -> dict:
        result = {}
        i = 0
        while i < len(args):
            if args[i].startswith("--"):
                key = args[i][2:]
                if key in ("help", "h"):
                    i += 1
                    continue
                if i + 1 < len(args) and not args[i + 1].startswith("--"):
                    result[key] = args[i + 1]
                    i += 2
                else:
                    result[key] = True
                    i += 1
            else:
                i += 1
        return result

    @abstractmethod
    def execute(self, args: list[str]):
        pass
