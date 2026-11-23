"""
Clones a repository from its path on disk.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def git(directory: Path, *arguments: str) -> str:
    """
    :return: What git printed.
    """
    return subprocess.run(
        ["git", *arguments],
        cwd=directory,
        check=True,
        capture_output=True,
        encoding="utf-8",
    ).stdout


def clone(remote: Path, clone: Path) -> None:
    """
    Clone *remote* into *clone*.
    """
    git(clone.parent, "clone", "--quiet", remote.as_uri(), str(clone))
