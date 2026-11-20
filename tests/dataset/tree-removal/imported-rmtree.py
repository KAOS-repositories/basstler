"""
Removes directories with :func:`shutil.rmtree` under other names.
"""

from __future__ import annotations

import shutil as filesystem
from pathlib import Path
from shutil import rmtree
from shutil import rmtree as remove_tree

filesystem.rmtree(Path("clone"))
rmtree(Path("clone"))
remove_tree(Path("clone"))
