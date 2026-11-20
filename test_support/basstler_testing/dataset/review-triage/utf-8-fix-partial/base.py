from __future__ import annotations

from pathlib import Path


def copy(source: Path, target: Path) -> None:
    target.write_text(source.read_text())
