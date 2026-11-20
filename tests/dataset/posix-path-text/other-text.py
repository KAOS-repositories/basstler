"""
Text that is no path written with str, or a path already written as POSIX text.
"""

from __future__ import annotations

import os
from pathlib import Path

from basstler.locations import ProjectLocation

from .paths import RelativelyImportedLocation


def texts(tmp_path: Path, count: int, name: str) -> list[str]:
    """
    :return: Texts the check leaves alone.
    """
    return [
        str(tmp_path),
        str(count),
        f"{name}",
        str(ProjectLocation),
        f"{ProjectLocation.PERSONAL_NOTES!r}",
        ProjectLocation.PERSONAL_NOTES.as_posix(),
        Path(os.path.relpath(tmp_path, name)).as_posix(),
        str(RelativelyImportedLocation.ROOT),
    ]
