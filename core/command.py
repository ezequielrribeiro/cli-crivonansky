from abc import ABC, abstractmethod


class Command(ABC):
    name: str = ""
    description: str = ""

    def __init__(self):
        self.context = None

    @abstractmethod
    def execute(self, args: list[str]):
        pass
