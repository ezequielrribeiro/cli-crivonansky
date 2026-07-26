import typing
from pathlib import Path

from core.run.vinyl import VinylFile


def rename(fn: typing.Callable[[VinylFile], str]) -> typing.Callable[[VinylFile], VinylFile]:
    def _transform(vinyl: VinylFile) -> VinylFile:
        new_rel = Path(fn(vinyl))
        return VinylFile(
            path=(vinyl.base / new_rel).absolute(),
            relative=new_rel,
            base=vinyl.base,
            contents=vinyl.contents,
            cwd=vinyl.cwd,
        )
    return _transform


def concat(filename: str) -> typing.Callable[[typing.Generator[VinylFile, None, None]], VinylFile]:
    def _transform(generator) -> VinylFile:
        parts = []
        first = None
        for vinyl in generator:
            if first is None:
                first = vinyl
            parts.append(vinyl.contents)
        merged = b"\n".join(parts)
        return first.with_path(filename).with_contents(merged)
    return _transform


def replace(search: str, replace: str) -> typing.Callable[[VinylFile], VinylFile]:
    def _transform(vinyl: VinylFile) -> VinylFile:
        text = vinyl.contents.decode("utf-8")
        text = text.replace(search, replace)
        return vinyl.with_contents(text.encode("utf-8"))
    return _transform


def filter(predicate: typing.Callable[[VinylFile], bool]) -> typing.Callable[[VinylFile], VinylFile | None]:
    def _transform(vinyl: VinylFile) -> VinylFile | None:
        return vinyl if predicate(vinyl) else None
    return _transform


def through(fn: typing.Callable[[VinylFile], VinylFile]) -> typing.Callable[[VinylFile], VinylFile]:
    return fn
