"""
Names a file joined onto a repository path, written with str.
"""

from __future__ import annotations

from basstler.locations import ProjectLocation as Location

OTHER_NOTES = (Location.PERSONAL_NOTES / "some-other-notes.md").as_posix()
"""
The notes of another person.
"""
