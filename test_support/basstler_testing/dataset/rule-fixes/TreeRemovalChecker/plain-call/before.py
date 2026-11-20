"""
Removes a directory with :func:`shutil.rmtree`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

shutil.copytree(Path("template"), Path("clone"))
shutil.rmtree(Path("clone"))
