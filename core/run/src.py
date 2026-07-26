import typing
from pathlib import Path

from core.run.vinyl import VinylFile
from core.run.pipeline import PipeStream


def src(patterns: typing.Union[str, list[str]], base: str | None = None) -> PipeStream:
    if isinstance(patterns, str):
        patterns = [patterns]

    def _generate():
        matched = []
        for pattern in patterns:
            matched.extend(sorted(Path.cwd().glob(pattern)))

        if not matched:
            return

        common_base = _resolve_base(matched, base)

        for filepath in matched:
            if not filepath.is_file():
                continue
            try:
                contents = filepath.read_bytes()
            except Exception:
                continue

            rel = filepath.relative_to(common_base)

            yield VinylFile(
                path=filepath.absolute(),
                relative=rel,
                base=common_base.absolute(),
                contents=contents,
                cwd=Path.cwd(),
            )

    return PipeStream(_generate())


def _resolve_base(matched: list[Path], base: str | None) -> Path:
    if base is not None:
        return Path(base)

    common = Path.cwd()
    for p in matched:
        if p.parent == Path.cwd():
            return Path.cwd()

    parent = matched[0].parent
    for p in matched[1:]:
        if p.parent != parent:
            return Path.cwd()
    return parent
