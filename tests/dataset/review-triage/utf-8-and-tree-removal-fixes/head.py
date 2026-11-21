from __future__ import annotations

import shutil
from pathlib import Path

from basstler.directory_tree import DirectoryTree


def replace_copy(source: Path, target: Path) -> None:
    DirectoryTree(target, ignore_errors=True).remove()
    shutil.copytree(source, target)
    (target / "copied").write_text(source.name, encoding="utf-8")
