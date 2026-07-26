from dataclasses import dataclass, field
from pathlib import Path
import typing


@dataclass
class VinylFile:
    path: Path
    relative: Path
    base: Path
    contents: bytes
    cwd: Path = field(default_factory=Path.cwd)

    def clone(self) -> "VinylFile":
        return VinylFile(
            path=self.path,
            relative=self.relative,
            base=self.base,
            contents=self.contents,
            cwd=self.cwd,
        )

    def with_contents(self, data: typing.Union[bytes, str]) -> "VinylFile":
        if isinstance(data, str):
            data = data.encode("utf-8")
        return VinylFile(
            path=self.path,
            relative=self.relative,
            base=self.base,
            contents=data,
            cwd=self.cwd,
        )

    def with_path(self, relative: typing.Union[str, Path]) -> "VinylFile":
        rel = Path(relative)
        return VinylFile(
            path=self.base / rel,
            relative=rel,
            base=self.base,
            contents=self.contents,
            cwd=self.cwd,
        )

    @property
    def stem(self) -> str:
        return self.path.stem

    @property
    def ext(self) -> str:
        return self.path.suffix

    @property
    def text(self) -> str:
        return self.contents.decode("utf-8")
