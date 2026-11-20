"""
Stands in for :mod:`basstler.personal_notes.git_identity`, printing the identity path of
a colleague who shares the notes branch without owning its repository.
"""

from __future__ import annotations

from basstler.locations import ProjectLocation

print(ProjectLocation.CONTRIBUTOR_GIT_IDENTITIES.value / "a-colleague")
