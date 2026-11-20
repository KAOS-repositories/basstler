from __future__ import annotations

from pathlib import Path


def first_lines(directory: Path) -> list[str]:
    return [
        path.read_text(encoding="utf-8").splitlines()[0]
        for path in sorted(directory.iterdir())
    ]
