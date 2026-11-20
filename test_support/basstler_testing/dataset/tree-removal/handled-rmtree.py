"""
Removes a directory with :func:`shutil.rmtree` and a handler that DirectoryTree lacks.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def ignore(*arguments: object) -> None:
    """
    Do nothing about a refusal.
    """


shutil.rmtree(Path("clone"), onexc=ignore)
