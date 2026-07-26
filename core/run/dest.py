import typing
from pathlib import Path

from core.run.vinyl import VinylFile


def dest(directory: typing.Union[str, Path]) -> typing.Callable[[VinylFile], VinylFile]:
    dest_path = Path(directory)

    def _write(vinyl: VinylFile) -> VinylFile:
        _write_file(vinyl, dest_path)
        return vinyl

    return _write


def _write_file(vinyl: VinylFile, dest_path: Path):
    output = dest_path.absolute() / vinyl.relative
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(vinyl.contents)
