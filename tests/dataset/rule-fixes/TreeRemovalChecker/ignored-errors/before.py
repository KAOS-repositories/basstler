"""
Removes a directory with :func:`shutil.rmtree`, ignoring its errors.
"""

from __future__ import annotations

import shutil
from pathlib import Path

shutil.copytree(Path("template"), Path("clone"))
shutil.rmtree(Path("clone"), ignore_errors=True)
