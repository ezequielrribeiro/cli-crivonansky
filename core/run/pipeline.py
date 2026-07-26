import typing
from pathlib import Path

from core.run.vinyl import VinylFile


class PipeStream:
    def __init__(self, generator: typing.Generator[VinylFile, None, None]):
        self._generator = generator

    def pipe(self, *transforms: typing.Callable) -> "PipeStream":
        def _chain():
            for vinyl in self._generator:
                result = vinyl
                for transform in transforms:
                    if result is None:
                        break
                    result = transform(result)
                if result is not None:
                    yield result

        return PipeStream(_chain())

    def through(self, *transforms: typing.Callable) -> "PipeStream":
        return self.pipe(*transforms)

    def dest(self, directory: typing.Union[str, Path]) -> list[VinylFile]:
        from core.run.dest import _write_file

        dest_path = Path(directory)
        written = []
        for vinyl in self._generator:
            _write_file(vinyl, dest_path)
            written.append(vinyl)
        return written

    def __iter__(self):
        return self._generator

    def __next__(self):
        return next(self._generator)
