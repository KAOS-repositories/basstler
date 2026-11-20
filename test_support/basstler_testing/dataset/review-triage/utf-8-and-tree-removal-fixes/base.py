from __future__ import annotations

import shutil
from pathlib import Path


def replace_copy(source: Path, target: Path) -> None:
    shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(source, target)
    (target / "copied").write_text(source.name)
