"""
Removes a directory with :func:`shutil.rmtree`, ignoring its errors.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from basstler.directory_tree import DirectoryTree

shutil.copytree(Path("template"), Path("clone"))
DirectoryTree(Path("clone"), ignore_errors=True).remove()
