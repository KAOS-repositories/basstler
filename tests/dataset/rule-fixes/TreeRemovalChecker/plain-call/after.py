"""
Removes a directory with :func:`shutil.rmtree`.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from basstler.directory_tree import DirectoryTree

shutil.copytree(Path("template"), Path("clone"))
DirectoryTree(Path("clone")).remove()
