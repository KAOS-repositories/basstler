"""
Removes two directories where the tree is already imported.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from basstler.directory_tree import DirectoryTree


def clean(clone: Path, scratch: Path) -> None:
    """
    Remove *clone*, then *scratch*.
    """
    shutil.copytree(scratch, clone)
    DirectoryTree(
        clone,
        ignore_errors=False,
    ).remove()
    DirectoryTree(scratch).remove()
