"""
Removes a directory with :func:`shutil.rmtree`, which stops at a read-only entry.
"""

from __future__ import annotations

import shutil
from pathlib import Path

shutil.rmtree(Path("clone"))  # violation
shutil.rmtree(Path("clone"), ignore_errors=True)  # violation
