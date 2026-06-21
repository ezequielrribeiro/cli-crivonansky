import os
import importlib
import inspect
from core.command import Command


def load_commands(registry, context, package="commands"):
    package_path = package.replace(".", "/")

    for file in os.listdir(package_path):
        if file.endswith(".py") and not file.startswith("__"):
            module_name = f"{package}.{file[:-3]}"
            module = importlib.import_module(module_name)

            for _, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, Command)
                    and obj is not Command
                ):
                    instance = obj()
                    instance.context = context

                    name = instance.name
                    if not name.startswith("/"):
                        name = f"/{name}"
                    registry.register(name, instance)
