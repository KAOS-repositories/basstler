from __future__ import annotations

from pathlib import Path


def first_line(path: Path) -> str:
    return path.read_text().splitlines()[0]
